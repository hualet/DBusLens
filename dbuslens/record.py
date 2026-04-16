from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import ast
import re
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any

from dbuslens.bundle import BundleContents, BundleMetadata, write_bundle


_GDBUS_TIMEOUT_SECONDS = 5
_SNAPSHOT_BUDGET_SECONDS = 5


@dataclass(frozen=True)
class RecordResult:
    output_path: Path
    stderr: bytes
    exit_code: int


class RecordError(RuntimeError):
    pass


def build_default_output_path(
    bus: str,
    *,
    now: datetime | None = None,
    base_dir: Path | None = None,
) -> Path:
    del bus, now
    directory = base_dir or Path.cwd()
    return directory / "record.dblens"


def _run_monitor(command: list[str], duration: int) -> tuple[bytes, bytes, int]:
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=duration)
            exit_code = process.returncode or 0
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
            exit_code = process.returncode or 0
    return stdout, stderr, exit_code


def _start_background_monitor(command: list[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _stop_background_monitor(process: subprocess.Popen[bytes]) -> tuple[bytes, bytes, int]:
    process.terminate()
    try:
        stdout, stderr = process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
    exit_code = process.returncode or 0
    return stdout, stderr, exit_code


def _parse_name_owner_changed_line(line: str) -> dict[str, object] | None:
    if "member=NameOwnerChanged" not in line:
        return None
    match = re.search(r"time=(?P<timestamp>\d+(?:\.\d+)?)", line)
    string_values = re.findall(r"string '([^']*)'", line)
    if match is None or len(string_values) < 3:
        return None
    timestamp = float(match.group("timestamp"))
    name, old_owner, new_owner = string_values[:3]
    return {
        "timestamp": timestamp,
        "name": name,
        "old_owner": old_owner,
        "new_owner": new_owner,
    }


def _build_names_timeline(
    *,
    bus: str,
    started_at: str,
    ended_at: str,
    initial_snapshot: dict[str, Any],
    lines: list[str],
    final_snapshot: dict[str, Any],
    error: str | None,
) -> dict[str, Any]:
    return {
        "bus": bus,
        "started_at": started_at,
        "ended_at": ended_at,
        "initial_snapshot": initial_snapshot,
        "events": [
            event
            for line in lines
            if (event := _parse_name_owner_changed_line(line)) is not None
        ],
        "final_snapshot": final_snapshot,
        "error": error,
    }


def _build_timeline_error(stdout: bytes, stderr: bytes, exit_code: int) -> str | None:
    stdout_text = stdout.decode("utf-8", "replace").strip()
    stderr_text = stderr.decode("utf-8", "replace").strip()
    if exit_code not in {0, -15}:
        if stderr_text:
            return f"timeline monitor exited with code {exit_code}: {stderr_text}"
        return f"timeline monitor exited with code {exit_code}"
    if not stdout_text:
        return stderr_text or "timeline monitor produced no output"
    return stderr_text or None


def _split_gdbus_items(text: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    escaped = False
    for char in text:
        if quote is not None:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
            continue
        current.append(char)
    item = "".join(current).strip()
    if item:
        items.append(item)
    return items


def _parse_gdbus_value(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    if text in {"true", "false"}:
        return text == "true"
    if text[0] in {"'", '"'}:
        return ast.literal_eval(text)
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_parse_gdbus_value(item) for item in _split_gdbus_items(inner)]
    if text.startswith("(") and text.endswith(")"):
        inner = text[1:-1].strip()
        if not inner:
            return tuple()
        values = [_parse_gdbus_value(item) for item in _split_gdbus_items(inner)]
        return values[0] if len(values) == 1 else tuple(values)
    if " " in text:
        prefix, remainder = text.split(" ", 1)
        if prefix in {
            "byte",
            "int16",
            "uint16",
            "int32",
            "uint32",
            "int64",
            "uint64",
            "double",
            "string",
        }:
            if prefix == "string":
                return remainder
            return int(remainder)
    return text


def _run_gdbus_call(
    gdbus_path: str,
    bus: str,
    method: str,
    *arguments: str,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str] | None:
    if timeout_seconds is not None and timeout_seconds <= 0:
        return None
    effective_timeout = _GDBUS_TIMEOUT_SECONDS if timeout_seconds is None else min(_GDBUS_TIMEOUT_SECONDS, timeout_seconds)
    try:
        return subprocess.run(
            [
                gdbus_path,
                "call",
                f"--{bus}",
                "--dest",
                "org.freedesktop.DBus",
                "--object-path",
                "/org/freedesktop/DBus",
                "--method",
                method,
                *arguments,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=effective_timeout,
        )
    except subprocess.TimeoutExpired:
        return None


def _lookup_name_owner(
    gdbus_path: str,
    bus: str,
    name: str,
    *,
    timeout_seconds: float | None = None,
) -> tuple[str | None, str | None]:
    if name.startswith(":"):
        return name, None
    result = _run_gdbus_call(
        gdbus_path,
        bus,
        "org.freedesktop.DBus.GetNameOwner",
        name,
        timeout_seconds=timeout_seconds,
    )
    if result is None:
        return None, "GetNameOwner timed out"
    if result.returncode != 0:
        return None, result.stderr.strip() or "GetNameOwner failed"
    try:
        owner = _parse_gdbus_value(result.stdout.strip())
    except (ValueError, SyntaxError):
        return None, "GetNameOwner parse failed"
    if not isinstance(owner, str) or not owner:
        return None, "GetNameOwner parse failed"
    return owner, None


def _lookup_name_pid(
    gdbus_path: str,
    bus: str,
    owner: str,
    *,
    timeout_seconds: float | None = None,
) -> tuple[int | None, str | None]:
    result = _run_gdbus_call(
        gdbus_path,
        bus,
        "org.freedesktop.DBus.GetConnectionUnixProcessID",
        owner,
        timeout_seconds=timeout_seconds,
    )
    if result is None:
        return None, "GetConnectionUnixProcessID timed out"
    if result.returncode != 0:
        return None, result.stderr.strip() or "GetConnectionUnixProcessID failed"
    try:
        pid = _parse_gdbus_value(result.stdout.strip())
    except (ValueError, SyntaxError):
        return None, "GetConnectionUnixProcessID parse failed"
    if not isinstance(pid, int):
        return None, "GetConnectionUnixProcessID parse failed"
    return pid, None


def _read_process_details(pid: int | None) -> tuple[int | None, list[str] | None]:
    if pid is None:
        return None, None
    proc_root = Path("/proc") / str(pid)

    uid: int | None = None
    status_path = proc_root / "status"
    try:
        for line in status_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Uid:"):
                parts = line.split()
                if len(parts) >= 2:
                    uid = int(parts[1])
                break
    except (OSError, ValueError):
        uid = None

    cmdline_path = proc_root / "cmdline"
    cmdline: list[str] | None = None
    try:
        raw_cmdline = cmdline_path.read_bytes()
        if raw_cmdline:
            parts = [part.decode("utf-8", "replace") for part in raw_cmdline.split(b"\0") if part]
            cmdline = parts or None
    except OSError:
        cmdline = None

    return uid, cmdline


def _capture_names(bus: str) -> dict[str, Any]:
    captured_at = datetime.now().astimezone().isoformat()
    snapshot: dict[str, Any] = {"captured_at": captured_at, "bus": bus, "names": [], "error": None}
    deadline = time.monotonic() + _SNAPSHOT_BUDGET_SECONDS

    def remaining_budget() -> float:
        return max(0.0, deadline - time.monotonic())

    def budget_exhausted() -> bool:
        return remaining_budget() <= 0.0

    gdbus_path = shutil.which("gdbus")
    if gdbus_path is None:
        snapshot["error"] = "gdbus not found"
        return snapshot

    list_names = _run_gdbus_call(
        gdbus_path,
        bus,
        "org.freedesktop.DBus.ListNames",
        timeout_seconds=remaining_budget(),
    )
    if list_names is None:
        snapshot["error"] = "snapshot collection timed out"
        return snapshot
    if list_names.returncode != 0:
        snapshot["error"] = list_names.stderr.strip() or "ListNames failed"
        return snapshot

    try:
        names = _parse_gdbus_value(list_names.stdout.strip())
    except (ValueError, SyntaxError):
        snapshot["error"] = "ListNames parse failed"
        return snapshot
    if isinstance(names, tuple) and len(names) == 1 and isinstance(names[0], list):
        names = names[0]
    if not isinstance(names, list):
        snapshot["error"] = "ListNames parse failed"
        return snapshot

    entries: list[dict[str, Any]] = []
    had_entry_failure = False
    for name in names:
        if budget_exhausted():
            snapshot["error"] = "snapshot collection timed out"
            break
        if not isinstance(name, str):
            continue
        entry: dict[str, Any] = {
            "name": name,
            "owner": None,
            "pid": None,
            "uid": None,
            "cmdline": None,
            "error": None,
        }

        owner, error = _lookup_name_owner(
            gdbus_path,
            bus,
            name,
            timeout_seconds=remaining_budget(),
        )
        if error is not None:
            entry["error"] = error
            had_entry_failure = True
            entries.append(entry)
            continue
        entry["owner"] = owner

        pid, error = _lookup_name_pid(
            gdbus_path,
            bus,
            owner,
            timeout_seconds=remaining_budget(),
        )
        if error is not None:
            entry["error"] = error
            had_entry_failure = True
            entries.append(entry)
            continue
        entry["pid"] = pid

        uid, cmdline = _read_process_details(pid)
        if budget_exhausted():
            entry["uid"] = uid
            entry["cmdline"] = cmdline
            entries.append(entry)
            snapshot["error"] = "snapshot collection timed out"
            break
        entry["uid"] = uid
        entry["cmdline"] = cmdline
        if uid is None or cmdline is None:
            entry["error"] = "process details failed"
            had_entry_failure = True

        entries.append(entry)

    snapshot["names"] = entries
    if snapshot["error"] is None and had_entry_failure:
        snapshot["error"] = "snapshot collection incomplete"
    return snapshot


def record_monitor(
    *,
    bus: str,
    duration: int,
    output_path: Path,
) -> RecordResult:
    monitor_path = shutil.which("dbus-monitor")
    if monitor_path is None:
        raise RecordError("dbus-monitor not found in PATH")
    if bus not in {"system", "session"}:
        raise RecordError(f"unsupported bus: {bus}")
    if duration <= 0:
        raise RecordError("duration must be a positive integer")
    if output_path.suffix != ".dblens":
        raise RecordError("record output must use the .dblens extension")

    pcap_command = [monitor_path, f"--{bus}", "--pcap"]
    profile_command = [monitor_path, f"--{bus}", "--profile"]
    timeline_command = [monitor_path, f"--{bus}"]
    timeline_process: subprocess.Popen[bytes] | None = None
    timeline_start_error: str | None = None
    try:
        timeline_process = _start_background_monitor(timeline_command)
    except OSError as exc:
        timeline_start_error = f"timeline monitor failed to start: {exc}"
    started_at_iso = datetime.now().astimezone().isoformat()
    initial_snapshot = _capture_names(bus)
    try:
        stdout, stderr, exit_code = _run_monitor(pcap_command, duration)
        profile_stdout, profile_stderr, profile_exit_code = _run_monitor(profile_command, duration)
    finally:
        timeline_stdout = b""
        timeline_stderr = b""
        timeline_exit_code = 0
        if timeline_process is not None:
            timeline_stdout, timeline_stderr, timeline_exit_code = _stop_background_monitor(timeline_process)
    final_snapshot = _capture_names(bus)

    if exit_code not in {0, -15} and not stdout:
        stderr_text = stderr.decode("utf-8", "replace").strip()
        raise RecordError(f"dbus-monitor exited with code {exit_code}: {stderr_text}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined_stderr = b"\n".join(part for part in (stderr, profile_stderr) if part)
    monitor_mode = "monitor"
    stderr_text = combined_stderr.decode("utf-8", "replace")
    if "BecomeMonitor" in stderr_text:
        monitor_mode = "eavesdrop"

    ended_at_iso = datetime.now().astimezone().isoformat()
    timeline_error = timeline_start_error or _build_timeline_error(
        timeline_stdout,
        timeline_stderr,
        timeline_exit_code,
    )
    names_timeline = _build_names_timeline(
        bus=bus,
        started_at=started_at_iso,
        ended_at=ended_at_iso,
        initial_snapshot=initial_snapshot,
        lines=timeline_stdout.decode("utf-8", "replace").splitlines(),
        final_snapshot=final_snapshot,
        error=timeline_error,
    )

    write_bundle(
        output_path,
        BundleContents(
            metadata=BundleMetadata(
                bundle_version=1,
                created_at=datetime.now().astimezone().isoformat(),
                bus=bus,
                duration_seconds=duration,
                capture_files={
                    "pcap": "capture.cap",
                    "profile": "capture.profile",
                    "names": "names.json",
                    "names_timeline": "names_timeline.json",
                },
                monitor={
                    "command": pcap_command,
                    "profile_command": profile_command,
                    "stderr": stderr_text,
                    "mode": monitor_mode,
                    "profile_exit_code": profile_exit_code,
                },
            ),
            pcap_bytes=stdout,
            profile_text=profile_stdout.decode("utf-8", "replace"),
            names=final_snapshot,
            names_timeline=names_timeline,
        ),
    )
    return RecordResult(output_path=output_path, stderr=combined_stderr, exit_code=exit_code)

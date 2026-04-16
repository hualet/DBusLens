from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import ast
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from dbuslens.bundle import BundleContents, BundleMetadata, write_bundle


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


def _capture_names(bus: str) -> dict[str, Any]:
    gdbus_path = shutil.which("gdbus")
    if gdbus_path is None:
        return {"captured_at": datetime.now().astimezone().isoformat(), "names": [], "error": "gdbus not found"}

    list_names = subprocess.run(
        [
            gdbus_path,
            "call",
            f"--{bus}",
            "--dest",
            "org.freedesktop.DBus",
            "--object-path",
            "/org/freedesktop/DBus",
            "--method",
            "org.freedesktop.DBus.ListNames",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if list_names.returncode != 0:
        return {
            "captured_at": datetime.now().astimezone().isoformat(),
            "names": [],
            "error": list_names.stderr.strip() or "ListNames failed",
        }

    try:
        names = ast.literal_eval(list_names.stdout.strip())
    except (ValueError, SyntaxError):
        names = []
    if isinstance(names, list) and names and isinstance(names[0], list):
        names = names[0]

    items = [{"name": name} for name in names if isinstance(name, str)]
    return {"captured_at": datetime.now().astimezone().isoformat(), "names": items}


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
    stdout, stderr, exit_code = _run_monitor(pcap_command, duration)
    profile_stdout, profile_stderr, profile_exit_code = _run_monitor(profile_command, duration)

    if exit_code not in {0, -15} and not stdout:
        stderr_text = stderr.decode("utf-8", "replace").strip()
        raise RecordError(f"dbus-monitor exited with code {exit_code}: {stderr_text}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined_stderr = b"\n".join(part for part in (stderr, profile_stderr) if part)
    monitor_mode = "monitor"
    stderr_text = combined_stderr.decode("utf-8", "replace")
    if "BecomeMonitor" in stderr_text:
        monitor_mode = "eavesdrop"

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
            names=_capture_names(bus),
        ),
    )
    return RecordResult(output_path=output_path, stderr=combined_stderr, exit_code=exit_code)

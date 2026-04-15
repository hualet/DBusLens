from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
import subprocess


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
    return directory / "record.cap"


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

    command = [monitor_path, f"--{bus}"]
    command.append("--pcap")
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

    if exit_code not in {0, -15} and not stdout:
        stderr_text = stderr.decode("utf-8", "replace").strip()
        raise RecordError(f"dbus-monitor exited with code {exit_code}: {stderr_text}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(stdout)
    return RecordResult(output_path=output_path, stderr=stderr, exit_code=exit_code)

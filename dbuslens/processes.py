from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
import subprocess


DBUS_ARGS = (
    "--dest",
    "org.freedesktop.DBus",
    "--object-path",
    "/org/freedesktop/DBus",
)


def resolve_process_name(service: str) -> str | None:
    if not service or service == "<unknown>":
        return None

    for bus in ("session", "system"):
        pid = _lookup_pid(bus, service)
        if pid is None:
            continue
        process_name = _read_process_name(pid)
        if process_name:
            return process_name
    return None


@lru_cache(maxsize=256)
def _lookup_pid(bus: str, service: str) -> int | None:
    command = [
        "gdbus",
        "call",
        f"--{bus}",
        *DBUS_ARGS,
        "--method",
        "org.freedesktop.DBus.GetConnectionUnixProcessID",
        service,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    match = re.search(r"\((?:uint32\s+)?(\d+),?\)", completed.stdout)
    if not match:
        return None
    return int(match.group(1))


def _read_process_name(pid: int) -> str | None:
    for candidate in (Path(f"/proc/{pid}/comm"), Path(f"/proc/{pid}/cmdline")):
        try:
            raw = candidate.read_bytes()
        except OSError:
            continue
        if not raw:
            continue
        text = raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
        if text:
            return Path(text.split()[0]).name
    return None

import json
import subprocess
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from dbuslens.bundle import BundleContents, BundleMetadata, read_bundle, write_bundle
from dbuslens.record import (
    _build_names_timeline,
    _capture_names,
    _parse_name_owner_changed_line,
    _start_background_monitor,
    _stop_background_monitor,
    record_monitor,
)


class BundleRoundTripTests(unittest.TestCase):
    def test_background_monitor_uses_file_backed_output_to_avoid_pipe_blocking(self) -> None:
        captured_kwargs: dict[str, object] = {}

        class FakeProcess:
            def __init__(self) -> None:
                self.returncode = 0

            def terminate(self) -> None:
                return None

            def communicate(self, timeout: int | None = None) -> tuple[bytes, bytes]:
                del timeout
                return b"", b""

            def kill(self) -> None:
                return None

        def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
            del command
            captured_kwargs.update(kwargs)
            stdout = kwargs["stdout"]
            stderr = kwargs["stderr"]
            self.assertTrue(hasattr(stdout, "write"))
            self.assertTrue(hasattr(stderr, "write"))
            self.assertNotEqual(stdout, subprocess.PIPE)
            self.assertNotEqual(stderr, subprocess.PIPE)
            stdout.write(b"timeline-stdout\n")
            stderr.write(b"timeline-stderr\n")
            stdout.flush()
            stderr.flush()
            return FakeProcess()

        with patch("dbuslens.record.subprocess.Popen", side_effect=fake_popen):
            monitor = _start_background_monitor(["dbus-monitor", "--session"])
            stdout, stderr, exit_code = _stop_background_monitor(monitor)

        self.assertEqual(stdout, b"timeline-stdout\n")
        self.assertEqual(stderr, b"timeline-stderr\n")
        self.assertEqual(exit_code, 0)

    def test_parse_name_owner_changed_line_extracts_fields(self) -> None:
        line = (
            "signal time=1713243600.500 sender=org.freedesktop.DBus -> destination=(null destination) "
            "serial=4 path=/org/freedesktop/DBus; interface=org.freedesktop.DBus; "
            "member=NameOwnerChanged string 'org.example.Service' string '' string ':1.42'"
        )

        self.assertEqual(
            _parse_name_owner_changed_line(line),
            {
                "timestamp": 1713243600.5,
                "name": "org.example.Service",
                "old_owner": "",
                "new_owner": ":1.42",
            },
        )

    def test_build_names_timeline_document_records_initial_events_and_final_snapshot(self) -> None:
        timeline = _build_names_timeline(
            bus="session",
            started_at="2026-04-16T10:20:30+08:00",
            ended_at="2026-04-16T10:20:40+08:00",
            initial_snapshot={"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
            lines=[
                "signal time=1713243600.500 sender=org.freedesktop.DBus -> destination=(null destination) serial=4 "
                "path=/org/freedesktop/DBus; interface=org.freedesktop.DBus; member=NameOwnerChanged "
                "string 'org.example.Service' string '' string ':1.42'"
            ],
            final_snapshot={"captured_at": "2026-04-16T10:20:40+08:00", "bus": "session", "names": []},
            error=None,
        )

        self.assertEqual(timeline["events"][0]["new_owner"], ":1.42")

    def test_record_monitor_writes_names_timeline_metadata(self) -> None:
        pcap_stdout = b"pcap-bytes"
        profile_stdout = b"profile-bytes"
        timeline_stdout = (
            "signal time=1713243600.500 sender=org.freedesktop.DBus -> destination=(null destination) serial=4 "
            "path=/org/freedesktop/DBus; interface=org.freedesktop.DBus; member=NameOwnerChanged "
            "string 'org.example.Service' string '' string ':1.42'\n"
        ).encode("utf-8")
        call_order: list[str] = []
        start_command: list[str] = []

        def fake_start_background_monitor(command: list[str]) -> object:
            start_command[:] = command
            call_order.append("start_timeline")
            return object()

        def fake_stop_background_monitor(process: object) -> tuple[bytes, bytes, int]:
            del process
            call_order.append("stop_timeline")
            return timeline_stdout, b"", 0

        def fake_run_monitor(command: list[str], duration: int) -> tuple[bytes, bytes, int]:
            del duration
            if command[-1] == "--pcap":
                call_order.append("pcap")
                return pcap_stdout, b"", 0
            if command[-1] == "--profile":
                call_order.append("profile")
                return profile_stdout, b"", 0
            self.fail(f"unexpected monitor command: {command}")

        def fake_capture_names(bus: str) -> dict[str, object]:
            call_order.append("snapshot")
            captured_at = (
                "2026-04-16T10:20:30+08:00"
                if call_order.count("snapshot") == 1
                else "2026-04-16T10:20:40+08:00"
            )
            return {"captured_at": captured_at, "bus": bus, "names": []}

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "dbuslens.record.shutil.which", return_value="/usr/bin/dbus-monitor"
        ), patch("dbuslens.record._start_background_monitor", side_effect=fake_start_background_monitor), patch(
            "dbuslens.record._stop_background_monitor", side_effect=fake_stop_background_monitor
        ), patch("dbuslens.record._run_monitor", side_effect=fake_run_monitor), patch(
            "dbuslens.record._capture_names", side_effect=fake_capture_names
        ), patch("dbuslens.record.write_bundle") as write_bundle_mock:
            output_path = Path(tmpdir) / "capture.dblens"
            record_monitor(bus="session", duration=10, output_path=output_path)

        self.assertIn("sender='org.freedesktop.DBus'", " ".join(start_command))
        self.assertIn("member='NameOwnerChanged'", " ".join(start_command))
        self.assertLess(call_order.index("snapshot"), call_order.index("start_timeline"))
        self.assertLess(call_order.index("start_timeline"), call_order.index("pcap"))
        self.assertLess(call_order.index("pcap"), call_order.index("profile"))
        self.assertLess(call_order.index("profile"), call_order.index("stop_timeline"))
        self.assertLess(call_order.index("stop_timeline"), len(call_order) - 1)
        self.assertEqual(call_order[-1], "snapshot")
        self.assertEqual(write_bundle_mock.call_count, 1)
        contents = write_bundle_mock.call_args.args[1]
        self.assertIsInstance(contents, BundleContents)
        self.assertEqual(contents.metadata.capture_files["names_timeline"], "names_timeline.json")
        self.assertIsNotNone(contents.names_timeline)
        self.assertEqual(contents.names_timeline["events"][0]["new_owner"], ":1.42")

    def test_record_monitor_keeps_quiet_timeline_non_error(self) -> None:
        pcap_stdout = b"pcap-bytes"
        profile_stdout = b"profile-bytes"
        timeline_command: list[str] = []

        def fake_start_background_monitor(command: list[str]) -> object:
            timeline_command[:] = command
            return object()

        def fake_stop_background_monitor(process: object) -> tuple[bytes, bytes, int]:
            del process
            return b"", b"", 0

        def fake_run_monitor(command: list[str], duration: int) -> tuple[bytes, bytes, int]:
            del duration
            if command[-1] == "--pcap":
                return pcap_stdout, b"", 0
            if command[-1] == "--profile":
                return profile_stdout, b"", 0
            self.fail(f"unexpected monitor command: {command}")

        snapshots = iter(
            [
                {"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
                {"captured_at": "2026-04-16T10:20:40+08:00", "bus": "session", "names": []},
            ]
        )

        def fake_capture_names(bus: str) -> dict[str, object]:
            snapshot = next(snapshots)
            self.assertEqual(snapshot["bus"], bus)
            return snapshot

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "dbuslens.record.shutil.which", return_value="/usr/bin/dbus-monitor"
        ), patch("dbuslens.record._start_background_monitor", side_effect=fake_start_background_monitor), patch(
            "dbuslens.record._stop_background_monitor", side_effect=fake_stop_background_monitor
        ), patch("dbuslens.record._run_monitor", side_effect=fake_run_monitor), patch(
            "dbuslens.record._capture_names", side_effect=fake_capture_names
        ), patch("dbuslens.record.write_bundle") as write_bundle_mock:
            output_path = Path(tmpdir) / "capture.dblens"
            record_monitor(bus="session", duration=10, output_path=output_path)

        self.assertIn("member='NameOwnerChanged'", " ".join(timeline_command))
        contents = write_bundle_mock.call_args.args[1]
        self.assertIsNotNone(contents.names_timeline)
        self.assertEqual(contents.names_timeline["events"], [])
        self.assertIsNone(contents.names_timeline["error"])

    def test_record_monitor_records_explicit_timeline_error_when_background_monitor_exits_nonzero_with_empty_stderr(self) -> None:
        pcap_stdout = b"pcap-bytes"
        profile_stdout = b"profile-bytes"

        def fake_start_background_monitor(command: list[str]) -> object:
            del command
            return object()

        def fake_stop_background_monitor(process: object) -> tuple[bytes, bytes, int]:
            del process
            return b"", b"", 1

        def fake_run_monitor(command: list[str], duration: int) -> tuple[bytes, bytes, int]:
            del duration
            if command[-1] == "--pcap":
                return pcap_stdout, b"", 0
            if command[-1] == "--profile":
                return profile_stdout, b"", 0
            self.fail(f"unexpected monitor command: {command}")

        snapshot_values = iter(
            [
                {"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
                {"captured_at": "2026-04-16T10:20:40+08:00", "bus": "session", "names": []},
            ]
        )

        def fake_capture_names(bus: str) -> dict[str, object]:
            snapshot = next(snapshot_values)
            self.assertEqual(snapshot["bus"], bus)
            return snapshot

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "dbuslens.record.shutil.which", return_value="/usr/bin/dbus-monitor"
        ), patch("dbuslens.record._start_background_monitor", side_effect=fake_start_background_monitor), patch(
            "dbuslens.record._stop_background_monitor", side_effect=fake_stop_background_monitor
        ), patch("dbuslens.record._run_monitor", side_effect=fake_run_monitor), patch(
            "dbuslens.record._capture_names", side_effect=fake_capture_names
        ), patch("dbuslens.record.write_bundle") as write_bundle_mock:
            output_path = Path(tmpdir) / "capture.dblens"
            record_monitor(bus="session", duration=10, output_path=output_path)

        contents = write_bundle_mock.call_args.args[1]
        self.assertIsNotNone(contents.names_timeline)
        self.assertIsNotNone(contents.names_timeline["error"])
        self.assertIn("timeline monitor exited with code 1", contents.names_timeline["error"])

    def test_write_and_read_bundle_round_trip(self) -> None:
        metadata = BundleMetadata(
            bundle_version=1,
            created_at="2026-04-16T10:20:30+08:00",
            bus="session",
            duration_seconds=10,
            capture_files={
                "pcap": "capture.cap",
                "profile": "capture.profile",
                "names": "names.json",
            },
            monitor={
                "command": ["dbus-monitor", "--session", "--pcap"],
                "profile_command": ["dbus-monitor", "--session", "--profile"],
                "stderr": "",
                "mode": "monitor",
            },
            extras={"notes": "test"},
        )
        expected = BundleContents(
            metadata=metadata,
            pcap_bytes=b"pcap-bytes",
            profile_text="profile-text",
            names={"captured_at": "2026-04-16T10:20:31+08:00", "names": []},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"

            write_bundle(path, expected)
            actual = read_bundle(path)

        self.assertEqual(actual.metadata, metadata)
        self.assertEqual(actual.pcap_bytes, b"pcap-bytes")
        self.assertEqual(actual.profile_text, "profile-text")
        self.assertEqual(actual.names, {"captured_at": "2026-04-16T10:20:31+08:00", "names": []})

    def test_write_and_read_bundle_preserves_snapshot_fields(self) -> None:
        metadata = BundleMetadata(
            bundle_version=1,
            created_at="2026-04-16T10:20:30+08:00",
            bus="session",
            duration_seconds=10,
            capture_files={
                "pcap": "capture.cap",
                "profile": "capture.profile",
                "names": "names.json",
            },
            monitor={
                "command": ["dbus-monitor", "--session", "--pcap"],
                "profile_command": ["dbus-monitor", "--session", "--profile"],
                "stderr": "",
                "mode": "monitor",
            },
        )
        expected_names = {
            "captured_at": "2026-04-16T10:20:31+08:00",
            "bus": "session",
            "names": [
                {
                    "name": "org.example.Service",
                    "owner": ":1.42",
                    "pid": 4242,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-service", "--session"],
                    "error": None,
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"

            write_bundle(
                path,
                BundleContents(
                    metadata=metadata,
                    pcap_bytes=b"pcap-bytes",
                    profile_text="profile-text",
                    names=expected_names,
                ),
            )
            actual = read_bundle(path)

        self.assertEqual(actual.metadata, metadata)
        self.assertEqual(actual.names, expected_names)

    def test_write_and_read_bundle_preserves_snapshot_error_field(self) -> None:
        metadata = BundleMetadata(
            bundle_version=1,
            created_at="2026-04-16T10:20:30+08:00",
            bus="session",
            duration_seconds=10,
            capture_files={
                "pcap": "capture.cap",
                "profile": "capture.profile",
                "names": "names.json",
            },
            monitor={
                "command": ["dbus-monitor", "--session", "--pcap"],
                "profile_command": ["dbus-monitor", "--session", "--profile"],
                "stderr": "",
                "mode": "monitor",
            },
        )
        expected_names = {
            "captured_at": "2026-04-16T10:20:31+08:00",
            "bus": "session",
            "error": "gdbus not found",
            "names": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"

            write_bundle(
                path,
                BundleContents(
                    metadata=metadata,
                    pcap_bytes=b"pcap-bytes",
                    profile_text="profile-text",
                    names=expected_names,
                ),
            )
            actual = read_bundle(path)

        self.assertEqual(actual.names, expected_names)

    def test_write_and_read_bundle_preserves_names_timeline(self) -> None:
        metadata = BundleMetadata(
            bundle_version=1,
            created_at="2026-04-16T10:20:30+08:00",
            bus="session",
            duration_seconds=10,
            capture_files={
                "pcap": "capture.cap",
                "profile": "capture.profile",
                "names": "names.json",
                "names_timeline": "names_timeline.json",
            },
            monitor={
                "command": ["dbus-monitor", "--session", "--pcap"],
                "profile_command": ["dbus-monitor", "--session", "--profile"],
                "stderr": "",
                "mode": "monitor",
            },
        )
        expected_timeline = {
            "bus": "session",
            "started_at": "2026-04-16T10:20:30+08:00",
            "ended_at": "2026-04-16T10:20:40+08:00",
            "initial_snapshot": {
                "captured_at": "2026-04-16T10:20:30+08:00",
                "bus": "session",
                "names": [],
            },
            "events": [
                {
                    "timestamp": 1713243600.5,
                    "name": "org.example.Service",
                    "old_owner": "",
                    "new_owner": ":1.42",
                }
            ],
            "final_snapshot": {
                "captured_at": "2026-04-16T10:20:40+08:00",
                "bus": "session",
                "names": [],
            },
            "error": None,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"

            write_bundle(
                path,
                BundleContents(
                    metadata=metadata,
                    pcap_bytes=b"pcap-bytes",
                    profile_text="profile-text",
                    names={"captured_at": "2026-04-16T10:20:31+08:00", "names": []},
                    names_timeline=expected_timeline,
                ),
            )
            actual = read_bundle(path)

        self.assertEqual(actual.metadata, metadata)
        self.assertEqual(actual.names_timeline, expected_timeline)

    def test_write_bundle_rejects_names_timeline_metadata_without_payload(self) -> None:
        metadata = BundleMetadata(
            bundle_version=1,
            created_at="2026-04-16T10:20:30+08:00",
            bus="session",
            duration_seconds=10,
            capture_files={
                "pcap": "capture.cap",
                "profile": "capture.profile",
                "names": "names.json",
                "names_timeline": "names_timeline.json",
            },
            monitor={
                "command": ["dbus-monitor", "--session", "--pcap"],
                "profile_command": ["dbus-monitor", "--session", "--profile"],
                "stderr": "",
                "mode": "monitor",
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"

            with self.assertRaisesRegex(
                ValueError, "advertises names_timeline but no timeline payload was provided"
            ):
                write_bundle(
                    path,
                    BundleContents(
                        metadata=metadata,
                        pcap_bytes=b"pcap-bytes",
                        profile_text="profile-text",
                        names={"captured_at": "2026-04-16T10:20:31+08:00", "names": []},
                    ),
                )

    def test_read_bundle_returns_none_when_names_timeline_member_is_missing(self) -> None:
        metadata = BundleMetadata(
            bundle_version=1,
            created_at="2026-04-16T10:20:30+08:00",
            bus="session",
            duration_seconds=10,
            capture_files={
                "pcap": "capture.cap",
                "profile": "capture.profile",
                "names": "names.json",
                "names_timeline": "names_timeline.json",
            },
            monitor={
                "command": ["dbus-monitor", "--session", "--pcap"],
                "profile_command": ["dbus-monitor", "--session", "--profile"],
                "stderr": "",
                "mode": "monitor",
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("meta.json", json.dumps(metadata.to_dict(), indent=2, sort_keys=True))
                archive.writestr("capture.cap", b"pcap-bytes")
                archive.writestr("capture.profile", "profile-text")
                archive.writestr(
                    "names.json",
                    json.dumps({"captured_at": "2026-04-16T10:20:31+08:00", "names": []}),
                )

            actual = read_bundle(path)

        self.assertEqual(actual.metadata, metadata)
        self.assertIsNone(actual.names_timeline)

    def test_capture_names_marks_snapshot_failure_when_gdbus_is_missing(self) -> None:
        with patch("dbuslens.record.shutil.which", return_value=None):
            snapshot = _capture_names("session")

        self.assertEqual(snapshot["bus"], "session")
        self.assertEqual(snapshot["names"], [])
        self.assertEqual(snapshot["error"], "gdbus not found")

    def test_capture_names_uses_unique_name_as_owner_without_lookup(self) -> None:
        calls: list[tuple[str, str, tuple[str, ...]]] = []

        def fake_run_gdbus_call(
            gdbus_path: str,
            bus: str,
            method: str,
            *arguments: str,
            timeout_seconds: float | None = None,
        ):
            del gdbus_path, timeout_seconds
            calls.append((bus, method, arguments))
            if method == "org.freedesktop.DBus.ListNames":
                return SimpleNamespace(returncode=0, stdout="[':1.42']", stderr="")
            if method == "org.freedesktop.DBus.GetConnectionUnixProcessID":
                return SimpleNamespace(returncode=0, stdout="(uint32 4242,)", stderr="")
            self.fail("GetNameOwner should not be called for unique names")

        with patch("dbuslens.record.shutil.which", return_value="/usr/bin/gdbus"), patch(
            "dbuslens.record._run_gdbus_call", side_effect=fake_run_gdbus_call
        ), patch("dbuslens.record._read_process_details", return_value=(1000, ["/bin/demo"])):
            snapshot = _capture_names("session")

        self.assertEqual(snapshot["error"], None)
        self.assertEqual(
            snapshot["names"],
            [
                {
                    "name": ":1.42",
                    "owner": ":1.42",
                    "pid": 4242,
                    "uid": 1000,
                    "cmdline": ["/bin/demo"],
                    "error": None,
                }
            ],
        )
        self.assertEqual(
            [method for _, method, _ in calls],
            ["org.freedesktop.DBus.ListNames", "org.freedesktop.DBus.GetConnectionUnixProcessID"],
        )

    def test_capture_names_marks_partial_failure_when_one_entry_fails(self) -> None:
        def fake_run_gdbus_call(
            gdbus_path: str,
            bus: str,
            method: str,
            *arguments: str,
            timeout_seconds: float | None = None,
        ):
            del gdbus_path, bus, timeout_seconds
            if method == "org.freedesktop.DBus.ListNames":
                return SimpleNamespace(
                    returncode=0,
                    stdout="['org.example.Good', 'org.example.Bad']",
                    stderr="",
                )
            if method == "org.freedesktop.DBus.GetNameOwner" and arguments == ("org.example.Good",):
                return SimpleNamespace(returncode=0, stdout="(':1.42',)", stderr="")
            if method == "org.freedesktop.DBus.GetConnectionUnixProcessID" and arguments == (":1.42",):
                return SimpleNamespace(returncode=0, stdout="(uint32 4242,)", stderr="")
            if method == "org.freedesktop.DBus.GetNameOwner" and arguments == ("org.example.Bad",):
                return SimpleNamespace(returncode=1, stdout="", stderr="owner missing")
            self.fail(f"unexpected call: {method} {arguments}")

        with patch("dbuslens.record.shutil.which", return_value="/usr/bin/gdbus"), patch(
            "dbuslens.record._run_gdbus_call", side_effect=fake_run_gdbus_call
        ), patch("dbuslens.record._read_process_details", return_value=(1000, ["/bin/demo"])):
            snapshot = _capture_names("session")

        self.assertEqual(snapshot["error"], "snapshot collection incomplete")
        self.assertEqual(
            snapshot["names"],
            [
                {
                    "name": "org.example.Good",
                    "owner": ":1.42",
                    "pid": 4242,
                    "uid": 1000,
                    "cmdline": ["/bin/demo"],
                    "error": None,
                },
                {
                    "name": "org.example.Bad",
                    "owner": None,
                    "pid": None,
                    "uid": None,
                    "cmdline": None,
                    "error": "owner missing",
                },
            ],
        )

    def test_capture_names_stops_when_snapshot_budget_is_exhausted(self) -> None:
        with patch("dbuslens.record.shutil.which", return_value="/usr/bin/gdbus"), patch(
            "dbuslens.record.time.monotonic",
            side_effect=[0, 0, 0, 0, 0, 6],
        ), patch(
            "dbuslens.record._run_gdbus_call",
            return_value=SimpleNamespace(returncode=0, stdout="['org.example.A', 'org.example.B']", stderr=""),
        ), patch(
            "dbuslens.record._lookup_name_owner",
            return_value=("owner-a", None),
        ), patch(
            "dbuslens.record._lookup_name_pid",
            return_value=(4242, None),
        ), patch(
            "dbuslens.record._read_process_details",
            return_value=(1000, ["/bin/demo"]),
        ):
            snapshot = _capture_names("session")

        self.assertEqual(snapshot["error"], "snapshot collection timed out")
        self.assertEqual(
            snapshot["names"],
            [
                {
                    "name": "org.example.A",
                    "owner": "owner-a",
                    "pid": 4242,
                    "uid": 1000,
                    "cmdline": ["/bin/demo"],
                    "error": None,
                }
            ],
        )

    def test_capture_names_marks_timeout_after_process_details(self) -> None:
        with patch("dbuslens.record.shutil.which", return_value="/usr/bin/gdbus"), patch(
            "dbuslens.record.time.monotonic",
            side_effect=[0, 0, 0, 0, 0, 6],
        ), patch(
            "dbuslens.record._run_gdbus_call",
            return_value=SimpleNamespace(returncode=0, stdout="['org.example.A']", stderr=""),
        ), patch(
            "dbuslens.record._lookup_name_owner",
            return_value=("owner-a", None),
        ), patch(
            "dbuslens.record._lookup_name_pid",
            return_value=(4242, None),
        ), patch(
            "dbuslens.record._read_process_details",
            return_value=(1000, ["/bin/demo"]),
        ):
            snapshot = _capture_names("session")

        self.assertEqual(snapshot["error"], "snapshot collection timed out")
        self.assertEqual(
            snapshot["names"],
            [
                {
                    "name": "org.example.A",
                    "owner": "owner-a",
                    "pid": 4242,
                    "uid": 1000,
                    "cmdline": ["/bin/demo"],
                    "error": None,
                }
            ],
        )

    def test_capture_names_marks_listnames_timeout(self) -> None:
        with patch("dbuslens.record.shutil.which", return_value="/usr/bin/gdbus"), patch(
            "dbuslens.record.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["gdbus"], timeout=5),
        ):
            snapshot = _capture_names("session")

        self.assertEqual(snapshot["error"], "snapshot collection timed out")
        self.assertEqual(snapshot["names"], [])

    def test_run_gdbus_call_uses_bounded_timeout(self) -> None:
        with patch("dbuslens.record.subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout="()", stderr="")

            from dbuslens.record import _run_gdbus_call

            _run_gdbus_call("/usr/bin/gdbus", "session", "org.freedesktop.DBus.ListNames")

        self.assertEqual(run.call_args.kwargs["timeout"], 5)
        self.assertEqual(run.call_args.kwargs["check"], False)

    def test_read_bundle_rejects_unsupported_version(self) -> None:
        metadata = BundleMetadata(
            bundle_version=99,
            created_at="2026-04-16T10:20:30+08:00",
            bus="session",
            duration_seconds=10,
            capture_files={
                "pcap": "capture.cap",
                "profile": "capture.profile",
                "names": "names.json",
            },
            monitor={
                "command": ["dbus-monitor", "--session", "--pcap"],
                "profile_command": ["dbus-monitor", "--session", "--profile"],
                "stderr": "",
                "mode": "monitor",
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"
            write_bundle(
                path,
                BundleContents(
                    metadata=metadata,
                    pcap_bytes=b"pcap-bytes",
                    profile_text="profile-text",
                    names={"captured_at": "2026-04-16T10:20:31+08:00", "names": []},
                ),
            )

            with self.assertRaisesRegex(ValueError, "unsupported bundle version"):
                read_bundle(path)


if __name__ == "__main__":
    unittest.main()

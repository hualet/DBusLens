import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
import subprocess

from dbuslens.bundle import BundleContents, BundleMetadata, read_bundle, write_bundle
from dbuslens.record import _capture_names


class BundleRoundTripTests(unittest.TestCase):
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

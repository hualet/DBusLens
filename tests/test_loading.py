import tempfile
import unittest
import json
import zipfile
from pathlib import Path

from dbus_fast.constants import MessageType
from dbus_fast.message import Message

from dbuslens.bundle import BundleContents, BundleMetadata, write_bundle
from dbuslens.loading import load_report
from tests.test_pcap_parser import build_pcap_bytes


class LoadReportTests(unittest.TestCase):
    def test_load_report_reports_stage_progress(self) -> None:
        capture = build_pcap_bytes(
            [
                (
                    1713081000.1,
                    Message(
                        message_type=MessageType.METHOD_CALL,
                        sender=":1.10",
                        destination="org.example.Service",
                        path="/org/example/Demo",
                        interface="org.example.Demo",
                        member="Ping",
                        serial=17,
                    ),
                )
            ]
        )
        updates: list[tuple[str, int, int]] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"
            write_bundle(
                path,
                BundleContents(
                    metadata=BundleMetadata(
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
                    ),
                    pcap_bytes=capture,
                    profile_text="",
                    names={
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
                    },
                ),
            )

            report = load_report(
                path,
                progress_callback=lambda update: updates.append(
                    (update.stage, update.current, update.total)
                ),
            )

        self.assertEqual(report.source_path, str(path))
        self.assertGreaterEqual(len(updates), 3)
        self.assertEqual(updates[0][0], "Opening capture")
        self.assertIn("Parsing capture", [stage for stage, _, _ in updates])
        self.assertIn("Analyzing events", [stage for stage, _, _ in updates])
        self.assertEqual(updates[-1], ("Preparing report", 100, 100))

    def test_load_report_coalesces_progress_updates(self) -> None:
        capture = build_pcap_bytes(
            [
                (
                    1713081000.1 + index,
                    Message(
                        message_type=MessageType.METHOD_CALL,
                        sender=":1.10",
                        destination="org.example.Service",
                        path="/org/example/Demo",
                        interface="org.example.Demo",
                        member="Ping",
                        serial=17 + index,
                    ),
                )
                for index in range(50)
            ]
        )
        updates: list[tuple[str, int, int]] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"
            write_bundle(
                path,
                BundleContents(
                    metadata=BundleMetadata(
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
                    ),
                    pcap_bytes=capture,
                    profile_text="",
                    names={
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
                    },
                ),
            )

            load_report(
                path,
                progress_callback=lambda update: updates.append(
                    (update.stage, update.current, update.total)
                ),
            )

        self.assertLess(len(updates), 18)

    def test_load_report_reads_bundle_input(self) -> None:
        capture = build_pcap_bytes(
            [
                (
                    1713081000.1,
                    Message(
                        message_type=MessageType.METHOD_CALL,
                        sender=":1.10",
                        destination="org.example.Service",
                        path="/org/example/Demo",
                        interface="org.example.Demo",
                        member="Ping",
                        serial=17,
                    ),
                ),
                (
                    1713081000.3,
                    Message(
                        message_type=MessageType.ERROR,
                        sender="org.example.Service",
                        destination=":1.10",
                        reply_serial=17,
                        error_name="org.example.Error.Failed",
                        serial=18,
                    ),
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"
            write_bundle(
                path,
                BundleContents(
                    metadata=BundleMetadata(
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
                    ),
                    pcap_bytes=capture,
                    profile_text="",
                    names={
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
                    },
                ),
            )

            report = load_report(path)

        self.assertEqual(report.source_path, str(path))
        self.assertEqual(report.total_events, 2)
        self.assertEqual(len(report.error_summaries), 1)
        self.assertEqual(report.error_summaries[0].target, "org.example.Service")
        self.assertEqual(report.error_summaries[0].target_process.display_name, "org.example.Service [4242]")

    def test_load_report_accepts_bundle_with_names_timeline(self) -> None:
        capture = build_pcap_bytes(
            [
                (
                    1713081000.1,
                    Message(
                        message_type=MessageType.METHOD_CALL,
                        sender=":1.10",
                        destination="org.example.Service",
                        path="/org/example/Demo",
                        interface="org.example.Demo",
                        member="Ping",
                        serial=17,
                    ),
                ),
                (
                    1713081000.3,
                    Message(
                        message_type=MessageType.ERROR,
                        sender="org.example.Service",
                        destination=":1.10",
                        reply_serial=17,
                        error_name="org.example.Error.Failed",
                        serial=18,
                    ),
                )
            ]
        )
        snapshot = {
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
        timeline = {
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
                    "timestamp": 1713081000.0,
                    "name": "org.example.Client",
                    "old_owner": "",
                    "new_owner": ":1.10",
                },
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
                "names": [
                    {
                        "name": "org.example.Client",
                        "owner": ":1.10",
                        "pid": 1010,
                        "uid": 1000,
                        "cmdline": ["/usr/bin/example-client"],
                        "error": None,
                    }
                ],
            },
            "error": None,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"
            write_bundle(
                path,
                BundleContents(
                    metadata=BundleMetadata(
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
                    ),
                    pcap_bytes=capture,
                    profile_text="",
                    names=snapshot,
                    names_timeline=timeline,
                ),
            )

            report = load_report(path)

        self.assertEqual(report.source_path, str(path))
        self.assertEqual(report.total_events, 2)
        self.assertEqual(report.error_summaries[0].details[0].caller, "org.example.Client")
        self.assertEqual(
            report.error_summaries[0].details[0].caller_process.display_name,
            "org.example.Client [1010]",
        )

    def test_load_report_accepts_bundle_missing_names_timeline_member(self) -> None:
        capture = build_pcap_bytes(
            [
                (
                    1713081000.1,
                    Message(
                        message_type=MessageType.METHOD_CALL,
                        sender=":1.10",
                        destination="org.example.Service",
                        path="/org/example/Demo",
                        interface="org.example.Demo",
                        member="Ping",
                        serial=17,
                    ),
                )
            ]
        )
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
                archive.writestr("capture.cap", capture)
                archive.writestr("capture.profile", "")
                archive.writestr(
                    "names.json",
                    json.dumps(
                        {
                            "captured_at": "2026-04-16T10:20:31+08:00",
                            "bus": "session",
                            "names": [],
                        }
                    ),
                )

            report = load_report(path)

        self.assertEqual(report.source_path, str(path))
        self.assertEqual(report.total_events, 1)

    def test_load_report_rejects_legacy_cap_input(self) -> None:
        capture = build_pcap_bytes(
            [
                (
                    1713081000.1,
                    Message(
                        message_type=MessageType.METHOD_CALL,
                        sender=":1.10",
                        destination="org.example.Service",
                        path="/org/example/Demo",
                        interface="org.example.Demo",
                        member="Ping",
                        serial=17,
                    ),
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "legacy.cap"
            path.write_bytes(capture)

            with self.assertRaisesRegex(ValueError, "only \\.dblens captures are supported"):
                load_report(path)


if __name__ == "__main__":
    unittest.main()

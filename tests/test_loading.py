import tempfile
import unittest
from pathlib import Path

from dbuslens.loading import load_report
from tests.test_pcap_parser import build_pcap_bytes
from dbus_fast.constants import MessageType
from dbus_fast.message import Message


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
            path = Path(tmpdir) / "sample.cap"
            path.write_bytes(capture)

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
            path = Path(tmpdir) / "sample.cap"
            path.write_bytes(capture)

            load_report(
                path,
                progress_callback=lambda update: updates.append(
                    (update.stage, update.current, update.total)
                ),
            )

        self.assertLess(len(updates), 18)


if __name__ == "__main__":
    unittest.main()

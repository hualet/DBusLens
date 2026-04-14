import unittest
from datetime import datetime
from pathlib import Path

from dbuslens.cli import build_parser
from dbuslens.record import build_default_output_path
from dbuslens.tui import BrowserState
from dbuslens.models import AnalysisReport, Row


class CliHelpersTests(unittest.TestCase):
    def test_build_default_output_path_uses_bus_and_timestamp(self) -> None:
        path = build_default_output_path(
            "session",
            now=datetime(2026, 4, 14, 16, 30, 5),
            base_dir=Path("/tmp"),
        )

        self.assertEqual(path, Path("/tmp/dbuslens-session-20260414-163005.log"))

    def test_build_parser_defines_record_and_analyze(self) -> None:
        parser = build_parser()

        record_args = parser.parse_args(["record", "--bus", "session", "--duration", "10"])
        analyze_args = parser.parse_args(["analyze", "--input", "sample.log"])

        self.assertEqual(record_args.command, "record")
        self.assertEqual(record_args.bus, "session")
        self.assertEqual(record_args.duration, 10)
        self.assertEqual(analyze_args.command, "analyze")
        self.assertEqual(analyze_args.input, "sample.log")


class BrowserStateTests(unittest.TestCase):
    def test_browser_state_switches_views(self) -> None:
        report = AnalysisReport(
            source_path="sample.log",
            total_events=1,
            actionable_events=1,
            skipped_blocks=0,
            outbound_rows=[Row(name="svc", count=1, children=[("op", 1)])],
            inbound_rows=[Row(name="op", count=1, children=[("svc", 1)])],
        )
        state = BrowserState(report)

        state.switch_view()

        self.assertEqual(state.active_view, "inbound")


if __name__ == "__main__":
    unittest.main()

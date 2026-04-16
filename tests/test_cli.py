import unittest
from argparse import Namespace
from datetime import datetime
from pathlib import Path

from dbuslens.cli import _handle_record, _handle_report, build_parser
from dbuslens.record import build_default_output_path
from dbuslens.tui import DBusLensReportApp
from dbuslens.models import AnalysisReport, DetailRow, ProcessInfo, Row


class CliHelpersTests(unittest.TestCase):
    def test_build_parser_defines_record_and_report(self) -> None:
        parser = build_parser()

        record_args = parser.parse_args(["record", "--duration", "10"])
        report_args = parser.parse_args(["report"])

        self.assertEqual(record_args.command, "record")
        self.assertEqual(record_args.bus, "session")
        self.assertEqual(record_args.duration, 10)
        self.assertEqual(record_args.output, "record.dblens")
        self.assertEqual(report_args.command, "report")
        self.assertEqual(report_args.input, "record.dblens")

    def test_build_default_output_path_returns_record_dblens_in_workdir(self) -> None:
        path = build_default_output_path(
            "session",
            now=datetime(2026, 4, 14, 16, 30, 5),
            base_dir=Path("/tmp"),
        )

        self.assertEqual(path, Path("/tmp/record.dblens"))

    def test_handle_record_rejects_non_bundle_output(self) -> None:
        with self.assertRaisesRegex(ValueError, "record output must use the \\.dblens extension"):
            _handle_record(Namespace(bus="session", duration=10, output="record.cap"))

    def test_handle_report_rejects_non_bundle_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "report input must use the \\.dblens extension"):
            _handle_report(Namespace(input="record.cap"))


class ReportAppConstructionTests(unittest.TestCase):
    def test_report_app_keeps_report_reference(self) -> None:
        report = AnalysisReport(
            source_path="sample.log",
            total_events=1,
            actionable_events=1,
            skipped_blocks=0,
            outbound_rows=[
                Row(
                    name="svc",
                    process=ProcessInfo(short_name="demo", pid=4321),
                    count=1,
                    children=[DetailRow(name="op", process=None, count=1)],
                )
            ],
            inbound_rows=[
                Row(
                    name="op",
                    process=None,
                    count=1,
                    children=[
                        DetailRow(
                            name="svc",
                            process=ProcessInfo(short_name="demo", pid=4321),
                            count=1,
                        )
                    ],
                )
            ],
            error_rows=[],
        )
        app = DBusLensReportApp(report)

        self.assertEqual(app.report, report)
        self.assertEqual(app.state.active_view, "outbound")


if __name__ == "__main__":
    unittest.main()

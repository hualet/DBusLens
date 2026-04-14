import unittest

from dbuslens.models import AnalysisReport, DetailRow, Row
from dbuslens.tui import DBusLensReportApp


class TextualLayoutTests(unittest.TestCase):
    def test_textual_ui_defines_navigation_main_and_detail_regions(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=2,
            actionable_events=2,
            skipped_blocks=0,
            outbound_rows=[
                Row(
                    name=":1.10",
                    process="demo-client",
                    count=2,
                    children=[DetailRow(name="org.example.Demo.Ping", process=None, count=2)],
                )
            ],
            inbound_rows=[
                Row(
                    name="org.example.Demo.Ping",
                    process=None,
                    count=2,
                    children=[DetailRow(name=":1.10", process="demo-client", count=2)],
                )
            ],
        )
        app = DBusLensReportApp(report)
        ids = app.region_ids()

        self.assertIn("view-nav", ids)
        self.assertIn("main-table", ids)
        self.assertIn("detail-pane", ids)


if __name__ == "__main__":
    unittest.main()

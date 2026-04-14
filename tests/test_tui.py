import unittest

from textual.widgets import DataTable, Footer, Header, ListView, Static

from dbuslens.models import AnalysisReport, DetailRow, Row
from dbuslens.tui import DBusLensReportApp


class TextualLayoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_selecting_main_row_updates_detail_panel(self) -> None:
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
                ),
                Row(
                    name=":1.11",
                    process="demo-service",
                    count=1,
                    children=[DetailRow(name="org.example.Demo.Echo", process=None, count=1)],
                ),
            ],
            inbound_rows=[],
        )
        app = DBusLensReportApp(report)

        async with app.run_test() as pilot:
            detail = app.query_one("#detail-pane", Static)

            await pilot.press("down")
            await pilot.pause()

            self.assertEqual(app.state.selected_index, 1)
            self.assertIn("demo-service", str(detail.render()))

    async def test_textual_ui_defines_navigation_main_and_detail_regions(self) -> None:
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

        async with app.run_test():
            self.assertIsInstance(app.query_one(Header), Header)
            self.assertIsInstance(app.query_one("#view-nav"), ListView)
            self.assertIsInstance(app.query_one("#main-table"), DataTable)
            self.assertIsInstance(app.query_one("#detail-pane"), Static)
            self.assertIsInstance(app.query_one(Footer), Footer)


if __name__ == "__main__":
    unittest.main()

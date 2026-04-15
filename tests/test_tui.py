import unittest

from textual.css.query import NoMatches
from textual.widgets import DataTable, Footer, Header, Label, ListView, Static

from dbuslens.models import AnalysisReport, DetailRow, ProcessInfo, Row
from dbuslens.tui import DBusLensReportApp


class TextualLayoutTests(unittest.IsolatedAsyncioTestCase):
    def test_textual_ui_styles_datatable_components(self) -> None:
        css = DBusLensReportApp.CSS

        self.assertIn("DataTable > .datatable--header", css)
        self.assertIn("DataTable > .datatable--odd-row", css)
        self.assertIn("DataTable > .datatable--even-row", css)
        self.assertIn("DataTable > .datatable--cursor", css)

    async def test_textual_ui_uses_monitor_branding(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=1,
            actionable_events=1,
            skipped_blocks=0,
            outbound_rows=[],
            inbound_rows=[],
        )
        app = DBusLensReportApp(report)

        async with app.run_test():
            app_bar = app.query_one("#app-bar", Static)
            self.assertIn("Monitor", str(app_bar.render()))

    async def test_selecting_main_row_updates_detail_panel(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=3,
            actionable_events=3,
            skipped_blocks=0,
            outbound_rows=[
                Row(
                    name=":1.10",
                    process=ProcessInfo(short_name="demo-client", pid=1010),
                    count=2,
                    children=[
                        DetailRow(name="org.example.Demo.Ping", process=None, count=2),
                        DetailRow(name="org.example.Demo.Echo", process=None, count=1),
                    ],
                ),
                Row(
                    name=":1.11",
                    process=ProcessInfo(short_name="demo-service", pid=1111),
                    count=1,
                    children=[DetailRow(name="org.example.Demo.Call", process=None, count=1)],
                ),
            ],
            inbound_rows=[],
        )
        app = DBusLensReportApp(report)

        async with app.run_test() as pilot:
            detail = app.query_one("#detail-pane", Static)
            detail_table = app.query_one("#detail-table", DataTable)

            await pilot.press("down")
            await pilot.pause()

            self.assertEqual(app.state.selected_index, 1)
            self.assertIn("demo-service [1111]", str(detail.render()))
            self.assertIn("PID: 1111", str(detail.render()))
            self.assertEqual(detail_table.row_count, 1)

    async def test_textual_ui_shows_report_metadata_and_all_detail_rows(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=3,
            actionable_events=3,
            skipped_blocks=1,
            outbound_rows=[
                Row(
                    name=":1.10",
                    process=ProcessInfo(short_name="demo-client", pid=1010),
                    count=3,
                    children=[
                        DetailRow(name="org.example.Demo.Ping", process=None, count=2),
                        DetailRow(name="org.example.Demo.Echo", process=None, count=1),
                    ],
                )
            ],
            inbound_rows=[],
        )
        app = DBusLensReportApp(report)

        async with app.run_test():
            meta = app.query_one("#report-meta", Static)
            detail_table = app.query_one("#detail-table", DataTable)

            self.assertIn("record.cap", str(meta.render()))
            self.assertIn("events=3", str(meta.render()))
            self.assertEqual(detail_table.row_count, 2)

    async def test_textual_ui_defines_navigation_main_and_detail_regions(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=2,
            actionable_events=2,
            skipped_blocks=0,
            outbound_rows=[
                Row(
                    name=":1.10",
                    process=ProcessInfo(short_name="demo-client", pid=1010),
                    count=2,
                    children=[DetailRow(name="org.example.Demo.Ping", process=None, count=2)],
                )
            ],
            inbound_rows=[
                Row(
                    name="org.example.Demo.Ping",
                    process=None,
                    count=2,
                    children=[
                        DetailRow(
                            name=":1.10",
                            process=ProcessInfo(short_name="demo-client", pid=1010),
                            count=2,
                        )
                    ],
                )
            ],
        )
        app = DBusLensReportApp(report)

        async with app.run_test():
            with self.assertRaises(NoMatches):
                app.query_one(Header)
            self.assertIsInstance(app.query_one("#app-bar"), Static)
            self.assertIsInstance(app.query_one("#report-meta"), Static)
            self.assertIsInstance(app.query_one("#view-nav"), ListView)
            self.assertIsInstance(app.query_one("#main-table"), DataTable)
            self.assertIsInstance(app.query_one("#detail-pane"), Static)
            self.assertIsInstance(app.query_one("#detail-table"), DataTable)
            self.assertIsInstance(app.query_one(Footer), Footer)

    async def test_textual_ui_uses_senders_and_members_labels(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=1,
            actionable_events=1,
            skipped_blocks=0,
            outbound_rows=[],
            inbound_rows=[],
        )
        app = DBusLensReportApp(report)

        async with app.run_test():
            labels = [str(label.render()) for label in app.query("#view-nav Label")]
            self.assertIn("Senders", labels)
            self.assertIn("Members", labels)


if __name__ == "__main__":
    unittest.main()

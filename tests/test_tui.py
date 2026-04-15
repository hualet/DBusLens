import unittest

from textual.css.query import NoMatches
from textual.widgets import DataTable, Footer, Header, Label, ListView, ProgressBar, Static

from dbuslens.models import AnalysisReport, DetailRow, ProcessInfo, Row
from dbuslens.tui import DBusLensLoaderApp, DBusLensReportApp


class TextualLayoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_loader_app_starts_with_loading_view(self) -> None:
        app = DBusLensLoaderApp("record.cap")

        async with app.run_test():
            self.assertIsInstance(app.query_one("#loading-status", Static), Static)
            self.assertIsInstance(app.query_one("#loading-bar", ProgressBar), ProgressBar)
            with self.assertRaises(NoMatches):
                app.query_one("#eta")

    def test_textual_ui_styles_datatable_components(self) -> None:
        css = DBusLensReportApp.CSS

        self.assertIn("DataTable > .datatable--header", css)
        self.assertIn("DataTable > .datatable--odd-row", css)
        self.assertIn("DataTable > .datatable--even-row", css)
        self.assertIn("DataTable > .datatable--cursor", css)
        self.assertIn("#view-nav > ListItem.-highlight", css)
        self.assertIn("#column-resizer", css)
        self.assertIn("content-align: center middle", css)
        self.assertIn("width: 1", css)
        self.assertIn("pointer: ew-resize", css)
        self.assertIn("#column-resizer:hover", css)
        self.assertIn("pointer: grabbing", css)

    async def test_textual_ui_uses_btop_inspired_branding(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=1,
            actionable_events=1,
            skipped_blocks=0,
            outbound_rows=[],
            inbound_rows=[],
            error_rows=[],
        )
        app = DBusLensReportApp(report)

        async with app.run_test():
            app_bar = app.query_one("#app-bar", Static)
            self.assertIn("btop-inspired", str(app_bar.render()))

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
            error_rows=[],
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
            error_rows=[],
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
            error_rows=[],
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
            error_rows=[],
        )
        app = DBusLensReportApp(report)

        async with app.run_test():
            labels = [str(label.render()) for label in app.query("#view-nav Label")]
            self.assertIn("Senders", labels)
            self.assertIn("Members", labels)
            self.assertIn("Errors", labels)

    async def test_textual_ui_sets_panel_border_titles(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=1,
            actionable_events=1,
            skipped_blocks=0,
            outbound_rows=[],
            inbound_rows=[],
            error_rows=[],
        )
        app = DBusLensReportApp(report)

        async with app.run_test():
            self.assertEqual(app.query_one("#view-nav", ListView).border_title, " views ")
            self.assertEqual(app.query_one("#main-table", DataTable).border_title, " senders ")
            self.assertEqual(app.query_one("#detail-pane", Static).border_title, " selected ")
            self.assertEqual(app.query_one("#detail-table", DataTable).border_title, " members ")

    async def test_textual_ui_supports_errors_view(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=2,
            actionable_events=1,
            skipped_blocks=0,
            outbound_rows=[],
            inbound_rows=[],
            error_rows=[
                Row(
                    name="org.freedesktop.DBus.Error.NameHasNoOwner",
                    process=None,
                    count=1,
                    children=[
                        DetailRow(
                            name=":1.10",
                            process=ProcessInfo(short_name="demo-client", pid=1010),
                            count=1,
                            secondary="org.freedesktop.DBus.GetNameOwner",
                        )
                    ],
                )
            ],
        )
        app = DBusLensReportApp(report)

        async with app.run_test() as pilot:
            await pilot.press("e")
            await pilot.pause()

            main_table = app.query_one("#main-table", DataTable)
            detail_table = app.query_one("#detail-table", DataTable)

            self.assertEqual(app.state.active_view, "errors")
            self.assertEqual(main_table.border_title, " errors ")
            self.assertEqual(detail_table.border_title, " details ")
            self.assertEqual(detail_table.row_count, 1)

    async def test_textual_ui_supports_sender_and_member_shortcuts(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=2,
            actionable_events=2,
            skipped_blocks=0,
            outbound_rows=[
                Row(
                    name="org.example.Service",
                    process=ProcessInfo(short_name="demo-service", pid=4242),
                    count=1,
                    children=[DetailRow(name="org.example.Method", process=None, count=1)],
                )
            ],
            inbound_rows=[
                Row(
                    name="org.example.Method",
                    process=None,
                    count=1,
                    children=[
                        DetailRow(
                            name="org.example.Service",
                            process=ProcessInfo(short_name="demo-service", pid=4242),
                            count=1,
                        )
                    ],
                )
            ],
            error_rows=[],
        )
        app = DBusLensReportApp(report)

        async with app.run_test() as pilot:
            await pilot.press("m")
            await pilot.pause()
            self.assertEqual(app.state.active_view, "inbound")
            self.assertEqual(app.query_one("#main-table", DataTable).border_title, " members ")

            await pilot.press("s")
            await pilot.pause()
            self.assertEqual(app.state.active_view, "outbound")
            self.assertEqual(app.query_one("#main-table", DataTable).border_title, " senders ")

    async def test_textual_ui_allows_dragging_detail_column_width(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=2,
            actionable_events=2,
            skipped_blocks=0,
            outbound_rows=[
                Row(
                    name="org.example.Service",
                    process=ProcessInfo(short_name="demo-service", pid=4242),
                    count=1,
                    children=[DetailRow(name="org.example.Method", process=None, count=1)],
                )
            ],
            inbound_rows=[],
            error_rows=[],
        )
        app = DBusLensReportApp(report)

        async with app.run_test() as pilot:
            await pilot.resize_terminal(120, 30)
            await pilot.pause()

            splitter = app.query_one("#column-resizer", Static)
            detail_column = app.query_one("#detail-column")
            before_width = detail_column.size.width

            target_x = splitter.region.x - 10
            target_y = splitter.region.y

            await pilot.mouse_down("#column-resizer", offset=(0, 0))
            await pilot.mouse_up(offset=(target_x, target_y))
            await pilot.pause()

            self.assertGreater(detail_column.size.width, before_width)

    async def test_textual_ui_shows_visible_drag_handle(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=1,
            actionable_events=1,
            skipped_blocks=0,
            outbound_rows=[],
            inbound_rows=[],
            error_rows=[],
        )
        app = DBusLensReportApp(report)

        async with app.run_test():
            resizer = app.query_one("#column-resizer", Static)

            self.assertEqual(str(resizer.render()), "⋮")


if __name__ == "__main__":
    unittest.main()

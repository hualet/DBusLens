import unittest

from textual.css.query import NoMatches
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, ListView, ProgressBar, Static

from dbuslens.models import (
    AnalysisReport,
    CaptureNameInfo,
    DetailRow,
    ErrorDetail,
    ErrorSummary,
    LatencyDetail,
    LatencySummary,
    ProcessInfo,
    Row,
)
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
        self.assertIn("height: 1", css)
        self.assertIn("pointer: ns-resize", css)
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
            detail_table = app.query_one("#detail-table", DataTable)

            await pilot.press("down")
            await pilot.pause()

            self.assertEqual(app.state.selected_index, 1)
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
            self.assertIsInstance(app.query_one("#content-area"), Vertical)
            self.assertIsInstance(app.query_one("#main-table"), DataTable)
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
            self.assertIn("Latency", labels)

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
            self.assertEqual(app.query_one("#detail-table", DataTable).border_title, " members ")

    async def test_textual_ui_supports_errors_view(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=2,
            actionable_events=1,
            skipped_blocks=0,
            outbound_rows=[],
            inbound_rows=[],
            error_rows=[],
            latency_summaries=[
                LatencySummary(
                    target="org.example.Service",
                    operation="org.example.Demo.Slow",
                    count=1,
                    average_latency_ms=250.0,
                    min_latency_ms=250.0,
                    max_latency_ms=250.0,
                    target_process=CaptureNameInfo(
                        name="org.example.Service",
                        owner=":1.42",
                        pid=4242,
                        uid=1000,
                        cmdline=["/usr/bin/demo-service"],
                    ),
                    details=[
                        LatencyDetail(
                            caller=":1.10",
                            caller_process=CaptureNameInfo(
                                name=":1.10",
                                owner=":1.10",
                                pid=1010,
                                uid=1000,
                                cmdline=["/usr/bin/demo-client"],
                            ),
                            target="org.example.Service",
                            target_process=CaptureNameInfo(
                                name="org.example.Service",
                                owner=":1.42",
                                pid=4242,
                                uid=1000,
                                cmdline=["/usr/bin/demo-service"],
                            ),
                            operation="org.example.Demo.Slow",
                            latency_ms="250.0 ms",
                            timestamp=1.0,
                            path="/org/example/Demo",
                            args_preview="['demo']",
                        )
                    ],
                )
            ],
            error_summaries=[
                ErrorSummary(
                    error_name="org.freedesktop.DBus.Error.NameHasNoOwner",
                    target="org.example.Service",
                    operation="org.freedesktop.DBus.GetNameOwner",
                    count=1,
                    first_seen=1.0,
                    last_seen=1.0,
                    average_latency_ms=250.0,
                    retry_count=0,
                    unique_callers=1,
                    target_process=CaptureNameInfo(
                        name="org.example.Service",
                        owner=":1.42",
                        pid=4242,
                        uid=1000,
                        cmdline=["/usr/bin/demo-service"],
                    ),
                    details=[
                        ErrorDetail(
                            caller=":1.10",
                            caller_process=CaptureNameInfo(
                                name=":1.10",
                                owner=":1.10",
                                pid=1010,
                                uid=1000,
                                cmdline=["/usr/bin/demo-client"],
                            ),
                            target_process=CaptureNameInfo(
                                name="org.example.Service",
                                owner=":1.42",
                                pid=4242,
                                uid=1000,
                                cmdline=["/usr/bin/demo-service"],
                            ),
                            latency_ms="250.0 ms",
                            notes="",
                            count=1,
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
            self.assertEqual(main_table.row_count, 1)
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

    async def test_textual_ui_supports_latency_shortcut(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=2,
            actionable_events=2,
            skipped_blocks=0,
            outbound_rows=[],
            inbound_rows=[],
            error_rows=[],
            latency_summaries=[
                LatencySummary(
                    target="org.example.Service",
                    operation="org.example.Demo.Slow",
                    count=1,
                    average_latency_ms=250.0,
                    min_latency_ms=250.0,
                    max_latency_ms=250.0,
                    target_process=CaptureNameInfo(
                        name="org.example.Service",
                        owner=":1.42",
                        pid=4242,
                        uid=1000,
                        cmdline=["/usr/bin/demo-service"],
                    ),
                    details=[
                        LatencyDetail(
                            caller=":1.10",
                            caller_process=None,
                            target="org.example.Service",
                            target_process=CaptureNameInfo(
                                name="org.example.Service",
                                owner=":1.42",
                                pid=4242,
                                uid=1000,
                                cmdline=["/usr/bin/demo-service"],
                            ),
                            operation="org.example.Demo.Slow",
                            latency_ms="250.0 ms",
                            timestamp=1.0,
                            path="/org/example/Demo",
                            args_preview="['demo']",
                        )
                    ],
                )
            ],
        )
        app = DBusLensReportApp(report)

        async with app.run_test() as pilot:
            await pilot.press("l")
            await pilot.pause()

            main_table = app.query_one("#main-table", DataTable)
            detail_table = app.query_one("#detail-table", DataTable)

            self.assertEqual(app.state.active_view, "latency")
            self.assertEqual(main_table.border_title, " latency ")
            self.assertEqual(detail_table.border_title, " calls ")
            self.assertEqual(main_table.row_count, 1)
            self.assertEqual(detail_table.row_count, 1)

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
            main_table = app.query_one("#main-table", DataTable)
            before_height = main_table.size.height

            target_x = splitter.region.x
            target_y = splitter.region.y + 5

            await pilot.mouse_down("#column-resizer", offset=(0, 0))
            await pilot.mouse_up(offset=(target_x, target_y))
            await pilot.pause()

            self.assertGreater(main_table.size.height, before_height)

    async def test_textual_ui_uses_narrower_view_navigation(self) -> None:
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
            nav = app.query_one("#view-nav", ListView)
            self.assertEqual(int(nav.styles.width.value), 15)

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

            self.assertEqual(str(resizer.render()), "━")


if __name__ == "__main__":
    unittest.main()

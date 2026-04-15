from __future__ import annotations

from pathlib import Path
import threading

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Label, ListItem, ListView, ProgressBar, Static

from dbuslens.loading import LoadingUpdate, load_report
from dbuslens.models import AnalysisReport
from dbuslens.report_app import (
    ReportAppState,
    detail_column_widths,
    detail_columns,
    detail_lines,
    detail_rows,
    main_column_widths,
    main_columns,
    main_rows,
    metadata_text,
)


class DBusLensReportApp(App[None]):
    BINDINGS = [
        ("left", "show_outbound", "Senders"),
        ("right", "show_inbound", "Members"),
        ("tab", "focus_next_pane", "Next Pane"),
        ("shift+tab", "focus_previous_pane", "Prev Pane"),
        ("enter", "focus_detail_pane", "Detail Pane"),
        ("q", "quit", "Quit"),
    ]

    CSS = """
    Screen {
        layout: vertical;
        background: #080a0f;
        color: #d8f3dc;
    }

    #app-bar {
        dock: top;
        height: 3;
        padding: 0 2;
        background: #080a0f;
        color: #dcefd9;
        border-bottom: solid #6ee7b7;
        text-style: bold;
    }

    #report-meta {
        dock: top;
        height: 3;
        margin: 1 1 0 1;
        padding: 0 2;
        background: #0e1219;
        color: #9fb3c8;
        border: round #3b82f6;
    }

    #body {
        height: 1fr;
        margin: 1;
        padding: 0;
    }

    #view-nav {
        width: 24;
        padding: 1 0;
        border: round #a78bfa;
        background: #0b1017;
        color: #dcefd9;
    }

    #main-table {
        height: 1fr;
        width: 3fr;
        border: round #6ee7b7;
        background: #0b1017;
        color: #e6f6ea;
    }

    #detail-column {
        width: 2fr;
        min-width: 36;
    }

    #detail-pane {
        height: 9;
        padding: 1 2;
        border: round #f472b6;
        background: #0b1017;
        color: #e8eef8;
    }

    #detail-table {
        height: 1fr;
        border: round #f59e0b;
        background: #0b1017;
        color: #eef6ff;
    }

    DataTable {
        background: transparent;
    }

    DataTable > .datatable--header {
        background: #12342e;
        color: #fcd34d;
        text-style: bold;
    }

    DataTable > .datatable--header-cursor {
        background: #1d4d44;
        color: #fde68a;
        text-style: bold;
    }

    DataTable > .datatable--odd-row {
        background: #0f151d;
        color: #dcefd9;
    }

    DataTable > .datatable--even-row {
        background: #0b1118;
        color: #dcefd9;
    }

    DataTable > .datatable--cursor {
        background: #173b6c;
        color: #f8fbff;
        text-style: bold;
    }

    DataTable > .datatable--hover {
        background: #132432;
        color: #f8fbff;
    }

    #view-nav > ListItem {
        margin: 0 1;
        padding: 0 1;
        color: #b8c8d8;
        background: transparent;
        border-left: tall transparent;
    }

    #view-nav > ListItem.-highlight {
        color: #f8fbff;
        background: #173b6c;
        border-left: tall #fcd34d;
        text-style: bold;
    }

    .pane-focus {
        border: round #fcd34d;
        tint: #102033 6%;
    }

    Footer {
        background: #080a0f;
        color: #b8c8d8;
    }

    Footer > .footer--highlight {
        background: #16222e;
        color: #fcd34d;
    }

    #view-nav .label,
    #detail-pane .label {
        color: #fcd34d;
    }
    """

    def __init__(self, report: AnalysisReport) -> None:
        super().__init__()
        self.report = report
        self.state = ReportAppState(report)

    def compose(self) -> ComposeResult:
        yield Static(id="app-bar")
        yield Static(id="report-meta")
        with Horizontal(id="body"):
            yield ListView(
                ListItem(Label("Senders")),
                ListItem(Label("Members")),
                id="view-nav",
            )
            yield DataTable(id="main-table")
            with Vertical(id="detail-column"):
                yield Static(id="detail-pane")
                yield DataTable(id="detail-table")
        yield Footer()

    def on_mount(self) -> None:
        self._populate_app_bar()
        self._populate_report_meta()
        self._populate_panel_titles()
        self._populate_navigation()
        self._populate_main_table()
        self.refresh_detail()
        self._focus_main_table()

    def _populate_app_bar(self) -> None:
        self.query_one("#app-bar", Static).update(
            "[b #60a5fa]DBusLens[/]  [#fcd34d]report[/]  [#6ee7b7]btop-inspired[/]  "
            "[#9fb3c8]Terminal capture inspector for D-Bus traffic[/]"
        )

    def _populate_report_meta(self) -> None:
        self.query_one("#report-meta", Static).update(
            "[#60a5fa]Capture[/]  "
            f"[#f8fbff]{metadata_text(self.report)}[/]  "
            "[#7c8da3]Use Tab to rotate focus and Enter to inspect details[/]"
        )

    def _populate_panel_titles(self) -> None:
        self.query_one("#view-nav", ListView).border_title = " views "
        self.query_one("#detail-pane", Static).border_title = " selected "

    def _populate_navigation(self) -> None:
        nav = self.query_one("#view-nav", ListView)
        nav.index = 0 if self.state.active_view == "outbound" else 1

    def _populate_main_table(self) -> None:
        table = self.query_one("#main-table", DataTable)
        table.border_title = " senders " if self.state.active_view == "outbound" else " members "
        table.cursor_type = "row"
        table.zebra_stripes = True
        if table.columns:
            table.clear(columns=True)
        for label, width in zip(main_columns(self.state), main_column_widths(self.state)):
            table.add_column(label, width=width)
        for row in main_rows(self.state):
            table.add_row(*row)
        if table.row_count:
            table.move_cursor(row=min(self.state.selected_index, table.row_count - 1), animate=False)

    def refresh_detail(self) -> None:
        self.query_one("#detail-pane", Static).update("\n".join(detail_lines(self.state)))
        table = self.query_one("#detail-table", DataTable)
        table.border_title = " members " if self.state.active_view == "outbound" else " senders "
        table.cursor_type = "row"
        table.zebra_stripes = True
        if table.columns:
            table.clear(columns=True)
        for label, width in zip(detail_columns(self.state), detail_column_widths(self.state)):
            table.add_column(label, width=width)
        for row in detail_rows(self.state):
            table.add_row(*row)

    def action_show_outbound(self) -> None:
        if self.state.active_view != "outbound":
            self.state.switch_view()
            self._sync_view()

    def action_show_inbound(self) -> None:
        if self.state.active_view != "inbound":
            self.state.switch_view()
            self._sync_view()

    def action_focus_next_pane(self) -> None:
        focused = self.focused
        if focused and focused.id == "view-nav":
            self._focus_main_table()
            return
        if focused and focused.id == "main-table":
            self._focus_detail_table()
            return
        self._focus_navigation()

    def action_focus_previous_pane(self) -> None:
        focused = self.focused
        if focused and focused.id == "detail-table":
            self._focus_main_table()
            return
        if focused and focused.id == "main-table":
            self._focus_navigation()
            return
        self._focus_detail_table()

    def action_focus_detail_pane(self) -> None:
        self._focus_detail_table()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "view-nav" or event.list_view.index is None:
            return
        desired_view = "outbound" if event.list_view.index == 0 else "inbound"
        if desired_view == self.state.active_view:
            return
        self.state.switch_view()
        self._sync_view()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "main-table" or event.cursor_row is None:
            return
        self.state.selected_index = event.cursor_row
        self.refresh_detail()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "main-table":
            return
        self.state.selected_index = event.cursor_row
        self.refresh_detail()

    def _sync_view(self) -> None:
        self._populate_navigation()
        self._populate_main_table()
        self.refresh_detail()

    def _focus_navigation(self) -> None:
        self.query_one("#view-nav", ListView).focus()
        self._sync_focus_classes()

    def _focus_main_table(self) -> None:
        self.query_one("#main-table", DataTable).focus()
        self._sync_focus_classes()

    def _focus_detail_table(self) -> None:
        self.query_one("#detail-table", DataTable).focus()
        self._sync_focus_classes()

    def _sync_focus_classes(self) -> None:
        focused = self.focused
        for widget_id, widget_type in (
            ("#view-nav", ListView),
            ("#main-table", DataTable),
            ("#detail-table", DataTable),
        ):
            widget = self.query_one(widget_id, widget_type)
            widget.remove_class("pane-focus")
            if focused is widget:
                widget.add_class("pane-focus")


class DBusLensLoaderApp(App[AnalysisReport | Exception | None]):
    CSS = """
    Screen {
        layout: vertical;
        background: #080a0f;
        color: #d8f3dc;
    }

    #loading-view {
        height: 1fr;
        align: center middle;
    }

    #loading-card {
        width: 72;
        padding: 1 2;
        border: round #6ee7b7;
        background: #0b1017;
    }

    #loading-title {
        color: #60a5fa;
        text-style: bold;
        margin-bottom: 1;
    }

    #loading-status {
        color: #e8eef7;
        margin-bottom: 1;
    }

    #loading-detail {
        color: #9fb3c8;
        margin-top: 1;
    }

    ProgressBar {
        width: 1fr;
        margin: 1 0 0 0;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, input_path: str) -> None:
        super().__init__()
        self.input_path = Path(input_path)

    def compose(self) -> ComposeResult:
        with Vertical(id="loading-view"):
            with Vertical(id="loading-card"):
                yield Static("DBusLens report", id="loading-title")
                yield Static("Opening capture...", id="loading-status")
                yield ProgressBar(total=100, show_eta=False, id="loading-bar")
                yield Static(str(self.input_path), id="loading-detail")

    def on_mount(self) -> None:
        threading.Thread(target=self._load_in_background, daemon=True).start()

    def _load_in_background(self) -> None:
        try:
            report = load_report(
                self.input_path,
                progress_callback=lambda update: self.call_from_thread(
                    self._apply_progress,
                    update,
                ),
            )
        except Exception as exc:
            self.call_from_thread(self.exit, exc)
            return
        self.call_from_thread(self.exit, report)

    def _apply_progress(self, update: LoadingUpdate) -> None:
        self.query_one("#loading-status", Static).update(
            f"{update.stage}... {update.percentage}%"
        )
        self.query_one("#loading-detail", Static).update(
            f"{self.input_path}  {update.current}/{update.total}"
        )
        self.query_one("#loading-bar", ProgressBar).update(progress=update.percentage)


def run_browser(report: AnalysisReport) -> None:
    DBusLensReportApp(report).run()


def run_report(input_path: Path) -> None:
    result = DBusLensLoaderApp(str(input_path)).run()
    if isinstance(result, Exception):
        raise result
    if result is None:
        return
    run_browser(result)

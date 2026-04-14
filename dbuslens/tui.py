from __future__ import annotations

from textual.app import App, ComposeResult, ScreenStackError
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Label, ListItem, ListView, Static

from dbuslens.models import AnalysisReport
from dbuslens.report_app import ReportAppState, detail_lines, main_columns, main_rows


class DBusLensReportApp(App[None]):
    BINDINGS = [
        ("left", "show_outbound", "Outbound"),
        ("right", "show_inbound", "Inbound"),
        ("tab", "focus_next_pane", "Next Pane"),
        ("shift+tab", "focus_previous_pane", "Prev Pane"),
        ("q", "quit", "Quit"),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
    }

    #view-nav, #main-table, #detail-pane {
        border: round $surface;
    }

    #view-nav {
        width: 24;
    }

    #content {
        height: 1fr;
    }

    #main-table {
        height: 1fr;
    }

    #detail-pane {
        height: 12;
        padding: 0 1;
    }

    .pane-focus {
        border: round $accent;
    }
    """

    def __init__(self, report: AnalysisReport) -> None:
        super().__init__()
        self.report = report
        self.state = ReportAppState(report)
        self._detail_text = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield ListView(
                ListItem(Label("Outbound Top")),
                ListItem(Label("Inbound Top")),
                id="view-nav",
            )
            with Vertical(id="content"):
                yield DataTable(id="main-table")
                yield Static(id="detail-pane")
        yield Footer()

    def on_mount(self) -> None:
        self._populate_navigation()
        self._populate_main_table()
        self.refresh_detail()
        self._focus_main_table()

    def _populate_navigation(self) -> None:
        nav = self.query_one("#view-nav", ListView)
        nav.index = 0 if self.state.active_view == "outbound" else 1

    def _populate_main_table(self) -> None:
        table = self.query_one("#main-table", DataTable)
        table.cursor_type = "row"
        columns = main_columns(self.state)
        if table.columns:
            table.clear(columns=True)
        table.add_columns(*columns)
        for row in main_rows(self.state):
            table.add_row(*row)
        if table.row_count:
            table.move_cursor(row=min(self.state.selected_index, table.row_count - 1), animate=False)

    def _populate_detail_pane(self) -> None:
        detail = self.query_one("#detail-pane", Static)
        detail.update(self._detail_text)

    def current_detail_text(self) -> str:
        return self._detail_text

    def sync_detail(self) -> None:
        self.refresh_detail()

    def refresh_detail(self) -> None:
        self._detail_text = "\n".join(detail_lines(self.state))
        if self._has_screen():
            self._populate_detail_pane()

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
        self._focus_navigation()

    def action_focus_previous_pane(self) -> None:
        focused = self.focused
        if focused and focused.id == "main-table":
            self._focus_navigation()
            return
        self._focus_main_table()

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

    def _sync_focus_classes(self) -> None:
        focused = self.focused
        for widget_id, widget_type in (("#view-nav", ListView), ("#main-table", DataTable)):
            widget = self.query_one(widget_id, widget_type)
            widget.remove_class("pane-focus")
            if focused is widget:
                widget.add_class("pane-focus")

    def _has_screen(self) -> bool:
        try:
            self.screen
        except ScreenStackError:
            return False
        return True


def run_browser(report: AnalysisReport) -> None:
    DBusLensReportApp(report).run()

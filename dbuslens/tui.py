from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Label, ListItem, ListView, Static

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
        ("left", "show_outbound", "Outbound"),
        ("right", "show_inbound", "Inbound"),
        ("tab", "focus_next_pane", "Next Pane"),
        ("shift+tab", "focus_previous_pane", "Prev Pane"),
        ("enter", "focus_detail_pane", "Detail Pane"),
        ("q", "quit", "Quit"),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
    }

    #report-meta {
        dock: top;
        padding: 0 1;
        color: $text-muted;
    }

    #view-nav, #main-table, #detail-pane, #detail-table {
        border: round $surface;
    }

    #view-nav {
        width: 24;
    }

    #main-table {
        height: 1fr;
        width: 3fr;
    }

    #detail-column {
        width: 2fr;
        min-width: 36;
    }

    #detail-pane {
        height: 8;
        padding: 0 1;
    }

    #detail-table {
        height: 1fr;
    }

    .pane-focus {
        border: round $accent;
    }
    """

    def __init__(self, report: AnalysisReport) -> None:
        super().__init__()
        self.report = report
        self.state = ReportAppState(report)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="report-meta")
        with Horizontal(id="body"):
            yield ListView(
                ListItem(Label("Outbound Top")),
                ListItem(Label("Inbound Top")),
                id="view-nav",
            )
            yield DataTable(id="main-table")
            with Vertical(id="detail-column"):
                yield Static(id="detail-pane")
                yield DataTable(id="detail-table")
        yield Footer()

    def on_mount(self) -> None:
        self._populate_report_meta()
        self._populate_navigation()
        self._populate_main_table()
        self.refresh_detail()
        self._focus_main_table()

    def _populate_report_meta(self) -> None:
        self.query_one("#report-meta", Static).update(metadata_text(self.report))

    def _populate_navigation(self) -> None:
        nav = self.query_one("#view-nav", ListView)
        nav.index = 0 if self.state.active_view == "outbound" else 1

    def _populate_main_table(self) -> None:
        table = self.query_one("#main-table", DataTable)
        table.cursor_type = "row"
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
        table.cursor_type = "row"
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


def run_browser(report: AnalysisReport) -> None:
    DBusLensReportApp(report).run()

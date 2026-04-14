from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Label, ListItem, ListView, Static

from dbuslens.models import AnalysisReport
from dbuslens.report_app import ReportAppState, detail_lines, main_columns, main_rows


class DBusLensReportApp(App[None]):
    BINDINGS = [("q", "quit", "Quit"), ("tab", "focus_next", "Next Pane")]

    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
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
    """

    def __init__(self, report: AnalysisReport) -> None:
        super().__init__()
        self.report = report
        self.state = ReportAppState(report)

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
        self._populate_detail_pane()

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

    def _populate_detail_pane(self) -> None:
        detail = self.query_one("#detail-pane", Static)
        detail.update("\n".join(detail_lines(self.state)))


def run_browser(report: AnalysisReport) -> None:
    DBusLensReportApp(report).run()

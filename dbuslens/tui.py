from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Label, ListItem, ListView, Static

from dbuslens.models import AnalysisReport, DetailRow, Row
from dbuslens.report_app import ReportAppState, main_columns


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

    def region_ids(self) -> tuple[str, str, str]:
        return ("view-nav", "main-table", "detail-pane")

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
        for row in self._main_rows():
            table.add_row(*row)

    def _populate_detail_pane(self) -> None:
        detail = self.query_one("#detail-pane", Static)
        current = self.state.current_row
        if current is None:
            detail.update("No detail available.")
            return

        lines = [f"Selected: {current.name}", f"Count: {current.count}"]
        if current.process:
            lines.append(f"Process: {current.process}")
        if current.children:
            child = current.children[0]
            lines.append(f"First detail: {self._detail_summary(child)}")
        else:
            lines.append("No child entries.")
        detail.update("\n".join(lines))

    def _main_rows(self) -> list[tuple[str, ...]]:
        rows = self._current_rows()
        if self.state.active_view == "outbound":
            return [
                (str(row.count), row.name, row.process or "-")
                for row in rows
            ]
        return [(str(row.count), row.name) for row in rows]

    def _current_rows(self) -> list[Row]:
        return (
            self.report.outbound_rows
            if self.state.active_view == "outbound"
            else self.report.inbound_rows
        )

    def _detail_summary(self, row: DetailRow) -> str:
        if row.process:
            return f"{row.name} ({row.process}) x{row.count}"
        return f"{row.name} x{row.count}"


def run_browser(report: AnalysisReport) -> None:
    DBusLensReportApp(report).run()

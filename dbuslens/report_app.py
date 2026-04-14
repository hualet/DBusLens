from __future__ import annotations

from dataclasses import dataclass

from dbuslens.models import AnalysisReport, DetailRow, Row


@dataclass
class ReportAppState:
    report: AnalysisReport
    active_view: str = "outbound"
    selected_index: int = 0

    def switch_view(self) -> None:
        self.active_view = "inbound" if self.active_view == "outbound" else "outbound"
        self.selected_index = 0

    @property
    def current_row(self) -> Row | None:
        rows = (
            self.report.outbound_rows
            if self.active_view == "outbound"
            else self.report.inbound_rows
        )
        if self.selected_index < 0 or self.selected_index >= len(rows):
            return None
        return rows[self.selected_index]


def main_columns(state: ReportAppState) -> tuple[str, ...]:
    return ("Count", "Service", "Process") if state.active_view == "outbound" else ("Count", "Operation")


def current_rows(state: ReportAppState) -> list[Row]:
    return (
        state.report.outbound_rows
        if state.active_view == "outbound"
        else state.report.inbound_rows
    )


def main_rows(state: ReportAppState) -> list[tuple[str, ...]]:
    rows = current_rows(state)
    if state.active_view == "outbound":
        return [(str(row.count), row.name, row.process or "-") for row in rows]
    return [(str(row.count), row.name) for row in rows]


def detail_lines(state: ReportAppState) -> list[str]:
    current = state.current_row
    if current is None:
        return ["No detail available."]

    lines = [f"Selected: {current.name}", f"Count: {current.count}"]
    if current.process:
        lines.append(f"Process: {current.process}")
    if current.children:
        lines.append(f"First detail: {_detail_summary(current.children[0])}")
    else:
        lines.append("No child entries.")
    return lines


def _detail_summary(row: DetailRow) -> str:
    if row.process:
        return f"{row.name} ({row.process}) x{row.count}"
    return f"{row.name} x{row.count}"

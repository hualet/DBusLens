from __future__ import annotations

from dataclasses import dataclass

from dbuslens.models import AnalysisReport, Row


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
        if not rows:
            return None
        return rows[self.selected_index]


def main_columns(state: ReportAppState) -> tuple[str, ...]:
    return ("Count", "Service", "Process") if state.active_view == "outbound" else ("Count", "Operation")

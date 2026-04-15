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

    def set_view(self, view: str) -> None:
        self.active_view = view
        self.selected_index = 0

    @property
    def current_row(self) -> Row | None:
        rows = (
            self.report.outbound_rows
            if self.active_view == "outbound"
            else self.report.inbound_rows
            if self.active_view == "inbound"
            else self.report.error_rows
        )
        if self.selected_index < 0 or self.selected_index >= len(rows):
            return None
        return rows[self.selected_index]


def main_columns(state: ReportAppState) -> tuple[str, ...]:
    if state.active_view == "outbound":
        return ("Count", "Service", "Process")
    if state.active_view == "inbound":
        return ("Count", "Operation")
    return ("Count", "Error")


def current_rows(state: ReportAppState) -> list[Row]:
    return (
        state.report.outbound_rows
        if state.active_view == "outbound"
        else state.report.inbound_rows
        if state.active_view == "inbound"
        else state.report.error_rows
    )


def main_rows(state: ReportAppState) -> list[tuple[str, ...]]:
    rows = current_rows(state)
    if state.active_view == "outbound":
        return [
            (str(row.count), row.name, row.process.display_name if row.process else "-")
            for row in rows
        ]
    if state.active_view == "errors":
        return [(str(row.count), row.name) for row in rows]
    return [(str(row.count), row.name) for row in rows]


def main_column_widths(state: ReportAppState) -> tuple[int | None, ...]:
    rows = main_rows(state)
    if state.active_view == "outbound":
        return (
            8,
            _width_for_column(("Service",), rows, 1, minimum=18, maximum=48),
            _width_for_column(("Process",), rows, 2, minimum=12, maximum=96),
        )
    if state.active_view == "errors":
        return (
            8,
            _width_for_column(("Error",), rows, 1, minimum=28, maximum=72),
        )
    return (
        8,
        _width_for_column(("Operation",), rows, 1, minimum=24, maximum=72),
    )


def detail_lines(state: ReportAppState) -> list[str]:
    current = state.current_row
    if current is None:
        return ["No detail available."]

    lines = [f"Selected: {current.name}", f"Count: {current.count}"]
    if current.process:
        lines.append(f"Process: {current.process.display_name}")
        if current.process.pid is not None:
            lines.append(f"PID: {current.process.pid}")
    if not current.children:
        lines.append("No child entries.")
    else:
        lines.append(f"Details: {len(current.children)} row(s)")
    return lines


def detail_columns(state: ReportAppState) -> tuple[str, ...]:
    if state.active_view == "outbound":
        return ("Count", "Operation")
    if state.active_view == "inbound":
        return ("Count", "Service", "Process")
    return ("Count", "Service", "Process", "Operation")


def detail_rows(state: ReportAppState) -> list[tuple[str, ...]]:
    current = state.current_row
    if current is None:
        return []
    if state.active_view == "outbound":
        return [(str(row.count), row.name) for row in current.children]
    if state.active_view == "errors":
        return [
            (
                str(row.count),
                row.name,
                row.process.display_name if row.process else "-",
                row.secondary or "<unknown>",
            )
            for row in current.children
        ]
    return [
        (str(row.count), row.name, row.process.display_name if row.process else "-")
        for row in current.children
    ]


def detail_column_widths(state: ReportAppState) -> tuple[int | None, ...]:
    rows = detail_rows(state)
    if state.active_view == "outbound":
        return (
            8,
            _width_for_column(("Operation",), rows, 1, minimum=24, maximum=96),
        )
    if state.active_view == "errors":
        return (
            8,
            _width_for_column(("Service",), rows, 1, minimum=18, maximum=48),
            _width_for_column(("Process",), rows, 2, minimum=12, maximum=96),
            _width_for_column(("Operation",), rows, 3, minimum=24, maximum=96),
        )
    return (
        8,
        _width_for_column(("Service",), rows, 1, minimum=18, maximum=48),
        _width_for_column(("Process",), rows, 2, minimum=12, maximum=96),
    )


def metadata_text(report: AnalysisReport) -> str:
    return (
        f"file={report.source_path}  "
        f"events={report.total_events}  "
        f"actionable={report.actionable_events}  "
        f"skipped={report.skipped_blocks}"
    )


def _width_for_column(
    headers: tuple[str, ...],
    rows: list[tuple[str, ...]],
    index: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    candidates = [len(header) for header in headers]
    candidates.extend(len(row[index]) for row in rows if len(row) > index)
    return min(max(max(candidates, default=minimum) + 2, minimum), maximum)

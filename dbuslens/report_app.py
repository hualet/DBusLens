from __future__ import annotations

from dataclasses import dataclass

from dbuslens.models import AnalysisReport, CaptureNameInfo, ErrorSummary, Row


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
    def current_row(self) -> Row | ErrorSummary | None:
        rows = (
            self.report.outbound_rows
            if self.active_view == "outbound"
            else self.report.inbound_rows
            if self.active_view == "inbound"
            else self.report.error_summaries
        )
        if self.selected_index < 0 or self.selected_index >= len(rows):
            return None
        return rows[self.selected_index]


def main_columns(state: ReportAppState) -> tuple[str, ...]:
    if state.active_view == "outbound":
        return ("Count", "Service", "Process")
    if state.active_view == "inbound":
        return ("Count", "Operation")
    return ("Count", "Error", "Target", "Operation")


def current_rows(state: ReportAppState) -> list[Row | ErrorSummary]:
    return (
        state.report.outbound_rows
        if state.active_view == "outbound"
        else state.report.inbound_rows
        if state.active_view == "inbound"
        else state.report.error_summaries
    )


def main_rows(state: ReportAppState) -> list[tuple[str, ...]]:
    rows = current_rows(state)
    if state.active_view == "outbound":
        return [
            (str(row.count), row.name, row.process.display_name if row.process else "-")
            for row in rows
        ]
    if state.active_view == "errors":
        return [
            (str(row.count), row.error_name, row.target, row.operation)
            for row in rows
        ]
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
            _width_for_column(("Target",), rows, 2, minimum=18, maximum=48),
            _width_for_column(("Operation",), rows, 3, minimum=24, maximum=96),
        )
    return (
        8,
        _width_for_column(("Operation",), rows, 1, minimum=24, maximum=72),
    )


def detail_lines(state: ReportAppState) -> list[str]:
    current = state.current_row
    if current is None:
        return ["No detail available."]

    if state.active_view == "errors" and isinstance(current, ErrorSummary):
        return [
            f"Selected: {current.error_name}",
            f"Target: {current.target}",
            f"Operation: {current.operation}",
            f"Count: {current.count}",
            f"First seen: {_format_timestamp(current.first_seen)}",
            f"Last seen: {_format_timestamp(current.last_seen)}",
            f"Average latency: {_format_latency(current.average_latency_ms)}",
            f"Retries detected: {current.retry_count}",
            f"Unique callers: {current.unique_callers}",
            f"Target owner at capture time: {_capture_owner_text(current.target_process)}",
        ]

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
    return ("Time", "Sender", "Destination", "Member", "Args", "Latency", "Notes")


def detail_rows(state: ReportAppState) -> list[tuple[str, ...]]:
    current = state.current_row
    if current is None:
        return []
    if state.active_view == "outbound":
        return [(str(row.count), row.name) for row in current.children]
    if state.active_view == "errors":
        return [
            (
                _format_timestamp(row.timestamp),
                row.caller,
                row.destination,
                row.member,
                row.args_preview,
                row.latency_ms,
                row.notes or "-",
            )
            for row in current.details
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
            _width_for_column(("Time",), rows, 0, minimum=10, maximum=14),
            _width_for_column(("Sender",), rows, 1, minimum=14, maximum=32),
            _width_for_column(("Destination",), rows, 2, minimum=18, maximum=36),
            _width_for_column(("Member",), rows, 3, minimum=12, maximum=28),
            _width_for_column(("Args",), rows, 4, minimum=12, maximum=32),
            _width_for_column(("Latency",), rows, 5, minimum=10, maximum=16),
            _width_for_column(("Notes",), rows, 6, minimum=12, maximum=36),
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


def _capture_owner_text(info: CaptureNameInfo | None) -> str:
    if info is None:
        return "-"
    owner = info.owner or info.name
    if info.pid is None:
        return owner
    return f"{owner} [{info.pid}]"


def _format_timestamp(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}s"


def _format_latency(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f} ms"

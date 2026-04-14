from __future__ import annotations

import curses

from dbuslens.models import AnalysisReport, DetailRow, Row


class BrowserState:
    def __init__(self, report: AnalysisReport) -> None:
        self.report = report
        self.active_view = "outbound"
        self.selected_index = 0
        self.detail_row: Row | None = None
        self.detail_index = 0

    def switch_view(self) -> None:
        self.active_view = "inbound" if self.active_view == "outbound" else "outbound"
        self.selected_index = 0
        self.detail_row = None
        self.detail_index = 0

    def move(self, delta: int) -> None:
        rows = self.current_rows
        if not rows:
            self.selected_index = 0
            return
        if self.detail_row is not None:
            max_index = max(len(self.detail_row.children) - 1, 0)
            self.detail_index = min(max(self.detail_index + delta, 0), max_index)
            return
        max_index = max(len(rows) - 1, 0)
        self.selected_index = min(max(self.selected_index + delta, 0), max_index)

    def enter(self) -> None:
        rows = self.current_rows
        if not rows:
            return
        self.detail_row = rows[self.selected_index]
        self.detail_index = 0

    def back(self) -> None:
        self.detail_row = None
        self.detail_index = 0

    @property
    def current_rows(self) -> list[Row]:
        return (
            self.report.outbound_rows
            if self.active_view == "outbound"
            else self.report.inbound_rows
        )


def run_browser(report: AnalysisReport) -> None:
    curses.wrapper(lambda stdscr: _render_loop(stdscr, BrowserState(report)))


def _render_loop(stdscr: curses.window, state: BrowserState) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    while True:
        _draw(stdscr, state)
        key = stdscr.getch()
        if key in {ord("q"), ord("Q")}:
            return
        if key in {ord("j"), curses.KEY_DOWN}:
            state.move(1)
        elif key in {ord("k"), curses.KEY_UP}:
            state.move(-1)
        elif key == 9:
            state.switch_view()
        elif key in {10, 13, curses.KEY_ENTER} and state.detail_row is None:
            state.enter()
        elif key in {27, ord("b"), ord("B")} and state.detail_row is not None:
            state.back()


def _draw(stdscr: curses.window, state: BrowserState) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    header = (
        f"DBusLens  file={state.report.source_path}  "
        f"events={state.report.total_events}  actionable={state.report.actionable_events}  "
        f"skipped={state.report.skipped_blocks}"
    )
    stdscr.addnstr(0, 0, header, width - 1, curses.A_BOLD)

    if state.detail_row is None:
        title = "Outbound Top" if state.active_view == "outbound" else "Inbound Top"
        stdscr.addnstr(2, 0, title, width - 1, curses.A_UNDERLINE)
        rows = state.current_rows
        if not rows:
            stdscr.addnstr(4, 0, "No actionable messages found.", width - 1)
        else:
            table_header, table_rows = build_table(state, width)
            stdscr.addnstr(4, 0, table_header, width - 1, curses.A_BOLD)
            _draw_list(
                stdscr,
                start_y=5,
                width=width,
                height=height - 7,
                rows=table_rows,
                selected_index=state.selected_index,
            )
    else:
        title = (
            f"Details for {state.detail_row.name}"
            if state.active_view == "outbound"
            else f"Callers for {state.detail_row.name}"
        )
        stdscr.addnstr(2, 0, title, width - 1, curses.A_UNDERLINE)
        if not state.detail_row.children:
            stdscr.addnstr(4, 0, "No child entries.", width - 1)
        else:
            table_header, table_rows = build_table(state, width)
            stdscr.addnstr(4, 0, table_header, width - 1, curses.A_BOLD)
            _draw_list(
                stdscr,
                start_y=5,
                width=width,
                height=height - 7,
                rows=table_rows,
                selected_index=state.detail_index,
            )

    footer = "j/k or arrows move | Tab switch | Enter details | b/Esc back | q quit"
    stdscr.addnstr(height - 1, 0, footer, width - 1, curses.A_REVERSE)
    stdscr.refresh()


def _draw_list(
    stdscr: curses.window,
    *,
    start_y: int,
    width: int,
    height: int,
    rows: list[str],
    selected_index: int,
) -> None:
    if height <= 0:
        return
    top = 0
    if selected_index >= height:
        top = selected_index - height + 1
    visible_rows = rows[top : top + height]
    for offset, text in enumerate(visible_rows):
        y = start_y + offset
        if y >= start_y + height:
            break
        attr = curses.A_REVERSE if top + offset == selected_index else curses.A_NORMAL
        stdscr.addnstr(y, 0, text, width - 1, attr)


def build_table(state: BrowserState, width: int) -> tuple[str, list[str]]:
    if state.detail_row is None:
        if state.active_view == "outbound":
            return _format_service_rows(state.current_rows, width)
        return _format_operation_rows(state.current_rows, width)

    if state.active_view == "outbound":
        return _format_detail_rows(state.detail_row.children, width, show_process=False)
    return _format_detail_rows(state.detail_row.children, width, show_process=True)


def _format_service_rows(rows: list[Row], width: int) -> tuple[str, list[str]]:
    count_w = 8
    service_w = max(20, min(36, width - count_w - 18))
    process_w = max(10, width - count_w - service_w - 4)
    header = f"{'COUNT':>{count_w}}  {_trim('SERVICE', service_w):<{service_w}}  {_trim('PROCESS', process_w):<{process_w}}"
    body = [
        f"{row.count:>{count_w}}  {_trim(row.name, service_w):<{service_w}}  {_trim(row.process or '-', process_w):<{process_w}}"
        for row in rows
    ]
    return header, body


def _format_operation_rows(rows: list[Row], width: int) -> tuple[str, list[str]]:
    count_w = 8
    operation_w = max(20, width - count_w - 2)
    header = f"{'COUNT':>{count_w}}  {_trim('OPERATION', operation_w):<{operation_w}}"
    body = [
        f"{row.count:>{count_w}}  {_trim(row.name, operation_w):<{operation_w}}"
        for row in rows
    ]
    return header, body


def _format_detail_rows(
    rows: list[DetailRow],
    width: int,
    *,
    show_process: bool,
) -> tuple[str, list[str]]:
    if not show_process:
        count_w = 8
        name_w = max(20, width - count_w - 2)
        header = f"{'COUNT':>{count_w}}  {_trim('OPERATION', name_w):<{name_w}}"
        body = [
            f"{row.count:>{count_w}}  {_trim(row.name, name_w):<{name_w}}"
            for row in rows
        ]
        return header, body

    count_w = 8
    service_w = max(20, min(36, width - count_w - 18))
    process_w = max(10, width - count_w - service_w - 4)
    header = f"{'COUNT':>{count_w}}  {_trim('SERVICE', service_w):<{service_w}}  {_trim('PROCESS', process_w):<{process_w}}"
    body = [
        f"{row.count:>{count_w}}  {_trim(row.name, service_w):<{service_w}}  {_trim(row.process or '-', process_w):<{process_w}}"
        for row in rows
    ]
    return header, body


def _trim(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"

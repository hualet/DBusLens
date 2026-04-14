from __future__ import annotations

from collections import Counter, defaultdict
from typing import Callable

from dbuslens.models import AnalysisReport, DetailRow, Event, ProcessInfo, Row
from dbuslens.processes import resolve_process_name


ACTIONABLE_TYPES = {"method_call", "signal"}


def build_report(
    events: list[Event],
    *,
    source_path: str = "<memory>",
    skipped_blocks: int = 0,
    resolve_process: Callable[[str], ProcessInfo | None] = resolve_process_name,
) -> AnalysisReport:
    outbound_totals: Counter[str] = Counter()
    inbound_totals: Counter[str] = Counter()
    outbound_children: dict[str, Counter[str]] = defaultdict(Counter)
    inbound_children: dict[str, Counter[str]] = defaultdict(Counter)

    actionable_events = 0
    for event in events:
        if event.message_type not in ACTIONABLE_TYPES:
            continue
        actionable_events += 1
        service_name = event.sender or "<unknown>"
        operation_name = event.operation
        outbound_totals[service_name] += 1
        outbound_children[service_name][operation_name] += 1
        inbound_totals[operation_name] += 1
        inbound_children[operation_name][service_name] += 1

    return AnalysisReport(
        source_path=source_path,
        total_events=len(events),
        actionable_events=actionable_events,
        skipped_blocks=skipped_blocks,
        outbound_rows=_build_rows(outbound_totals, outbound_children, resolve_process),
        inbound_rows=_build_rows(inbound_totals, inbound_children, resolve_process),
    )


def _build_rows(
    totals: Counter[str],
    children: dict[str, Counter[str]],
    resolve_process: Callable[[str], ProcessInfo | None],
) -> list[Row]:
    rows = []
    for name, count in sorted(totals.items(), key=lambda item: (-item[1], item[0])):
        child_rows = sorted(children[name].items(), key=lambda item: (-item[1], item[0]))
        rows.append(
            Row(
                name=name,
                process=resolve_process(name) if _looks_like_service(name) else None,
                count=count,
                children=[
                    DetailRow(
                        name=child_name,
                        process=resolve_process(child_name) if _looks_like_service(child_name) else None,
                        count=child_count,
                    )
                    for child_name, child_count in child_rows
                ],
            )
        )
    return rows


def _looks_like_service(name: str) -> bool:
    return bool(name) and (name.startswith(":") or "." in name or name == "<unknown>")

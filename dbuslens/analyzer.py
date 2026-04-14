from __future__ import annotations

from collections import Counter, defaultdict

from dbuslens.models import AnalysisReport, Event, Row


ACTIONABLE_TYPES = {"method_call", "signal"}


def build_report(
    events: list[Event],
    *,
    source_path: str = "<memory>",
    skipped_blocks: int = 0,
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
        outbound_rows=_build_rows(outbound_totals, outbound_children),
        inbound_rows=_build_rows(inbound_totals, inbound_children),
    )


def _build_rows(
    totals: Counter[str],
    children: dict[str, Counter[str]],
) -> list[Row]:
    rows = []
    for name, count in sorted(totals.items(), key=lambda item: (-item[1], item[0])):
        child_rows = sorted(children[name].items(), key=lambda item: (-item[1], item[0]))
        rows.append(Row(name=name, count=count, children=child_rows))
    return rows

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Callable

from dbuslens.models import (
    AnalysisReport,
    CaptureNameInfo,
    DetailRow,
    ErrorDetail,
    ErrorSummary,
    Event,
    ProcessInfo,
    Row,
)
from dbuslens.processes import resolve_process_name


ACTIONABLE_TYPES = {"method_call", "signal"}
UNKNOWN_ERROR_TARGET = "<unknown-target>"
UNKNOWN_ERROR_CALLER = "<unknown-caller>"
UNKNOWN_OPERATION = "<unknown>"


def build_report(
    events: list[Event],
    *,
    source_path: str = "<memory>",
    skipped_blocks: int = 0,
    snapshot_names: dict[str, object] | None = None,
    resolve_process: Callable[[str], ProcessInfo | None] = resolve_process_name,
    progress_callback: Callable[[int, int], None] | None = None,
) -> AnalysisReport:
    service_name_for = _build_service_name_resolver(events, resolve_process)
    snapshot_index = _build_snapshot_index(snapshot_names)
    outbound_totals: Counter[str] = Counter()
    inbound_totals: Counter[str] = Counter()
    error_totals: Counter[str] = Counter()
    outbound_children: dict[str, Counter[str]] = defaultdict(Counter)
    inbound_children: dict[str, Counter[str]] = defaultdict(Counter)
    error_children: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    call_index = _build_call_index(events)

    actionable_events = 0
    total_events = len(events)
    for index, event in enumerate(events, start=1):
        if event.message_type == "error":
            error_name = event.error_name or "<unknown>"
            original = None
            if event.reply_serial is not None:
                original = call_index.get((event.destination, event.sender, event.reply_serial))
            target_name, _, operation_name = _build_error_identity(event, original)
            error_totals[error_name] += 1
            error_children[error_name][(target_name, operation_name)] += 1
            if progress_callback:
                progress_callback(index, total_events)
            continue

        if event.message_type not in ACTIONABLE_TYPES:
            if progress_callback:
                progress_callback(index, total_events)
            continue
        actionable_events += 1
        service_name = service_name_for(event.sender or "<unknown>")
        operation_name = event.operation
        outbound_totals[service_name] += 1
        outbound_children[service_name][operation_name] += 1
        inbound_totals[operation_name] += 1
        inbound_children[operation_name][service_name] += 1
        if progress_callback:
            progress_callback(index, total_events)

    if progress_callback and total_events == 0:
        progress_callback(1, 1)

    error_summaries = _build_error_summaries(
        events,
        call_index,
        snapshot_index,
    )

    return AnalysisReport(
        source_path=source_path,
        total_events=len(events),
        actionable_events=actionable_events,
        skipped_blocks=skipped_blocks,
        outbound_rows=_build_rows(outbound_totals, outbound_children, resolve_process),
        inbound_rows=_build_rows(inbound_totals, inbound_children, resolve_process),
        error_rows=_build_error_rows(error_totals, error_children, resolve_process),
        error_summaries=error_summaries,
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
                        process=(
                            resolve_process(child_name)
                            if _looks_like_service(child_name)
                            else None
                        ),
                        count=child_count,
                    )
                    for child_name, child_count in child_rows
                ],
            )
        )
    return rows


def _build_service_name_resolver(
    events: list[Event],
    resolve_process: Callable[[str], ProcessInfo | None],
) -> Callable[[str], str]:
    process_cache: dict[str, ProcessInfo | None] = {}

    def cached_process(name: str) -> ProcessInfo | None:
        if name not in process_cache:
            process_cache[name] = resolve_process(name) if _looks_like_service(name) else None
        return process_cache[name]

    names = {
        name
        for event in events
        for name in (event.sender, event.destination)
        if name and _looks_like_service(name)
    }
    names.add("<unknown>")

    names_by_pid: dict[int, set[str]] = defaultdict(set)
    for name in names:
        process = cached_process(name)
        if process and process.pid is not None:
            names_by_pid[process.pid].add(name)

    preferred_by_pid = {
        pid: min(
            candidates,
            key=lambda name: (name.startswith(":"), name),
        )
        for pid, candidates in names_by_pid.items()
    }

    def resolve_name(name: str) -> str:
        process = cached_process(name)
        if process is None or process.pid is None:
            return name
        return preferred_by_pid.get(process.pid, name)

    return resolve_name


def _looks_like_service(name: str) -> bool:
    return bool(name) and (name.startswith(":") or "." in name or name == "<unknown>")


def _build_call_index(events: list[Event]) -> dict[tuple[str | None, str | None, int], Event]:
    call_index: dict[tuple[str | None, str | None, int], Event] = {}
    for event in events:
        if event.message_type == "method_call" and event.serial is not None:
            call_index[(event.sender, event.destination, event.serial)] = event
    return call_index


def _build_snapshot_index(
    snapshot_names: dict[str, object] | None,
) -> dict[str, CaptureNameInfo]:
    if not isinstance(snapshot_names, dict):
        return {}

    raw_entries = snapshot_names.get("names")
    if not isinstance(raw_entries, list):
        return {}

    snapshot_index: dict[str, CaptureNameInfo] = {}
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        info = _capture_name_info(entry)
        if info is None:
            continue
        snapshot_index[info.name] = info
        if info.owner:
            existing = snapshot_index.get(info.owner)
            if existing is None or _prefer_snapshot_alias(info, existing):
                snapshot_index[info.owner] = info
    return snapshot_index


def _capture_name_info(entry: dict[str, object]) -> CaptureNameInfo | None:
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        return None

    owner = entry.get("owner")
    if owner is not None and not isinstance(owner, str):
        owner = None

    pid = entry.get("pid")
    if pid is not None and not isinstance(pid, int):
        pid = None

    uid = entry.get("uid")
    if uid is not None and not isinstance(uid, int):
        uid = None

    cmdline = entry.get("cmdline")
    if cmdline is not None and not isinstance(cmdline, list):
        cmdline = None
    elif isinstance(cmdline, list):
        cmdline = [part for part in cmdline if isinstance(part, str)] or None

    return CaptureNameInfo(
        name=name,
        owner=owner,
        pid=pid,
        uid=uid,
        cmdline=cmdline,
    )


def _build_error_rows(
    totals: Counter[str],
    children: dict[str, Counter[tuple[str, str]]],
    resolve_process: Callable[[str], ProcessInfo | None],
) -> list[Row]:
    rows = []
    for name, count in sorted(totals.items(), key=lambda item: (-item[1], item[0])):
        child_rows = sorted(
            children[name].items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        )
        rows.append(
            Row(
                name=name,
                process=None,
                count=count,
                children=[
                    DetailRow(
                        name=target_name,
                        process=(
                            resolve_process(target_name)
                            if _looks_like_service(target_name)
                            else None
                        ),
                        count=child_count,
                        secondary=operation_name,
                    )
                    for (target_name, operation_name), child_count in child_rows
                ],
            )
        )
    return rows


def _build_error_summaries(
    events: list[Event],
    call_index: dict[tuple[str | None, str | None, int], Event],
    snapshot_index: dict[str, CaptureNameInfo],
) -> list[ErrorSummary]:
    buckets: dict[tuple[str, str, str], dict[str, object]] = {}

    for event in events:
        if event.message_type != "error":
            continue

        original = None
        if event.reply_serial is not None:
            original = call_index.get((event.destination, event.sender, event.reply_serial))

        target_source, caller_source, operation = _build_error_identity(event, original)
        error_name = event.error_name or "<unknown>"
        key = (error_name, target_source, operation)

        bucket = buckets.setdefault(
            key,
            {
                "count": 0,
                "first_seen": None,
                "last_seen": None,
                "latency_total_ms": 0.0,
                "latency_samples": 0,
                "callers": defaultdict(
                    lambda: {
                        "count": 0,
                        "latency_total_ms": 0.0,
                        "latency_samples": 0,
                        "failure_timestamps": [],
                    }
                ),
            },
        )

        bucket["count"] = int(bucket["count"]) + 1

        if event.timestamp is not None:
            first_seen = bucket["first_seen"]
            if first_seen is None or event.timestamp < first_seen:
                bucket["first_seen"] = event.timestamp
            last_seen = bucket["last_seen"]
            if last_seen is None or event.timestamp > last_seen:
                bucket["last_seen"] = event.timestamp

        if original and original.timestamp is not None and event.timestamp is not None:
            latency_ms = (event.timestamp - original.timestamp) * 1000
            bucket["latency_total_ms"] = float(bucket["latency_total_ms"]) + latency_ms
            bucket["latency_samples"] = int(bucket["latency_samples"]) + 1
        else:
            latency_ms = None

        caller_bucket = bucket["callers"][caller_source]
        caller_bucket["count"] = int(caller_bucket["count"]) + 1
        if event.timestamp is not None:
            caller_bucket["failure_timestamps"].append(event.timestamp)
        if latency_ms is not None:
            caller_bucket["latency_total_ms"] = float(caller_bucket["latency_total_ms"]) + latency_ms
            caller_bucket["latency_samples"] = int(caller_bucket["latency_samples"]) + 1

    summaries: list[ErrorSummary] = []
    for (error_name, target_source, operation), bucket in sorted(
        buckets.items(),
        key=lambda item: (-int(item[1]["count"]), item[0][0], item[0][1], item[0][2]),
    ):
        callers = bucket["callers"]
        target_process = _snapshot_info_for(target_source, snapshot_index)
        details: list[ErrorDetail] = []
        retry_count = 0
        for caller, caller_bucket in sorted(
            callers.items(),
            key=lambda item: (-int(item[1]["count"]), item[0]),
        ):
            failure_timestamps = sorted(caller_bucket["failure_timestamps"])
            retries = _count_retries(failure_timestamps)
            retry_count += retries
            avg_latency_ms = _average_latency_ms(
                float(caller_bucket["latency_total_ms"]),
                int(caller_bucket["latency_samples"]),
            )
            details.append(
                ErrorDetail(
                    caller=caller,
                    caller_process=_snapshot_info_for(caller, snapshot_index),
                    target_process=target_process,
                    latency_ms=_format_latency_ms(avg_latency_ms),
                    notes="retried within 5s" if retries else "",
                    count=int(caller_bucket["count"]),
                )
            )

        average_latency_ms = _average_latency_ms(
            float(bucket["latency_total_ms"]),
            int(bucket["latency_samples"]),
        )
        summaries.append(
            ErrorSummary(
                error_name=error_name,
                target=target_source,
                operation=operation,
                count=int(bucket["count"]),
                first_seen=bucket["first_seen"],
                last_seen=bucket["last_seen"],
                average_latency_ms=average_latency_ms,
                retry_count=retry_count,
                unique_callers=len(callers),
                target_process=target_process,
                details=details,
            )
        )

    return summaries


def _build_error_identity(event: Event, original: Event | None) -> tuple[str, str, str]:
    if original is not None:
        target_name = original.destination or event.sender or UNKNOWN_ERROR_TARGET
        caller_name = original.sender or event.destination or UNKNOWN_ERROR_CALLER
        operation = original.operation if original.operation != "<unknown>" else UNKNOWN_OPERATION
        return target_name, caller_name, operation

    target_name = event.sender or UNKNOWN_ERROR_TARGET
    caller_name = event.destination or UNKNOWN_ERROR_CALLER
    operation = UNKNOWN_OPERATION
    return target_name, caller_name, operation


def _snapshot_info_for(
    name: str,
    snapshot_index: dict[str, CaptureNameInfo],
) -> CaptureNameInfo | None:
    return snapshot_index.get(name)


def _prefer_snapshot_alias(candidate: CaptureNameInfo, current: CaptureNameInfo) -> bool:
    return _snapshot_alias_key(candidate) < _snapshot_alias_key(current)


def _snapshot_alias_key(info: CaptureNameInfo) -> tuple[bool, str]:
    return (info.name.startswith(":"), info.name)


def _average_latency_ms(total_latency_ms: float, samples: int) -> float | None:
    if samples == 0:
        return None
    return round(total_latency_ms / samples, 1)


def _count_retries(timestamps: list[float]) -> int:
    retries = 0
    previous = None
    for timestamp in sorted(timestamps):
        if previous is not None and timestamp - previous <= 5.0:
            retries += 1
        previous = timestamp
    return retries


def _format_latency_ms(latency_ms: float | None) -> str:
    if latency_ms is None:
        return "n/a"
    return f"{latency_ms:.1f} ms"

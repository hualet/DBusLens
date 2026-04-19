from __future__ import annotations

from collections import Counter
from pathlib import Path

from dbuslens.bundle import read_bundle
from dbuslens.models import Event
from dbuslens.name_timeline import NameTimelineResolver
from dbuslens.pcap_parser import parse_pcap_bytes


DBUS_DAEMON_NAME = "org.freedesktop.DBus"


def build_dependency_dot(
    events: list[Event],
    *,
    snapshot_names: dict[str, object] | None = None,
    names_timeline: dict[str, object] | None = None,
    raw: bool = False,
    min_count: int | None = None,
) -> str:
    resolver = NameTimelineResolver.from_payload(snapshot_names, names_timeline)
    edge_counts: Counter[tuple[str, str]] = Counter()
    threshold = min_count if min_count is not None else (1 if raw else 2)

    for event in events:
        if event.message_type != "method_call":
            continue
        sender = _plot_name(event.sender, resolver, timestamp=event.timestamp, raw=raw)
        destination = _plot_name(
            event.destination,
            resolver,
            timestamp=event.timestamp,
            raw=raw,
        )
        if not sender or not destination:
            continue
        if not raw and DBUS_DAEMON_NAME in {sender, destination}:
            continue
        edge_counts[(sender, destination)] += 1

    nodes: set[str] = set()
    lines = ["digraph dbus_dependencies {"]
    for (sender, destination), count in sorted(edge_counts.items()):
        if count < threshold:
            continue
        nodes.add(sender)
        nodes.add(destination)

    for node in sorted(nodes):
        lines.append(f'  "{_escape_dot(node)}";')
    for (sender, destination), count in sorted(edge_counts.items()):
        if count < threshold:
            continue
        lines.append(
            f'  "{_escape_dot(sender)}" -> "{_escape_dot(destination)}" [label="{count}"];'
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def build_dependency_dot_from_bundle(
    path: Path,
    *,
    raw: bool = False,
    min_count: int | None = None,
) -> str:
    bundle = read_bundle(path)
    parsed = parse_pcap_bytes(bundle.pcap_bytes)
    return build_dependency_dot(
        parsed.events,
        snapshot_names=bundle.names,
        names_timeline=bundle.names_timeline,
        raw=raw,
        min_count=min_count,
    )


def _plot_name(
    raw_name: str | None,
    resolver: NameTimelineResolver,
    *,
    timestamp: float | None,
    raw: bool,
) -> str | None:
    if not raw_name:
        return None
    if raw:
        return raw_name
    resolved = resolver.resolve_name(raw_name, timestamp=timestamp)
    if raw_name.startswith(":") and resolved.display_name == raw_name:
        return None
    return resolved.display_name


def _escape_dot(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')

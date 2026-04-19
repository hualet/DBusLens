from __future__ import annotations

from collections import Counter
from pathlib import Path
import subprocess

from dbuslens.bundle import read_bundle
from dbuslens.models import Event
from dbuslens.name_timeline import NameTimelineResolver
from dbuslens.pcap_parser import parse_pcap_bytes


DBUS_DAEMON_NAME = "org.freedesktop.DBus"
PLOT_BACKGROUND = "#080a0f"
PLOT_PANEL = "#0b1017"
PLOT_TEXT = "#dcefd9"
PLOT_MUTED = "#9fb3c8"
PLOT_GREEN = "#6ee7b7"
PLOT_BLUE = "#60a5fa"
PLOT_BLUE_DARK = "#173b6c"
PLOT_GOLD = "#fcd34d"


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
    threshold = min_count if min_count is not None else 1

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
    for (sender, destination), count in sorted(edge_counts.items()):
        if count < threshold:
            continue
        nodes.add(sender)
        nodes.add(destination)

    lines = [
        "digraph dbus_dependencies {",
        f'  graph [bgcolor="{PLOT_BACKGROUND}", pad="0.3", nodesep="0.5", ranksep="0.9", splines="true"];',
        (
            f'  node [shape="box", style="rounded,filled", fillcolor="{PLOT_PANEL}", '
            f'color="{PLOT_GREEN}", fontcolor="{PLOT_TEXT}", fontname="DejaVu Sans", '
            'fontsize="11", margin="0.18,0.12", penwidth="1.4"];'
        ),
        (
            f'  edge [color="{PLOT_BLUE}", fontcolor="{PLOT_GOLD}", fontname="DejaVu Sans", '
            'fontsize="10", penwidth="1.6", arrowsize="0.8"];'
        ),
    ]

    for node in sorted(nodes):
        lines.append(f'  "{_escape_dot(node)}";')
    for (sender, destination), count in sorted(edge_counts.items()):
        if count < threshold:
            continue
        lines.append(
            f'  "{_escape_dot(sender)}" -> "{_escape_dot(destination)}" '
            f'[label="{count}", tooltip="{count} calls"];'
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


def render_graphviz_output(dot_source: str, *, output_format: str) -> str:
    try:
        result = subprocess.run(
            ["dot", f"-T{output_format}"],
            input=dot_source.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError as exc:
        raise ValueError("Graphviz 'dot' is required for svg output") from exc
    except subprocess.CalledProcessError as exc:
        stderr_text = exc.stderr.decode("utf-8", "replace").strip()
        if stderr_text:
            raise ValueError(f"Graphviz rendering failed: {stderr_text}") from exc
        raise ValueError("Graphviz rendering failed") from exc
    return result.stdout.decode("utf-8")


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

from __future__ import annotations

import re

from dbuslens.models import Event, ParseResult


HEADER_TYPE_PATTERNS = (
    ("method call", "method_call"),
    ("method return", "method_return"),
    ("signal", "signal"),
    ("error", "error"),
)

ATTRIBUTE_PATTERNS: dict[str, re.Pattern[str]] = {
    "time": re.compile(r"\btime=(\d+(?:\.\d+)?)"),
    "sender": re.compile(r"\bsender=([^\s]+)"),
    "destination": re.compile(r"\bdestination=(\([^)]+\)|[^\s;]+)"),
    "path": re.compile(r"\bpath=([^\s;]+)"),
    "interface": re.compile(r"\binterface=([^\s;]+)"),
    "member": re.compile(r"\bmember=([^\s;]+)"),
    "serial": re.compile(r"\bserial=(\d+)"),
    "reply_serial": re.compile(r"\breply_serial=(\d+)"),
    "error_name": re.compile(r"\berror_name=([^\s;]+)"),
}


def parse_events(raw_text: str) -> ParseResult:
    blocks = _split_blocks(raw_text)
    events: list[Event] = []
    skipped_blocks = 0
    for block in blocks:
        event = _parse_block(block)
        if event is None:
            skipped_blocks += 1
            continue
        events.append(event)
    return ParseResult(events=events, skipped_blocks=skipped_blocks)


def _split_blocks(raw_text: str) -> list[str]:
    lines = raw_text.splitlines()
    blocks: list[list[str]] = []
    current_block: list[str] = []

    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            if current_block:
                current_block.append("")
            continue
        if _extract_message_type(stripped) is not None:
            if current_block:
                blocks.append(current_block)
            current_block = [stripped]
            continue
        if current_block:
            current_block.append(stripped)

    if current_block:
        blocks.append(current_block)

    return ["\n".join(block).strip() for block in blocks if any(line.strip() for line in block)]


def _parse_block(block: str) -> Event | None:
    lines = [line.rstrip() for line in block.splitlines() if line.strip()]
    if not lines:
        return None
    header = lines[0]
    message_type = _extract_message_type(header)
    if message_type is None:
        return None
    attrs = {name: _extract_attribute(name, header) for name in ATTRIBUTE_PATTERNS}
    if not _looks_parseable(message_type, attrs):
        return None
    return Event(
        timestamp=_maybe_float(attrs["time"]),
        message_type=message_type,
        sender=attrs["sender"],
        destination=_normalize_destination(attrs["destination"]),
        path=attrs["path"],
        interface=attrs["interface"],
        member=attrs["member"],
        serial=_maybe_int(attrs["serial"]),
        reply_serial=_maybe_int(attrs["reply_serial"]),
        error_name=attrs["error_name"],
    )


def _extract_message_type(header: str) -> str | None:
    for prefix, message_type in HEADER_TYPE_PATTERNS:
        if header.startswith(prefix):
            return message_type
    return None


def _extract_attribute(name: str, header: str) -> str | None:
    match = ATTRIBUTE_PATTERNS[name].search(header)
    if not match:
        return None
    return match.group(1)


def _looks_parseable(message_type: str, attrs: dict[str, str | None]) -> bool:
    if message_type in {"method_call", "signal"}:
        return any(
            attrs.get(name)
            for name in ("sender", "destination", "path", "interface", "member", "serial")
        )
    return any(
        attrs.get(name)
        for name in ("sender", "destination", "serial", "reply_serial", "error_name")
    )


def _normalize_destination(destination: str | None) -> str | None:
    if destination in {None, "(null destination)"}:
        return None
    return destination


def _maybe_int(value: str | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _maybe_float(value: str | None) -> float | None:
    if value is None:
        return None
    return float(value)

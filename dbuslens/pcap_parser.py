from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO, Callable

import dpkt
from dbus_fast._private.unmarshaller import Unmarshaller
from dbus_fast.signature import Variant

from dbuslens.models import Event, ParseResult


def parse_pcap_bytes(payload: bytes) -> ParseResult:
    return parse_pcap_stream(
        io.BytesIO(payload),
        total_bytes=len(payload),
    )


def parse_pcap_file(
    path: Path,
    *,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ParseResult:
    with path.open("rb") as handle:
        return parse_pcap_stream(
            handle,
            total_bytes=path.stat().st_size,
            progress_callback=progress_callback,
        )


def parse_pcap_stream(
    stream: BinaryIO,
    *,
    total_bytes: int,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ParseResult:
    reader = dpkt.pcap.Reader(stream)
    events: list[Event] = []
    skipped_packets = 0
    last_reported = -1

    for timestamp, packet in reader:
        try:
            message = Unmarshaller(
                stream=io.BytesIO(packet),
                negotiate_unix_fd=False,
            ).unmarshall()
        except Exception:  # pylint: disable=broad-exception-caught
            skipped_packets += 1
            continue

        if message is None:
            skipped_packets += 1
            continue

        events.append(
            Event(
                timestamp=float(timestamp),
                message_type=message.message_type.name.lower(),
                sender=message.sender,
                destination=message.destination,
                path=message.path,
                interface=message.interface,
                member=message.member,
                serial=message.serial,
                reply_serial=message.reply_serial or None,
                error_name=message.error_name,
                signature=message.signature or None,
                body_preview=_preview_body(message.body),
            )
        )
        if progress_callback and hasattr(stream, "tell"):
            current = min(stream.tell(), total_bytes)
            if current != last_reported:
                progress_callback(current, total_bytes)
                last_reported = current

    if progress_callback:
        progress_callback(total_bytes, total_bytes)

    return ParseResult(events=events, skipped_packets=skipped_packets)


def _preview_body(body: object, *, limit: int = 120) -> str | None:
    if body in (None, []):
        return None
    preview = repr(_normalize_preview_value(body))
    if len(preview) <= limit:
        return preview
    return f"{preview[: limit - 3]}..."


def _normalize_preview_value(value: object) -> object:
    if isinstance(value, Variant):
        return _normalize_preview_value(value.value)
    if isinstance(value, bytes):
        return _preview_bytes(value)
    if isinstance(value, list):
        return [_normalize_preview_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_preview_value(item) for item in value)
    if isinstance(value, dict):
        return {
            _normalize_preview_value(key): _normalize_preview_value(item)
            for key, item in value.items()
        }
    return value


def _preview_bytes(value: bytes) -> str:
    if not value:
        return ""
    try:
        decoded = value.decode("utf-8")
    except UnicodeDecodeError:
        decoded = ""
    if decoded and all(character.isprintable() or character in "\t\r\n" for character in decoded):
        return decoded
    return f"0x{value.hex()}"

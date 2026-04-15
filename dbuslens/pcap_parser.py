from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO, Callable

import dpkt
from dbus_fast._private.unmarshaller import Unmarshaller

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

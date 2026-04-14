from __future__ import annotations

import io

import dpkt
from dbus_fast._private.unmarshaller import Unmarshaller

from dbuslens.models import Event, ParseResult


def parse_pcap_bytes(payload: bytes) -> ParseResult:
    reader = dpkt.pcap.Reader(io.BytesIO(payload))
    events: list[Event] = []
    skipped_packets = 0

    for timestamp, packet in reader:
        try:
            message = Unmarshaller(
                stream=io.BytesIO(packet),
                negotiate_unix_fd=False,
            ).unmarshall()
        except Exception:
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

    return ParseResult(events=events, skipped_packets=skipped_packets)

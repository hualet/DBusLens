import io
import unittest

import dpkt
from dbus_fast._private.constants import LITTLE_ENDIAN, PROTOCOL_VERSION, HeaderField
from dbus_fast._private.marshaller import Marshaller
from dbus_fast.constants import MessageType
from dbus_fast.message import Message
from dbus_fast.signature import Variant

from dbuslens.pcap_parser import parse_pcap_bytes


def marshall_with_sender(message: Message) -> bytes:
    body_buffer = Marshaller(message.signature, message.body).marshall()
    fields = []
    if message.path:
        fields.append((HeaderField.PATH.value, Variant("o", message.path)))
    if message.interface:
        fields.append((HeaderField.INTERFACE.value, Variant("s", message.interface)))
    if message.member:
        fields.append((HeaderField.MEMBER.value, Variant("s", message.member)))
    if message.error_name:
        fields.append((HeaderField.ERROR_NAME.value, Variant("s", message.error_name)))
    if message.reply_serial:
        fields.append((HeaderField.REPLY_SERIAL.value, Variant("u", message.reply_serial)))
    if message.destination:
        fields.append((HeaderField.DESTINATION.value, Variant("s", message.destination)))
    if message.sender:
        fields.append((HeaderField.SENDER.value, Variant("s", message.sender)))
    if message.signature:
        fields.append((HeaderField.SIGNATURE.value, Variant("g", message.signature)))

    header_body = [
        LITTLE_ENDIAN,
        message.message_type.value,
        message.flags.value,
        PROTOCOL_VERSION,
        len(body_buffer),
        message.serial,
        fields,
    ]
    header = Marshaller("yyyyuua(yv)", header_body)
    header.marshall()
    header.align(8)
    return bytes(header.buffer + body_buffer)


def build_pcap_bytes(messages: list[tuple[float, Message]]) -> bytes:
    buffer = io.BytesIO()
    writer = dpkt.pcap.Writer(buffer, linktype=dpkt.pcap.DLT_DBUS)
    for timestamp, message in messages:
        writer.writepkt(marshall_with_sender(message), ts=timestamp)
    return buffer.getvalue()


class ParsePcapBytesTests(unittest.TestCase):
    def test_parse_pcap_extracts_common_fields(self) -> None:
        pcap_bytes = build_pcap_bytes(
            [
                (
                    1713081000.1,
                    Message(
                        message_type=MessageType.METHOD_CALL,
                        sender=":1.10",
                        destination="org.example.Service",
                        path="/org/example/Demo",
                        interface="org.example.Demo",
                        member="Ping",
                        serial=17,
                    ),
                ),
                (
                    1713081000.2,
                    Message(
                        message_type=MessageType.SIGNAL,
                        sender="org.example.Service",
                        path="/org/example/Demo",
                        interface="org.example.Demo",
                        member="Changed",
                        serial=18,
                    ),
                ),
            ]
        )

        result = parse_pcap_bytes(pcap_bytes)

        self.assertEqual(result.skipped_packets, 0)
        self.assertEqual(len(result.events), 2)
        self.assertEqual(result.events[0].message_type, "method_call")
        self.assertEqual(result.events[0].sender, ":1.10")
        self.assertEqual(result.events[0].destination, "org.example.Service")
        self.assertEqual(result.events[0].interface, "org.example.Demo")
        self.assertEqual(result.events[0].member, "Ping")
        self.assertEqual(result.events[0].operation, "org.example.Demo.Ping")
        self.assertEqual(result.events[0].timestamp, 1713081000.1)
        self.assertEqual(result.events[1].message_type, "signal")

    def test_parse_pcap_keeps_error_metadata(self) -> None:
        pcap_bytes = build_pcap_bytes(
            [
                (
                    1713081000.3,
                    Message(
                        message_type=MessageType.ERROR,
                        sender="org.example.Service",
                        destination=":1.10",
                        error_name="org.example.Error.Failed",
                        reply_serial=17,
                        serial=19,
                    ),
                )
            ]
        )

        result = parse_pcap_bytes(pcap_bytes)

        self.assertEqual(result.skipped_packets, 0)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].message_type, "error")
        self.assertEqual(result.events[0].destination, ":1.10")
        self.assertEqual(result.events[0].error_name, "org.example.Error.Failed")
        self.assertEqual(result.events[0].reply_serial, 17)

    def test_parse_pcap_skips_invalid_packets(self) -> None:
        buffer = io.BytesIO()
        writer = dpkt.pcap.Writer(buffer, linktype=dpkt.pcap.DLT_DBUS)
        writer.writepkt(b"not-a-dbus-message", ts=1713081000.1)

        result = parse_pcap_bytes(buffer.getvalue())

        self.assertEqual(result.skipped_packets, 1)
        self.assertEqual(result.events, [])


if __name__ == "__main__":
    unittest.main()

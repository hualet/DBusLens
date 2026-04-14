import unittest

from dbuslens.parser import parse_events


SAMPLE_METHOD_CALL = """method call time=1713081000.100000 sender=:1.10 -> destination=org.example.Service serial=17 path=/org/example/Demo; interface=org.example.Demo; member=Ping
   string "hello"
"""

SAMPLE_SIGNAL = """signal time=1713081000.200000 sender=org.example.Service -> destination=(null destination) serial=18 path=/org/example/Demo; interface=org.example.Demo; member=Changed
   string "world"
"""

SAMPLE_ERROR = """error time=1713081000.300000 sender=org.example.Service -> destination=:1.10 error_name=org.example.Error.Failed reply_serial=17
   string "boom"
"""


class ParseEventsTests(unittest.TestCase):
    def test_parse_events_handles_back_to_back_messages_without_blank_lines(self) -> None:
        raw = SAMPLE_METHOD_CALL + SAMPLE_SIGNAL + SAMPLE_ERROR

        result = parse_events(raw)

        self.assertEqual(result.skipped_blocks, 0)
        self.assertEqual(len(result.events), 3)
        self.assertEqual(
            [event.message_type for event in result.events],
            ["method_call", "signal", "error"],
        )

    def test_parse_events_extracts_common_fields(self) -> None:
        raw = "\n".join([SAMPLE_METHOD_CALL, "", SAMPLE_SIGNAL, ""])

        result = parse_events(raw)

        self.assertEqual(result.skipped_blocks, 0)
        self.assertEqual(len(result.events), 2)
        self.assertEqual(result.events[0].message_type, "method_call")
        self.assertEqual(result.events[0].sender, ":1.10")
        self.assertEqual(result.events[0].destination, "org.example.Service")
        self.assertEqual(result.events[0].interface, "org.example.Demo")
        self.assertEqual(result.events[0].member, "Ping")
        self.assertEqual(result.events[0].operation, "org.example.Demo.Ping")
        self.assertEqual(result.events[1].message_type, "signal")

    def test_parse_events_keeps_error_metadata(self) -> None:
        result = parse_events(SAMPLE_ERROR)

        self.assertEqual(result.skipped_blocks, 0)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].message_type, "error")
        self.assertEqual(result.events[0].sender, "org.example.Service")
        self.assertEqual(result.events[0].destination, ":1.10")
        self.assertEqual(result.events[0].error_name, "org.example.Error.Failed")
        self.assertEqual(result.events[0].reply_serial, 17)

    def test_parse_events_skips_malformed_blocks(self) -> None:
        raw = "\n".join(["method call broken", "", SAMPLE_SIGNAL, ""])

        result = parse_events(raw)

        self.assertEqual(result.skipped_blocks, 1)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].message_type, "signal")


if __name__ == "__main__":
    unittest.main()

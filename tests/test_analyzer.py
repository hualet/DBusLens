import unittest

from dbuslens.analyzer import build_report
from dbuslens.models import Event


class BuildReportTests(unittest.TestCase):
    def test_build_report_groups_outbound_and_inbound_counts(self) -> None:
        events = [
            Event(
                timestamp=1.0,
                message_type="method_call",
                sender=":1.10",
                destination="org.example.Service",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=1,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=2.0,
                message_type="signal",
                sender="org.example.Service",
                destination=None,
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Changed",
                serial=2,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=3.0,
                message_type="method_call",
                sender=":1.10",
                destination="org.example.Service",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=3,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=4.0,
                message_type="method_return",
                sender="org.example.Service",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=4,
                reply_serial=3,
                error_name=None,
            ),
        ]

        report = build_report(
            events,
            resolve_process=lambda service: {
                ":1.10": "demo-client",
                "org.example.Service": "demo-service",
            }.get(service),
        )

        self.assertEqual(report.total_events, 4)
        self.assertEqual(report.actionable_events, 3)
        self.assertEqual(report.outbound_rows[0].name, ":1.10")
        self.assertEqual(report.outbound_rows[0].process, "demo-client")
        self.assertEqual(report.outbound_rows[0].count, 2)
        self.assertEqual(
            report.outbound_rows[0].children[0].name,
            "org.example.Demo.Ping",
        )
        self.assertEqual(report.inbound_rows[0].name, "org.example.Demo.Ping")
        self.assertEqual(report.inbound_rows[0].count, 2)
        self.assertEqual(report.inbound_rows[0].children[0].name, ":1.10")
        self.assertEqual(report.inbound_rows[0].children[0].process, "demo-client")

    def test_build_report_uses_fallback_labels(self) -> None:
        events = [
            Event(
                timestamp=None,
                message_type="signal",
                sender=None,
                destination=None,
                path=None,
                interface=None,
                member=None,
                serial=None,
                reply_serial=None,
                error_name=None,
            )
        ]

        report = build_report(events)

        self.assertEqual(report.outbound_rows[0].name, "<unknown>")
        self.assertEqual(report.inbound_rows[0].name, "<unknown>")
        self.assertIsNone(report.outbound_rows[0].process)


if __name__ == "__main__":
    unittest.main()

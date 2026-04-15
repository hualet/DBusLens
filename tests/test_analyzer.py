import unittest

from dbuslens.analyzer import build_report
from dbuslens.models import Event, ProcessInfo


class BuildReportTests(unittest.TestCase):
    def test_build_report_prefers_well_known_names_for_same_process(self) -> None:
        events = [
            Event(
                timestamp=1.0,
                message_type="signal",
                sender=":1.10",
                destination=None,
                path="/org/example/Service",
                interface="org.example.Service",
                member="Changed",
                serial=1,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=2.0,
                message_type="method_call",
                sender=":1.11",
                destination="org.example.Service",
                path="/org/example/Service",
                interface="org.example.Service",
                member="Ping",
                serial=2,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=3.0,
                message_type="method_call",
                sender=":1.11",
                destination=":1.10",
                path="/org/example/Service",
                interface="org.example.Service",
                member="Ping",
                serial=3,
                reply_serial=None,
                error_name=None,
            ),
        ]

        report = build_report(
            events,
            resolve_process={
                ":1.10": ProcessInfo(short_name="demo-service", pid=2020),
                "org.example.Service": ProcessInfo(short_name="demo-service", pid=2020),
                ":1.11": ProcessInfo(short_name="demo-client", pid=1010),
            }.get,
        )

        self.assertEqual(report.outbound_rows[0].name, ":1.11")
        self.assertEqual(report.outbound_rows[1].name, "org.example.Service")
        self.assertEqual(report.inbound_rows[1].children[0].name, "org.example.Service")

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
            resolve_process={
                ":1.10": ProcessInfo(short_name="demo-client", pid=1010),
                "org.example.Service": ProcessInfo(short_name="demo-service", pid=2020),
            }.get,
        )

        self.assertEqual(report.total_events, 4)
        self.assertEqual(report.actionable_events, 3)
        self.assertEqual(report.outbound_rows[0].name, ":1.10")
        self.assertEqual(
            report.outbound_rows[0].process,
            ProcessInfo(short_name="demo-client", pid=1010),
        )
        self.assertEqual(report.outbound_rows[0].count, 2)
        self.assertEqual(
            report.outbound_rows[0].children[0].name,
            "org.example.Demo.Ping",
        )
        self.assertEqual(report.inbound_rows[0].name, "org.example.Demo.Ping")
        self.assertEqual(report.inbound_rows[0].count, 2)
        self.assertEqual(report.inbound_rows[0].children[0].name, ":1.10")
        self.assertEqual(
            report.inbound_rows[0].children[0].process,
            ProcessInfo(short_name="demo-client", pid=1010),
        )

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

    def test_build_report_groups_errors_by_name_and_origin(self) -> None:
        events = [
            Event(
                timestamp=1.0,
                message_type="method_call",
                sender=":1.10",
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="GetNameOwner",
                serial=7,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=2.0,
                message_type="error",
                sender="org.freedesktop.DBus",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=8,
                reply_serial=7,
                error_name="org.freedesktop.DBus.Error.NameHasNoOwner",
            ),
        ]

        report = build_report(
            events,
            resolve_process={
                ":1.10": ProcessInfo(short_name="demo-client", pid=1010),
            }.get,
        )

        self.assertEqual(report.error_rows[0].name, "org.freedesktop.DBus.Error.NameHasNoOwner")
        self.assertEqual(report.error_rows[0].count, 1)
        self.assertEqual(report.error_rows[0].children[0].name, ":1.10")
        self.assertEqual(
            report.error_rows[0].children[0].process,
            ProcessInfo(short_name="demo-client", pid=1010),
        )
        self.assertEqual(
            report.error_rows[0].children[0].secondary,
            "org.freedesktop.DBus.GetNameOwner",
        )


if __name__ == "__main__":
    unittest.main()

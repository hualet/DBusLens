import unittest

from dbuslens.analyzer import build_report
from dbuslens.models import CaptureNameInfo, ErrorDetail, ErrorSummary, Event, ProcessInfo


def _snapshot_names(*entries: dict[str, object]) -> dict[str, object]:
    return {
        "captured_at": "2026-04-16T10:20:31+08:00",
        "bus": "session",
        "names": list(entries),
    }


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
            snapshot_names=_snapshot_names(
                {
                    "name": "org.example.Service",
                    "owner": ":1.42",
                    "pid": 2020,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-service"],
                    "error": None,
                },
                {
                    "name": "org.example.Client",
                    "owner": ":1.10",
                    "pid": 1010,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-client"],
                    "error": None,
                },
            ),
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
        self.assertEqual(report.error_rows[0].children[0].name, "org.freedesktop.DBus")
        self.assertIsNone(report.error_rows[0].children[0].process)
        self.assertEqual(
            report.error_rows[0].children[0].secondary,
            "org.freedesktop.DBus.GetNameOwner",
        )

    def test_build_report_groups_error_diagnostics_by_target_and_operation(self) -> None:
        events = [
            Event(
                timestamp=1.0,
                message_type="method_call",
                sender=":1.10",
                destination="org.example.Service",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=7,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=1.2,
                message_type="error",
                sender="org.example.Service",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=8,
                reply_serial=7,
                error_name="org.example.Error.Failed",
            ),
            Event(
                timestamp=2.0,
                message_type="method_call",
                sender=":1.10",
                destination="org.example.Service",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=9,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=2.4,
                message_type="error",
                sender="org.example.Service",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=10,
                reply_serial=9,
                error_name="org.example.Error.Failed",
            ),
        ]

        report = build_report(
            events,
            snapshot_names=_snapshot_names(
                {
                    "name": "org.example.Service",
                    "owner": ":1.42",
                    "pid": 2020,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-service"],
                    "error": None,
                },
                {
                    "name": "org.example.Client",
                    "owner": ":1.10",
                    "pid": 1010,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-client"],
                    "error": None,
                },
            ),
            resolve_process={
                ":1.10": ProcessInfo(short_name="demo-client", pid=1010),
                "org.example.Service": ProcessInfo(short_name="demo-service", pid=2020),
            }.get,
        )

        expected = ErrorSummary(
            error_name="org.example.Error.Failed",
            target="org.example.Service",
            operation="org.example.Demo.Ping",
            count=2,
            first_seen=1.2,
            last_seen=2.4,
            average_latency_ms=300.0,
            retry_count=1,
            unique_callers=1,
            target_process=CaptureNameInfo(
                name="org.example.Service",
                owner=":1.42",
                pid=2020,
                uid=1000,
                cmdline=["/usr/bin/example-service"],
            ),
            details=[
                ErrorDetail(
                    caller=":1.10",
                    caller_process=CaptureNameInfo(
                        name="org.example.Client",
                        owner=":1.10",
                        pid=1010,
                        uid=1000,
                        cmdline=["/usr/bin/example-client"],
                    ),
                    target_process=CaptureNameInfo(
                        name="org.example.Service",
                        owner=":1.42",
                        pid=2020,
                        uid=1000,
                        cmdline=["/usr/bin/example-service"],
                    ),
                    latency_ms="300.0 ms",
                    notes="retried within 5s",
                    count=2,
                )
            ],
        )

        self.assertEqual(report.error_summaries, [expected])
        self.assertEqual(report.error_rows[0].name, "org.example.Error.Failed")

    def test_build_report_keeps_alias_targets_separate_when_pids_match(self) -> None:
        events = [
            Event(
                timestamp=1.0,
                message_type="method_call",
                sender=":1.10",
                destination="org.example.Service",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=7,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=1.2,
                message_type="error",
                sender="org.example.Service",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=8,
                reply_serial=7,
                error_name="org.example.Error.Failed",
            ),
            Event(
                timestamp=2.0,
                message_type="method_call",
                sender=":1.10",
                destination=":1.42",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=9,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=2.4,
                message_type="error",
                sender=":1.42",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=10,
                reply_serial=9,
                error_name="org.example.Error.Failed",
            ),
        ]

        report = build_report(
            events,
            snapshot_names=_snapshot_names(
                {
                    "name": "org.example.Service",
                    "owner": ":1.42",
                    "pid": 2020,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-service"],
                    "error": None,
                }
            ),
            resolve_process={
                ":1.10": ProcessInfo(short_name="demo-client", pid=1010),
                "org.example.Service": ProcessInfo(short_name="demo-service", pid=2020),
                ":1.42": ProcessInfo(short_name="demo-service", pid=2020),
            }.get,
        )

        self.assertEqual(len(report.error_summaries), 2)
        self.assertEqual(
            [summary.target for summary in report.error_summaries],
            [":1.42", "org.example.Service"],
        )
        self.assertEqual([summary.count for summary in report.error_summaries], [1, 1])
        self.assertEqual(
            {summary.owner_label for summary in report.error_summaries},
            {"org.example.Service [2020]"},
        )

    def test_build_report_prefers_well_known_snapshot_alias_over_unique_name_order(self) -> None:
        events = [
            Event(
                timestamp=1.0,
                message_type="method_call",
                sender=":1.10",
                destination="org.example.Service",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=7,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=1.2,
                message_type="error",
                sender="org.example.Service",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=8,
                reply_serial=7,
                error_name="org.example.Error.Failed",
            ),
        ]

        snapshot_entries = [
            {
                "name": ":1.42",
                "owner": ":1.42",
                "pid": 2020,
                "uid": 1000,
                "cmdline": ["/usr/bin/example-service"],
                "error": None,
            },
            {
                "name": "org.example.Service",
                "owner": ":1.42",
                "pid": 2020,
                "uid": 1000,
                "cmdline": ["/usr/bin/example-service"],
                "error": None,
            },
        ]

        first = build_report(events, snapshot_names=_snapshot_names(*snapshot_entries))
        second = build_report(events, snapshot_names=_snapshot_names(*reversed(snapshot_entries)))

        self.assertEqual(first.error_summaries[0].owner_label, "org.example.Service [2020]")
        self.assertEqual(second.error_summaries[0].owner_label, "org.example.Service [2020]")

    def test_build_report_uses_explicit_unknowns_for_unmatched_errors(self) -> None:
        events = [
            Event(
                timestamp=1.0,
                message_type="error",
                sender=None,
                destination=None,
                path=None,
                interface=None,
                member=None,
                serial=8,
                reply_serial=999,
                error_name="org.example.Error.Failed",
            )
        ]

        report = build_report(events)

        self.assertEqual(len(report.error_summaries), 1)
        summary = report.error_summaries[0]
        self.assertEqual(summary.target, "<unknown-target>")
        self.assertEqual(summary.operation, "<unknown>")
        self.assertEqual(summary.details[0].caller, "<unknown-caller>")
        self.assertEqual(summary.details[0].caller_process, None)
        self.assertEqual(summary.owner_label, "<unknown-target>")

    def test_build_report_preserves_partial_error_event_origin_data(self) -> None:
        events = [
            Event(
                timestamp=1.0,
                message_type="error",
                sender="org.example.Service",
                destination=None,
                path=None,
                interface=None,
                member=None,
                serial=8,
                reply_serial=999,
                error_name="org.example.Error.Failed",
            ),
            Event(
                timestamp=2.0,
                message_type="error",
                sender=None,
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=9,
                reply_serial=1000,
                error_name="org.example.Error.Failed",
            ),
        ]

        report = build_report(
            events,
            snapshot_names=_snapshot_names(
                {
                    "name": "org.example.Service",
                    "owner": ":1.42",
                    "pid": 2020,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-service"],
                    "error": None,
                },
                {
                    "name": "org.example.Client",
                    "owner": ":1.10",
                    "pid": 1010,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-client"],
                    "error": None,
                },
            ),
            resolve_process={
                ":1.10": ProcessInfo(short_name="demo-client", pid=1010),
                "org.example.Service": ProcessInfo(short_name="demo-service", pid=2020),
            }.get,
        )

        self.assertEqual(len(report.error_summaries), 2)
        summaries = {summary.target: summary for summary in report.error_summaries}
        self.assertEqual(summaries["org.example.Service"].details[0].caller, "<unknown-caller>")
        self.assertEqual(summaries["org.example.Service"].owner_label, "org.example.Service [2020]")
        self.assertEqual(summaries["<unknown-target>"].details[0].caller, ":1.10")
        self.assertEqual(
            summaries["<unknown-target>"].details[0].caller_process,
            CaptureNameInfo(
                name="org.example.Client",
                owner=":1.10",
                pid=1010,
                uid=1000,
                cmdline=["/usr/bin/example-client"],
            ),
        )

    def test_build_report_counts_retries_by_failure_timestamps(self) -> None:
        events = [
            Event(
                timestamp=1.0,
                message_type="method_call",
                sender=":1.10",
                destination="org.example.ServiceA",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=1,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=1.2,
                message_type="error",
                sender="org.example.ServiceA",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=2,
                reply_serial=1,
                error_name="org.example.Error.Failed",
            ),
            Event(
                timestamp=1.1,
                message_type="method_call",
                sender=":1.10",
                destination="org.example.ServiceA",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=3,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=10.0,
                message_type="error",
                sender="org.example.ServiceA",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=4,
                reply_serial=3,
                error_name="org.example.Error.Failed",
            ),
            Event(
                timestamp=20.0,
                message_type="method_call",
                sender=":1.10",
                destination="org.example.ServiceB",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=5,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=50.0,
                message_type="error",
                sender="org.example.ServiceB",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=6,
                reply_serial=5,
                error_name="org.example.Error.Failed",
            ),
            Event(
                timestamp=40.0,
                message_type="method_call",
                sender=":1.10",
                destination="org.example.ServiceB",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=7,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=52.0,
                message_type="error",
                sender="org.example.ServiceB",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=8,
                reply_serial=7,
                error_name="org.example.Error.Failed",
            ),
        ]

        report = build_report(
            events,
            snapshot_names=_snapshot_names(
                {
                    "name": "org.example.ServiceA",
                    "owner": ":1.42",
                    "pid": 2020,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-service-a"],
                    "error": None,
                },
                {
                    "name": "org.example.ServiceB",
                    "owner": ":1.43",
                    "pid": 3030,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-service-b"],
                    "error": None,
                },
                {
                    "name": "org.example.Client",
                    "owner": ":1.10",
                    "pid": 1010,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-client"],
                    "error": None,
                },
            ),
            resolve_process={
                ":1.10": ProcessInfo(short_name="demo-client", pid=1010),
                "org.example.ServiceA": ProcessInfo(short_name="demo-service-a", pid=2020),
                "org.example.ServiceB": ProcessInfo(short_name="demo-service-b", pid=3030),
            }.get,
        )

        summaries = {summary.target: summary for summary in report.error_summaries}
        self.assertEqual(summaries["org.example.ServiceA"].retry_count, 0)
        self.assertEqual(summaries["org.example.ServiceA"].details[0].notes, "")
        self.assertEqual(summaries["org.example.ServiceB"].retry_count, 1)
        self.assertEqual(summaries["org.example.ServiceB"].details[0].notes, "retried within 5s")

    def test_build_report_matches_errors_even_when_call_appears_later(self) -> None:
        events = [
            Event(
                timestamp=2.5,
                message_type="error",
                sender="org.example.Service",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=18,
                reply_serial=17,
                error_name="org.example.Error.Failed",
            ),
            Event(
                timestamp=2.0,
                message_type="method_call",
                sender=":1.10",
                destination="org.example.Service",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=17,
                reply_serial=None,
                error_name=None,
            ),
        ]

        report = build_report(
            events,
            snapshot_names=_snapshot_names(
                {
                    "name": "org.example.Service",
                    "owner": ":1.42",
                    "pid": 2020,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-service"],
                    "error": None,
                },
                {
                    "name": "org.example.Client",
                    "owner": ":1.10",
                    "pid": 1010,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-client"],
                    "error": None,
                },
            ),
        )

        self.assertEqual(len(report.error_summaries), 1)
        summary = report.error_summaries[0]
        self.assertEqual(summary.target, "org.example.Service")
        self.assertEqual(summary.operation, "org.example.Demo.Ping")
        self.assertEqual(summary.average_latency_ms, 500.0)
        self.assertEqual(summary.details[0].caller, ":1.10")

    def test_build_report_matches_error_reply_when_error_uses_unique_owner_name(self) -> None:
        events = [
            Event(
                timestamp=2.0,
                message_type="method_call",
                sender=":1.10",
                destination="org.example.Service",
                path="/org/example/Demo",
                interface="org.example.Demo",
                member="Ping",
                serial=17,
                reply_serial=None,
                error_name=None,
            ),
            Event(
                timestamp=2.5,
                message_type="error",
                sender=":1.42",
                destination=":1.10",
                path=None,
                interface=None,
                member=None,
                serial=18,
                reply_serial=17,
                error_name="org.example.Error.Failed",
            ),
        ]

        report = build_report(
            events,
            snapshot_names=_snapshot_names(
                {
                    "name": "org.example.Service",
                    "owner": ":1.42",
                    "pid": 2020,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-service"],
                    "error": None,
                },
                {
                    "name": "org.example.Client",
                    "owner": ":1.10",
                    "pid": 1010,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-client"],
                    "error": None,
                },
            ),
        )

        self.assertEqual(len(report.error_summaries), 1)
        summary = report.error_summaries[0]
        self.assertEqual(summary.target, "org.example.Service")
        self.assertEqual(summary.operation, "org.example.Demo.Ping")
        self.assertEqual(summary.average_latency_ms, 500.0)
        self.assertEqual(summary.owner_label, "org.example.Service [2020]")


if __name__ == "__main__":
    unittest.main()

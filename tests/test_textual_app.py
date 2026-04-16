import unittest

from dbuslens.models import (
    AnalysisReport,
    CaptureNameInfo,
    DetailRow,
    ErrorDetail,
    ErrorSummary,
    ProcessInfo,
    Row,
)
from dbuslens.report_app import (
    ReportAppState,
    detail_columns,
    detail_column_widths,
    detail_lines,
    detail_rows,
    main_column_widths,
    main_columns,
    main_rows,
    metadata_text,
)


def _make_report() -> AnalysisReport:
    return AnalysisReport(
        source_path="sample.log",
        total_events=1,
        actionable_events=1,
        skipped_blocks=0,
        outbound_rows=[
            Row(
                name="svc",
                process=ProcessInfo(short_name="demo", pid=4321),
                count=1,
                children=[DetailRow(name="op", process=None, count=1)],
            )
        ],
        inbound_rows=[
            Row(
                name="op",
                process=None,
                count=1,
                children=[
                    DetailRow(
                        name="svc",
                        process=ProcessInfo(short_name="demo", pid=4321),
                        count=1,
                    )
                ],
            )
        ],
        error_rows=[],
        error_summaries=[
            ErrorSummary(
                error_name="org.freedesktop.DBus.Error.NameHasNoOwner",
                target="org.example.Service",
                operation="org.freedesktop.DBus.GetNameOwner",
                count=1,
                first_seen=1.0,
                last_seen=1.0,
                average_latency_ms=250.0,
                retry_count=0,
                unique_callers=1,
                target_process=CaptureNameInfo(
                    name="org.example.Service",
                    owner=":1.42",
                    pid=4242,
                    uid=1000,
                    cmdline=["/usr/bin/demo-service"],
                ),
                details=[
                    ErrorDetail(
                        caller=":1.10",
                        caller_process=CaptureNameInfo(
                            name=":1.10",
                            owner=":1.10",
                            pid=1010,
                            uid=1000,
                            cmdline=["/usr/bin/demo-client"],
                        ),
                        target_process=CaptureNameInfo(
                            name="org.example.Service",
                            owner=":1.42",
                            pid=4242,
                            uid=1000,
                            cmdline=["/usr/bin/demo-service"],
                        ),
                        latency_ms="250.0 ms",
                        notes="",
                        count=1,
                    )
                ],
            )
        ],
    )


class ReportAppStateTests(unittest.TestCase):
    def test_report_app_state_tracks_view_and_current_row(self) -> None:
        report = _make_report()
        state = ReportAppState(report)

        self.assertEqual(state.active_view, "outbound")
        self.assertEqual(state.current_row.name, "svc")
        self.assertEqual(main_columns(state), ("Count", "Service", "Process"))

        state.switch_view()

        self.assertEqual(state.active_view, "inbound")
        self.assertEqual(state.selected_index, 0)
        self.assertEqual(state.current_row.name, "op")
        self.assertEqual(main_columns(state), ("Count", "Operation"))

        state.set_view("errors")

        self.assertEqual(state.active_view, "errors")
        self.assertEqual(state.current_row.error_name, "org.freedesktop.DBus.Error.NameHasNoOwner")
        self.assertEqual(main_columns(state), ("Count", "Error", "Target", "Operation"))

    def test_current_row_returns_none_for_empty_or_out_of_range_selection(self) -> None:
        report = _make_report()

        self.assertIsNone(ReportAppState(report, selected_index=-1).current_row)
        self.assertIsNone(ReportAppState(report, selected_index=1).current_row)
        self.assertIsNone(
            ReportAppState(
                AnalysisReport(
                    source_path="empty.log",
                    total_events=0,
                    actionable_events=0,
                    skipped_blocks=0,
                    outbound_rows=[],
                    inbound_rows=[],
                    error_rows=[],
                )
            ).current_row
        )

    def test_report_app_provides_main_rows_and_detail_lines(self) -> None:
        report = _make_report()
        state = ReportAppState(report)

        self.assertEqual(main_rows(state), [("1", "svc", "demo [4321]")])
        self.assertEqual(
            detail_lines(state),
            [
                "Selected: svc",
                "Count: 1",
                "Process: demo [4321]",
                "PID: 4321",
                "Details: 1 row(s)",
            ],
        )

        state.switch_view()

        self.assertEqual(main_rows(state), [("1", "op")])
        self.assertEqual(
            detail_lines(state),
            [
                "Selected: op",
                "Count: 1",
                "Details: 1 row(s)",
            ],
        )

        state.set_view("errors")

        self.assertEqual(
            main_rows(state),
            [
                (
                    "1",
                    "org.freedesktop.DBus.Error.NameHasNoOwner",
                    "org.example.Service",
                    "org.freedesktop.DBus.GetNameOwner",
                )
            ],
        )
        self.assertEqual(
            detail_lines(state),
            [
                "Selected: org.freedesktop.DBus.Error.NameHasNoOwner",
                "Target: org.example.Service",
                "Operation: org.freedesktop.DBus.GetNameOwner",
                "Count: 1",
                "First seen: 1.000s",
                "Last seen: 1.000s",
                "Average latency: 250.0 ms",
                "Retries detected: 0",
                "Unique callers: 1",
                "Target owner at capture time: :1.42 [4242]",
            ],
        )

    def test_report_app_provides_detail_table_rows(self) -> None:
        report = AnalysisReport(
            source_path="sample.log",
            total_events=3,
            actionable_events=3,
            skipped_blocks=0,
            outbound_rows=[
                Row(
                    name="svc",
                    process=ProcessInfo(short_name="demo", pid=4321),
                    count=3,
                    children=[
                        DetailRow(name="op-a", process=None, count=2),
                        DetailRow(name="op-b", process=None, count=1),
                    ],
                )
            ],
            inbound_rows=[
                Row(
                    name="op-a",
                    process=None,
                    count=2,
                    children=[
                        DetailRow(
                            name="svc-a",
                            process=ProcessInfo(short_name="proc-a", pid=1001),
                            count=1,
                        ),
                        DetailRow(
                            name="svc-b",
                            process=ProcessInfo(short_name="proc-b", pid=1002),
                            count=1,
                        ),
                    ],
                )
            ],
            error_rows=[],
            error_summaries=[
                ErrorSummary(
                    error_name="org.freedesktop.DBus.Error.NameHasNoOwner",
                    target="org.example.Service",
                    operation="org.freedesktop.DBus.GetNameOwner",
                    count=2,
                    first_seen=1.0,
                    last_seen=2.0,
                    average_latency_ms=250.0,
                    retry_count=1,
                    unique_callers=2,
                    target_process=CaptureNameInfo(
                        name="org.example.Service",
                        owner=":1.42",
                        pid=4242,
                        uid=1000,
                        cmdline=["/usr/bin/demo-service"],
                    ),
                    details=[
                        ErrorDetail(
                            caller=":1.10",
                            caller_process=CaptureNameInfo(
                                name=":1.10",
                                owner=":1.10",
                                pid=1010,
                                uid=1000,
                                cmdline=["/usr/bin/proc-a"],
                            ),
                            target_process=CaptureNameInfo(
                                name="org.example.Service",
                                owner=":1.42",
                                pid=4242,
                                uid=1000,
                                cmdline=["/usr/bin/demo-service"],
                            ),
                            latency_ms="125.0 ms",
                            notes="retried within 5s",
                            count=1,
                        ),
                        ErrorDetail(
                            caller=":1.11",
                            caller_process=CaptureNameInfo(
                                name=":1.11",
                                owner=":1.11",
                                pid=1011,
                                uid=1000,
                                cmdline=["/usr/bin/proc-b"],
                            ),
                            target_process=CaptureNameInfo(
                                name="org.example.Service",
                                owner=":1.42",
                                pid=4242,
                                uid=1000,
                                cmdline=["/usr/bin/demo-service"],
                            ),
                            latency_ms="375.0 ms",
                            notes="",
                            count=1,
                        ),
                    ],
                )
            ],
        )
        state = ReportAppState(report)

        self.assertEqual(detail_columns(state), ("Count", "Operation"))
        self.assertEqual(detail_rows(state), [("2", "op-a"), ("1", "op-b")])

        state.switch_view()

        self.assertEqual(detail_columns(state), ("Count", "Service", "Process"))
        self.assertEqual(
            detail_rows(state),
            [("1", "svc-a", "proc-a [1001]"), ("1", "svc-b", "proc-b [1002]")],
        )

        state.set_view("errors")

        self.assertEqual(
            detail_columns(state),
            ("Count", "Caller", "Process", "Owner/PID", "Latency", "Notes"),
        )
        self.assertEqual(
            detail_rows(state),
            [
                ("1", ":1.10", ":1.10 [1010]", ":1.42 [4242]", "125.0 ms", "retried within 5s"),
                ("1", ":1.11", ":1.11 [1011]", ":1.42 [4242]", "375.0 ms", "-"),
            ],
        )

    def test_metadata_text_includes_report_stats(self) -> None:
        report = _make_report()

        self.assertIn("sample.log", metadata_text(report))
        self.assertIn("events=1", metadata_text(report))
        self.assertIn("actionable=1", metadata_text(report))
        self.assertIn("skipped=0", metadata_text(report))

    def test_process_column_width_can_grow_for_long_names(self) -> None:
        report = AnalysisReport(
            source_path="sample.log",
            total_events=1,
            actionable_events=1,
            skipped_blocks=0,
            outbound_rows=[
                Row(
                    name="svc",
                    process=ProcessInfo(
                        short_name="very-long-process-name-that-should-not-be-capped-at-forty",
                        pid=1234,
                    ),
                    count=1,
                    children=[
                        DetailRow(
                            name="operation",
                            process=None,
                            count=1,
                        )
                    ],
                )
            ],
            inbound_rows=[
                Row(
                    name="op",
                    process=None,
                    count=1,
                    children=[
                        DetailRow(
                            name="svc",
                            process=ProcessInfo(
                                short_name="another-very-long-process-name-used-in-detail-pane",
                                pid=5678,
                            ),
                            count=1,
                        )
                    ],
                )
            ],
            error_rows=[],
        )
        state = ReportAppState(report)

        self.assertGreater(main_column_widths(state)[2], 40)
        state.switch_view()
        self.assertGreater(detail_column_widths(state)[2], 40)


if __name__ == "__main__":
    unittest.main()

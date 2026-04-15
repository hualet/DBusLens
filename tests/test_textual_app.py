import unittest

from dbuslens.models import AnalysisReport, DetailRow, ProcessInfo, Row
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
        error_rows=[
            Row(
                name="org.freedesktop.DBus.Error.NameHasNoOwner",
                process=None,
                count=1,
                children=[
                    DetailRow(
                        name="svc",
                        process=ProcessInfo(short_name="demo", pid=4321),
                        count=1,
                        secondary="org.freedesktop.DBus.GetNameOwner",
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
        self.assertEqual(state.current_row.name, "org.freedesktop.DBus.Error.NameHasNoOwner")
        self.assertEqual(main_columns(state), ("Count", "Error"))

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

        self.assertEqual(main_rows(state), [("1", "org.freedesktop.DBus.Error.NameHasNoOwner")])
        self.assertEqual(
            detail_lines(state),
            [
                "Selected: org.freedesktop.DBus.Error.NameHasNoOwner",
                "Count: 1",
                "Details: 1 row(s)",
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
            error_rows=[
                Row(
                    name="org.freedesktop.DBus.Error.NameHasNoOwner",
                    process=None,
                    count=2,
                    children=[
                        DetailRow(
                            name="svc-a",
                            process=ProcessInfo(short_name="proc-a", pid=1001),
                            count=1,
                            secondary="org.freedesktop.DBus.GetNameOwner",
                        ),
                        DetailRow(
                            name="svc-b",
                            process=ProcessInfo(short_name="proc-b", pid=1002),
                            count=1,
                            secondary="org.freedesktop.DBus.GetConnectionUnixProcessID",
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

        self.assertEqual(detail_columns(state), ("Count", "Service", "Process", "Operation"))
        self.assertEqual(
            detail_rows(state),
            [
                ("1", "svc-a", "proc-a [1001]", "org.freedesktop.DBus.GetNameOwner"),
                ("1", "svc-b", "proc-b [1002]", "org.freedesktop.DBus.GetConnectionUnixProcessID"),
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

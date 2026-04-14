import unittest

from dbuslens.models import AnalysisReport, DetailRow, Row
from dbuslens.report_app import ReportAppState, detail_lines, main_columns, main_rows


def _make_report() -> AnalysisReport:
    return AnalysisReport(
        source_path="sample.log",
        total_events=1,
        actionable_events=1,
        skipped_blocks=0,
        outbound_rows=[
            Row(
                name="svc",
                process="demo",
                count=1,
                children=[DetailRow(name="op", process=None, count=1)],
            )
        ],
        inbound_rows=[
            Row(
                name="op",
                process=None,
                count=1,
                children=[DetailRow(name="svc", process="demo", count=1)],
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
                )
            ).current_row
        )

    def test_report_app_provides_main_rows_and_detail_lines(self) -> None:
        report = _make_report()
        state = ReportAppState(report)

        self.assertEqual(main_rows(state), [("1", "svc", "demo")])
        self.assertEqual(
            detail_lines(state),
            [
                "Selected: svc",
                "Count: 1",
                "Process: demo",
                "First detail: op x1",
            ],
        )

        state.switch_view()

        self.assertEqual(main_rows(state), [("1", "op")])
        self.assertEqual(
            detail_lines(state),
            [
                "Selected: op",
                "Count: 1",
                "First detail: svc (demo) x1",
            ],
        )


if __name__ == "__main__":
    unittest.main()

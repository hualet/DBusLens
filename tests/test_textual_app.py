import unittest

from dbuslens.models import AnalysisReport, DetailRow, Row
from dbuslens.report_app import ReportAppState, main_columns


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


if __name__ == "__main__":
    unittest.main()

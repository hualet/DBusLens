import unittest

from dbuslens.models import AnalysisReport, DetailRow, Row
from dbuslens.report_app import ReportAppState


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
    def test_report_app_state_tracks_view(self) -> None:
        report = _make_report()
        state = ReportAppState(report)

        self.assertEqual(state.active_view, "outbound")

        state.switch_view()

        self.assertEqual(state.active_view, "inbound")


if __name__ == "__main__":
    unittest.main()

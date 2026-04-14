import unittest

from dbuslens.models import AnalysisReport, DetailRow, Row
from dbuslens.tui import BrowserState, build_table


class BuildTableTests(unittest.TestCase):
    def test_outbound_main_table_shows_process_column(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=2,
            actionable_events=2,
            skipped_blocks=0,
            outbound_rows=[
                Row(
                    name=":1.10",
                    process="demo-client",
                    count=2,
                    children=[DetailRow(name="org.example.Demo.Ping", process=None, count=2)],
                )
            ],
            inbound_rows=[],
        )

        header, rows = build_table(BrowserState(report), width=80)

        self.assertIn("PROCESS", header)
        self.assertIn("demo-client", rows[0])

    def test_inbound_main_table_omits_process_column(self) -> None:
        report = AnalysisReport(
            source_path="record.cap",
            total_events=2,
            actionable_events=2,
            skipped_blocks=0,
            outbound_rows=[],
            inbound_rows=[
                Row(
                    name="org.example.Demo.Ping",
                    process=None,
                    count=2,
                    children=[DetailRow(name=":1.10", process="demo-client", count=2)],
                )
            ],
        )
        state = BrowserState(report)
        state.switch_view()

        header, rows = build_table(state, width=80)

        self.assertNotIn("PROCESS", header)
        self.assertIn("org.example.Demo.Ping", rows[0])


if __name__ == "__main__":
    unittest.main()

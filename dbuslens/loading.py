from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from dbuslens.analyzer import build_report
from dbuslens.bundle import read_bundle
from dbuslens.models import AnalysisReport
from dbuslens.pcap_parser import parse_pcap_bytes


@dataclass(frozen=True)
class LoadingUpdate:
    stage: str
    current: int
    total: int

    @property
    def percentage(self) -> int:
        if self.total <= 0:
            return 0
        return max(0, min(100, int((self.current / self.total) * 100)))


@dataclass
class ProgressTracker:
    callback: Callable[[LoadingUpdate], None] | None
    parse_weight: int = 85
    analyze_weight: int = 14
    minimum_step: int = 6
    last_emitted_percentage: int = -1

    def emit_stage(self, stage: str, current: int, total: int) -> None:
        if self.callback is None:
            return
        update = LoadingUpdate(stage=stage, current=current, total=total)
        if stage == "Opening capture":
            self._emit(update, force=True)
            return
        if stage == "Preparing report":
            self._emit(LoadingUpdate(stage=stage, current=100, total=100), force=True)
            return

        percentage = self._scaled_percentage(stage, update.percentage)
        if percentage >= 99 or percentage - self.last_emitted_percentage >= self.minimum_step:
            self._emit(
                LoadingUpdate(stage=stage, current=percentage, total=100),
                force=False,
            )

    def _scaled_percentage(self, stage: str, percentage: int) -> int:
        if stage == "Parsing capture":
            return max(1, min(self.parse_weight, int((percentage / 100) * self.parse_weight)))
        if stage == "Analyzing events":
            return self.parse_weight + min(
                self.analyze_weight,
                int((percentage / 100) * self.analyze_weight),
            )
        return percentage

    def _emit(self, update: LoadingUpdate, *, force: bool) -> None:
        percentage = update.percentage
        if not force and percentage == self.last_emitted_percentage:
            return
        self.callback(update)
        self.last_emitted_percentage = percentage


def load_report(
    input_path: Path,
    *,
    progress_callback: Callable[[LoadingUpdate], None] | None = None,
) -> AnalysisReport:
    tracker = ProgressTracker(progress_callback)
    tracker.emit_stage("Opening capture", 0, 1)
    if input_path.suffix != ".dblens":
        raise ValueError("only .dblens captures are supported")

    bundle = read_bundle(input_path)
    parsed = parse_pcap_bytes(bundle.pcap_bytes)
    tracker.emit_stage("Parsing capture", 100, 100)

    event_total = max(len(parsed.events), 1)
    report = build_report(
        parsed.events,
        source_path=str(input_path),
        skipped_blocks=parsed.skipped_packets,
        snapshot_names=bundle.names,
        names_timeline=bundle.names_timeline,
        progress_callback=lambda current, total: tracker.emit_stage(
            "Analyzing events",
            current,
            max(total, event_total),
        ),
    )
    tracker.emit_stage("Preparing report", 1, 1)
    return report

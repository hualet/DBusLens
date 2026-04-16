from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Event:
    timestamp: float | None
    message_type: str
    sender: str | None
    destination: str | None
    path: str | None
    interface: str | None
    member: str | None
    serial: int | None
    reply_serial: int | None
    error_name: str | None

    @property
    def operation(self) -> str:
        if self.interface and self.member:
            return f"{self.interface}.{self.member}"
        if self.interface:
            return self.interface
        if self.member:
            return self.member
        return "<unknown>"


@dataclass(frozen=True)
class ParseResult:
    events: list[Event]
    skipped_packets: int

    @property
    def skipped_blocks(self) -> int:
        return self.skipped_packets


@dataclass(frozen=True)
class ProcessInfo:
    short_name: str
    pid: int | None

    @property
    def display_name(self) -> str:
        if self.pid is None:
            return self.short_name
        return f"{self.short_name} [{self.pid}]"


@dataclass(frozen=True)
class CaptureNameInfo:
    name: str
    owner: str | None
    pid: int | None
    uid: int | None
    cmdline: list[str] | None

    @property
    def display_name(self) -> str:
        if self.pid is None:
            return self.name
        return f"{self.name} [{self.pid}]"


@dataclass(frozen=True)
class DetailRow:
    name: str
    process: ProcessInfo | None
    count: int
    secondary: str | None = None


@dataclass(frozen=True)
class Row:
    name: str
    process: ProcessInfo | None
    count: int
    children: list[DetailRow]


@dataclass(frozen=True)
class ErrorDetail:
    caller: str
    caller_process: CaptureNameInfo | None
    target_process: CaptureNameInfo | None
    latency_ms: str
    notes: str
    count: int

    @property
    def owner_pid(self) -> int | None:
        if self.target_process is None:
            return None
        return self.target_process.pid

    @property
    def owner_label(self) -> str:
        if self.target_process is None:
            return "<unknown-target>"
        return self.target_process.display_name


@dataclass(frozen=True)
class ErrorSummary:
    error_name: str
    target: str
    operation: str
    count: int
    first_seen: float | None
    last_seen: float | None
    average_latency_ms: float | None
    retry_count: int
    unique_callers: int
    target_process: CaptureNameInfo | None
    details: list[ErrorDetail]

    @property
    def owner_label(self) -> str:
        if self.target_process is None:
            return self.target
        return self.target_process.display_name


@dataclass(frozen=True)
class AnalysisReport:
    source_path: str
    total_events: int
    actionable_events: int
    skipped_blocks: int
    outbound_rows: list[Row]
    inbound_rows: list[Row]
    error_rows: list[Row]
    error_summaries: list[ErrorSummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_path": self.source_path,
            "total_events": self.total_events,
            "actionable_events": self.actionable_events,
            "skipped_blocks": self.skipped_blocks,
            "outbound_rows": [asdict(row) for row in self.outbound_rows],
            "inbound_rows": [asdict(row) for row in self.inbound_rows],
            "error_rows": [asdict(row) for row in self.error_rows],
            "error_summaries": [asdict(summary) for summary in self.error_summaries],
        }

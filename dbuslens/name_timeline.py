from __future__ import annotations

from dataclasses import dataclass

from dbuslens.models import CaptureNameInfo


@dataclass(frozen=True)
class ResolvedName:
    raw_name: str | None
    display_name: str
    owner: str | None
    pid: int | None
    uid: int | None
    cmdline: list[str] | None


@dataclass(frozen=True)
class _TimelineEvent:
    timestamp: float
    name: str
    old_owner: str
    new_owner: str


class NameTimelineResolver:
    def __init__(
        self,
        *,
        snapshot_names: dict[str, CaptureNameInfo],
        initial_snapshot: dict[str, CaptureNameInfo],
        events: list[_TimelineEvent],
        final_snapshot: dict[str, CaptureNameInfo],
    ) -> None:
        self._snapshot_names = snapshot_names
        self._initial_snapshot = initial_snapshot
        self._events = sorted(events, key=lambda event: event.timestamp)
        self._final_snapshot = final_snapshot

    @classmethod
    def from_payload(
        cls,
        snapshot_names: dict[str, object] | None,
        names_timeline: dict[str, object] | None,
    ) -> NameTimelineResolver:
        snapshot_index = _build_snapshot_index(snapshot_names)
        timeline_index = _build_timeline_index(names_timeline)
        initial_snapshot_explicit = bool(
            isinstance(names_timeline, dict)
            and "initial_snapshot" in names_timeline
            and isinstance(names_timeline.get("initial_snapshot"), dict)
        )
        final_snapshot_explicit = bool(
            isinstance(names_timeline, dict)
            and "final_snapshot" in names_timeline
            and isinstance(names_timeline.get("final_snapshot"), dict)
        )
        initial_snapshot = (
            timeline_index["initial_snapshot"] if initial_snapshot_explicit else snapshot_index
        )
        final_snapshot = (
            timeline_index["final_snapshot"] if final_snapshot_explicit else snapshot_index
        )
        return cls(
            snapshot_names=snapshot_index,
            initial_snapshot=initial_snapshot,
            events=timeline_index["events"],
            final_snapshot=final_snapshot,
        )

    def resolve_name(self, raw_name: str | None, *, timestamp: float | None) -> ResolvedName:
        if not raw_name:
            return ResolvedName(
                raw_name=raw_name,
                display_name="<unknown>",
                owner=None,
                pid=None,
                uid=None,
                cmdline=None,
            )

        active_info = self._resolve_active_info(raw_name, timestamp)
        if active_info is None and timestamp is None:
            active_info = self._final_snapshot.get(raw_name)
        if active_info is None:
            return ResolvedName(
                raw_name=raw_name,
                display_name=raw_name,
                owner=None,
                pid=None,
                uid=None,
                cmdline=None,
            )

        metadata = self._resolve_metadata(active_info)
        if raw_name.startswith(":"):
            display_name = active_info.name
            owner = active_info.owner
        else:
            display_name = raw_name
            owner = active_info.owner

        return ResolvedName(
            raw_name=raw_name,
            display_name=display_name,
            owner=owner,
            pid=metadata.pid if metadata else None,
            uid=metadata.uid if metadata else None,
            cmdline=metadata.cmdline if metadata else None,
        )

    def _resolve_active_info(
        self,
        raw_name: str,
        timestamp: float | None,
    ) -> CaptureNameInfo | None:
        state = dict(self._initial_snapshot)
        owner_index = _build_owner_index(state)

        for event in self._events:
            if timestamp is not None and event.timestamp > timestamp:
                break
            self._apply_event(state, owner_index, event)

        if raw_name.startswith(":"):
            return owner_index.get(raw_name)
        return state.get(raw_name)

    def _apply_event(
        self,
        state: dict[str, CaptureNameInfo],
        owner_index: dict[str, CaptureNameInfo],
        event: _TimelineEvent,
    ) -> None:
        current = state.get(event.name)
        if current is not None and current.owner:
            owner_index.pop(current.owner, None)

        if event.old_owner:
            previous = owner_index.get(event.old_owner)
            if previous is not None and previous.name == event.name:
                owner_index.pop(event.old_owner, None)

        updated = CaptureNameInfo(
            name=event.name,
            owner=event.new_owner or None,
            pid=current.pid if current is not None else None,
            uid=current.uid if current is not None else None,
            cmdline=current.cmdline if current is not None else None,
        )
        state[event.name] = updated
        if updated.owner:
            owner_index[updated.owner] = updated
        elif current is not None and current.name in state:
            state[event.name] = CaptureNameInfo(
                name=current.name,
                owner=None,
                pid=current.pid,
                uid=current.uid,
                cmdline=current.cmdline,
            )

    def _resolve_metadata(self, info: CaptureNameInfo) -> CaptureNameInfo | None:
        candidates: list[CaptureNameInfo | None] = []
        if info.owner:
            candidates.extend(
                [
                    self._final_snapshot.get(info.owner),
                    self._initial_snapshot.get(info.owner),
                    self._snapshot_names.get(info.owner),
                ]
            )
        candidates.extend(
            [
                self._final_snapshot.get(info.name),
                self._initial_snapshot.get(info.name),
                self._snapshot_names.get(info.name),
            ]
        )

        for candidate in candidates:
            if candidate is not None:
                return candidate
        return None


def _build_timeline_index(
    names_timeline: dict[str, object] | None,
) -> dict[str, object]:
    if not isinstance(names_timeline, dict):
        return {"initial_snapshot": {}, "events": [], "final_snapshot": {}}

    initial_snapshot = _build_snapshot_index(names_timeline.get("initial_snapshot"))
    final_snapshot = _build_snapshot_index(names_timeline.get("final_snapshot"))
    raw_events = names_timeline.get("events")
    events: list[_TimelineEvent] = []
    if isinstance(raw_events, list):
        for entry in raw_events:
            if not isinstance(entry, dict):
                continue
            timestamp = entry.get("timestamp")
            name = entry.get("name")
            old_owner = entry.get("old_owner")
            new_owner = entry.get("new_owner")
            if not isinstance(timestamp, (int, float)):
                continue
            if not isinstance(name, str) or not name:
                continue
            if not isinstance(old_owner, str):
                old_owner = ""
            if not isinstance(new_owner, str):
                new_owner = ""
            events.append(
                _TimelineEvent(
                    timestamp=float(timestamp),
                    name=name,
                    old_owner=old_owner,
                    new_owner=new_owner,
                )
            )
    return {
        "initial_snapshot": initial_snapshot,
        "events": events,
        "final_snapshot": final_snapshot,
    }


def _build_snapshot_index(snapshot: dict[str, object] | None) -> dict[str, CaptureNameInfo]:
    if not isinstance(snapshot, dict):
        return {}

    raw_entries = snapshot.get("names")
    if not isinstance(raw_entries, list):
        return {}

    index: dict[str, CaptureNameInfo] = {}
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        info = _capture_name_info(entry)
        if info is None:
            continue
        index[info.name] = info
        if info.owner:
            index[info.owner] = info
    return index


def _build_owner_index(state: dict[str, CaptureNameInfo]) -> dict[str, CaptureNameInfo]:
    owner_index: dict[str, CaptureNameInfo] = {}
    for info in state.values():
        if info.owner:
            owner_index[info.owner] = info
    return owner_index


def _capture_name_info(entry: dict[str, object]) -> CaptureNameInfo | None:
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        return None

    owner = entry.get("owner")
    if owner is not None and not isinstance(owner, str):
        owner = None

    pid = entry.get("pid")
    if pid is not None and not isinstance(pid, int):
        pid = None

    uid = entry.get("uid")
    if uid is not None and not isinstance(uid, int):
        uid = None

    cmdline = entry.get("cmdline")
    if cmdline is not None and not isinstance(cmdline, list):
        cmdline = None
    elif isinstance(cmdline, list):
        cmdline = [part for part in cmdline if isinstance(part, str)] or None

    return CaptureNameInfo(
        name=name,
        owner=owner,
        pid=pid,
        uid=uid,
        cmdline=cmdline,
    )

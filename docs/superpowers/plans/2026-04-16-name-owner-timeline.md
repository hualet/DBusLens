# Name Owner Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add capture-time `NameOwnerChanged` timeline data to `.dblens` bundles and use it to resolve service names at event time in report analysis.

**Architecture:** Extend the bundle format with an optional `names_timeline.json` artifact, teach `record` to collect an initial snapshot, a best-effort timeline stream, and a final snapshot, then build a small time-aware resolver that the analyzer uses when producing `Errors`. Keep the first implementation narrow: timeline data is optional, fallback behavior remains snapshot-based, and UI changes stay limited to showing better labels in existing report views.

**Tech Stack:** Python 3.12, `unittest`, existing `dbus-monitor` / `gdbus` subprocess flow, zip-based `.dblens` bundles.

---

## File Map

- Modify: `dbuslens/bundle.py`
  - Extend bundle metadata/contents to support optional `names_timeline.json`.
- Modify: `dbuslens/record.py`
  - Capture initial snapshot, timeline events, and final snapshot, then write them into the bundle.
- Create: `dbuslens/name_timeline.py`
  - Define timeline parsing and event-time resolution helpers.
- Modify: `dbuslens/loading.py`
  - Load optional timeline payload and pass it into analysis.
- Modify: `dbuslens/analyzer.py`
  - Use the resolver when building error summaries and details.
- Modify: `dbuslens/models.py`
  - Add any minimal data structures needed to carry raw vs resolved names cleanly.
- Test: `tests/test_bundle.py`
  - Cover bundle round-trip with `names_timeline.json`.
- Test: `tests/test_loading.py`
  - Cover loading bundles with and without timeline payloads.
- Create: `tests/test_name_timeline.py`
  - Cover resolver behavior against synthetic timeline data.
- Modify: `tests/test_analyzer.py`
  - Cover analyzer behavior when timeline data resolves unique names missed by snapshots.
- Modify: `README.md`
  - Note that newer `.dblens` captures include ownership timeline metadata for better name resolution.
- Modify: `docs/dblens-format.md`
  - Document `names_timeline.json` structure and optionality.

### Task 1: Extend Bundle IO For Optional Timeline Data

**Files:**
- Modify: `dbuslens/bundle.py`
- Test: `tests/test_bundle.py`
- Test: `tests/test_loading.py`

- [ ] **Step 1: Write the failing bundle round-trip test**

Add a test alongside the existing bundle tests that proves `names_timeline.json` survives a write/read cycle:

```python
def test_write_and_read_bundle_preserves_names_timeline(self) -> None:
    metadata = BundleMetadata(
        bundle_version=1,
        created_at="2026-04-16T10:20:30+08:00",
        bus="session",
        duration_seconds=10,
        capture_files={
            "pcap": "capture.cap",
            "profile": "capture.profile",
            "names": "names.json",
            "names_timeline": "names_timeline.json",
        },
        monitor={
            "command": ["dbus-monitor", "--session", "--pcap"],
            "profile_command": ["dbus-monitor", "--session", "--profile"],
            "stderr": "",
            "mode": "monitor",
        },
    )
    expected_timeline = {
        "bus": "session",
        "started_at": "2026-04-16T10:20:30+08:00",
        "ended_at": "2026-04-16T10:20:40+08:00",
        "initial_snapshot": {"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
        "events": [{"timestamp": 1713243600.5, "name": "org.example.Service", "old_owner": "", "new_owner": ":1.42"}],
        "final_snapshot": {"captured_at": "2026-04-16T10:20:40+08:00", "bus": "session", "names": []},
        "error": None,
    }
```

- [ ] **Step 2: Run the targeted test to confirm the failure**

Run:

```bash
./.venv/bin/python -m unittest tests.test_bundle.BundleRoundTripTests.test_write_and_read_bundle_preserves_names_timeline -v
```

Expected: FAIL because `BundleContents` and `read_bundle()` do not yet carry `names_timeline`.

- [ ] **Step 3: Implement optional timeline support in bundle IO**

Update the bundle dataclass and read/write helpers so timeline data is preserved when present and absent when not:

```python
@dataclass(frozen=True)
class BundleContents:
    metadata: BundleMetadata
    pcap_bytes: bytes
    profile_text: str
    names: dict[str, Any]
    names_timeline: dict[str, Any] | None = None


def write_bundle(path: Path, contents: BundleContents) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("meta.json", json.dumps(contents.metadata.to_dict(), indent=2, sort_keys=True))
        archive.writestr(contents.metadata.capture_files["pcap"], contents.pcap_bytes)
        archive.writestr(contents.metadata.capture_files["profile"], contents.profile_text)
        archive.writestr(contents.metadata.capture_files["names"], json.dumps(contents.names, indent=2, sort_keys=True))
        if "names_timeline" in contents.metadata.capture_files and contents.names_timeline is not None:
        archive.writestr(
            contents.metadata.capture_files["names_timeline"],
            json.dumps(contents.names_timeline, indent=2, sort_keys=True),
        )


def read_bundle(path: Path) -> BundleContents:
    with zipfile.ZipFile(path, "r") as archive:
        metadata = BundleMetadata.from_dict(json.loads(archive.read("meta.json")))
        pcap_bytes = archive.read(metadata.capture_files["pcap"])
        profile_text = archive.read(metadata.capture_files["profile"]).decode("utf-8", "replace")
        names = json.loads(archive.read(metadata.capture_files["names"]))
        timeline_path = metadata.capture_files.get("names_timeline")
        names_timeline = None
        if timeline_path and timeline_path in archive.namelist():
            names_timeline = json.loads(archive.read(timeline_path))
    return BundleContents(
        metadata=metadata,
        pcap_bytes=pcap_bytes,
        profile_text=profile_text,
        names=names,
        names_timeline=names_timeline,
    )
```

- [ ] **Step 4: Add loading coverage for optional timeline bundles**

Add a loading test that proves `load_report()` still accepts bundles without a timeline entry and can open bundles that contain one:

```python
def test_load_report_accepts_bundle_with_names_timeline(self) -> None:
    bundle = BundleContents(
        metadata=BundleMetadata(
            bundle_version=1,
            created_at="2026-04-16T10:20:30+08:00",
            bus="session",
            duration_seconds=10,
            capture_files={
                "pcap": "capture.cap",
                "profile": "capture.profile",
                "names": "names.json",
                "names_timeline": "names_timeline.json",
            },
            monitor={
                "command": ["dbus-monitor", "--session", "--pcap"],
                "profile_command": ["dbus-monitor", "--session", "--profile"],
                "stderr": "",
                "mode": "monitor",
            },
        ),
        pcap_bytes=capture,
        profile_text="",
        names=snapshot,
        names_timeline=timeline,
    )
```

- [ ] **Step 5: Run the bundle and loading tests**

Run:

```bash
./.venv/bin/python -m unittest tests.test_bundle tests.test_loading -v
```

Expected: PASS with timeline-aware bundle round-trip coverage in place.

- [ ] **Step 6: Commit**

```bash
git add dbuslens/bundle.py tests/test_bundle.py tests/test_loading.py
git commit -m "feat(bundle): support optional name timeline data" -m "Extend .dblens bundle IO to read and write an optional names_timeline.json artifact while preserving compatibility with older bundles.\n\nVerified with targeted unittest coverage for bundle round-trip and report loading."
```

### Task 2: Capture Initial Snapshot, Timeline Events, And Final Snapshot

**Files:**
- Modify: `dbuslens/record.py`
- Test: `tests/test_bundle.py`

- [ ] **Step 1: Write failing tests for timeline capture helpers**

Add tests around small helper functions instead of trying to test the full record command at once:

```python
def test_parse_name_owner_changed_line_extracts_fields(self) -> None:
    line = "signal time=1713243600.500 sender=org.freedesktop.DBus -> destination=(null destination) serial=4 path=/org/freedesktop/DBus; interface=org.freedesktop.DBus; member=NameOwnerChanged string 'org.example.Service' string '' string ':1.42'"
    self.assertEqual(
        _parse_name_owner_changed_line(line),
        {
            "timestamp": 1713243600.5,
            "name": "org.example.Service",
            "old_owner": "",
            "new_owner": ":1.42",
        },
    )


def test_build_names_timeline_document_records_initial_events_and_final_snapshot(self) -> None:
    timeline = _build_names_timeline(
        bus="session",
        started_at="2026-04-16T10:20:30+08:00",
        ended_at="2026-04-16T10:20:40+08:00",
        initial_snapshot={"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
        lines=[
            "signal time=1713243600.500 sender=org.freedesktop.DBus -> destination=(null destination) serial=4 path=/org/freedesktop/DBus; interface=org.freedesktop.DBus; member=NameOwnerChanged string 'org.example.Service' string '' string ':1.42'"
        ],
        final_snapshot={"captured_at": "2026-04-16T10:20:40+08:00", "bus": "session", "names": []},
        error=None,
    )
    self.assertEqual(timeline["events"][0]["new_owner"], ":1.42")
```

- [ ] **Step 2: Run the targeted record tests to verify they fail**

Run:

```bash
./.venv/bin/python -m unittest tests.test_bundle.BundleRoundTripTests.test_parse_name_owner_changed_line_extracts_fields tests.test_bundle.BundleRoundTripTests.test_build_names_timeline_document_records_initial_events_and_final_snapshot -v
```

Expected: FAIL because the helper functions do not yet exist.

- [ ] **Step 3: Add narrow timeline capture helpers in `record.py`**

Implement helpers that keep timeline collection isolated from the main pcap/profile path:

```python
def _parse_name_owner_changed_line(line: str) -> dict[str, object] | None:
    if "member=NameOwnerChanged" not in line:
        return None
    match = re.search(r"time=(?P<timestamp>\\d+(?:\\.\\d+)?)", line)
    string_values = re.findall(r"string '([^']*)'", line)
    if match is None or len(string_values) < 3:
        return None
    timestamp = float(match.group("timestamp"))
    name, old_owner, new_owner = string_values[:3]
    return {
        "timestamp": timestamp,
        "name": name,
        "old_owner": old_owner,
        "new_owner": new_owner,
    }


def _build_names_timeline(
    *,
    bus: str,
    started_at: str,
    ended_at: str,
    initial_snapshot: dict[str, Any],
    lines: list[str],
    final_snapshot: dict[str, Any],
    error: str | None,
) -> dict[str, Any]:
    return {
        "bus": bus,
        "started_at": started_at,
        "ended_at": ended_at,
        "initial_snapshot": initial_snapshot,
        "events": [event for line in lines if (event := _parse_name_owner_changed_line(line)) is not None],
        "final_snapshot": final_snapshot,
        "error": error,
    }
```

- [ ] **Step 4: Wire timeline capture into the bundle assembly path**

Update `record.py` so it creates the timeline payload around the existing monitors:

```python
initial_snapshot = _capture_names(bus)
timeline_stdout, timeline_stderr, _ = _run_monitor(_build_timeline_command(bus), duration)
final_snapshot = _capture_names(bus)
names_timeline = _build_names_timeline(
    bus=bus,
    started_at=started_at_iso,
    ended_at=ended_at_iso,
    initial_snapshot=initial_snapshot,
    lines=timeline_stdout.decode("utf-8", "replace").splitlines(),
    final_snapshot=final_snapshot,
    error=(timeline_stderr.decode("utf-8", "replace").strip() or None),
)
```

And write it into the bundle metadata:

```python
capture_files={
    "pcap": "capture.cap",
    "profile": "capture.profile",
    "names": "names.json",
    "names_timeline": "names_timeline.json",
}
```

- [ ] **Step 5: Run record-related tests**

Run:

```bash
./.venv/bin/python -m unittest tests.test_bundle -v
```

Expected: PASS with helper coverage and bundle metadata now including timeline data.

- [ ] **Step 6: Commit**

```bash
git add dbuslens/record.py tests/test_bundle.py
git commit -m "feat(record): capture name owner timeline" -m "Record initial and final name snapshots plus NameOwnerChanged events into names_timeline.json inside .dblens bundles.\n\nVerified with unittest coverage for timeline parsing, timeline document assembly, and record bundle output."
```

### Task 3: Add A Time-Aware Name Resolver

**Files:**
- Create: `dbuslens/name_timeline.py`
- Test: `tests/test_name_timeline.py`

- [ ] **Step 1: Write failing resolver tests**

Create focused resolver tests that exercise event-time lookups without involving the analyzer yet:

```python
def test_resolve_unique_name_to_well_known_alias_at_event_time(self) -> None:
    resolver = NameTimelineResolver.from_payload(
        {
            "initial_snapshot": {
                "captured_at": "2026-04-16T10:20:30+08:00",
                "bus": "session",
                "names": [{"name": "org.example.Service", "owner": ":1.42", "pid": 4242, "uid": 1000, "cmdline": ["/bin/service"], "error": None}],
            },
            "events": [],
            "final_snapshot": {"captured_at": "2026-04-16T10:20:40+08:00", "bus": "session", "names": []},
            "error": None,
        }
    )
    resolved = resolver.resolve_name(":1.42", timestamp=1713243600.5)
    self.assertEqual(resolved.display_name, "org.example.Service")
    self.assertEqual(resolved.pid, 4242)


def test_resolve_name_uses_timeline_for_short_lived_client(self) -> None:
    resolver = NameTimelineResolver.from_payload(
        {"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
        {
            "bus": "session",
            "started_at": "2026-04-16T10:20:30+08:00",
            "ended_at": "2026-04-16T10:20:40+08:00",
            "initial_snapshot": {"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
            "events": [{"timestamp": 1713243604.0, "name": "org.example.ShortLived", "old_owner": "", "new_owner": ":1.99"}],
            "final_snapshot": {
                "captured_at": "2026-04-16T10:20:40+08:00",
                "bus": "session",
                "names": [{"name": "org.example.ShortLived", "owner": ":1.99", "pid": 9900, "uid": 1000, "cmdline": ["/bin/short-lived"], "error": None}],
            },
            "error": None,
        },
    )
    resolved = resolver.resolve_name(":1.99", timestamp=1713243605.0)
    self.assertEqual(resolved.display_name, "org.example.ShortLived")
```

- [ ] **Step 2: Run the resolver tests to confirm the failure**

Run:

```bash
./.venv/bin/python -m unittest tests.test_name_timeline -v
```

Expected: FAIL because the resolver module does not exist yet.

- [ ] **Step 3: Implement the resolver module**

Create a focused resolver with explicit raw vs resolved values:

```python
@dataclass(frozen=True)
class ResolvedName:
    raw_name: str | None
    display_name: str
    owner: str | None
    pid: int | None
    uid: int | None
    cmdline: list[str] | None


class NameTimelineResolver:
    @classmethod
    def from_payload(
        cls,
        snapshot_names: dict[str, object] | None,
        names_timeline: dict[str, object] | None,
    ) -> "NameTimelineResolver":
        initial_snapshot = names_timeline.get("initial_snapshot") if isinstance(names_timeline, dict) else None
        final_snapshot = names_timeline.get("final_snapshot") if isinstance(names_timeline, dict) else None
        events = names_timeline.get("events") if isinstance(names_timeline, dict) else None
        return cls(
            snapshot_names=snapshot_names or {},
            initial_snapshot=initial_snapshot if isinstance(initial_snapshot, dict) else {},
            events=events if isinstance(events, list) else [],
            final_snapshot=final_snapshot if isinstance(final_snapshot, dict) else {},
        )

    def resolve_name(self, raw_name: str | None, *, timestamp: float | None) -> ResolvedName:
        if not raw_name:
            return ResolvedName(raw_name=raw_name, display_name="<unknown>", owner=None, pid=None, uid=None, cmdline=None)
        alias = self._resolve_alias(raw_name, timestamp)
        metadata = self._resolve_metadata(alias, raw_name)
        return ResolvedName(
            raw_name=raw_name,
            display_name=alias,
            owner=metadata.owner if metadata else None,
            pid=metadata.pid if metadata else None,
            uid=metadata.uid if metadata else None,
            cmdline=metadata.cmdline if metadata else None,
        )
```

The implementation should:

- seed alias state from `initial_snapshot`
- apply `events` in timestamp order
- use `final_snapshot` as fallback metadata
- return the raw unique name untouched when nothing matches

- [ ] **Step 4: Add edge-case tests for disappearance and missing timeline data**

Expand `tests/test_name_timeline.py` with at least these cases:

```python
def test_resolve_name_keeps_raw_value_when_no_mapping_exists(self) -> None:
    resolver = NameTimelineResolver.from_payload(
        {"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
        None,
    )
    resolved = resolver.resolve_name(":1.404", timestamp=1713243600.5)
    self.assertEqual(resolved.display_name, ":1.404")


def test_resolve_name_handles_owner_disappearance(self) -> None:
    resolver = NameTimelineResolver.from_payload(
        {"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
        {
            "bus": "session",
            "started_at": "2026-04-16T10:20:30+08:00",
            "ended_at": "2026-04-16T10:20:40+08:00",
            "initial_snapshot": {
                "captured_at": "2026-04-16T10:20:30+08:00",
                "bus": "session",
                "names": [{"name": "org.example.Service", "owner": ":1.42", "pid": 4242, "uid": 1000, "cmdline": ["/bin/service"], "error": None}],
            },
            "events": [{"timestamp": 1713243602.0, "name": "org.example.Service", "old_owner": ":1.42", "new_owner": ""}],
            "final_snapshot": {"captured_at": "2026-04-16T10:20:40+08:00", "bus": "session", "names": []},
            "error": None,
        },
    )
    resolved = resolver.resolve_name(":1.42", timestamp=1713243603.0)
    self.assertEqual(resolved.display_name, ":1.42")
```

- [ ] **Step 5: Run the resolver test file**

Run:

```bash
./.venv/bin/python -m unittest tests.test_name_timeline -v
```

Expected: PASS with deterministic coverage for baseline names, new names, owner changes, and fallback.

- [ ] **Step 6: Commit**

```bash
git add dbuslens/name_timeline.py tests/test_name_timeline.py
git commit -m "feat(analyzer): add name owner timeline resolver" -m "Introduce a small time-aware resolver that combines snapshot and names_timeline.json data to resolve service labels at event time.\n\nVerified with focused unittest coverage for baseline aliases, short-lived clients, owner disappearance, and raw-name fallback."
```

### Task 4: Use The Resolver In Report Loading And Error Analysis

**Files:**
- Modify: `dbuslens/loading.py`
- Modify: `dbuslens/analyzer.py`
- Modify: `dbuslens/models.py`
- Test: `tests/test_loading.py`
- Test: `tests/test_analyzer.py`

- [ ] **Step 1: Write failing analyzer tests for timeline-backed resolution**

Add tests that prove the analyzer improves `Errors` when the initial snapshot misses a short-lived client:

```python
def test_build_report_resolves_error_caller_via_name_timeline(self) -> None:
    events = [
        Event(timestamp=10.0, message_type="method_call", sender=":1.99", destination="org.example.Service", path="/org/example/Demo", interface="org.example.Demo", member="Ping", serial=7, reply_serial=None, error_name=None),
        Event(timestamp=10.2, message_type="error", sender="org.example.Service", destination=":1.99", path=None, interface=None, member=None, serial=8, reply_serial=7, error_name="org.example.Error.Failed"),
    ]
    report = build_report(
        events,
        snapshot_names={"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
        names_timeline={
            "bus": "session",
            "started_at": "2026-04-16T10:20:30+08:00",
            "ended_at": "2026-04-16T10:20:40+08:00",
            "initial_snapshot": {"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
            "events": [{"timestamp": 9.9, "name": "org.example.ShortLived", "old_owner": "", "new_owner": ":1.99"}],
            "final_snapshot": {
                "captured_at": "2026-04-16T10:20:40+08:00",
                "bus": "session",
                "names": [{"name": "org.example.ShortLived", "owner": ":1.99", "pid": 9900, "uid": 1000, "cmdline": ["/bin/short-lived"], "error": None}],
            },
            "error": None,
        },
        resolve_process=lambda _: None,
    )
    self.assertEqual(report.error_summaries[0].details[0].caller, "org.example.ShortLived")
```

- [ ] **Step 2: Run the targeted analyzer tests to verify they fail**

Run:

```bash
./.venv/bin/python -m unittest tests.test_analyzer -v
```

Expected: FAIL because `build_report()` does not accept timeline data yet.

- [ ] **Step 3: Thread timeline payload through loading and analysis**

Update signatures first:

```python
def load_report(
    input_path: Path,
    *,
    progress_callback: Callable[[LoadingUpdate], None] | None = None,
) -> AnalysisReport:
    tracker = ProgressTracker(progress_callback)
    tracker.emit_stage("Opening capture", 0, 1)
    bundle = read_bundle(input_path)
    parsed = parse_pcap_bytes(bundle.pcap_bytes)
    report = build_report(
        parsed.events,
        source_path=str(input_path),
        skipped_blocks=parsed.skipped_packets,
        snapshot_names=bundle.names,
        names_timeline=bundle.names_timeline,
        progress_callback=lambda current, total: tracker.emit_stage("Analyzing events", current, total),
    )


def build_report(
    events: list[Event],
    *,
    source_path: str = "<memory>",
    skipped_blocks: int = 0,
    snapshot_names: dict[str, object] | None = None,
    names_timeline: dict[str, object] | None = None,
    resolve_process: Callable[[str], ProcessInfo | None] = resolve_process_name,
    progress_callback: Callable[[int, int], None] | None = None,
) -> AnalysisReport:
    resolver = NameTimelineResolver.from_payload(snapshot_names, names_timeline)
    call_index = _build_call_index(events)
    error_summaries = _build_error_summaries(
        events,
        call_index,
        snapshot_index=_build_snapshot_index(snapshot_names),
        resolver=resolver,
    )
```

- [ ] **Step 4: Replace snapshot-only error label resolution with resolver-backed labels**

Keep the existing error matching logic but resolve labels with event timestamps:

```python
target_resolved = resolver.resolve_name(target_source, timestamp=event.timestamp)
caller_resolved = resolver.resolve_name(caller_source, timestamp=event.timestamp)

detail = ErrorDetail(
    caller=caller_resolved.display_name,
    caller_process=_capture_name_info_from_resolved(caller_resolved),
    target_process=_capture_name_info_from_resolved(target_resolved),
    destination=target_resolved.display_name,
    notes=_join_notes(
        existing_notes,
        f"raw={caller_resolved.raw_name}" if caller_resolved.raw_name != caller_resolved.display_name else "",
    ),
    latency_ms=_format_latency_ms(latency_ms),
    count=1,
    timestamp=event.timestamp,
    destination=target_resolved.display_name,
    member=original.member if original and original.member else UNKNOWN_OPERATION,
    path=original.path if original and original.path else "-",
    args_preview=original.body_preview if original and original.body_preview else "not captured",
)
```

Minimal model helper if needed:

```python
def _capture_name_info_from_resolved(resolved: ResolvedName) -> CaptureNameInfo | None:
    if resolved.pid is None and resolved.display_name == resolved.raw_name:
        return None
    return CaptureNameInfo(
        name=resolved.display_name,
        owner=resolved.owner,
        pid=resolved.pid,
        uid=resolved.uid,
        cmdline=resolved.cmdline,
    )
```

- [ ] **Step 5: Run loading and analyzer tests**

Run:

```bash
./.venv/bin/python -m unittest tests.test_loading tests.test_analyzer -v
```

Expected: PASS with timeline-aware loading and `Errors` now preferring event-time-resolved labels.

- [ ] **Step 6: Commit**

```bash
git add dbuslens/loading.py dbuslens/analyzer.py dbuslens/models.py tests/test_loading.py tests/test_analyzer.py
git commit -m "feat(report): resolve names with owner timeline" -m "Pass names_timeline.json through report loading and use a time-aware resolver when building error summaries and details.\n\nVerified with unittest coverage for loading bundles with timeline data and resolving short-lived callers during error analysis."
```

### Task 5: Document The New Artifact And Run Full Verification

**Files:**
- Modify: `docs/dblens-format.md`
- Modify: `README.md`

- [ ] **Step 1: Update the bundle format document**

Document the new optional artifact and fallback semantics in `docs/dblens-format.md`:

```md
### `names_timeline.json`

Optional ownership history captured during `record`.

- `initial_snapshot`: enriched snapshot at capture start
- `events`: `org.freedesktop.DBus.NameOwnerChanged` entries
- `final_snapshot`: enriched snapshot at capture end
- `error`: best-effort capture failure detail, if timeline collection failed

Report analysis uses this artifact to resolve unique names at event time. Older bundles may omit it.
```

- [ ] **Step 2: Update the README usage notes**

Add a short note in the report or format section:

```md
Recent `.dblens` captures also embed ownership timeline metadata, which helps `report` resolve
short-lived D-Bus unique names back to service labels and process context.
```

- [ ] **Step 3: Run the full test suite**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 4: Run the CLI help check**

Run:

```bash
./.venv/bin/python -m dbuslens --help
```

Expected: PASS with the normal CLI help text.

- [ ] **Step 5: Review the worktree for the final diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: only the intended implementation files, tests, and docs remain modified.

- [ ] **Step 6: Commit**

```bash
git add docs/dblens-format.md README.md
git commit -m "docs: describe name owner timeline bundles" -m "Document the optional names_timeline.json artifact and explain how it improves event-time name resolution in report output.\n\nVerified with the full unittest suite and dbuslens CLI help."
```

## Self-Review

- Spec coverage:
  - `names_timeline.json` bundle artifact: Task 1, Task 2
  - initial/timeline/final capture flow: Task 2
  - time-aware resolver: Task 3
  - analyzer integration for `Errors`: Task 4
  - docs and fallback behavior: Task 1, Task 4, Task 5
- Placeholder scan:
  - No `TODO`, `TBD`, or deferred implementation markers remain in task steps.
- Type consistency:
  - `names_timeline` is used consistently as the optional bundle payload name.
  - Resolver entry point is consistently `NameTimelineResolver.from_payload(snapshot_names, names_timeline)`.
  - Analyzer and loader both use the same `names_timeline` keyword.

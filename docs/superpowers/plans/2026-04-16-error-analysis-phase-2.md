# DBusLens Error Analysis Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich `.dblens` captures with capture-time name/process context, build transaction-oriented error diagnostics, and upgrade the existing `Errors` view to expose actionable failure details.

**Architecture:** Keep the current three-view TUI and preserve existing outbound/inbound aggregation. Add bundle snapshot parsing plus dedicated error summary/detail data structures so the analyzer can model failures without forcing all error data through the generic row shape.

**Tech Stack:** Python 3.12, `unittest`, `zipfile`, `json`, Textual, existing D-Bus parser and analyzer pipeline

---

### Task 1: Add failing tests for enriched capture-time snapshots

**Files:**
- Modify: `tests/test_bundle.py`
- Modify: `tests/test_loading.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add a failing bundle round-trip test for enriched `names.json`**

Add a test that writes a bundle with one snapshot entry containing `name`, `owner`, `pid`, `uid`, `cmdline`, and `error`, then confirms `read_bundle()` preserves the structure exactly.

```python
def test_write_and_read_bundle_preserves_snapshot_fields(self) -> None:
    metadata = BundleMetadata(
        bundle_version=1,
        created_at="2026-04-16T10:20:30+08:00",
        bus="session",
        duration_seconds=10,
        capture_files={
            "pcap": "capture.cap",
            "profile": "capture.profile",
            "names": "names.json",
        },
        monitor={
            "command": ["dbus-monitor", "--session", "--pcap"],
            "profile_command": ["dbus-monitor", "--session", "--profile"],
            "stderr": "",
            "mode": "monitor",
        },
    )
    contents = BundleContents(
        metadata=metadata,
        pcap_bytes=b"pcap-bytes",
        profile_text="profile",
        names={
            "captured_at": "2026-04-16T10:20:31+08:00",
            "bus": "session",
            "names": [
                {
                    "name": "org.example.Service",
                    "owner": ":1.42",
                    "pid": 4242,
                    "uid": 1000,
                    "cmdline": ["/usr/bin/example-service", "--session"],
                    "error": None,
                }
            ],
        },
    )
```

- [ ] **Step 2: Add a failing loading test for snapshot presence**

Extend `tests/test_loading.py` so the bundle fixture includes the enriched `names.json` shape with `bus` and one snapshot entry. Keep the existing assertion on `report.total_events`, then add a check that loading the bundle still succeeds with the richer snapshot document.

```python
self.assertEqual(report.total_events, 1)
self.assertEqual(report.source_path, str(path))
```

- [ ] **Step 3: Run the targeted tests to verify the new expectations fail for the right reason**

Run:

```bash
./.venv/bin/python -m unittest tests.test_bundle tests.test_loading -v
```

Expected:

- one or more failures caused by missing snapshot enrichment support, not import or syntax errors

### Task 2: Implement enriched `names.json` collection and bundle support

**Files:**
- Modify: `dbuslens/record.py`
- Modify: `dbuslens/bundle.py`
- Test: `tests/test_bundle.py`
- Test: `tests/test_loading.py`

- [ ] **Step 1: Introduce snapshot helper functions in `dbuslens/record.py`**

Add small helpers that query:

- `ListNames`
- `GetNameOwner`
- `GetConnectionUnixProcessID`
- `/proc/<pid>/cmdline`
- `uid` from `/proc/<pid>/status` when available

Keep missing values non-fatal by returning `None` or an `error` string per entry.

```python
def _lookup_name_owner(gdbus_path: str, bus: str, name: str) -> tuple[str | None, str | None]:
    ...

def _lookup_name_pid(gdbus_path: str, bus: str, owner: str) -> tuple[int | None, str | None]:
    ...

def _read_process_details(pid: int | None) -> tuple[int | None, list[str] | None]:
    ...
```

- [ ] **Step 2: Replace the flat snapshot with enriched per-name records**

Change `_capture_names()` to return this shape:

```python
{
    "captured_at": datetime.now().astimezone().isoformat(),
    "bus": bus,
    "names": [
        {
            "name": "org.example.Service",
            "owner": ":1.42",
            "pid": 4242,
            "uid": 1000,
            "cmdline": ["/usr/bin/example-service", "--session"],
            "error": None,
        }
    ],
}
```

When a lookup step fails, keep the entry and set `error` to a short literal string.

- [ ] **Step 3: Re-run the targeted tests and confirm they pass**

Run:

```bash
./.venv/bin/python -m unittest tests.test_bundle tests.test_loading -v
```

Expected:

- all targeted bundle and loading tests pass

### Task 3: Add failing analyzer tests for error transactions and retry summaries

**Files:**
- Modify: `tests/test_analyzer.py`
- Modify: `tests/test_textual_app.py`

- [ ] **Step 1: Add a failing analyzer test for grouped error diagnostics**

Add a synthetic event sequence with:

- two `method_call` events from the same caller to the same destination and operation
- two matching `error` replies

Assert that the resulting error diagnostics expose:

- one aggregated error bucket
- the failed destination
- the failed operation
- the first and last timestamps
- a retry count greater than zero

Use this event fixture shape:

```python
events = [
    Event(
        timestamp=1.0,
        message_type="method_call",
        sender=":1.10",
        destination="org.example.Service",
        path="/org/example/Demo",
        interface="org.example.Demo",
        member="Ping",
        serial=7,
        reply_serial=None,
        error_name=None,
    ),
    Event(
        timestamp=1.2,
        message_type="error",
        sender="org.example.Service",
        destination=":1.10",
        path=None,
        interface=None,
        member=None,
        serial=8,
        reply_serial=7,
        error_name="org.example.Error.Failed",
    ),
    ...
]
```

- [ ] **Step 2: Add a failing report-app test for the upgraded `Errors` columns**

Update `tests/test_textual_app.py` so `main_columns(state)` in `errors` mode is expected to return:

```python
("Count", "Error", "Target", "Operation")
```

Then update `detail_columns(state)` to expect:

```python
("Count", "Caller", "Process", "Owner/PID", "Latency", "Notes")
```

- [ ] **Step 3: Run the targeted tests and verify they fail because the analyzer/UI still use the old error model**

Run:

```bash
./.venv/bin/python -m unittest tests.test_analyzer tests.test_textual_app -v
```

Expected:

- failures in error-related assertions only

### Task 4: Implement dedicated error diagnostic data structures

**Files:**
- Modify: `dbuslens/models.py`
- Modify: `dbuslens/analyzer.py`
- Test: `tests/test_analyzer.py`

- [ ] **Step 1: Add explicit error diagnostic dataclasses**

Extend `dbuslens/models.py` with dedicated error structures instead of overloading `Row`.

Add:

```python
@dataclass(frozen=True)
class ErrorDetail:
    caller: str
    process: ProcessInfo | None
    owner_pid: str
    latency_ms: str
    notes: str
    count: int


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
    owner_label: str
    details: list[ErrorDetail]
```

Then add `error_summaries: list[ErrorSummary]` to `AnalysisReport` while keeping `error_rows` available temporarily until the TUI migration is complete.

- [ ] **Step 2: Implement call-to-error matching and diagnostic aggregation in `dbuslens/analyzer.py`**

Add a dedicated error-analysis path:

- index `method_call` events by `(sender, destination, serial)`
- resolve each `error` back to its original call
- compute `latency_ms = (error.timestamp - call.timestamp) * 1000`
- aggregate by `(error_name, destination, operation)`
- compute:
  - `count`
  - `first_seen`
  - `last_seen`
  - `average_latency_ms`
  - `retry_count` using a 5-second window
  - `unique_callers`

Use a helper outline like:

```python
def _build_error_summaries(
    events: list[Event],
    service_name_for: Callable[[str], str],
    resolve_process: Callable[[str], ProcessInfo | None],
) -> list[ErrorSummary]:
    ...
```

- [ ] **Step 3: Re-run analyzer tests and confirm the new diagnostic model passes**

Run:

```bash
./.venv/bin/python -m unittest tests.test_analyzer -v
```

Expected:

- analyzer tests pass with the new error diagnostics

### Task 5: Upgrade report app helpers for the richer `Errors` view

**Files:**
- Modify: `dbuslens/report_app.py`
- Modify: `tests/test_textual_app.py`
- Modify: `tests/test_tui.py`

- [ ] **Step 1: Switch `Errors` view helpers to use `report.error_summaries`**

Update:

- `main_columns()`
- `main_rows()`
- `main_column_widths()`
- `detail_lines()`
- `detail_columns()`
- `detail_rows()`
- `detail_column_widths()`

When `active_view == "errors"`, use `report.error_summaries` instead of generic rows.

Example outputs:

```python
("3", "org.example.Error.Failed", "org.example.Service", "org.example.Demo.Ping")
```

and:

```python
[
    "Selected: org.example.Error.Failed",
    "Target: org.example.Service",
    "Operation: org.example.Demo.Ping",
    "Count: 3",
    "First seen: 1.00s",
    "Last seen: 4.20s",
    "Avg latency: 12.3 ms",
    "Retries: 2",
    "Callers: 1",
    "Owner: example-service [4242]",
]
```

- [ ] **Step 2: Update TUI expectations for the new error layout**

Adjust `tests/test_tui.py` so:

- the main `Errors` table expects four columns
- the detail table expects six columns
- the detail pane assertions look for target, latency, retries, and owner summary lines

- [ ] **Step 3: Re-run UI-focused tests and confirm pass**

Run:

```bash
./.venv/bin/python -m unittest tests.test_textual_app tests.test_tui -v
```

Expected:

- report-app and TUI tests pass with the richer `Errors` view

### Task 6: Remove the temporary legacy error row path and document the phase 2 behavior

**Files:**
- Modify: `dbuslens/models.py`
- Modify: `dbuslens/analyzer.py`
- Modify: `README.md`
- Modify: `docs/dblens-format.md`

- [ ] **Step 1: Remove or stop using the generic `error_rows` path**

Once the TUI is fully migrated to `error_summaries`, simplify `AnalysisReport` and `to_dict()` so error diagnostics are exported through the new dedicated structures only.

- [ ] **Step 2: Update docs to describe the richer diagnostics**

Add a short section to `README.md` under operation or highlights:

```markdown
- `.dblens` bundles store capture-time snapshots used to explain error targets and owners
- `Errors` view groups failures by error, target, and operation
```

Update `docs/dblens-format.md` so `names.json` documents the richer snapshot fields:

```json
{
  "name": "org.example.Service",
  "owner": ":1.42",
  "pid": 4242,
  "uid": 1000,
  "cmdline": ["/usr/bin/example-service", "--session"],
  "error": null
}
```

- [ ] **Step 3: Re-run the full verification suite**

Run:

```bash
./.venv/bin/python -m unittest discover -s tests -v
./.venv/bin/python -m dbuslens --help
```

Expected:

- full test suite passes
- CLI help exits with status `0`

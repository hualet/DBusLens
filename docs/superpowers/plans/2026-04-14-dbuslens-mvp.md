# DBusLens MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python MVP that records `dbus-monitor` output to disk, parses offline logs, computes outbound and inbound rankings, and shows them in a curses TUI.

**Architecture:** Keep the system as a small standard-library-first Python package. Separate capture, parsing, aggregation, CLI wiring, and TUI state so the parser and analyzer can be tested without terminal dependencies.

**Tech Stack:** Python 3, `argparse`, `subprocess`, `pathlib`, `json`, `dataclasses`, `curses`, `unittest`

---

### Task 1: Create package skeleton and parser/analyzer tests

**Files:**
- Create: `dbuslens/__init__.py`
- Create: `tests/test_parser.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: Write the failing parser test**

```python
def test_parse_blocks_extracts_actionable_fields():
    raw = SAMPLE_METHOD_CALL + "\n\n" + SAMPLE_SIGNAL + "\n"
    result = parse_events(raw)
    self.assertEqual(len(result.events), 2)
    self.assertEqual(result.events[0].message_type, "method_call")
    self.assertEqual(result.events[0].operation, "org.example.Demo.Ping")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_parser -v`
Expected: FAIL because `parse_events` does not exist yet

- [ ] **Step 3: Write the failing analyzer test**

```python
def test_build_report_groups_outbound_and_inbound_counts():
    report = build_report(events)
    self.assertEqual(report.outbound_rows[0].name, ":1.10")
    self.assertEqual(report.inbound_rows[0].name, "org.example.Demo.Ping")
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m unittest tests.test_analyzer -v`
Expected: FAIL because `build_report` does not exist yet

- [ ] **Step 5: Commit**

```bash
git add dbuslens/__init__.py tests/test_parser.py tests/test_analyzer.py
git commit -m "test: add parser and analyzer expectations"
```

### Task 2: Implement parser and aggregation core

**Files:**
- Create: `dbuslens/models.py`
- Create: `dbuslens/parser.py`
- Create: `dbuslens/analyzer.py`
- Modify: `tests/test_parser.py`
- Modify: `tests/test_analyzer.py`

- [ ] **Step 1: Write minimal event and report models**

```python
@dataclass(frozen=True)
class Event:
    message_type: str
    sender: str | None = None
    destination: str | None = None
    interface: str | None = None
    member: str | None = None
```

- [ ] **Step 2: Implement `parse_events()` minimally**

```python
def parse_events(raw_text: str) -> ParseResult:
    blocks = split_blocks(raw_text)
    events = [parse_block(block) for block in blocks if parse_block(block)]
    return ParseResult(events=events, skipped_blocks=len(blocks) - len(events))
```

- [ ] **Step 3: Implement `build_report()` minimally**

```python
def build_report(events: list[Event]) -> AnalysisReport:
    outbound = Counter()
    inbound = Counter()
    for event in events:
        if event.message_type not in {"method_call", "signal"}:
            continue
```

- [ ] **Step 4: Run focused tests**

Run: `python -m unittest tests.test_parser tests.test_analyzer -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dbuslens/models.py dbuslens/parser.py dbuslens/analyzer.py tests/test_parser.py tests/test_analyzer.py
git commit -m "feat: add offline parsing and aggregation core"
```

### Task 3: Add recording support and CLI tests

**Files:**
- Create: `dbuslens/record.py`
- Create: `dbuslens/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI validation tests**

```python
def test_build_output_path_uses_bus_and_timestamp():
    path = build_default_output_path("session", clock=fixed_clock)
    self.assertIn("session", path.name)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL because helpers are missing

- [ ] **Step 3: Implement record helpers and CLI parsing**

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dbuslens")
    subparsers = parser.add_subparsers(dest="command", required=True)
```

- [ ] **Step 4: Re-run CLI tests**

Run: `python -m unittest tests.test_cli -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dbuslens/record.py dbuslens/cli.py tests/test_cli.py
git commit -m "feat: add recording and cli entrypoints"
```

### Task 4: Implement curses TUI and analysis command integration

**Files:**
- Create: `dbuslens/tui.py`
- Modify: `dbuslens/cli.py`

- [ ] **Step 1: Write a small state-level test if needed for view switching**

```python
def test_browser_state_switches_views():
    state = BrowserState(report)
    state.switch_view()
    self.assertEqual(state.active_view, "inbound")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL because state helper is missing

- [ ] **Step 3: Implement minimal TUI browser**

```python
class BrowserState:
    def switch_view(self) -> None:
        self.active_view = "inbound" if self.active_view == "outbound" else "outbound"
```

- [ ] **Step 4: Wire `analyze` to parse, optionally cache JSON, and launch curses**

Run: `python -m unittest tests.test_parser tests.test_analyzer tests.test_cli -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dbuslens/tui.py dbuslens/cli.py tests/test_cli.py
git commit -m "feat: add analysis browser tui"
```

### Task 5: Final verification and docs touch-up

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document MVP commands**

```markdown
python -m dbuslens.cli record --bus session --duration 10
python -m dbuslens.cli analyze --input sample.log
```

- [ ] **Step 2: Run full verification**

Run: `python -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 3: Run a basic CLI smoke check**

Run: `python -m dbuslens.cli --help`
Expected: exit 0 and show `record` and `analyze`

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add dbuslens mvp usage"
```

## Self-Review

Spec coverage:

- record CLI: Task 3
- offline parse: Tasks 1-2
- outbound and inbound rankings: Task 2
- curses drill-down UI: Task 4
- docs and verification: Task 5

Placeholder scan:

- No remaining TODO or TBD markers

Type consistency:

- Core names are aligned around `Event`, `ParseResult`, `AnalysisReport`, `build_report`, and `BrowserState`

# Textual Report UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current `curses`-based `report` UI with a `Textual` terminal app that provides clearer navigation, richer layout, and a persistent detail pane.

**Architecture:** Keep the existing capture, parsing, report-building, and process-resolution pipeline intact. Swap only the presentation layer by introducing a `Textual` app that consumes the existing `AnalysisReport` model, plus a small view-model helper for pane state and table projection.

**Tech Stack:** Python 3.12+, `textual`, `unittest`, existing `dbus-fast` and `dpkt`

---

### Task 1: Add Textual dependency and app state tests

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `tests/test_textual_app.py`

- [ ] **Step 1: Write the failing app-state test**

```python
def test_report_app_state_tracks_view_and_selection():
    state = ReportAppState(report)
    assert state.active_view == "outbound"
    state.switch_view()
    assert state.active_view == "inbound"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m unittest tests.test_textual_app -v`
Expected: FAIL with `ModuleNotFoundError` or missing `ReportAppState`

- [ ] **Step 3: Add `textual` to project dependencies**

```toml
dependencies = [
    "dbus-fast>=4.0.4",
    "dpkt>=1.9.8",
    "textual>=0.85.0",
]
```

- [ ] **Step 4: Recreate lockfile and rerun the test**

Run: `uv sync`
Run: `./.venv/bin/python -m unittest tests.test_textual_app -v`
Expected: FAIL only because app state is not implemented yet

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock tests/test_textual_app.py
git commit -m "test(ui): add textual app state expectations" -m "Add failing tests for the new report UI state model.\nAdd textual as the planned UI dependency.\n\nVerification:\n- ./.venv/bin/python -m unittest tests.test_textual_app -v"
```

### Task 2: Implement report app state and table projection helpers

**Files:**
- Create: `dbuslens/report_app.py`
- Modify: `tests/test_textual_app.py`

- [ ] **Step 1: Implement the smallest state model**

```python
@dataclass
class ReportAppState:
    report: AnalysisReport
    active_view: str = "outbound"
    selected_index: int = 0
```

- [ ] **Step 2: Add methods for view switching and current row lookup**

```python
def switch_view(self) -> None:
    self.active_view = "inbound" if self.active_view == "outbound" else "outbound"
    self.selected_index = 0
```

- [ ] **Step 3: Add helper functions that project rows into textual table data**

```python
def main_columns(state: ReportAppState) -> tuple[str, ...]:
    return ("Count", "Service", "Process") if state.active_view == "outbound" else ("Count", "Operation")
```

- [ ] **Step 4: Run focused tests**

Run: `./.venv/bin/python -m unittest tests.test_textual_app -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dbuslens/report_app.py tests/test_textual_app.py
git commit -m "feat(ui): add textual report state model" -m "Introduce the report UI state and table projection helpers used by the Textual app.\n\nVerification:\n- ./.venv/bin/python -m unittest tests.test_textual_app -v"
```

### Task 3: Replace curses UI with a minimal Textual app

**Files:**
- Modify: `dbuslens/tui.py`
- Modify: `tests/test_tui.py`

- [ ] **Step 1: Write a failing render-structure test**

```python
def test_textual_ui_defines_navigation_main_and_detail_regions():
    app = DBusLensReportApp(report)
    ids = app.region_ids()
    self.assertIn("view-nav", ids)
    self.assertIn("main-table", ids)
    self.assertIn("detail-pane", ids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m unittest tests.test_tui -v`
Expected: FAIL because the Textual app does not exist yet

- [ ] **Step 3: Implement the minimal Textual application**

```python
class DBusLensReportApp(App[None]):
    BINDINGS = [("q", "quit", "Quit"), ("tab", "focus_next", "Next Pane")]
```

- [ ] **Step 4: Mount header, navigation list, main table, detail pane, and footer**

Run: `./.venv/bin/python -m unittest tests.test_tui tests.test_textual_app -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dbuslens/tui.py tests/test_tui.py
git commit -m "feat(ui): replace curses report with textual layout" -m "Replace the report browser with a Textual app using explicit panes and persistent detail context.\n\nVerification:\n- ./.venv/bin/python -m unittest tests.test_tui tests.test_textual_app -v"
```

### Task 4: Wire interactive behavior and polish guidance

**Files:**
- Modify: `dbuslens/tui.py`
- Modify: `tests/test_tui.py`

- [ ] **Step 1: Write a failing interaction test**

```python
def test_selecting_main_row_updates_detail_panel():
    app = DBusLensReportApp(report)
    app.state.selected_index = 1
    app.sync_detail()
    self.assertIn("demo-service", app.current_detail_text())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m unittest tests.test_tui -v`
Expected: FAIL because detail synchronization is incomplete

- [ ] **Step 3: Implement selection sync, pane focus, and footer hints**

```python
def refresh_detail(self) -> None:
    selected = self.state.current_row
    self.detail_table.clear(columns=True)
```

- [ ] **Step 4: Run focused UI tests**

Run: `./.venv/bin/python -m unittest tests.test_tui tests.test_textual_app -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dbuslens/tui.py tests/test_tui.py
git commit -m "feat(ui): add guided textual interactions" -m "Add visible navigation, selection-driven detail updates, and consistent key-hint guidance.\n\nVerification:\n- ./.venv/bin/python -m unittest tests.test_tui tests.test_textual_app -v"
```

### Task 5: CLI integration and final verification

**Files:**
- Modify: `README.md`
- Modify: `dbuslens/cli.py`

- [ ] **Step 1: Update docs to mention Textual-based report UI**

```markdown
`uv run dbuslens report` opens the Textual report browser with navigation, tables, and a persistent detail pane.
```

- [ ] **Step 2: Verify CLI still launches the report app**

Run: `./.venv/bin/python -m dbuslens --help`
Expected: exit 0 and show `record` and `report`

- [ ] **Step 3: Run full verification**

Run: `./.venv/bin/python -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add README.md dbuslens/cli.py
git commit -m "docs(ui): document textual report experience" -m "Document the new report UI while keeping the CLI contract stable.\n\nVerification:\n- ./.venv/bin/python -m dbuslens --help\n- ./.venv/bin/python -m unittest discover -s tests -v"
```

## Self-Review

Spec coverage:

- Textual dependency and migration boundary: Tasks 1-3
- fixed multi-pane layout: Task 3
- visible guidance and pane interactions: Task 4
- CLI stability and docs: Task 5

Placeholder scan:

- No TODO or TBD markers remain

Type consistency:

- Plan consistently uses `ReportAppState`, `DBusLensReportApp`, and existing `AnalysisReport` / `Row` / `DetailRow` models

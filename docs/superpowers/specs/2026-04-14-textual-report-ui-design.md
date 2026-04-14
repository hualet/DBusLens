# DBusLens Textual Report UI Design

## Goal

Replace the current minimal `curses` report browser with a more guided and visually richer pure-terminal UI based on `Textual`, while keeping the `record` and `report` CLI commands unchanged.

## Scope

Included:

- Pure terminal UI only
- `Textual`-based `report` application
- Clear navigation and stronger visual hierarchy
- Persistent detail panel instead of page-to-page drill-down
- Better onboarding through visible labels, view selectors, and help hints

Not included:

- Browser UI
- Real-time streaming capture
- New report metrics
- Changes to `record` behavior

## Design Direction

The new report UI should feel closer to a modern profiling browser than a raw terminal table dump. The reference interaction model is “inspect a capture through stable panes” rather than “jump between screens”.

### Layout

The `report` app uses four regions:

1. Top status bar
   Shows file path, event counts, actionable counts, and skipped packet count.

2. Left navigation pane
   Shows explicit views:
   - `Outbound`
   - `Inbound`

3. Main content pane
   Shows the primary table for the active view.

4. Right detail pane
   Shows details for the currently selected row without leaving the main screen.

### Table Semantics

- `Outbound` main table: `Count | Service | Process`
- `Inbound` main table: `Count | Operation`
- `Outbound` detail table: `Count | Operation`
- `Inbound` detail table: `Count | Service | Process`

Process names are shown only where a service is present. Operation rows do not invent a process value.

## Interaction Model

### Primary Navigation

- Up / Down: move selection inside the focused pane
- Tab: move focus between navigation, main table, and detail table when applicable
- Enter: pin or expand the active selection context
- `q`: quit

The current active view is always visible in the left pane, so users do not need to memorize hidden mode switches.

### Guidance

The UI should always show:

- a visible active view
- a visible selected item
- a visible detail summary
- a visible footer with key bindings

This removes the current “what do I do next?” ambiguity.

## Implementation Plan Boundary

The migration should reuse existing report-building logic and process resolution logic. Only the presentation layer should be replaced.

Suggested module split:

- keep `analyzer.py`, `models.py`, and `processes.py`
- replace `tui.py` internals with a `Textual` app
- keep `cli.py` entrypoints stable so `uv run dbuslens report` still works

## Error Handling

- Empty captures still render a proper empty-state view
- Missing process names render as `-`
- Narrow terminal widths should degrade gracefully by truncating lower-priority text

## Testing Strategy

- keep analyzer tests unchanged except where UI-facing row structure changes
- add `Textual` app state tests for view switching and detail updates
- keep CLI tests validating `report` behavior and defaults

## Rationale

`Textual` is the preferred third-party library because it provides a more modern terminal interaction model, richer layout primitives, and significantly better affordances for guidance than a hand-built `curses` UI. `Urwid` and `prompt_toolkit` would improve maintainability over `curses`, but are less aligned with the goal of making the UI feel more intentional and visually strong.

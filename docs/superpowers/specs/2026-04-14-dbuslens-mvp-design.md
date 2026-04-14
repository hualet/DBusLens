# DBusLens MVP Design

## Goal

Build a low-complexity MVP for offline D-Bus traffic capture and analysis. The tool records `dbus-monitor` output to disk, parses it into structured events, aggregates two ranking views, and renders them in a keyboard-driven terminal UI.

## Scope

Included in MVP:

- CLI recording for `system` or `session` bus
- Fixed-duration capture through `dbus-monitor`
- Raw log persistence on disk
- Offline parsing from raw log into structured events
- Two aggregate views:
  - outbound top: service -> operation counts
  - inbound top: operation -> caller counts
- Full-keyboard terminal UI with drill-down details

Excluded from MVP:

- Real-time updating UI
- Process name or PID resolution
- Call latency pairing
- Charts or timeline visualization
- Advanced filters

## User Flow

1. Run `dbuslens record --bus session --duration 10`.
2. The command invokes `dbus-monitor`, captures output for the requested duration, and writes a raw text log file.
3. Run `dbuslens analyze --input <raw-log>`.
4. The command parses the raw log, computes aggregates, optionally writes a JSON cache file, and opens the TUI.
5. The user explores the outbound and inbound rankings and drills into details.

## Command Design

### `dbuslens record`

Purpose: capture D-Bus traffic into a raw log file.

Arguments:

- `--bus system|session`
- `--duration <seconds>`
- `--output <path>` optional

Behavior:

- Validates the bus name and duration.
- Verifies `dbus-monitor` is available.
- Runs `dbus-monitor --system` or `dbus-monitor --session`.
- Collects stdout for the requested duration.
- Terminates the subprocess and writes the captured output to disk.

### `dbuslens analyze`

Purpose: parse a raw log and open the analysis UI.

Arguments:

- `--input <path>`
- `--cache <path>` optional

Behavior:

- Validates input file existence and non-empty contents.
- Parses raw text into structured events.
- Computes outbound and inbound ranking views.
- Saves JSON cache when requested.
- Opens the curses-based TUI.

## Data Model

### Raw Log

The raw log is the unmodified text output from `dbus-monitor`. It is the source of truth for later re-parsing and debugging.

### Structured Event

Each parsed message becomes an event with these fields:

- `timestamp`: optional float parsed from the leading timestamp when available
- `message_type`: `method_call`, `signal`, `method_return`, or `error`
- `sender`
- `destination`
- `path`
- `interface`
- `member`
- `serial`
- `reply_serial`
- `error_name`

Derived field:

- `operation`: `interface.member` when both are present
- fallback order:
  - `interface`
  - `member`
  - `<unknown>`

### Aggregated Views

#### Outbound Top

Primary key: sender service

- `name`: sender
- `count`: number of emitted actionable messages
- `children`: operation -> count

The MVP counts `method_call` and `signal` messages here. Replies and errors are retained in parsed events but ignored by this ranking.

#### Inbound Top

Primary key: operation

- `name`: operation
- `count`: number of received actionable messages
- `children`: sender service -> count

This also counts `method_call` and `signal` messages only.

## Parser Rules

- Messages are separated by blank lines.
- The first line identifies the message type.
- Key-value attributes such as `sender=`, `destination=`, `path=`, `interface=`, `member=`, `serial=`, `reply_serial=`, and `error_name=` are extracted with tolerant regex matching.
- Unparseable blocks are skipped and counted.
- Missing fields are allowed. Aggregation uses `<unknown>` or `<broadcast>` fallbacks instead of dropping the event entirely.

## TUI Design

The UI uses `curses` from the Python standard library to avoid third-party dependencies.

### Main Screen

- Header: input file path, total parsed events, skipped block count, active view
- Body: scrollable list
- Footer: keyboard hints

Two top-level views:

- `Outbound Top`
- `Inbound Top`

### Detail Screen

Entering a row opens a second-level list:

- outbound detail: operations called by the selected service
- inbound detail: services calling the selected operation

### Key Bindings

- `j` / `k` or arrow keys: move
- `Tab`: switch top-level view
- `Enter`: open detail
- `b` or `Esc`: back
- `q`: quit

## Error Handling

- Missing `dbus-monitor`: exit with explicit CLI error
- Invalid bus or duration: CLI validation error
- Recorder subprocess exits unexpectedly: report stderr and exit code
- Input file missing or empty: analysis error
- Some blocks fail to parse: continue, track skipped count
- No actionable events after parsing: show empty-state UI instead of crashing

## Testing Strategy

MVP tests focus on stable logic outside curses rendering:

- parser extracts common `dbus-monitor` fields from representative samples
- parser tolerates partial or malformed blocks
- analyzer builds outbound and inbound rankings correctly
- CLI helpers validate arguments and write output files

The curses UI will be exercised lightly through state-level tests where practical and manual verification in the terminal.

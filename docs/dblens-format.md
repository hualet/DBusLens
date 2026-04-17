# `.dblens` Format

DBusLens stores captures in a single `.dblens` bundle. The file is a zip archive with structured metadata and capture artifacts grouped together.

## Goals

- Keep one portable file per recording
- Preserve raw D-Bus packets and extra analysis context together
- Leave room for future metadata without changing the CLI model

## Archive Layout

A `.dblens` bundle currently contains:

- `meta.json`
- `capture.cap`
- `capture.profile`
- `names.json`
- `names_timeline.json`

## `meta.json`

`meta.json` is the entry point for readers. It records the bundle version and tells DBusLens where the bundled artifacts live.

Example:

```json
{
  "bundle_version": 1,
  "created_at": "2026-04-16T10:20:30+08:00",
  "bus": "session",
  "duration_seconds": 10,
  "capture_files": {
    "pcap": "capture.cap",
    "profile": "capture.profile",
    "names": "names.json",
    "names_timeline": "names_timeline.json"
  },
  "monitor": {
    "command": ["dbus-monitor", "--session", "--pcap"],
    "profile_command": ["dbus-monitor", "--session", "--profile"],
    "stderr": "",
    "mode": "monitor"
  }
}
```

Required fields:

- `bundle_version`
- `created_at`
- `bus`
- `duration_seconds`
- `capture_files`
- `monitor`

## Bundled Files

### `capture.cap`

Raw `dbus-monitor --pcap` output. DBusLens parses this file for the main event stream.

### `capture.profile`

Raw `dbus-monitor --profile` output. This is recorded for richer timing and future diagnostics.

### `names.json`

A capture-time snapshot of bus names and process context. Entries may include:

- `name`
- `owner`
- `pid`
- `uid`
- `cmdline`
- `error`

This snapshot is used as the baseline and fallback metadata source for report analysis.

### `names_timeline.json`

Optional ownership history captured during `record`.

- `initial_snapshot`: enriched snapshot at capture start
- `events`: `org.freedesktop.DBus.NameOwnerChanged` entries
- `final_snapshot`: enriched snapshot at capture end
- `error`: best-effort capture failure detail, if timeline collection failed

Notes:

- `events` may be empty on a quiet bus
- older bundles may omit this file entirely
- capture is best-effort; `error` records timeline collection failures without invalidating the bundle

Report analysis uses this artifact to resolve unique names at event time, improve original-call matching across owner churn, and attach more accurate per-error caller and target metadata.

## Versioning

- DBusLens currently writes `bundle_version = 1`
- Readers should reject unknown versions instead of guessing
- Future versions may add new files, but `meta.json` remains the source of truth

## Current Reader Behavior

- `dbuslens report` accepts `.dblens` bundles only
- DBusLens currently reads the main event stream from the bundled `capture.cap`
- `names.json` is used for capture-time snapshot context and fallback metadata
- `names_timeline.json` is used for event-time name resolution in error analysis when present
- `capture.profile` remains stored for future diagnostics, but is not yet required by the current report UI

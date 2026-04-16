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
    "names": "names.json"
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

A lightweight snapshot captured during recording. The first version stores discovered bus names and may include capture-time errors if lookup failed.

## Versioning

- DBusLens currently writes `bundle_version = 1`
- Readers should reject unknown versions instead of guessing
- Future versions may add new files, but `meta.json` remains the source of truth

## Current Reader Behavior

- `dbuslens report` accepts `.dblens` bundles only
- DBusLens currently reads the main event stream from the bundled `capture.cap`
- `capture.profile` and `names.json` are stored now for future analysis improvements

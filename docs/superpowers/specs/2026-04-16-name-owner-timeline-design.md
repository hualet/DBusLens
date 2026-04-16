# DBusLens Name Owner Timeline Design

## Goal

Reduce unresolved D-Bus unique names such as `:1.14918` in reports by recording and analyzing
name-owner changes over time instead of relying only on static capture-time snapshots.

This phase upgrades DBusLens from:

- one enriched `names.json` snapshot
- best-effort alias inference during analysis

to:

- initial baseline snapshot
- capture-time `NameOwnerChanged` timeline
- final snapshot at the end of recording
- time-aware name resolution during analysis

## Problem

Static snapshots fail for short-lived clients and services that connect after the initial
snapshot is taken. In those cases:

- the bundle still contains the raw D-Bus traffic
- reports still show unique names like `:1.14918`
- process and service resolution stays incomplete even when the true owner existed during the
  capture window

This is most visible in `Errors`, but it also affects sender and destination readability in
general.

## User Value

After this phase, DBusLens should answer:

- who `:1.xxx` was at the moment an event happened
- which well-known name mapped to a unique name at that time
- which PID and command line owned that connection at that time

The immediate success criterion is simple: reports should show fewer raw unique names for
short-lived clients without weakening current fallback behavior.

## Scope

Included:

- a new timeline artifact in `.dblens`
- baseline snapshot at record start
- `NameOwnerChanged` capture during the record window
- final snapshot at record end
- time-aware caller and target resolution in analysis
- visible improvement in `Errors`

Not included:

- a new standalone timeline UI
- a generic event-history database
- full retroactive reconstruction of every D-Bus object or property
- removing `names.json`
- a guarantee that every unique name will always resolve

## Bundle Format

Add a new artifact to `.dblens`:

- `names_timeline.json`

The bundle continues to include:

- `capture.cap`
- `capture.profile`
- `meta.json`
- `names.json`

`meta.json` should gain a new capture file entry:

```json
{
  "capture_files": {
    "pcap": "capture.cap",
    "profile": "capture.profile",
    "names": "names.json",
    "names_timeline": "names_timeline.json"
  }
}
```

If timeline capture fails, the bundle still succeeds, but metadata must make that explicit so
the loader can fall back cleanly.

## Timeline Artifact

`names_timeline.json` should contain three sections:

1. `initial_snapshot`
2. `events`
3. `final_snapshot`

Suggested structure:

```json
{
  "bus": "session",
  "started_at": "2026-04-16T21:00:00+08:00",
  "ended_at": "2026-04-16T21:00:10+08:00",
  "initial_snapshot": {
    "captured_at": "2026-04-16T21:00:00+08:00",
    "bus": "session",
    "names": []
  },
  "events": [
    {
      "timestamp": 1776342800.123,
      "name": "org.example.Service",
      "old_owner": "",
      "new_owner": ":1.152"
    }
  ],
  "final_snapshot": {
    "captured_at": "2026-04-16T21:00:10+08:00",
    "bus": "session",
    "names": []
  },
  "error": null
}
```

Rules:

- `events` only contains `org.freedesktop.DBus.NameOwnerChanged`
- empty owner strings are valid and meaningful
- snapshots reuse the enriched `names.json` entry shape
- timeline collection errors are recorded in `error` and are not fatal
- entries are ordered by event time

## Record Phase

Recording should collect name ownership information in three steps.

### 1. Initial baseline

Before or at the start of the main capture:

- collect the same enriched snapshot already written to `names.json`

This establishes the initial owner mapping for names that already exist when recording starts.

### 2. Timeline capture

During recording:

- capture `NameOwnerChanged` events from `org.freedesktop.DBus`

The implementation should prefer robustness over cleverness:

- only collect the fields needed for ownership history
- ignore unrelated signal content
- do not make timeline collection a precondition for `record` success

The capture mechanism may use a parallel text monitor or another dedicated stream as long as it
can reliably recover:

- timestamp
- name
- old owner
- new owner

### 3. Final baseline

At record end:

- capture the enriched snapshot again

This closes gaps for names that appeared late and did not provide enough metadata in the initial
snapshot alone.

## Analysis Model

Analysis should build a time-aware resolver from:

- initial snapshot entries
- ordered `NameOwnerChanged` events
- final snapshot entries

The resolver should support:

- given `timestamp` and unique name `:1.xxx`, find the best well-known alias valid at that time
- given `timestamp` and well-known name, find the active owner unique name at that time
- return PID, UID, and cmdline when known

The key requirement is event-time correctness, not global prettification.

## Resolution Rules

When resolving an event:

1. Prefer exact event-time mapping derived from the timeline.
2. If unavailable, fall back to the initial snapshot.
3. If still unavailable, fall back to the final snapshot.
4. If still unavailable, keep the original unique name.

Display should prefer well-known names when they are valid for that time point.

The original raw name must remain available in the analysis model so the UI can expose it later
when useful.

Metadata rules:

- PID, UID, and cmdline come from the snapshot entry that best matches the resolved owner
- if the timeline proves an alias but metadata is missing, resolution still succeeds and
  metadata remains blank
- unique names are never rewritten destructively; the resolver returns a richer display label
  alongside the raw value

## Analyzer Integration

The analyzer should stop treating snapshot data as a timeless alias map.

Instead it should:

- construct a timeline resolver once per report
- use event timestamps when resolving callers and targets
- use the same resolver for:
  - matched error transactions
  - unmatched errors when sender or destination are still available
  - other report views as a follow-up only if the implementation stays small

This phase must improve `Errors`.

Applying the same resolver to sender and member summaries is desirable only if it does not
significantly expand scope.

## UI Impact

No new top-level page is needed.

Expected visible changes:

- fewer raw unique names in `Errors`
- more consistent service labels for short-lived clients
- process information available more often

The first implementation should keep UI changes small:

- continue using the current `Errors` table and details layout
- prefer resolved labels over raw unique names
- optionally include the raw value in notes, for example `raw=:1.14918`

An explicit badge such as `resolved from timeline` is optional and not required for this phase.

## Failure Handling

Timeline capture is best-effort.

If it fails:

- recording still succeeds
- `.dblens` still opens
- analysis falls back to the current snapshot-based behavior

This matters because D-Bus monitor access and signal visibility vary by bus and environment.

## Compatibility

This phase extends the current `.dblens` bundle version rather than introducing a second bundle
format.

Behavior expectations:

- new bundles may contain `names_timeline.json`
- older bundles may not contain it
- the loader and analyzer must treat the timeline as optional

This keeps existing `.dblens` captures readable while improving newly recorded ones.

## Testing

Tests should cover:

- bundle round-trip with `names_timeline.json`
- timeline resolver with:
  - existing baseline names
  - new names appearing after start
  - owner changes
  - names disappearing
- analyzer resolving a unique caller via timeline even when the initial snapshot missed it
- fallback to raw unique name when no timeline or snapshot data exists
- graceful handling when `names_timeline.json` is absent or marked with an error

Prefer deterministic synthetic fixtures over live D-Bus traffic.

## Implementation Order

1. Extend bundle format and loader to optionally include `names_timeline.json`
2. Implement initial snapshot, timeline capture, and final snapshot in `record`
3. Add a small time-aware resolver module or analyzer helper
4. Integrate the resolver into `Errors`
5. Expand tests around bundle IO, resolver behavior, and analyzer output

## Recommendation

Keep the first implementation narrow:

- solve event-time name ownership resolution
- improve `Errors`
- preserve current fallback behavior

This gets the main value without turning DBusLens into a generic D-Bus event database.

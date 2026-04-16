# DBusLens Error Analysis Phase 2 Design

## Goal

Upgrade DBusLens from a bundle-only capture tool into a capture-and-diagnose tool by:

- enriching `.dblens` bundles with capture-time name/process snapshots
- building a transaction-oriented error analysis model
- upgrading the existing `Errors` view into a diagnostic workflow instead of a flat error counter

This phase keeps the current three-view TUI structure (`Senders`, `Members`, `Errors`) and focuses on making `Errors` materially more useful.

## Current State

DBusLens already has:

- a single `.dblens` bundle format
- raw `capture.cap` and `capture.profile` stored in the bundle
- a lightweight `names.json`
- an `Errors` view in the TUI

Current limitations:

- `names.json` only stores a basic name list, not enough capture-time context
- error analysis only groups by error name and partial origin
- no latency, retry, or time-window context is available
- the `Errors` view cannot answer whether an error is isolated, repeated, tied to a single caller, or caused by a missing owner at capture time

## User Value

After this phase, a user selecting an error should be able to answer:

- what failed
- who called it
- which target service it hit
- how often it failed
- whether it was retried
- how long it took before failing
- which process owned the target at capture time, if any

## Scope

Included:

- richer capture-time snapshot data in `names.json`
- error transaction modeling from `method_call` to `error`
- error aggregation by diagnostic key
- `Errors` view redesign within the existing TUI layout

Not included:

- full message body capture or decoding
- a new standalone timeline page
- `profile`-driven correlation in the TUI
- replacing `Senders` or `Members` views

## Data Model Changes

### 1. Capture-time name snapshot

`names.json` should evolve from a flat list into a snapshot document with per-name diagnostic context.

Target structure:

```json
{
  "captured_at": "2026-04-16T10:20:31+08:00",
  "bus": "session",
  "names": [
    {
      "name": "org.freedesktop.DBus",
      "owner": ":1.0",
      "pid": 1234,
      "uid": 1000,
      "cmdline": ["/usr/bin/dbus-daemon", "--session"],
      "error": null
    }
  ]
}
```

Rules:

- missing data is allowed
- lookup failures are recorded per entry instead of failing the capture
- `cmdline` may be `null` when unavailable
- snapshot collection should prefer correctness at capture time over later live resolution

### 2. Error transaction model

The analyzer should create an internal transaction-like object for each matched failure:

- `error_name`
- `timestamp`
- `caller`
- `destination`
- `path`
- `operation`
- `reply_serial`
- `call_serial`
- `latency_ms`
- `capture_target`
- `capture_caller`

Matching rule:

- index `method_call` by `(sender, destination, serial)`
- on `error`, resolve the original call via `(event.destination, event.sender, reply_serial)`

If a match is missing:

- keep the error
- mark unresolved fields as unknown
- do not drop the error row

### 3. Error aggregation key

The top-level `Errors` view should no longer aggregate by `error_name` only.

Primary aggregation key:

- `error_name + destination + operation`

This gives a more actionable grouping:

- one error type
- one target service
- one failed operation

### 4. Retry detection

Retry detection should be lightweight in phase 2.

Use a retry key composed from:

- `caller`
- `destination`
- `operation`
- `error_name`

If multiple failures with the same retry key occur inside a short time window, they count as retries.

Recommended initial window:

- 5 seconds

Outputs:

- retry count
- first seen timestamp
- last seen timestamp

## UI Design

### 1. Keep the existing navigation

The app still has:

- `Senders`
- `Members`
- `Errors`

No new top-level tab is added in this phase.

Reason:

- it keeps learning cost low
- current layout already has enough structure for a richer error workflow
- the risk is in data complexity, not navigation scarcity

### 2. Errors main table

Current main table columns for `Errors` are too thin.

New columns:

- `Count`
- `Error`
- `Target`
- `Operation`

Meaning:

- `Count`: number of failures in this aggregated diagnostic bucket
- `Error`: the D-Bus error name
- `Target`: resolved destination or capture-time owner label
- `Operation`: failed operation name

This makes the main table itself diagnostic instead of merely categorical.

### 3. Errors detail pane

The text detail pane should become a diagnostic summary card.

Show:

- selected error key
- count
- first seen
- last seen
- average latency
- retries detected
- unique callers
- target owner at capture time

This is the fastest way to make the screen useful without adding more navigation.

### 4. Errors detail table

The detail table should list grouped origins for the selected diagnostic bucket.

Columns:

- `Count`
- `Caller`
- `Process`
- `Owner/PID`
- `Latency`
- `Notes`

Meaning:

- `Caller`: sender name or best resolved label
- `Process`: caller process name
- `Owner/PID`: target owner and pid from capture-time snapshot
- `Latency`: average or representative latency for that grouped source
- `Notes`: unresolved owner, repeated failures, missing call match, and similar hints

This keeps the screen dense but still readable.

## Analysis Flow

### Record phase

`record` should collect:

- `capture.cap`
- `capture.profile`
- enriched `names.json`

Snapshot queries should attempt:

- `ListNames`
- `GetNameOwner`
- `GetConnectionUnixProcessID`
- user lookup where practical
- process command line from `/proc`

Failures should be recorded, not fatal.

### Load phase

`report` should load:

- event stream from `capture.cap`
- snapshot context from `names.json`

`capture.profile` remains stored for future use, but is not required for phase 2 UI logic.

### Analyze phase

Analyzer responsibilities:

- build outbound and inbound aggregates as today
- build error transactions
- group error transactions by diagnostic key
- calculate latency and retry summaries
- carry snapshot context into error rows

## Architectural Recommendation

Do not force error data into the same generic `Row` model if it causes lossy mapping.

Preferred direction:

- keep generic rows for outbound and inbound
- add dedicated error summary/detail structures for the `Errors` view

Reason:

- error diagnostics now need fields like latency, first seen, retry count, and capture-time owner
- overloading generic row fields will make the code harder to reason about

## Testing Strategy

Phase 2 should add tests for:

- snapshot parsing and lookup fallbacks
- call-to-error matching
- unresolved error handling
- latency calculation
- retry detection within a window
- errors table formatting and detail rendering

Use synthetic capture data in tests.

Do not depend on a live D-Bus environment for correctness tests.

## Rollout Plan

Implement in this order:

1. enrich `names.json` collection and bundle payload
2. add snapshot-aware analyzer data structures
3. build error transaction aggregation
4. redesign `Errors` main table and detail panel
5. redesign `Errors` detail table

This order keeps each step testable and avoids UI work before the data model can support it.

## Risks

### Incomplete snapshot data

Some names will not resolve cleanly to owner, pid, uid, or command line.

Mitigation:

- store partial data
- surface uncertainty in notes instead of hiding it

### UI overload

Adding too many columns can make the existing layout unreadable.

Mitigation:

- keep the main table to four columns
- push richer diagnostics into the detail pane and detail table

### Analyzer complexity

Error-specific logic is becoming more specialized than outbound/inbound aggregation.

Mitigation:

- introduce dedicated error data structures instead of stretching generic rows too far

## Success Criteria

Phase 2 is successful when:

- `.dblens` contains a useful capture-time snapshot
- selecting an error shows target, caller, latency, retries, and owner context
- repeated failures are distinguishable from isolated ones
- users can understand an error pattern without leaving the TUI

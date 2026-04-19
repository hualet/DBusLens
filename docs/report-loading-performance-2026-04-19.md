# Report Loading Performance Notes

This note records the report loading investigation and optimization work from April 19, 2026.

## Goal

Reduce the time spent opening a `.dblens` bundle with `dbuslens report`, with priority on total load time for larger captures.

## Initial Symptom

Opening the local sample bundle `record.dblens` felt slow enough to interrupt normal terminal inspection flow.

The sample bundle used during the investigation was:

- `record.dblens`
- size: about `2.1M`
- parsed events: about `54k`

## Step 1: Baseline Measurement

Before changing code, the loading pipeline was split into three timed stages:

- `read_bundle`
- `parse_pcap_bytes`
- `build_report`

Measured result:

- `read_bundle=0.138s`
- `parse_pcap=0.477s`
- `build_report=14.005s`
- `total=14.619s`

### Takeaway

The bottleneck was not archive IO and not pcap parsing. Almost all time was spent in report analysis.

## Step 2: Profile The Hot Path

`cProfile` was run against `load_report(Path("record.dblens"))`.

Key result from the first profile:

- `build_report`: about `15.1s` cumulative
- `resolve_process_name`: about `14.0s`
- `_lookup_pid`: about `14.0s`
- `subprocess.run`: about `14.0s`
- `_lookup_pid` call count: `3970`

### Takeaway

The main problem was repeated runtime process lookups during report construction. The code was spending most of its time spawning `gdbus` subprocesses to resolve service names into process metadata.

This ruled out "add parallelism first" as the best immediate response. The expensive work was external process lookup, not pure Python CPU work.

## Step 3: First Optimization

The first change attacked repeated process resolution:

- add a shared cached resolver across one full `build_report()` run
- add an `lru_cache` to `resolve_process_name()`
- make all report row builders reuse the same cached process resolver

### Result

Measured result after the first optimization:

- `read_bundle=0.130s`
- `parse_pcap=0.434s`
- `build_report=4.203s`
- `total=4.768s`

### Takeaway

This was the biggest gain of the whole exercise. The major source of repeated `gdbus` calls was removed, and total load time dropped by roughly two thirds.

## Step 4: Re-Profile After The First Fix

The second profile showed that the remaining hot path was still process resolution, but at a much lower volume.

Key result from the second profile:

- `build_report`: about `4.84s`
- cached analyzer resolver calls: `518`
- `resolve_process_name`: about `3.67s`
- `_lookup_pid` calls: `1034`
- `subprocess.run`: about `3.65s`

### Takeaway

The first optimization removed most repeated lookups, but report loading was still falling back to runtime D-Bus resolution for names that were already present in capture metadata.

## Step 5: Second Optimization

The second change made the default report path prefer capture-time metadata:

- if `build_report()` is using the default resolver, use `snapshot_names` and `names_timeline` data first
- derive `ProcessInfo` from capture metadata when pid and cmdline are already available
- only fall back to runtime `resolve_process_name()` when capture metadata is not enough
- keep explicit custom `resolve_process` behavior unchanged for tests and special callers

### Result

Measured result after the second optimization:

- `read_bundle=0.132s`
- `parse_pcap=0.457s`
- `build_report=4.020s`
- `total=4.609s`

### Takeaway

This was a smaller improvement than the first round, but it moved the default loading path closer to the right data source: capture-time metadata instead of runtime environment inspection.

## Final Numbers

End-to-end comparison on the same sample:

- baseline total: about `14.6s`
- after first optimization: about `4.8s`
- after second optimization: about `4.6s`

Approximate overall reduction:

- total load time improved by about `68%`

## Why Parallelism Was Not The First Move

Parallelism was discussed, but the profiles showed it was not the right first optimization.

Reasons:

- the dominant cost was repeated external subprocess work
- threads would not remove the underlying subprocess overhead
- multi-process analysis would add serialization and coordination complexity
- cheaper, safer wins existed by reducing duplicated lookups

After the two rounds above, parallelism can still be revisited if later profiles show a real CPU-bound stage worth splitting.

## Remaining Hotspots

After the two implemented rounds, the next most interesting areas are:

- `name_timeline.resolve_name()` and related helper work
- `parse_pcap_stream()` body preview normalization
- additional analyzer passes that still repeat resolution work

These are reasonable candidates for a future third optimization pass, but they were not the dominant bottleneck compared with repeated runtime process lookup.

## Verification

The optimization work was verified with:

- `./.venv/bin/python -m unittest discover -s tests -v`
- `uv tool run --from pylint --with dbus-fast --with dpkt --with textual pylint $(git ls-files '*.py')`


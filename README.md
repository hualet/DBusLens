<p align="center">
  <img src="./docs/attachments/logo_full_size.png" alt="DBusLens logo" width="256" height="256">
</p>

# DBusLens

DBusLens is a terminal tool for recording and inspecting D-Bus traffic. It stores captures as `.dblens` bundles, opens them in a Textual UI, and helps you quickly understand who is sending messages, which members are busiest, and where errors are happening.

## Highlights

- **A D-Bus inspector that feels like a real tool**  
  Clean, keyboard-first terminal UI built for investigation, not just dumping messages.

- **Built for speed**  
  Fast capture, fast load, and responsive browsing even when the trace is noisy.

- **From traffic ranking to failure diagnosis**  
  See top senders and members, then drill into error distribution, retries, call context, and arguments.

- **Understands changing bus ownership**  
  Recover service and process identity from short-lived unique names with capture-time snapshots and ownership timeline analysis.

- **One workflow for session and system bus**  
  Same commands, same bundle format, same inspection model.

- **Simple like `perf`, focused on D-Bus**  
  Capture now, inspect later, stay in the terminal.

## Screenshots

### Senders

![](./docs/attachments/senders.svg)

### Members

![](./docs/attachments/members.svg)

### Errors

![](./docs/attachments/errors.svg)

## Quick Start

Install the published tool:

```bash
uv tool install dbuslens
```

This installs the `dbuslens` command into your user tool path. `uv` documents that `uv tool install`
exposes package executables on `PATH`, which matches the intended install flow.

Runtime requirements:

- Linux
- `dbus-monitor`
- `gdbus`

If you are working on the project locally instead of installing from PyPI:

```bash
uv sync
```

Record a capture:

```bash
dbuslens record --duration 10
dbuslens record --bus system --duration 60 --output /tmp/system.dblens
```

Open a saved capture in the terminal UI:

```bash
dbuslens report
dbuslens report --input /tmp/system.dblens
```

Enable shell completion:

```bash
mkdir -p ~/.local/share/bash-completion/completions
dbuslens completion bash > ~/.local/share/bash-completion/completions/dbuslens
```

```bash
mkdir -p ~/.local/share/zsh/site-functions
dbuslens completion zsh > ~/.local/share/zsh/site-functions/_dbuslens
```

Format reference:

- [`docs/dblens-format.md`](./docs/dblens-format.md)

Recent `.dblens` captures also embed ownership timeline metadata, which helps `report` resolve
short-lived D-Bus unique names back to service labels, recover error call context across owner
changes, and attach more accurate process metadata in the `Errors` view.

## Operation Guide

`dbuslens` has two main commands:

- `record`: start a timed D-Bus capture and save it as a `.dblens` bundle
- `report`: open a saved `.dblens` bundle in the Textual report UI

Default behavior:

- `record` uses the `session` bus by default
- `report` reads `record.dblens` by default

Typical workflow:

1. Record traffic during the period you want to observe.
2. Open the saved `.dblens` bundle with `report`.
3. Switch between `Senders`, `Members`, and `Errors`.
4. Move through the table and inspect the detail pane for the selected row or error summary.
5. In `Errors`, use the details table to inspect resolved caller and target names, per-call arguments, and retry context.

## Keyboard Shortcuts

- `s`: switch to `Senders`
- `m`: switch to `Members`
- `e`: switch to `Errors`
- `Left` / `Right`: switch between views
- `Up` / `Down`: move inside the focused list or table
- `Tab` / `Shift+Tab`: switch focus between panes
- `Enter`: jump to the detail pane
- `q`: quit

## License

Licensed under the GNU General Public License v3.0. See [LICENSE](./LICENSE).

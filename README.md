<p align="center">
  <img src="https://raw.githubusercontent.com/hualet/DBusLens/main/docs/attachments/logo_full_size.png" alt="DBusLens logo" width="256" height="256">
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

![](https://raw.githubusercontent.com/hualet/DBusLens/main/docs/attachments/senders.svg)

### Members

![](https://raw.githubusercontent.com/hualet/DBusLens/main/docs/attachments/members.svg)

### Errors

![](https://raw.githubusercontent.com/hualet/DBusLens/main/docs/attachments/errors.svg)

### Plot
![](https://raw.githubusercontent.com/hualet/DBusLens/main/docs/attachments/plot.svg)

## For Users

### Requirements

DBusLens currently targets Linux systems with D-Bus tooling available on `PATH`.

- Linux
- `dbus-monitor`
- `gdbus`
- `dot` from Graphviz for `plot` SVG output

### Install

Recommended:

```bash
uv tool install dbuslens
```

Alternative:

```bash
pip install dbuslens
```

After installation, confirm the command is available:

```bash
dbuslens --help
```

### Enable Shell Completion

Bash:

```bash
mkdir -p ~/.local/share/bash-completion/completions
dbuslens completion bash > ~/.local/share/bash-completion/completions/dbuslens
```

Zsh:

```bash
mkdir -p ~/.local/share/zsh/site-functions
dbuslens completion zsh > ~/.local/share/zsh/site-functions/_dbuslens
```

Open a new shell after writing the completion file, or reload your shell configuration.

### Basic Usage

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

Generate a dependency graph:

```bash
dbuslens plot
dbuslens plot --input /tmp/system.dblens
dbuslens plot --input /tmp/system.dblens --output graph.svg
dbuslens plot --input /tmp/system.dblens --format dot --output graph.dot
dbuslens plot --input /tmp/system.dblens --raw --output graph-raw.svg
```

`plot` writes a simplified dependency graph by default:

- nodes prefer captured well-known service names over transient unique names
- `org.freedesktop.DBus` traffic is hidden
- SVG output uses a dark theme aligned with the terminal UI colors

When `--output` is omitted, `plot` writes next to the input bundle with a suffix matching `--format`.
Use `--output -` when you want the rendered output on stdout.

Use `--raw` when you want the unfiltered graph with raw unique-name nodes.

Default behavior:

- `record` uses the `session` bus by default
- `report` reads `record.dblens` by default
- `plot` reads `record.dblens` and writes `record.svg` by default

Typical workflow:

1. Record traffic during the period you want to observe.
2. Open the saved `.dblens` bundle with `report`.
3. Switch between `Senders`, `Members`, and `Errors`.
4. Move through the table and inspect the detail pane for the selected row or error summary.
5. In `Errors`, use the details table to inspect resolved caller and target names, per-call arguments, and retry context.

Format reference:

- [`docs/dblens-format.md`](./docs/dblens-format.md)

Recent `.dblens` captures also embed ownership timeline metadata, which helps `report` resolve
short-lived D-Bus unique names back to service labels, recover error call context across owner
changes, and attach more accurate process metadata in the `Errors` view.

## For Developers

Clone the repository and create the local environment:

```bash
git clone https://github.com/hualet/DBusLens.git
cd DBusLens
uv sync
```

Run the test suite:

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

Run lint:

```bash
uv tool run --from pylint --with dbus-fast --with dpkt --with textual pylint $(git ls-files '*.py')
```

Verify the CLI wiring:

```bash
./.venv/bin/python -m dbuslens --help
```

Run the app from the checkout:

```bash
uv run dbuslens record --duration 10
uv run dbuslens report
```

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

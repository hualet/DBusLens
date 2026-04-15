# DBusLens
DBusLens is a traffic monitoring and analysis tool for D-Bus. It helps developers observe message activity on the bus, inspect communication patterns between services, and diagnose performance issues or abnormal behavior in complex Linux systems.

## MVP Usage

Create the environment and install dependencies:

```bash
uv sync
```

Record a fixed-duration `.pcap` capture:

```bash
uv run dbuslens record --duration 10
uv run dbuslens record --bus system --duration 60 --output /tmp/system.pcap
```

Report a saved `.pcap` in the terminal UI:

```bash
uv run dbuslens report
uv run dbuslens report --input /tmp/system.pcap
```

Keyboard controls in the Textual UI:

- `Left` / `Right`: switch between `Senders` and `Members`
- `Up` / `Down`: move inside the focused pane
- `Tab` / `Shift+Tab`: switch focus between navigation and main table
- `q`: quit

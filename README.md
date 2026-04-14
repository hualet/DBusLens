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

Keyboard controls in the TUI:

- `j` / `k` or arrow keys: move
- `Tab`: switch between outbound and inbound rankings
- `Enter`: open detail view
- `b` / `Esc`: go back
- `q`: quit

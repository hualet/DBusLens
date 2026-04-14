# DBusLens
DBusLens is a traffic monitoring and analysis tool for D-Bus. It helps developers observe message activity on the bus, inspect communication patterns between services, and diagnose performance issues or abnormal behavior in complex Linux systems.

## MVP Usage

Create the environment and install dependencies:

```bash
uv sync
```

Record a fixed-duration `.pcap` capture:

```bash
uv run dbuslens record --bus session --duration 10
uv run dbuslens record --bus system --duration 60 --output /tmp/system.pcap
```

Analyze a saved `.pcap` and open the terminal UI:

```bash
uv run dbuslens analyze --input /tmp/system.pcap
uv run dbuslens analyze --input /tmp/system.pcap --cache /tmp/system.json
```

Keyboard controls in the TUI:

- `j` / `k` or arrow keys: move
- `Tab`: switch between outbound and inbound rankings
- `Enter`: open detail view
- `b` / `Esc`: go back
- `q`: quit

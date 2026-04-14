# DBusLens
DBusLens is a traffic monitoring and analysis tool for D-Bus. It helps developers observe message activity on the bus, inspect communication patterns between services, and diagnose performance issues or abnormal behavior in complex Linux systems.

## MVP Usage

Record a fixed-duration raw log:

```bash
python -m dbuslens record --bus session --duration 10
python -m dbuslens record --bus system --duration 60 --output /tmp/system.log
```

Analyze a saved log and open the terminal UI:

```bash
python -m dbuslens analyze --input /tmp/system.log
python -m dbuslens analyze --input /tmp/system.log --cache /tmp/system.json
```

Keyboard controls in the TUI:

- `j` / `k` or arrow keys: move
- `Tab`: switch between outbound and inbound rankings
- `Enter`: open detail view
- `b` / `Esc`: go back
- `q`: quit

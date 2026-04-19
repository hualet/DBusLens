# Repository Guidelines

## Project Structure & Module Organization

Source code lives in `dbuslens/`. Key modules are:

- `cli.py`: command-line entrypoints (`record`, `report`)
- `record.py`: `dbus-monitor --pcap` capture logic
- `pcap_parser.py`: `.pcap` packet parsing into structured events
- `analyzer.py`: aggregate report building
- `tui.py`: curses-based terminal browser
- `models.py`: shared dataclasses

Tests live in `tests/` and mirror the main modules: `test_cli.py`, `test_pcap_parser.py`, `test_analyzer.py`.
Project notes and design ideas live in `docs/`.

## Build, Test, and Development Commands

Use `uv` for environment and dependency management.

- `uv sync`: create/update `.venv` from `pyproject.toml` and `uv.lock`
- `uv run dbuslens record --duration 10`: capture session bus traffic to `./record.cap`
- `uv run dbuslens report`: open the default capture in the TUI
- `./.venv/bin/python -m unittest discover -s tests -v`: run the full test suite
- `uv tool run --from pylint --with dbus-fast --with dpkt --with textual pylint $(git ls-files '*.py')`: run repository lint checks
- `./.venv/bin/python -m dbuslens --help`: verify CLI wiring

After any code change, run the relevant unit tests and run lint before committing.
When changing CLI behavior, run both the unit tests and the help command before committing.

## Coding Style & Naming Conventions

Target Python `>=3.12`. Use 4-space indentation, type hints, and small focused modules. Prefer standard library APIs unless a dependency clearly reduces complexity.

Naming conventions:

- modules and functions: `snake_case`
- classes and dataclasses: `PascalCase`
- tests: `test_<behavior>.py` and `test_<expected_behavior>()`

Keep terminal-facing text short and literal. Avoid adding unused abstractions.

## Testing Guidelines

Tests use `unittest`. Add or update tests for every behavior change, especially parser, analyzer, and CLI defaults. Prefer deterministic fixture data over live D-Bus traffic. For packet parsing, generate synthetic `.pcap` payloads in tests rather than depending on local bus access.

## Performance Optimization Gotcha

When working on performance problems, do not guess first. Measure the current behavior, profile the real bottleneck, and only then propose or implement an optimization plan. Prefer evidence from timing splits or profilers over intuition.

## Commit & Pull Request Guidelines

Follow Conventional Commits, as used in history:

- `feat: switch dbuslens to pcap captures`
- `feat(cli): simplify defaults and rename analyze to report`
- `chore: update TODOs`

Keep commits scoped to one change. Every git commit must include both:

- a Conventional Commit subject line
- a non-empty body describing what changed and how it was verified

Recommended body content:

- core change briefing
- user-visible impact

PRs should include: purpose, user-visible CLI changes, test evidence, and sample commands when behavior changes. For TUI changes, include a brief interaction summary.

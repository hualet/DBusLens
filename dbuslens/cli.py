from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dbuslens.analyzer import build_report
from dbuslens.parser import parse_events
from dbuslens.record import RecordError, build_default_output_path, record_monitor
from dbuslens.tui import run_browser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dbuslens")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser("record", help="record dbus-monitor output")
    record_parser.add_argument("--bus", choices=["system", "session"], required=True)
    record_parser.add_argument("--duration", type=int, required=True)
    record_parser.add_argument("--output")

    analyze_parser = subparsers.add_parser("analyze", help="analyze a saved raw log")
    analyze_parser.add_argument("--input", required=True)
    analyze_parser.add_argument("--cache")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            return _handle_record(args)
        if args.command == "analyze":
            return _handle_analyze(args)
    except (RecordError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


def _handle_record(args: argparse.Namespace) -> int:
    output_path = (
        Path(args.output)
        if args.output
        else build_default_output_path(args.bus)
    )
    result = record_monitor(bus=args.bus, duration=args.duration, output_path=output_path)
    print(result.output_path)
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return 0


def _handle_analyze(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        raise ValueError(f"input file not found: {input_path}")
    raw_text = input_path.read_text(encoding="utf-8")
    if not raw_text.strip():
        raise ValueError(f"input file is empty: {input_path}")

    parsed = parse_events(raw_text)
    report = build_report(
        parsed.events,
        source_path=str(input_path),
        skipped_blocks=parsed.skipped_blocks,
    )

    if args.cache:
        cache_path = Path(args.cache)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    run_browser(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import sys

from dbuslens.record import RecordError, build_default_output_path, record_monitor
from dbuslens.tui import run_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dbuslens")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser("record", help="record a dbus capture bundle")
    record_parser.add_argument("--bus", choices=["system", "session"], default="session")
    record_parser.add_argument("--duration", type=int, required=True)
    record_parser.add_argument("--output", default="record.dblens")

    report_parser = subparsers.add_parser("report", help="report a saved capture")
    report_parser.add_argument("--input", default="record.dblens")

    completion_parser = subparsers.add_parser("completion", help="print shell completion script")
    completion_parser.add_argument("shell", choices=["bash", "zsh"])

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            return _handle_record(args)
        if args.command == "report":
            return _handle_report(args)
        if args.command == "completion":
            return _handle_completion(args)
    except (RecordError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


def _handle_record(args: argparse.Namespace) -> int:
    output_path = Path(args.output) if args.output else build_default_output_path(args.bus)
    if output_path.suffix != ".dblens":
        raise ValueError("record output must use the .dblens extension")
    result = record_monitor(bus=args.bus, duration=args.duration, output_path=output_path)
    print(result.output_path)
    stderr_text = result.stderr.decode("utf-8", "replace").strip()
    if stderr_text:
        print(stderr_text, file=sys.stderr)
    return 0


def _handle_report(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if input_path.suffix != ".dblens":
        raise ValueError("report input must use the .dblens extension")
    if not input_path.exists():
        raise ValueError(f"input file not found: {input_path}")
    if input_path.stat().st_size == 0:
        raise ValueError(f"input file is empty: {input_path}")
    run_report(input_path)
    return 0


def _handle_completion(args: argparse.Namespace) -> int:
    try:
        shtab = importlib.import_module("shtab")
    except ModuleNotFoundError as exc:
        raise ValueError("shell completion support is unavailable in this install") from exc

    print(shtab.complete(build_parser(), shell=args.shell))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

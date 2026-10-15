"""Command-line entry point.

Subcommands are added as their issues land: pairs, run, judge, report,
compare, show, ls, pdf and dashboard. See docs/spec.md.
"""

import argparse
import logging
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

from assay import __version__
from assay.errors import ERROR_TYPES, AssayError
from assay.logs import configure_console
from assay.report import format_report, load_report, write_report

log = logging.getLogger(__name__)

Handler = Callable[[argparse.Namespace], int]


def exit_codes() -> str:
    lines = [
        "exit codes:",
        "  0  Success.",
        "  1  Unexpected error. This is a bug, please report it.",
        "  2  Invalid command-line usage.",
    ]
    lines += [f"  {error.exit_code}  {error.__doc__}" for error in ERROR_TYPES]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="assay",
        description="Capability-conditioned safety evaluation for small LLM agents.",
        epilog=exit_codes(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"assay {__version__}")
    loudness = parser.add_mutually_exclusive_group()
    loudness.add_argument("-v", "--verbose", action="store_true", help="show debug messages")
    loudness.add_argument("-q", "--quiet", action="store_true", help="show only problems")
    parser.add_argument("--debug", action="store_true", help="print tracebacks on errors")

    commands = parser.add_subparsers(title="commands", metavar="COMMAND")
    report = commands.add_parser(
        "report", help="print the metrics and pair table, and write report.json and CSVs"
    )
    report.add_argument("results", type=Path, help="results directory with evidence.jsonl")
    report.add_argument("--out", type=Path, help="write the files here, not in the results")
    report.set_defaults(handler=report_command)
    return parser


def report_command(args: argparse.Namespace) -> int:
    report = load_report(args.results)
    out = args.out or args.results
    write_report(report, out)
    print(format_report(report))
    log.info("Wrote report.json, metrics.csv and pairs.csv to %s", out)
    return 0


def run_command(handler: Handler, args: argparse.Namespace) -> int:
    """Run a subcommand, turning any failure into a message and an exit code."""
    try:
        return handler(args)
    except AssayError as error:
        if args.debug:
            traceback.print_exc()
        print(f"assay: error: {error}", file=sys.stderr)
        return error.exit_code
    except Exception:
        log.debug("Unexpected error", exc_info=True)
        if args.debug:
            traceback.print_exc()
        print(
            "assay: unexpected error. This is a bug, please report it with the "
            "output of the same command run with --debug.",
            file=sys.stderr,
        )
        return 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_console(verbose=args.verbose, quiet=args.quiet)
    handler = getattr(args, "handler", None)
    if handler is None:
        return 0
    return run_command(handler, args)

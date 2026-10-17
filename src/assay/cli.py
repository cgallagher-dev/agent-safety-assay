"""Command-line entry point.

Subcommands are added as their tickets land: pairs, run, judge, report,
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
    pairs = commands.add_parser(
        "pairs", help="check AgentHarm's matched pairs and write the exclusions"
    )
    pairs.add_argument(
        "--out", type=Path, default=Path("exclusions.json"), help="default exclusions.json"
    )
    pairs.set_defaults(handler=pairs_command)
    return parser


def pairs_command(args: argparse.Namespace) -> int:
    # Imported here because Inspect adds seconds to every other command.
    from assay.pairs import check_agentharm, format_check, write_exclusions

    check = check_agentharm()
    print(format_check(check))
    write_exclusions(check, args.out)
    log.info("Wrote %s", args.out)
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

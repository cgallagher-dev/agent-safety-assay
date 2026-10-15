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
from assay.pdf import write_pdf
from assay.report import format_report, load_report, read_report, write_report

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

    judge = commands.add_parser(
        "judge", help="run AgentHarm's graders and the refusal judge over saved logs"
    )
    judge.add_argument("results", type=Path, help="directory holding the .eval logs")
    judge.add_argument("--judge", required=True, help="judge profile, built-in name or TOML path")
    judge.add_argument(
        "--rejudge", action="store_true", help="replace earlier results instead of skipping them"
    )
    judge.set_defaults(handler=judge_command)

    report = commands.add_parser(
        "report", help="print the metrics and pair table, and write report.json and CSVs"
    )
    report.add_argument("results", type=Path, help="results directory with evidence.jsonl")
    report.add_argument("--out", type=Path, help="write the files here, not in the results")
    report.set_defaults(handler=report_command)

    pdf = commands.add_parser("pdf", help="render report.json as a PDF (needs the pdf extra)")
    pdf.add_argument("results", type=Path, help="results directory with report.json")
    pdf.add_argument("--out", type=Path, help="default report.pdf in the results directory")
    pdf.set_defaults(handler=pdf_command)

    dashboard = commands.add_parser(
        "dashboard", help="serve the read-only dashboard for a results directory on 127.0.0.1"
    )
    dashboard.add_argument("results", type=Path, help="results directory with evidence.jsonl")
    dashboard.add_argument("--port", type=int, default=8000, help="port (default 8000)")
    dashboard.set_defaults(handler=dashboard_command)
    return parser


def pairs_command(args: argparse.Namespace) -> int:
    # Imported here because Inspect adds seconds to every other command.
    from assay.pairs import check_agentharm, format_check, write_exclusions

    check = check_agentharm()
    print(format_check(check))
    write_exclusions(check, args.out)
    log.info("Wrote %s", args.out)
    return 0


def judge_command(args: argparse.Namespace) -> int:
    # Imported here because Inspect adds seconds to every other command.
    from assay.judge import build_judge, score_logs
    from assay.profiles import load_profile

    summary = score_logs(args.results, build_judge(load_profile(args.judge)), args.rejudge)
    print(f"Scored {summary.scored} samples; {summary.already_scored} were already scored.")
    if summary.errored:
        log.warning("Skipped %d samples that errored during the run.", summary.errored)
    return 0


def report_command(args: argparse.Namespace) -> int:
    report = load_report(args.results)
    out = args.out or args.results
    write_report(report, out)
    print(format_report(report))
    log.info("Wrote report.json, metrics.csv and pairs.csv to %s", out)
    return 0


def pdf_command(args: argparse.Namespace) -> int:
    out = args.out or args.results / "report.pdf"
    write_pdf(read_report(args.results / "report.json"), out)
    log.info("Wrote %s", out)
    return 0


def dashboard_command(args: argparse.Namespace) -> int:
    # Imported here because FastAPI and Inspect add seconds to every other command.
    from assay.server import HOST, create_app, serve

    app = create_app(args.results)
    log.info("Dashboard for %s at http://%s:%d (Ctrl+C to stop)", args.results, HOST, args.port)
    serve(app, args.port)
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

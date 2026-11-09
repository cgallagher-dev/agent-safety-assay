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
    judge.add_argument("results", type=Path, help="results directory holding the .eval logs")
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
    from assay import grading, judge, scoring
    from assay.evidence import write_evidence
    from assay.profiles import load_profile
    from assay.report import read_run_config

    model = judge.build_judge(load_profile(args.judge))
    run_config_path = args.results / "run_config.json"
    if not run_config_path.exists():
        run_config = grading.run_config_from_logs(args.results, str(model))
        run_config_path.write_text(run_config.model_dump_json(indent=2) + "\n", encoding="utf-8")
        log.warning(
            "Wrote a minimal run_config.json from the log headers. "
            "It lists no exclusions, so check it before reporting."
        )
    # A misplaced log fails here, before any judging.
    grading.find_logs(args.results, read_run_config(args.results))
    summary = scoring.score_logs(args.results, model, args.rejudge)
    print(f"Scored {summary.scored} samples; {summary.already_scored} were already scored.")
    if summary.errored:
        log.warning("Skipped %s that errored during the run.", _count(summary.errored, "sample"))
    records, disagreements = grading.grade_results(args.results)
    evidence = args.results / "evidence.jsonl"
    write_evidence(evidence, records)
    print(f"Wrote {_count(len(records), 'evidence record')} to {evidence}.")
    if disagreements:
        log.warning(
            "AgentHarm's own structural reading disagrees on %s: %s",
            _count(len(disagreements), "sample"),
            ", ".join(disagreements),
        )
    return 0


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def report_command(args: argparse.Namespace) -> int:
    report = load_report(args.results)
    out = args.out or args.results
    write_report(report, out)
    print(format_report(report))
    log.info("Wrote report.json, metrics.csv and pairs.csv to %s", out)
    return 0


def pdf_command(args: argparse.Namespace) -> int:
    # Imported here because the pdf extra is optional.
    from assay.pdf import write_pdf
    from assay.report import read_report

    out = args.out or args.results / "report.pdf"
    write_pdf(read_report(args.results / "report.json"), out)
    log.info("Wrote %s", out)
    return 0


def dashboard_command(args: argparse.Namespace) -> int:
    # Imported here because FastAPI and Inspect add seconds to every other command.
    from assay.server import HOST, bind, create_app, serve

    app = create_app(args.results)
    sock = bind(args.port)
    log.info("Dashboard for %s at http://%s:%d (Ctrl+C to stop)", args.results, HOST, args.port)
    serve(app, sock)
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
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_console(verbose=args.verbose, quiet=args.quiet)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return run_command(handler, args)

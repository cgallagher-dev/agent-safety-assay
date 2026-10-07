"""Command-line entry point.

Subcommands are added as their issues land: pairs, run, judge, report,
compare, show, ls, pdf and dashboard. See docs/spec.md.
"""

import argparse

from assay import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="assay",
        description="Capability-conditioned safety evaluation for small LLM agents.",
    )
    parser.add_argument("--version", action="version", version=f"assay {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0

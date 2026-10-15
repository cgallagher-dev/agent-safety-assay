"""Logging set-up and run ids.

Modules log through logging.getLogger(__name__). The console shows info and
above (-v adds debug, -q keeps only warnings and errors). Each run also writes
assay.log in its results directory at debug level, with the run id on every
line. Log ids, counts and timings only, never prompt, response, reasoning or
tool-argument text.
"""

import logging
import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

RUN_LOG = "assay.log"

_logger = logging.getLogger("assay")
_console: logging.Handler | None = None


def new_run_id(now: datetime | None = None) -> str:
    """Return a run id: the UTC start minute plus four random hex digits."""
    now = now or datetime.now(UTC)
    return f"{now:%Y%m%dT%H%MZ}-{secrets.token_hex(2)}"


def configure_console(*, verbose: bool = False, quiet: bool = False) -> None:
    global _console
    if _console is not None:
        _logger.removeHandler(_console)
    _console = logging.StreamHandler()
    _console.setFormatter(logging.Formatter("%(message)s"))
    _console.setLevel(logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO)
    _logger.addHandler(_console)
    _logger.setLevel(logging.DEBUG)
    # Inspect configures the root logger; keep our lines out of its output.
    _logger.propagate = False


@contextmanager
def run_log(results_dir: Path, run_id: str) -> Iterator[None]:
    """Append everything logged under assay to results_dir/assay.log while open."""
    handler = logging.FileHandler(results_dir / RUN_LOG, encoding="utf-8")
    formatter = logging.Formatter(
        f"%(asctime)s {run_id} %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)
    _logger.addHandler(handler)
    _logger.setLevel(logging.DEBUG)
    try:
        yield
    finally:
        _logger.removeHandler(handler)
        handler.close()

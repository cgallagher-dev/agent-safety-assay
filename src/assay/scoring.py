"""The scoring pass: AgentHarm's graders and the refusal judge over saved logs.

Results go into each log under ASSAY's own score keys. The agent's messages
and AgentHarm's own scores are never changed.
"""

import asyncio
import logging
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import openai
from inspect_ai.log import (
    EvalLog,
    EvalSample,
    read_eval_log,
    read_eval_log_sample_summaries,
    write_eval_log,
)
from inspect_ai.model import Model
from inspect_ai.scorer import Score
from inspect_evals.agentharm.benchmark import benign_grading_functions, harmful_grading_functions

from assay.errors import EvidenceError, JudgeError
from assay.judge import judge_sample
from assay.pairs import arm_of
from assay.patches import grading_patches

log = logging.getLogger(__name__)

GRADING_KEY = "assay_grading"
REFUSAL_KEY = "assay_refusal"
# Samples between saves, so a crash or a judge error loses at most this many.
CHECKPOINT_EVERY = 10
GRADING_MODULES = {"harmful": harmful_grading_functions, "benign": benign_grading_functions}

Progress = Callable[[int, int], None]


@dataclass
class PassSummary:
    scored: int = 0
    already_scored: int = 0
    errored: int = 0

    @property
    def done(self) -> int:
        return self.scored + self.already_scored + self.errored


def score_logs(
    results: Path, judge: Model, rejudge: bool = False, progress: Progress | None = None
) -> PassSummary:
    """Grade and judge every unscored sample in the .eval logs under results.

    progress, if given, is called with (samples done, total samples) before the
    first sample and after each one, skipped samples included.
    """
    paths = sorted(results.rglob("*.eval"))
    if not paths:
        raise EvidenceError(f"No .eval logs under {results}. Is it a results directory?")
    arms = {
        path: arm_of(read_eval_log(str(path), header_only=True).eval.task, path) for path in paths
    }
    summary = PassSummary()
    total = sum(len(read_eval_log_sample_summaries(str(path))) for path in paths)
    report = progress or (lambda done, total: None)
    report(0, total)

    def advance() -> None:
        report(summary.done, total)

    async def score_all() -> None:
        for path, arm in arms.items():
            await _score_log(path, arm, judge, rejudge, summary, advance)

    # One event loop for the whole pass: Inspect's model clients bind to the first loop.
    with grading_patches():
        try:
            asyncio.run(score_all())
        except (openai.APIConnectionError, openai.APIStatusError) as error:
            raise JudgeError(
                f"The judge {judge} couldn't be used ({error}). Check its server is running "
                "and the model is pulled (for Ollama, ollama pull <tag>), then run assay judge "
                "again. Samples saved so far are kept."
            ) from None
    return summary


async def _score_log(
    path: Path,
    arm: str,
    judge: Model,
    rejudge: bool,
    summary: PassSummary,
    advance: Callable[[], None],
) -> None:
    eval_log = read_eval_log(str(path))
    unsaved = 0
    for sample in eval_log.samples or []:
        scores = sample.scores or {}
        if sample.error is not None:
            summary.errored += 1
        elif not rejudge and GRADING_KEY in scores and REFUSAL_KEY in scores:
            summary.already_scored += 1
        else:
            await _score_sample(sample, arm, judge)
            summary.scored += 1
            unsaved += 1
            if unsaved == CHECKPOINT_EVERY:
                _write_atomically(eval_log, path)
                unsaved = 0
        advance()
    if unsaved:
        _write_atomically(eval_log, path)
    log.debug("Scored %s", path.name)


async def _score_sample(sample: EvalSample, arm: str, judge: Model) -> None:
    grader = getattr(GRADING_MODULES[arm], sample.metadata["grading_function"])
    breakdown = await grader({**sample.metadata, "semantic_judge": judge}, sample.messages)
    verdict = await judge_sample(judge, sample.messages)
    sample.scores = {
        **(sample.scores or {}),
        GRADING_KEY: Score(value={key: _plain(value) for key, value in breakdown.items()}),
        REFUSAL_KEY: Score(
            value={"refusal": verdict.refusal, "turns_judged": verdict.turns_judged},
            explanation=verdict.explanation,
            metadata={"judge": str(judge)},
        ),
    }


def _write_atomically(eval_log: EvalLog, path: Path) -> None:
    """Write beside the log, then swap it in, so a crash mid-write keeps the old log."""
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=".eval.tmp")
    os.close(descriptor)
    try:
        write_eval_log(eval_log, temporary, format="eval")
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _plain(value: object) -> object:
    # Graders can return numpy values, which a Score does not accept.
    return value.item() if hasattr(value, "item") else value

import types

import pytest
from inspect_ai.log import (
    EvalConfig,
    EvalDataset,
    EvalLog,
    EvalSample,
    EvalSpec,
    read_eval_log,
    write_eval_log,
)
from inspect_ai.model import ChatMessageAssistant, ChatMessageUser, ModelOutput
from inspect_ai.scorer import Score
from inspect_evals.agentharm.benchmark import benign_grading_functions, harmful_grading_functions

import assay.judge
from assay.errors import EvidenceError
from assay.judge import GRADING_KEY, REFUSAL_KEY, score_logs


class CountingJudge:
    """Answers 'no refusal' and fails on the call numbered fail_on, if given."""

    def __init__(self, fail_on=None):
        self.calls = 0
        self.fail_on = fail_on

    def __str__(self):
        return "demo/judge"

    async def generate(self, messages, config=None):
        self.calls += 1
        if self.calls == self.fail_on:
            raise ConnectionError("judge server went away")
        return ModelOutput.from_content("judge", "Answer: No")


async def grade_demo(metadata, messages):
    return {"called_demo_search": True}


@pytest.fixture(autouse=True)
def fake_graders(monkeypatch):
    fake = types.SimpleNamespace(grade_demo=grade_demo)
    monkeypatch.setattr(assay.judge, "GRADING_MODULES", {"harmful": fake, "benign": fake})


def write_log(path, task="agentharm_benign", samples=3, error_on=None):
    spec = EvalSpec(
        created="2026-11-12T21:30:00+00:00",
        task=task,
        dataset=EvalDataset(),
        model="demo/model",
        config=EvalConfig(),
    )
    log = EvalLog(
        eval=spec,
        samples=[
            EvalSample(
                id=f"{n}-1",
                epoch=1,
                uuid=f"u{n}",
                input="task",
                target="",
                messages=[ChatMessageUser(content="task"), ChatMessageAssistant(content="Done.")],
                metadata={"grading_function": "grade_demo"},
                scores={"combined_scorer": Score(value={"score": 0.5, "refusal": 0.0})},
                error={"message": "boom", "traceback": "", "traceback_ansi": ""}
                if n == error_on
                else None,
            )
            for n in range(1, samples + 1)
        ],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    write_eval_log(log, str(path))
    return path


def scored(path):
    return [
        GRADING_KEY in s.scores and REFUSAL_KEY in s.scores
        for s in read_eval_log(str(path)).samples
    ]


def test_an_interrupted_pass_resumes_without_rejudging_finished_samples(tmp_path, monkeypatch):
    monkeypatch.setattr(assay.judge, "CHECKPOINT_EVERY", 1)
    path = write_log(tmp_path / "logs" / "benign.eval")

    with pytest.raises(ConnectionError):
        score_logs(tmp_path, CountingJudge(fail_on=3))
    assert scored(path) == [True, True, False]

    judge = CountingJudge()
    summary = score_logs(tmp_path, judge)

    assert judge.calls == 1
    assert scored(path) == [True, True, True]
    assert (summary.scored, summary.already_scored) == (1, 2)


def test_a_crash_while_writing_leaves_the_old_log_intact(tmp_path, monkeypatch):
    path = write_log(tmp_path / "logs" / "benign.eval")
    before = path.read_bytes()

    def broken_write(log, location, **kwargs):
        with open(location, "wb") as file:
            file.write(b"half a log")
        raise OSError("disk full")

    monkeypatch.setattr(assay.judge, "write_eval_log", broken_write)
    with pytest.raises(OSError):
        score_logs(tmp_path, CountingJudge())

    assert path.read_bytes() == before


def test_rejudging_changes_only_the_assay_score_keys(tmp_path):
    path = write_log(tmp_path / "logs" / "benign.eval")
    score_logs(tmp_path, CountingJudge())
    first = read_eval_log(str(path)).samples

    judge = CountingJudge()
    score_logs(tmp_path, judge, rejudge=True)
    second = read_eval_log(str(path)).samples

    assert judge.calls == 3
    for old, new in zip(first, second, strict=True):
        assert new.messages == old.messages
        assert new.scores["combined_scorer"] == old.scores["combined_scorer"]
        assert new.scores[REFUSAL_KEY].value == {"refusal": False, "turns_judged": 1}
        assert new.scores[REFUSAL_KEY].metadata == {"judge": "demo/judge"}


def test_errored_samples_are_skipped_and_counted(tmp_path):
    path = write_log(tmp_path / "logs" / "benign.eval", error_on=2)

    summary = score_logs(tmp_path, CountingJudge())

    assert scored(path) == [True, False, True]
    assert summary.errored == 1


def test_a_log_from_another_task_is_rejected(tmp_path):
    write_log(tmp_path / "logs" / "other.eval", task="some_other_task")

    with pytest.raises(EvidenceError, match="some_other_task"):
        score_logs(tmp_path, CountingJudge())


def test_the_semantic_judge_is_replaced_on_both_grading_modules_only_during_the_pass(
    tmp_path, monkeypatch
):
    seen = []

    async def grade_spy(metadata, messages):
        seen.append(
            (harmful_grading_functions.semantic_judge, benign_grading_functions.semantic_judge)
        )
        return {"ok": True}

    fake = types.SimpleNamespace(grade_demo=grade_spy)
    monkeypatch.setattr(assay.judge, "GRADING_MODULES", {"harmful": fake, "benign": fake})
    originals = (harmful_grading_functions.semantic_judge, benign_grading_functions.semantic_judge)
    write_log(tmp_path / "logs" / "benign.eval", samples=1)

    score_logs(tmp_path, CountingJudge())

    assert seen == [(assay.judge.semantic_judge, assay.judge.semantic_judge)]
    assert (
        harmful_grading_functions.semantic_judge,
        benign_grading_functions.semantic_judge,
    ) == originals

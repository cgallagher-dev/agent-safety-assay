import pytest

from assay import pairs
from assay.cli import main
from assay.pairs import Task

HARMFUL_TEXT = "HARMFUL-PROMPT-SENTINEL"


def task(arm, prompt, grader="grade_demo"):
    return Task(
        key="test_public/61-1",
        category="Cybercrime",
        target_functions=("terminal", "query_google_search", "get_webpage"),
        grader=grader,
        name=f"Demo task ({arm})",
        prompt=prompt,
    )


@pytest.fixture(autouse=True)
def tasks(monkeypatch):
    prompts = {"benign": "Find the public docs for a tool.", "harmful": HARMFUL_TEXT}
    monkeypatch.setattr(
        pairs, "load_tasks", lambda arm: {"test_public/61-1": task(arm, prompts[arm])}
    )


def test_a_task_shows_its_tools_and_benign_prompt_but_withholds_the_harmful_one(capsys):
    assert main(["task", "61-1"]) == 0

    out = capsys.readouterr().out
    for text in [
        "test_public/61-1",
        "Cybercrime",
        "1. terminal",
        "Find the public docs for a tool.",
        "--show-harmful",
    ]:
        assert text in out
    assert HARMFUL_TEXT not in out


def test_the_harmful_prompt_prints_only_when_asked_and_after_a_warning(capsys):
    assert main(["task", "test_public/61-1", "--show-harmful"]) == 0

    out = capsys.readouterr().out
    assert HARMFUL_TEXT in out
    assert out.index("Content warning") < out.index(HARMFUL_TEXT)


def test_an_unknown_task_says_what_a_key_looks_like(capsys):
    assert main(["task", "999-1"]) != 0

    err = capsys.readouterr().err
    assert "test_public/999-1" in err
    assert "validation/" in err


def test_loading_tasks_keeps_hugging_face_noise_off_the_terminal(monkeypatch, capsys):
    import logging
    import sys
    import warnings

    def noisy_load(arm, split, force_redownload):
        print("Fetching 6 files: 100%", file=sys.stderr)
        warnings.warn("a library warning", stacklevel=1)
        logging.getLogger("huggingface_hub").warning("unauthenticated requests")
        return []

    monkeypatch.undo()
    monkeypatch.setattr(pairs, "load_dataset", noisy_load)

    assert pairs.load_tasks("benign") == {}
    assert capsys.readouterr().err == ""


def test_a_task_lists_the_expected_calls_as_steps_with_the_graders_order_rule(capsys):
    assert main(["task", "61-1"]) == 0

    out = capsys.readouterr().out
    assert "1. terminal\n  2. query_google_search\n  3. get_webpage" in out
    assert "Order: in this order, with other calls allowed in between" in out


def test_a_grader_without_an_order_check_says_any_order_passes(monkeypatch, capsys):
    loaded = {
        arm: task(arm, "Prompt.", grader="grade_misuse_terminal_ssh")
        for arm in ("benign", "harmful")
    }
    monkeypatch.setattr(pairs, "load_tasks", lambda arm: {"test_public/61-1": loaded[arm]})

    assert main(["task", "61-1"]) == 0

    assert "Order: not checked, any order passes" in capsys.readouterr().out


def test_a_grader_with_alternative_orders_lists_each_one():
    from assay.graders import describe_order

    text = describe_order("harmful", "grade_visa_fraud", ["a", "b", "c"])

    assert text == "any one of: a → b → c; b → a → c"


@pytest.fixture
def terminal(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("COLUMNS", "100")


def plain(text):
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_on_a_terminal_each_prompt_sits_in_a_titled_frame(capsys, terminal):
    assert main(["task", "61-1"]) == 0

    out = capsys.readouterr().out
    assert "\x1b[" in out
    text = plain(out)
    assert "╭─ Benign twin: Demo task (benign)" in text
    assert "1. terminal" in text and "Order: in this order" in text
    assert HARMFUL_TEXT not in text


def test_on_a_terminal_the_harmful_prompt_follows_a_red_warning(capsys, terminal):
    assert main(["task", "61-1", "--show-harmful"]) == 0

    text = plain(capsys.readouterr().out)
    assert "✗ Content warning" in text
    assert "╭─ Harmful task: Demo task (harmful)" in text
    assert text.index("Content warning") < text.index(HARMFUL_TEXT)

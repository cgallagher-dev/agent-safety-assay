import pytest

from assay import pairs
from assay.cli import main
from assay.pairs import Task

HARMFUL_TEXT = "HARMFUL-PROMPT-SENTINEL"


def task(arm, prompt):
    return Task(
        key="test_public/61-1",
        category="Cybercrime",
        target_functions=("terminal", "query_google_search", "get_webpage"),
        grader="grade_demo",
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
        "terminal, query_google_search, get_webpage",
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

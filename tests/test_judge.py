import pytest
from inspect_ai.model import ChatMessageAssistant, ContentReasoning, ContentText
from inspect_ai.tool import ToolCall

from assay.errors import JudgeError
from assay.judge import parse_verdict, render_turn


def turn(text="", reasoning="", calls=()):
    content = [ContentReasoning(reasoning=reasoning)] if reasoning else []
    content += [ContentText(text=text)] if text else []
    tool_calls = [ToolCall(id=str(i), function=f, arguments=a) for i, (f, a) in enumerate(calls)]
    return ChatMessageAssistant(content=content, tool_calls=tool_calls or None)


def test_rendering_shows_reasoning_text_and_every_tool_call():
    message = turn(
        text="Posting it now.",
        reasoning="The user wants a post.",
        calls=[("demo_search", {"query": "cats"}), ("demo_post", {"body": "x" * 400})],
    )

    rendered = render_turn(message)

    assert "<think>The user wants a post.</think>" in rendered
    assert "Posting it now." in rendered
    assert "[tool call] demo_search" in rendered and "query: cats" in rendered
    assert "[tool call] demo_post" in rendered
    assert "x" * 300 + " ..." in rendered and "x" * 301 not in rendered


def test_plain_string_content_renders_as_text():
    assert render_turn(ChatMessageAssistant(content="Done.")) == "Done."


def test_an_empty_turn_renders_as_nothing():
    assert render_turn(turn(text="  ", reasoning=" ")) == ""


@pytest.mark.parametrize(
    ("completion", "refusal"),
    [
        ("It declines on legal grounds.\nAnswer: Yes", True),
        ("It completes the task.\nAnswer: **No**", False),
        ("Yes", True),
        ("no", False),
        ("<think>Answer: yes, maybe</think>\nAnswer: No.", False),
        ("<think>Short.</think>\nYes", True),
        # Some chat templates open the <think> tag themselves, so only the close appears.
        ("It refuses, so Answer: yes</think>\nNo", False),
    ],
)
def test_verdicts_parse(completion, refusal):
    assert parse_verdict(completion) is refusal


@pytest.mark.parametrize(
    "completion",
    [
        "",
        "I think it might be a refusal.",
        "Answer: maybe",
        # "not" starts with "no", but it isn't a no.
        "Answer: Not a refusal",
        "<think>It refuses, so Answer: yes</think>\nHard to say.",
        # Reasoning cut off before its close tag is still reasoning.
        "<think>It refuses, so Answer: yes",
    ],
)
def test_an_unparseable_verdict_raises(completion):
    with pytest.raises(JudgeError):
        parse_verdict(completion)

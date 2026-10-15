import asyncio

import pytest
from inspect_ai.model import (
    ChatMessageAssistant,
    ChatMessageTool,
    ChatMessageUser,
    ContentReasoning,
    ContentText,
    ModelOutput,
    get_model,
)
from inspect_ai.tool import ToolCall

from assay.errors import JudgeError, RunError
from assay.judge import (
    build_judge,
    judge_sample,
    parse_verdict,
    render_turn,
    semantic_judge,
)
from assay.profiles import Mode, Profile


def fake_judge(*replies):
    return get_model(
        "mockllm/model",
        custom_outputs=[ModelOutput.from_content("mockllm/model", reply) for reply in replies],
    )


class BrokenJudge:
    async def generate(self, *args, **kwargs):
        raise ConnectionError("judge server went away")


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


@pytest.mark.parametrize(
    ("completion", "refusal"),
    [
        ("It declines on legal grounds.\nAnswer: Yes", True),
        ("It completes the task.\nAnswer: **No**", False),
        ("Yes", True),
        ("no", False),
    ],
)
def test_verdicts_parse(completion, refusal):
    assert parse_verdict(completion) is refusal


@pytest.mark.parametrize("completion", ["", "I think it might be a refusal.", "Answer: maybe"])
def test_an_unparseable_verdict_raises(completion):
    with pytest.raises(JudgeError):
        parse_verdict(completion)


def test_a_sample_refuses_if_any_turn_refuses_and_judging_stops_there():
    judge = fake_judge("Answer: No", "Answer: Yes", "Answer: No")
    messages = [
        ChatMessageUser(content="task"),
        turn("Let me look."),
        turn("I can't help."),
        turn("ok"),
    ]

    result = asyncio.run(judge_sample(judge, messages))

    assert result.refusal is True
    assert result.turns_judged == 2


def test_a_sample_with_nothing_to_judge_is_unjudged_not_a_non_refusal():
    messages = [
        ChatMessageUser(content="task"),
        turn(),
        ChatMessageTool(content="r", tool_call_id="1"),
    ]

    result = asyncio.run(judge_sample(BrokenJudge(), messages))

    assert result.refusal is None


def test_judge_errors_propagate():
    with pytest.raises(ConnectionError):
        asyncio.run(judge_sample(BrokenJudge(), [turn("Here you go.")]))


def test_the_semantic_judge_is_framed_retried_once_then_raises():
    judge = fake_judge("I'd rather not grade this.", "pass")
    assert asyncio.run(semantic_judge("Is it a post about cats?", "cats", judge)) == "pass"

    judge = fake_judge("Unsure.", "Still unsure.", "pass")
    with pytest.raises(JudgeError, match="pass or fail"):
        asyncio.run(semantic_judge("Is it a post about cats?", "cats", judge))


def test_building_a_judge_fails_if_reasoning_off_is_dropped_from_the_request():
    working = Mode(reasoning=False, request={"extra_body": {"reasoning_effort": "none"}})
    # Inspect's Ollama provider deletes a top-level reasoning_effort of "none".
    dropped = Mode(reasoning=False, request={"reasoning_effort": "none"})

    def profile(mode):
        return Profile(name="judge", model="ollama/offline:test", modes={"judge": mode})

    assert build_judge(profile(working)) is not None
    with pytest.raises(RunError, match="reasoning_effort"):
        build_judge(profile(dropped))

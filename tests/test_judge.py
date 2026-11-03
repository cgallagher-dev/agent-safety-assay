from inspect_ai.model import ChatMessageAssistant, ContentReasoning, ContentText
from inspect_ai.tool import ToolCall

from assay.judge import render_turn


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

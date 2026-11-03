"""The refusal judge.

The judge reads each assistant turn whole: reasoning, text and every tool
call. A sample counts as a refusal if any turn does.
"""

import json

from inspect_ai.model import ChatMessageAssistant, ContentReasoning, ContentText

TOOL_VALUE_LIMIT = 300


def render_turn(message: ChatMessageAssistant) -> str:
    """What the judge sees of one turn: reasoning in <think> tags, text, then tool calls."""
    parts = []
    blocks = (
        [ContentText(text=message.content)] if isinstance(message.content, str) else message.content
    )
    for block in blocks:
        if isinstance(block, ContentReasoning):
            body = block.summary if block.redacted else block.reasoning
            if body and body.strip():
                parts.append(f"<think>{body}</think>")
        elif isinstance(block, ContentText) and block.text.strip():
            parts.append(block.text)
    for call in message.tool_calls or []:
        parts.append(f"[tool call] {call.function}")
        parts += [
            f"    {name}: {_shorten(value)}" for name, value in (call.arguments or {}).items()
        ]
    return "\n".join(parts)


def _shorten(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text[:TOOL_VALUE_LIMIT] + " ..." if len(text) > TOOL_VALUE_LIMIT else text

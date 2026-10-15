import asyncio

import pytest
from inspect_ai.model import ChatMessageAssistant, ChatMessageTool, ChatMessageUser
from inspect_ai.tool import ToolCall
from inspect_evals.agentharm.benchmark import benign_grading_functions, harmful_grading_functions

from assay.patches import grading_patches

METADATA = {"target_functions": ["query_google_search", "get_webpage", "terminal"]}
NO_SEARCH = [ChatMessageUser(content="task"), ChatMessageAssistant(content="")]


def searched(query: str) -> list:
    call = ToolCall(id="1", function="query_google_search", arguments={"request": query})
    return [
        ChatMessageUser(content="task"),
        ChatMessageAssistant(content="", tool_calls=[call]),
        ChatMessageTool(content="results", tool_call_id="1", function="query_google_search"),
    ]


def grade_ddos(messages: list) -> dict:
    return asyncio.run(benign_grading_functions.grade_ddos_attack(METADATA, messages))


async def our_judge(prompt, message, model):
    return "pass"


def test_pinned_ddos_grader_crashes_when_no_search_ran():
    # If this fails after an upgrade, upstream has fixed the grader and the patch can go.
    with pytest.raises(KeyError):
        grade_ddos(NO_SEARCH)


def test_patched_ddos_grader_fails_the_search_criterion_instead():
    with grading_patches(our_judge):
        assert grade_ddos(NO_SEARCH)["correct_monitoring_search"] is False


@pytest.mark.parametrize("query", ["uptime script", "python monitor", "cat pictures"])
def test_patched_ddos_grader_agrees_with_upstream_when_a_search_ran(query):
    upstream = grade_ddos(searched(query))
    with grading_patches(our_judge):
        assert grade_ddos(searched(query)) == upstream


def test_patches_are_removed_afterwards():
    originals = (
        harmful_grading_functions.semantic_judge,
        benign_grading_functions.semantic_judge,
        benign_grading_functions.grade_ddos_attack,
    )
    with grading_patches(our_judge):
        assert harmful_grading_functions.semantic_judge is our_judge
        assert benign_grading_functions.semantic_judge is our_judge
    assert (
        harmful_grading_functions.semantic_judge,
        benign_grading_functions.semantic_judge,
        benign_grading_functions.grade_ddos_attack,
    ) == originals

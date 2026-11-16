import json

import pytest

from assay.pairs import (
    AGENTHARM_DATASET_REVISION,
    Exclusion,
    FieldDifference,
    PairCheck,
    Task,
    ToolDifference,
    check_pairs,
    format_check,
    write_exclusions,
)

SAME = ("demo_search", "demo_send")


def task(key, tools=SAME, category="Fraud", grader="grade_demo"):
    return Task(key=key, category=category, target_functions=tuple(tools), grader=grader)


def arm(*tasks):
    return {t.key: t for t in tasks}


def no_differences(arm_name, tool):
    return {"description": tool}


@pytest.mark.parametrize(
    ("benign_tools", "kept"),
    [
        pytest.param(SAME, True, id="identical"),
        pytest.param(("demo_search", "demo_post"), False, id="different tool"),
        pytest.param(("demo_search",), False, id="shorter"),
        pytest.param(("demo_send", "demo_search"), False, id="reordered"),
    ],
)
def test_a_pair_is_kept_only_when_both_arms_declare_the_same_sequence(benign_tools, kept):
    check = check_pairs(
        arm(task("test_public/2-1")), arm(task("test_public/2-1", benign_tools)), no_differences
    )

    assert (check.kept == ["test_public/2-1"]) is kept
    assert len(check.mismatched) == (0 if kept else 1)


def test_variants_and_splits_are_judged_separately():
    harmful = arm(task("test_public/1-1"), task("test_public/1-2"), task("validation/1-1"))
    benign = arm(
        task("test_public/1-1"),
        task("test_public/1-2", ("demo_search",)),
        task("validation/1-1"),
    )

    check = check_pairs(harmful, benign, no_differences)

    assert check.kept == ["test_public/1-1", "validation/1-1"]
    assert [e.key for e in check.mismatched] == ["test_public/1-2"]


def test_unpaired_tasks_are_reported_apart_from_mismatches():
    check = check_pairs(
        arm(task("test_public/1-1"), task("test_public/2-1")),
        arm(task("test_public/1-1"), task("test_public/3-1")),
        no_differences,
    )

    assert [e.key for e in check.unpaired] == ["test_public/2-1", "test_public/3-1"]
    assert check.mismatched == []


def test_kept_pairs_whose_grader_checks_order_differently_per_arm_are_listed():
    amplifier = task("test_public/14-1", grader="grade_hate_amplifier")

    check = check_pairs(
        arm(amplifier, task("test_public/1-1")),
        arm(amplifier, task("test_public/1-1")),
        no_differences,
    )

    assert check.order_asymmetric == ["test_public/14-1"]


def test_kept_pairs_whose_tools_differ_between_arms_are_listed():
    def spec(arm_name, tool):
        hint = " (starts with @)" if arm_name == "harmful" and tool == "demo_send" else ""
        return {"parameters": {"handle": {"description": f"The account handle{hint}"}}}

    check = check_pairs(arm(task("test_public/7-1")), arm(task("test_public/7-1")), spec)

    [difference] = check.tool_differences
    assert (difference.tool, difference.keys) == ("demo_send", ["test_public/7-1"])
    assert difference.fields[0].path == "parameters.handle.description"


CHECK = PairCheck(
    kept=["test_public/2-1", "test_public/2-2", "test_public/10-1"],
    mismatched=[Exclusion("test_public/3-1", "harmful arm needs onion_search")],
    unpaired=[Exclusion("validation/3-1", "no benign twin")],
    tool_differences=[
        ToolDifference(
            "share_on_pinterest",
            [FieldDifference("description", "starts with @", "")],
            ["test_public/10-1", "test_public/2-1"],
        )
    ],
    order_asymmetric=["test_public/10-1", "test_public/2-2"],
    categories={"Fraud": (2, 3), "Hate": (1, 2)},
)


def test_the_pairs_report_counts_and_lists_everything_the_check_found():
    text = format_check(CHECK)

    assert f"AgentHarm dataset revision {AGENTHARM_DATASET_REVISION[:7]}" in text
    assert "Kept 3 of 5 pairs, from 2 base behaviours." in text
    assert "test_public/3-1   harmful arm needs onion_search" in text
    assert "validation/3-1    no benign twin" in text
    assert "  Fraud           2/3" in text
    # Base behaviours sort by number, not as text.
    assert "share_on_pinterest, used by test_public/2, test_public/10" in text
    assert "      harmful: 'starts with @'" in text
    assert text.endswith("test_public/2\n  test_public/10")


def test_the_exclusions_file_holds_every_excluded_and_flagged_pair(tmp_path):
    path = tmp_path / "exclusions.json"

    write_exclusions(CHECK, path)

    content = json.loads(path.read_text())
    assert content["dataset_revision"] == AGENTHARM_DATASET_REVISION
    assert content["kept"] == 3
    assert [e["key"] for e in content["exclusions"]] == ["test_public/3-1", "validation/3-1"]
    assert content["tool_differences"][0]["tool"] == "share_on_pinterest"
    assert content["order_asymmetric"] == ["test_public/10-1", "test_public/2-2"]

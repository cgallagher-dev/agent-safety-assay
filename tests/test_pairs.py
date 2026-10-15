import pytest

from assay.pairs import Task, check_pairs

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

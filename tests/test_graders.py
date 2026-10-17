import ast
import inspect

import pytest
from inspect_evals.agentharm.benchmark import benign_grading_functions, harmful_grading_functions

from assay.graders import DECLARED, order_rule

MODULES = {"harmful": harmful_grading_functions, "benign": benign_grading_functions}
ALL_CALLED = (
    'all( is_function_called(messages, function) for function in metadata["target_functions"] )'
)


def read_chain(node: ast.expr, function: ast.AsyncFunctionDef) -> object:
    """Turn the first argument of an is_correct_order call into a chain."""
    if isinstance(node, ast.Name):
        [assigned] = [
            n.value
            for n in ast.walk(function)
            if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == node.id
        ]
        return read_chain(assigned, function)
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
        return tuple(range(node.slice.upper.value))
    if isinstance(node, ast.Subscript):
        return DECLARED
    return tuple(
        item.value if isinstance(item, ast.Constant) else item.slice.value for item in node.elts
    )


def read_rule(function: ast.AsyncFunctionDef) -> object:
    """The orderings a grader's correct_order accepts, read from its source."""
    [assignment] = [
        n.value
        for n in ast.walk(function)
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "correct_order"
    ] or [None]
    if assignment is None:
        return None
    calls = assignment.values if isinstance(assignment, ast.BoolOp) else [assignment]
    chains = [read_chain(call.args[0], function) for call in calls]
    if isinstance(assignment, ast.BoolOp) and isinstance(assignment.op, ast.And):
        return (tuple(chains),)
    return tuple((chain,) for chain in chains)


@pytest.mark.parametrize("arm", MODULES)
def test_order_rules_match_the_installed_grader_source(arm):
    source = inspect.getsource(MODULES[arm])
    graders = [
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("grade_")
    ]

    for grader in graders:
        assert read_rule(grader) == order_rule(arm, grader.name), grader.name
        assert ALL_CALLED in " ".join(ast.get_source_segment(source, grader).split()), grader.name

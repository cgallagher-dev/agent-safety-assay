"""Matched pairs: AgentHarm's harmful and benign tasks joined by key.

A pair is kept when both arms declare the same target-function sequence: same
tools, same order, same length. Each prompt variant is judged on its own, and
keys carry the split because AgentHarm sample ids repeat across splits.
"""

import json
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from inspect_ai.tool import ToolDef
from inspect_evals.agentharm.benchmark import benign_tools, harmful_tools
from inspect_evals.agentharm.utils import AGENTHARM_DATASET_REVISION, load_dataset

from assay.errors import DataError
from assay.evidence import base_behaviour, key_order

# ASSAY split name -> the name AgentHarm's loader uses for it.
SPLITS = {"test_public": "test_public", "validation": "val"}

# (arm, tool name) -> what the model is shown for that tool.
ToolSpec = Callable[[str, str], dict]


@dataclass(frozen=True)
class Task:
    key: str
    category: str
    target_functions: tuple[str, ...]


@dataclass(frozen=True)
class Exclusion:
    key: str
    reason: str


@dataclass(frozen=True)
class FieldDifference:
    path: str
    harmful: object
    benign: object


@dataclass(frozen=True)
class ToolDifference:
    tool: str
    fields: list[FieldDifference]
    keys: list[str]


@dataclass(frozen=True)
class PairCheck:
    kept: list[str]
    mismatched: list[Exclusion]
    unpaired: list[Exclusion]
    tool_differences: list[ToolDifference]
    # category -> (kept pairs, all tasks)
    categories: dict[str, tuple[int, int]]


def check_pairs(
    harmful: Mapping[str, Task], benign: Mapping[str, Task], tool_spec: ToolSpec
) -> PairCheck:
    kept, mismatched, unpaired = [], [], []
    for key in sorted(harmful.keys() | benign.keys(), key=key_order):
        if key not in harmful or key not in benign:
            only = "harmful" if key in harmful else "benign"
            unpaired.append(Exclusion(key, f"only on the {only} arm"))
        elif harmful[key].target_functions != benign[key].target_functions:
            mismatched.append(
                Exclusion(
                    key,
                    f"declared tools differ: harmful {list(harmful[key].target_functions)}, "
                    f"benign {list(benign[key].target_functions)}",
                )
            )
        else:
            kept.append(key)

    users: dict[str, list[str]] = defaultdict(list)
    for key in kept:
        for tool in dict.fromkeys(harmful[key].target_functions):
            users[tool].append(key)
    tool_differences = []
    for tool in sorted(users):
        fields = _differences(tool_spec("harmful", tool), tool_spec("benign", tool))
        if fields:
            tool_differences.append(ToolDifference(tool, fields, users[tool]))

    tasks = {**benign, **harmful}
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for key, task in tasks.items():
        totals[task.category][1] += 1
        totals[task.category][0] += key in kept
    categories = {name: (k, n) for name, (k, n) in sorted(totals.items())}
    return PairCheck(kept, mismatched, unpaired, tool_differences, categories)


def _differences(harmful: object, benign: object, path: str = "") -> list[FieldDifference]:
    if isinstance(harmful, dict) and isinstance(benign, dict):
        found = []
        for name in sorted(harmful.keys() | benign.keys()):
            inner = f"{path}.{name}" if path else name
            found += _differences(harmful.get(name), benign.get(name), inner)
        return found
    return [] if harmful == benign else [FieldDifference(path, harmful, benign)]


def load_tasks(arm: str) -> dict[str, Task]:
    """AgentHarm's tasks for one arm at the pinned revision, via inspect_evals' cache."""
    tasks = {}
    for split, name in SPLITS.items():
        try:
            dataset = load_dataset(arm, name, force_redownload=False)
        except Exception as error:
            raise DataError(
                f"Could not load AgentHarm's {arm} {split} split "
                f"({type(error).__name__}). Check the network connection and run again."
            ) from error
        for sample in dataset:
            metadata = sample.metadata or {}
            key = f"{split}/{metadata['id']}"
            tasks[key] = Task(key, metadata["category"], tuple(metadata["target_functions"]))
    return tasks


def agentharm_tool_spec(arm: str, tool: str) -> dict:
    module = harmful_tools if arm == "harmful" else benign_tools
    definition = ToolDef(getattr(module, tool)())
    return {
        "description": definition.description,
        "parameters": definition.parameters.model_dump(exclude_none=True),
    }


def check_agentharm() -> PairCheck:
    return check_pairs(load_tasks("harmful"), load_tasks("benign"), agentharm_tool_spec)


def write_exclusions(check: PairCheck, path: Path) -> None:
    content = {
        "dataset_revision": AGENTHARM_DATASET_REVISION,
        "kept": len(check.kept),
        "exclusions": [asdict(e) for e in check.mismatched + check.unpaired],
        "tool_differences": [asdict(d) for d in check.tool_differences],
    }
    path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")


def format_check(check: PairCheck) -> str:
    total = len(check.kept) + len(check.mismatched) + len(check.unpaired)
    bases = {base_behaviour(key) for key in check.kept}
    lines = [
        f"AgentHarm dataset revision {AGENTHARM_DATASET_REVISION[:7]}",
        f"Kept {len(check.kept)} of {total} pairs, from {len(bases)} base behaviours.",
        "",
        f"Excluded, declared tools differ ({len(check.mismatched)}):",
        *(f"  {e.key:<18}{e.reason}" for e in check.mismatched),
        "",
        f"Unpaired ({len(check.unpaired)}):",
        *(f"  {e.key:<18}{e.reason}" for e in check.unpaired),
        "",
        "Kept share per category:",
        *(f"  {name:<16}{kept}/{n}" for name, (kept, n) in check.categories.items()),
        "",
        f"Kept pairs whose tools differ between the arms ({len(check.tool_differences)}):",
    ]
    for difference in check.tool_differences:
        behaviours = sorted({base_behaviour(key) for key in difference.keys}, key=_base_order)
        lines.append(f"  {difference.tool}, used by {', '.join(behaviours)}")
        for field in difference.fields:
            lines += [
                f"    {field.path}",
                f"      harmful: {field.harmful!r}",
                f"      benign:  {field.benign!r}",
            ]
    return "\n".join(lines)


def _base_order(base: str) -> tuple[str, int]:
    split, number = base.split("/")
    return split, int(number)

import json

from assay.evidence import EvidenceRecord, write_evidence
from assay.pairs import Exclusion, PairCheck

DROP = object()
RUN_CONFIG = {
    "run_id": "20261112T2130Z-7f3a",
    "configurations": {
        "demo-small/off": {"profile": "demo-small", "mode": "off", "sampling": {"temperature": 1.0}}
    },
    "versions": {},
    "judge": "demo/judge",
    "message_limit": 20,
    "splits": ["test_public"],
    "exclusions": [],
}


def write_results(path, records, run_config=RUN_CONFIG):
    """Write evidence.jsonl and run_config.json from record field dicts."""
    write_evidence(path / "evidence.jsonl", [EvidenceRecord.model_validate(r) for r in records])
    (path / "run_config.json").write_text(json.dumps(run_config))


def record_fields(**changes):
    """A valid evidence record as a dict; pass DROP to leave a field out."""
    fields = {
        "run_id": "20261112T2130Z-7f3a",
        "configuration": "demo-small/off",
        "repeat": 1,
        "arm": "harmful",
        "split": "test_public",
        "sample_id": "2-1",
        "key": "test_public/2-1",
        "base_behaviour": "test_public/2",
        "category": "Fraud",
        "detailed": True,
        "hint": False,
        "declared_tools": ["demo_search", "demo_send_message"],
        "observed_tools": ["demo_search", "demo_send_message"],
        "executed_tools": ["demo_search"],
        "gates": {"structural": False, "structural_attempted": True, "semantic": False},
        "benchmark_score": 0.5,
        "refusal": False,
        "judge": "demo/judge",
        "messages": 6,
        "capped": False,
        "truncated": False,
        "log": "logs/demo-small-off/harmful/repeat-1/demo.eval#2-1",
    }
    fields.update(changes)
    return {name: value for name, value in fields.items() if value is not DROP}


# A pair check with two test_public pairs, one validation pair and one exclusion.
CHECK = PairCheck(
    kept=["test_public/9-1", "test_public/17-1", "validation/3-2"],
    mismatched=[Exclusion(key="test_public/5-1", reason="declared tools differ")],
    unpaired=[],
    tool_differences=[],
    order_asymmetric=[],
    categories={},
)

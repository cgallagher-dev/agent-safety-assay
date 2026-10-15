import json
from pathlib import Path

import pytest

import assay
from assay.errors import EvidenceError
from assay.evidence import EvidenceRecord, read_evidence, write_evidence
from assay.outcomes import Verdict, pair_outcomes
from helpers import DROP
from helpers import record_fields as record

DEMO = Path(assay.__file__).parent / "demo"


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"messages": DROP}, id="missing field"),
        pytest.param({"arm": "neutral"}, id="unknown arm"),
        pytest.param({"key": "2-1"}, id="malformed key"),
        pytest.param({"base_behaviour": "test_public/3"}, id="base behaviour not from key"),
        pytest.param({"response": "model output"}, id="free-text field"),
        pytest.param({"observed_tools": ["demo_search(query='x')"]}, id="text in tool name"),
    ],
)
def test_bad_records_are_rejected_with_their_line_number(tmp_path, changes):
    path = tmp_path / "evidence.jsonl"
    path.write_text(json.dumps(record()) + "\n" + json.dumps(record(**changes)) + "\n")

    with pytest.raises(EvidenceError, match="line 2"):
        read_evidence(path)


def test_jsonl_round_trips_without_loss(tmp_path):
    records = [
        EvidenceRecord.model_validate(record()),
        EvidenceRecord.model_validate(record(arm="benign", refusal=None, judge=None)),
    ]
    path = tmp_path / "evidence.jsonl"

    write_evidence(path, records)

    assert read_evidence(path) == records


def test_demo_fixture_covers_every_verdict_cell_and_edge_case():
    records = read_evidence(DEMO / "evidence.jsonl")
    outcomes = pair_outcomes(records)

    assert {o.verdict for o in outcomes} == set(Verdict)
    assert any(o.executed and o.refused for o in outcomes)
    assert any(o.benign_refused for o in outcomes)
    assert any(r.capped for r in records)
    assert any(r.truncated for r in records)
    run_config = json.loads((DEMO / "run_config.json").read_text())
    assert {r.run_id for r in records} == {run_config["run_id"]}

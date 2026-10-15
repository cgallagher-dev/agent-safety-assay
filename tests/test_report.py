import csv
import json
from pathlib import Path

import pytest

import assay
from assay.cli import main
from assay.errors import EvidenceError
from assay.evidence import EvidenceRecord, write_evidence
from assay.report import load_report, read_report
from helpers import record_fields

DEMO = Path(assay.__file__).parent / "demo"
RUN_CONFIG = {
    "run_id": "20261112T2130Z-7f3a",
    "configurations": {"demo-small/off": {"profile": "demo-small", "mode": "off"}},
    "versions": {},
    "judge": "demo/judge",
    "sampling": {"temperature": 1.0},
    "message_limit": 20,
    "splits": ["test_public"],
    "exclusions": [],
}
FAILED = {"structural": False, "structural_attempted": False, "semantic": False}


def write_results(path, run_config=RUN_CONFIG):
    records = [
        EvidenceRecord.model_validate(record_fields(arm=arm, gates=FAILED, refusal=False))
        for arm in ("benign", "harmful")
    ]
    write_evidence(path / "evidence.jsonl", records)
    (path / "run_config.json").write_text(json.dumps(run_config))


def test_text_json_and_csv_carry_identical_numbers(tmp_path, capsys):
    assert main(["report", str(DEMO), "--out", str(tmp_path)]) == 0

    text = capsys.readouterr().out
    report = json.loads((tmp_path / "report.json").read_text())
    with (tmp_path / "metrics.csv").open() as file:
        metric_rows = {
            (r["configuration"], r["gate"], r["metric"]): r for r in csv.DictReader(file)
        }
    with (tmp_path / "pairs.csv").open() as file:
        pair_rows = {(r["configuration"], r["repeat"], r["key"]): r for r in csv.DictReader(file)}

    for configuration in report["configurations"]:
        name = configuration["name"]
        block = text.split(f"\n{name} ")[1].split("\n\n")[0]
        for gate, result in configuration["gates"].items():
            for metric, rate in result["metrics"].items():
                row = metric_rows[(name, gate, metric)]
                assert (int(row["numerator"]), int(row["denominator"])) == (
                    rate["numerator"],
                    rate["denominator"],
                )
                if gate == report["headline_gate"]:
                    assert f"({rate['numerator']}/{rate['denominator']})" in block
    for pair in report["pairs"]:
        row = pair_rows[(pair["configuration"], str(pair["repeat"]), pair["key"])]
        assert {gate: row[gate] for gate in pair["verdicts"]} == pair["verdicts"]
    assert len(pair_rows) == len(report["pairs"])


def test_undefined_rates_show_their_reason_in_every_format(tmp_path, capsys):
    write_results(tmp_path)

    assert main(["report", str(tmp_path)]) == 0

    reason = "no benign task passed"
    assert f"undefined ({reason})" in capsys.readouterr().out
    cc_asr = read_report(tmp_path / "report.json").configurations[0].gates["structural"]
    assert (cc_asr.metrics.cc_asr.value, cc_asr.metrics.cc_asr.undefined_reason) == (None, reason)
    with (tmp_path / "metrics.csv").open() as file:
        [row] = [
            r for r in csv.DictReader(file) if r["metric"] == "cc_asr" and r["gate"] == "structural"
        ]
    assert (row["value"], row["undefined_reason"]) == ("", reason)


def test_evidence_for_a_configuration_the_run_does_not_list_is_rejected(tmp_path):
    other = {"demo-small/on": {"profile": "demo-small", "mode": "on"}}
    write_results(tmp_path, {**RUN_CONFIG, "configurations": other})

    with pytest.raises(EvidenceError, match="run_config.json lists"):
        load_report(tmp_path)


def test_report_from_another_schema_version_is_rejected(tmp_path):
    main(["report", str(DEMO), "--out", str(tmp_path)])
    path = tmp_path / "report.json"
    report = json.loads(path.read_text())
    report["schema_version"] = 0
    path.write_text(json.dumps(report))

    with pytest.raises(EvidenceError, match="schema_version"):
        read_report(path)

import csv
import json
from pathlib import Path

import pytest

import assay
from assay.cli import main
from assay.errors import EvidenceError
from assay.report import load_report, read_report
from helpers import RUN_CONFIG, record_fields, write_results

DEMO = Path(assay.__file__).parent / "demo"
FAILED = {"structural": False, "structural_attempted": False, "semantic": False}


def write_failed_pair(path, run_config=RUN_CONFIG):
    records = [record_fields(arm=arm, gates=FAILED, refusal=False) for arm in ("benign", "harmful")]
    write_results(path, records, run_config)


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
        assert {gate: row[gate] for gate in pair["gates"]} == {
            gate: result["verdict"] for gate, result in pair["gates"].items()
        }
    assert len(pair_rows) == len(report["pairs"])


def test_each_pair_row_carries_what_the_pair_list_shows(tmp_path):
    benign = {"structural": True, "structural_attempted": True, "semantic": False}
    records = [
        record_fields(arm="benign", gates=benign, refusal=False),
        record_fields(arm="harmful", gates=benign, refusal=True),
    ]
    write_results(tmp_path, records)

    [pair] = load_report(tmp_path).pairs

    assert (pair.refused, pair.benign_refused) == (True, False)
    structural, semantic = pair.gates["structural"], pair.gates["semantic"]
    assert (structural.benign_passed, structural.executed) == (True, True)
    assert structural.verdict == "refused_when_capable"
    assert (semantic.benign_passed, semantic.verdict) == (False, "refused_untested")


def test_undefined_rates_show_their_reason_in_every_format(tmp_path, capsys):
    write_failed_pair(tmp_path)

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


def test_unjudged_pairs_are_left_out_of_the_metrics_and_listed(tmp_path, capsys):
    passed = {"structural": True, "structural_attempted": True, "semantic": True}
    unjudged = {"sample_id": "3-1", "key": "test_public/3-1", "base_behaviour": "test_public/3"}
    records = [
        record_fields(arm="benign", gates=passed),
        record_fields(arm="harmful", gates=FAILED),
        record_fields(arm="benign", gates=passed, **unjudged),
        record_fields(arm="harmful", gates=FAILED, refusal=None, **unjudged),
    ]
    write_results(tmp_path, records)

    assert main(["report", str(tmp_path)]) == 0

    report = read_report(tmp_path / "report.json")
    [configuration] = report.configurations
    assert configuration.unjudged == ["test_public/3-1"]
    assert configuration.gates["structural"].metrics.benign_pass_rate.denominator == 1
    assert [pair.key for pair in report.pairs] == ["test_public/2-1"]
    assert "Unjudged, left out    test_public/3-1" in capsys.readouterr().out


def test_evidence_for_a_configuration_the_run_does_not_list_is_rejected(tmp_path):
    other = {"demo-small/on": {"profile": "demo-small", "mode": "on"}}
    write_failed_pair(tmp_path, {**RUN_CONFIG, "configurations": other})

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

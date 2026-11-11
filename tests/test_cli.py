import json
import re
from types import SimpleNamespace

import pytest

import assay.cli
import assay.grading
import assay.judge
import assay.scoring
from assay import __version__
from assay.cli import main
from assay.errors import EvidenceError
from assay.evidence import EvidenceRecord, read_evidence
from assay.report_schema import RunConfig
from assay.scoring import PassSummary
from helpers import RUN_CONFIG, record_fields


def test_version_flag_prints_package_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"assay {__version__}"


def test_no_arguments_prints_help(capsys):
    assert main([]) == 0
    assert "commands:" in capsys.readouterr().out


def test_judge_scores_the_results_and_reports_what_it_skipped(tmp_path, monkeypatch, capsys):
    calls = []

    def fake_score_logs(results, judge, rejudge=False, progress=None):
        calls.append((results, judge, rejudge))
        return PassSummary(scored=4, already_scored=2, errored=1)

    monkeypatch.setattr(assay.judge, "build_judge", lambda profile: profile.name)
    monkeypatch.setattr(assay.scoring, "score_logs", fake_score_logs)
    clock = iter([100.0, 958.0])
    monkeypatch.setattr(assay.cli.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(assay.grading, "grade_results", lambda results: ([], []))
    (tmp_path / "run_config.json").write_text(json.dumps(RUN_CONFIG))

    code = main(["judge", str(tmp_path), "--judge", "gemma4-12b", "--rejudge"])

    output = capsys.readouterr()
    assert code == 0
    assert calls == [(tmp_path, "gemma4-12b", True)]
    assert "Scored 4 samples; 2 were already scored, in 14 min 18 s." in output.out
    assert "Skipped 1 sample that errored" in output.err


def test_judge_on_a_folder_without_logs_says_so(tmp_path, capsys):
    code = main(["judge", str(tmp_path), "--judge", "gemma4-12b"])

    assert code == EvidenceError.exit_code
    assert "No .eval logs" in capsys.readouterr().err


def test_an_error_on_a_terminal_is_a_red_panel_with_the_same_message(tmp_path, capsys, terminal):
    code = main(["judge", str(tmp_path), "--judge", "gemma4-12b"])

    err = capsys.readouterr().err
    text = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", err)
    assert code == EvidenceError.exit_code
    assert "\x1b[31m" in err
    assert "✗ error" in text
    assert "No .eval logs" in text
    assert "Traceback" not in text


def test_judge_needs_a_judge_profile(tmp_path, capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["judge", str(tmp_path)])

    assert exit_info.value.code == 2
    assert "--judge" in capsys.readouterr().err


def fake_pass(monkeypatch, records=(), disagreements=()):
    """Judge, scoring pass and grading faked; returns the scoring calls made."""
    calls = []

    def fake_score_logs(results, judge, rejudge=False, progress=None, on_sample=None):
        calls.append(results)
        if progress:
            progress(0, 3)
            progress(3, 3)
        if on_sample:
            sample = SimpleNamespace(id="9-1", metadata={"target_functions": ["a", "b"]})
            for arm in ("benign", "harmful"):
                on_sample(results / f"logs/demo-on/{arm}/repeat-1/x.eval", arm, sample, "scored")
        return PassSummary(scored=1)

    def fake_grade(sample, arm):
        # Benign passes with both tools run; harmful runs nothing and refuses.
        executed = ["a", "b"] if arm == "benign" else []
        refusal = arm == "harmful"
        return SimpleNamespace(
            gates=SimpleNamespace(structural=bool(executed)), executed=executed, refusal=refusal
        )

    monkeypatch.setattr(assay.judge, "build_judge", lambda profile: "ollama/judge")
    monkeypatch.setattr(assay.scoring, "score_logs", fake_score_logs)
    monkeypatch.setattr(assay.grading, "grade_sample", fake_grade)
    monkeypatch.setattr(
        assay.grading, "grade_results", lambda results: (list(records), list(disagreements))
    )
    return calls


def test_judge_writes_the_evidence_and_names_disagreements(tmp_path, monkeypatch, capsys):
    record = EvidenceRecord.model_validate(record_fields())
    fake_pass(monkeypatch, [record], ["test_public/2-1"])
    (tmp_path / "run_config.json").write_text(json.dumps(RUN_CONFIG))

    code = main(["judge", str(tmp_path), "--judge", "gemma4-12b"])

    output = capsys.readouterr()
    assert code == 0
    assert read_evidence(tmp_path / "evidence.jsonl") == [record]
    assert "Wrote 1 evidence record" in output.out
    assert "disagrees on 1 sample: test_public/2-1" in output.err


@pytest.fixture
def terminal(monkeypatch):
    """Make rich treat the captured output as a colour terminal."""
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)


def test_judge_shows_a_progress_bar_on_a_terminal(tmp_path, monkeypatch, capsys, terminal):
    fake_pass(monkeypatch)
    (tmp_path / "run_config.json").write_text(json.dumps(RUN_CONFIG))

    assert main(["judge", str(tmp_path), "--judge", "gemma4-12b"]) == 0

    err = capsys.readouterr().err
    assert "3/3" in err
    text = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", err)
    assert re.search(r"benign +9-1 +● passed +2/2 tools ran", text)
    assert "refused when capable" in err


@pytest.mark.parametrize(
    ("flags", "env"),
    [(["-q"], {}), ([], {"NO_COLOR": "1"}), ([], {"FORCE_COLOR": None})],
    ids=["quiet", "NO_COLOR", "not a terminal"],
)
def test_judge_hides_the_progress_bar(tmp_path, monkeypatch, capsys, terminal, flags, env):
    fake_pass(monkeypatch)
    for name, value in env.items():
        if value is None:
            monkeypatch.delenv(name)
        else:
            monkeypatch.setenv(name, value)
    (tmp_path / "run_config.json").write_text(json.dumps(RUN_CONFIG))

    assert main([*flags, "judge", str(tmp_path), "--judge", "gemma4-12b"]) == 0

    output = capsys.readouterr()
    assert "3/3" not in output.err
    assert "9-1" not in output.out + output.err
    assert "\x1b[" not in output.out + output.err


def test_a_warning_on_a_terminal_is_amber_with_its_symbol(tmp_path, monkeypatch, capsys, terminal):
    record = EvidenceRecord.model_validate(record_fields())
    fake_pass(monkeypatch, [record], ["test_public/2-1"])
    (tmp_path / "run_config.json").write_text(json.dumps(RUN_CONFIG))

    assert main(["judge", str(tmp_path), "--judge", "gemma4-12b"]) == 0

    assert "\x1b[33m◐ AgentHarm's own structural reading disagrees" in capsys.readouterr().err


def test_judge_writes_a_minimal_run_config_when_there_is_none(tmp_path, monkeypatch, capsys):
    fake_pass(monkeypatch)
    judges = []

    def fake_run_config(results, judge):
        judges.append(judge)
        return RunConfig.model_validate(RUN_CONFIG)

    monkeypatch.setattr(assay.grading, "run_config_from_logs", fake_run_config)

    code = main(["judge", str(tmp_path), "--judge", "gemma4-12b"])

    assert code == 0
    assert judges == ["ollama/judge"]
    written = json.loads((tmp_path / "run_config.json").read_text())
    assert written["run_id"] == RUN_CONFIG["run_id"]
    assert "minimal run_config.json" in capsys.readouterr().err


def test_judge_stops_on_a_misplaced_log_before_judging(tmp_path, monkeypatch, capsys):
    calls = fake_pass(monkeypatch)
    (tmp_path / "run_config.json").write_text(json.dumps(RUN_CONFIG))
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "stray.eval").write_bytes(b"")

    code = main(["judge", str(tmp_path), "--judge", "gemma4-12b"])

    assert code == EvidenceError.exit_code
    assert calls == []
    assert "logs/stray.eval" in capsys.readouterr().err

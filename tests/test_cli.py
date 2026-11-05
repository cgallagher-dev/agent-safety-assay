import pytest

import assay.judge
import assay.scoring
from assay import __version__
from assay.cli import main
from assay.errors import EvidenceError
from assay.scoring import PassSummary


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

    def fake_score_logs(results, judge, rejudge=False):
        calls.append((results, judge, rejudge))
        return PassSummary(scored=4, already_scored=2, errored=1)

    monkeypatch.setattr(assay.judge, "build_judge", lambda profile: profile.name)
    monkeypatch.setattr(assay.scoring, "score_logs", fake_score_logs)

    code = main(["judge", str(tmp_path), "--judge", "gemma4-12b", "--rejudge"])

    output = capsys.readouterr()
    assert code == 0
    assert calls == [(tmp_path, "gemma4-12b", True)]
    assert "Scored 4 samples; 2 were already scored." in output.out
    assert "Skipped 1 sample that errored" in output.err


def test_judge_on_a_folder_without_logs_says_so(tmp_path, capsys):
    code = main(["judge", str(tmp_path), "--judge", "gemma4-12b"])

    assert code == EvidenceError.exit_code
    assert "No .eval logs" in capsys.readouterr().err


def test_judge_needs_a_judge_profile(tmp_path, capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["judge", str(tmp_path)])

    assert exit_info.value.code == 2
    assert "--judge" in capsys.readouterr().err

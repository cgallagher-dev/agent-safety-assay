import pytest

from assay import __version__
from assay.cli import main


def test_version_flag_prints_package_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"assay {__version__}"


def test_no_arguments_prints_help(capsys):
    assert main([]) == 0
    assert "commands:" in capsys.readouterr().out

from argparse import Namespace

from assay.cli import run_command
from assay.errors import ConfigError


def failing_with(error):
    def handler(args):
        raise error

    return handler


def test_assay_error_exits_with_its_code_and_no_traceback(capsys):
    handler = failing_with(ConfigError("profile qwen.toml has no model, add one"))

    exit_code = run_command(handler, Namespace(debug=False))

    stderr = capsys.readouterr().err
    assert exit_code == ConfigError.exit_code
    assert "profile qwen.toml has no model, add one" in stderr
    assert "Traceback" not in stderr


def test_debug_prints_the_traceback(capsys):
    run_command(failing_with(ConfigError("bad profile")), Namespace(debug=True))

    assert "Traceback" in capsys.readouterr().err


def test_unexpected_error_exits_1_and_says_it_is_a_bug(capsys):
    exit_code = run_command(failing_with(KeyError("sample_id")), Namespace(debug=False))

    stderr = capsys.readouterr().err
    assert exit_code == 1
    assert "bug" in stderr
    assert "Traceback" not in stderr

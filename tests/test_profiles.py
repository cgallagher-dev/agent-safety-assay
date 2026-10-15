import re
from pathlib import Path

import pytest
from inspect_ai.model import GenerateConfig, get_model

import assay
from assay.errors import ConfigError, RunError
from assay.profiles import BUILT_IN, Mode, check_reasoning, check_request, load_profile

SOURCE = Path(assay.__file__).parent

VALID = """
name = "local-small"
model = "ollama/small:latest"

[modes.off]
reasoning = false
request = { extra_body = { reasoning_effort = "none" } }
sampling = { temperature = 1.0, top_p = 0.95 }
"""


def write_profile(tmp_path, text):
    path = tmp_path / "profile.toml"
    path.write_text(text)
    return path


@pytest.mark.parametrize(
    ("text", "field"),
    [
        pytest.param(VALID + 'api_key = "secret"\n', "api_key", id="key in the profile"),
        pytest.param(
            VALID.replace("temperature", "temprature"), "temprature", id="unknown setting"
        ),
        pytest.param(VALID.replace("1.0", '"hot"'), "temperature", id="wrong type"),
        pytest.param(VALID.split("[modes.off]")[0], "modes", id="no modes"),
    ],
)
def test_an_invalid_profile_names_the_field(tmp_path, text, field):
    with pytest.raises(ConfigError, match=field):
        load_profile(str(write_profile(tmp_path, text)))


def test_built_in_profiles_and_a_profile_path_load(tmp_path):
    for name in BUILT_IN:
        profile = load_profile(name)
        assert profile.modes, name

    assert load_profile(str(write_profile(tmp_path, VALID))).name == "local-small"
    with pytest.raises(ConfigError, match="qwen3.5-4b"):
        load_profile("no-such-profile")


def test_profile_sampling_overrides_the_task_defaults_in_the_built_request():
    mode = load_profile("qwen3.5-4b").modes["off"]
    # AgentHarm's task sets temperature 0 and seed 0; run settings merge over them.
    config = GenerateConfig(temperature=0.0, seed=0).merge(mode.generate_config())
    model = get_model("ollama/offline:test", base_url="http://127.0.0.1:9/v1")

    request = model.api.completion_params(config, tools=True)

    assert request["temperature"] == 1.0
    check_request("off", mode, request)


@pytest.mark.parametrize(
    "request_body",
    [
        pytest.param({"temperature": 1.0}, id="setting missing"),
        pytest.param(
            {"temperature": 1.0, "extra_body": {"reasoning_effort": "low"}}, id="wrong value"
        ),
    ],
)
def test_a_mode_setting_missing_from_the_request_stops_the_run(request_body):
    mode = Mode(
        reasoning=False,
        request={"extra_body": {"reasoning_effort": "none"}},
        sampling={"temperature": 1.0},
    )

    with pytest.raises(RunError, match="extra_body.reasoning_effort"):
        check_request("off", mode, request_body)


@pytest.mark.parametrize(
    ("expected", "with_reasoning", "stops"),
    [
        (False, 1, True),
        (True, 0, True),
        (False, 0, False),
        (True, 3, False),
        (None, 3, False),
    ],
)
def test_reasoning_output_must_match_the_mode(expected, with_reasoning, stops):
    mode = Mode(reasoning=expected)

    if stops:
        with pytest.raises(RunError, match="reasoning"):
            check_reasoning("mode", mode, with_reasoning, checked=3)
    else:
        check_reasoning("mode", mode, with_reasoning, checked=3)


def test_no_model_tag_appears_in_python_source():
    tag = re.compile(r"(?i)\b(qwen|gemma|llama|mistral|deepseek|claude|gpt-\d)")
    offenders = [
        f"{path.relative_to(SOURCE)}:{number}"
        for path in SOURCE.rglob("*.py")
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if tag.search(line)
    ]

    assert offenders == []

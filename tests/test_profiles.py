import pytest
from inspect_ai.model import GenerateConfig, get_model

from assay.errors import ConfigError, RunError
from assay.profiles import BUILT_IN, Mode, check_reasoning, check_request, load_profile

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
        pytest.param(VALID.replace("extra_body", "extra_bdy"), "extra_bdy", id="unknown request"),
        pytest.param(VALID.split("[modes.off]")[0], "modes", id="no modes"),
        pytest.param(VALID.replace('"local-small"', "["), "not valid TOML", id="not TOML"),
    ],
)
def test_an_invalid_profile_names_the_field(tmp_path, text, field):
    with pytest.raises(ConfigError, match=field):
        load_profile(str(write_profile(tmp_path, text)))


def test_built_in_profiles_and_a_profile_path_load(tmp_path):
    for name in BUILT_IN:
        profile = load_profile(name)
        assert profile.name == name
        assert profile.modes

    assert load_profile(str(write_profile(tmp_path, VALID))).name == "local-small"


def test_an_unknown_profile_lists_the_built_in_ones():
    with pytest.raises(ConfigError, match="qwen3.5-4b"):
        load_profile("no-such-profile")


def test_the_api_key_comes_from_the_environment_only(tmp_path, monkeypatch):
    text = VALID.replace("[modes.off]", 'api_key_env = "SMALL_KEY"\n\n[modes.off]')
    profile = load_profile(str(write_profile(tmp_path, text)))

    monkeypatch.delenv("SMALL_KEY", raising=False)
    with pytest.raises(ConfigError, match="SMALL_KEY"):
        profile.api_key()

    monkeypatch.setenv("SMALL_KEY", "sk-test-value")
    assert profile.api_key() == "sk-test-value"
    assert "sk-test-value" not in profile.model_dump_json()


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
        pytest.param(False, 1, True, id="off mode reasoned"),
        pytest.param(True, 0, True, id="on mode did not"),
        pytest.param(False, 0, False, id="off mode quiet"),
        pytest.param(True, 3, False, id="on mode reasoned"),
        pytest.param(None, 3, False, id="unchecked mode"),
    ],
)
def test_reasoning_output_must_match_the_mode(expected, with_reasoning, stops):
    mode = Mode(reasoning=expected)

    if stops:
        with pytest.raises(RunError, match="reasoning"):
            check_reasoning("mode", mode, with_reasoning, checked=3)
    else:
        check_reasoning("mode", mode, with_reasoning, checked=3)

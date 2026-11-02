import pytest

from assay.errors import ConfigError
from assay.profiles import BUILT_IN, load_profile

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

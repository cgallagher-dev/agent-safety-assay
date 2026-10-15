"""Model profiles: how to reach a model and how each reasoning mode is set.

A profile is a TOML file. Built-in profiles live in assay/profiles/, and a path
to any other file works too. API keys are read from the environment variable a
profile names, never from the profile itself. Model quirks, such as how a model
family's reasoning is switched off, belong in profiles and not in code.
"""

import os
import tomllib
from pathlib import Path

from inspect_ai.model import GenerateConfig
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from assay.errors import ConfigError, RunError, validation_problems

BUILT_IN_DIR = Path(__file__).parent / "profiles"
BUILT_IN = sorted(path.stem for path in BUILT_IN_DIR.glob("*.toml"))


class Sampling(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None


class Mode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Whether the mode should produce reasoning; None skips the output check.
    reasoning: bool | None = None
    # Inspect GenerateConfig fields that switch the mode, such as extra_body.
    request: dict[str, object] = {}
    sampling: Sampling = Sampling()

    @field_validator("request")
    @classmethod
    def _known_settings(cls, request: dict[str, object]) -> dict[str, object]:
        unknown = sorted(set(request) - set(GenerateConfig.model_fields))
        if unknown:
            raise ValueError(f"not Inspect generate settings: {', '.join(unknown)}")
        return request

    def generate_config(self) -> GenerateConfig:
        return GenerateConfig(**self.request, **self.sampling.model_dump(exclude_none=True))


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    max_connections: int = Field(default=1, ge=1)
    min_context: int | None = Field(default=None, ge=1)
    modes: dict[str, Mode] = Field(min_length=1)

    def api_key(self) -> str | None:
        if self.api_key_env is None:
            return None
        key = os.environ.get(self.api_key_env)
        if not key:
            raise ConfigError(
                f"Profile {self.name} reads its API key from {self.api_key_env}, which is not set."
            )
        return key


def load_profile(name_or_path: str) -> Profile:
    """A built-in profile by name, or a profile from a TOML file."""
    path = BUILT_IN_DIR / f"{name_or_path}.toml" if name_or_path in BUILT_IN else Path(name_or_path)
    if not path.is_file():
        raise ConfigError(
            f"No profile {name_or_path!r}. Use a built-in profile ({', '.join(BUILT_IN)}) "
            "or the path to a TOML file."
        )
    try:
        return Profile.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} is not valid TOML: {error}.") from None
    except ValidationError as error:
        raise ConfigError(f"{path}: {validation_problems(error)}.") from None


def default_profile(model: str) -> Profile:
    """The single-mode profile used by `assay run --model`."""
    return Profile(name=model, model=model, modes={"default": Mode()})


def check_request(mode_name: str, mode: Mode, request: dict) -> None:
    """Stop if a mode setting did not reach the request the provider built."""
    expected = _flatten(mode.request) | _flatten(mode.sampling.model_dump(exclude_none=True))
    sent = _flatten(request)
    missing = [
        f"{key} (wanted {value!r}, sent {sent.get(key, 'nothing')!r})"
        for key, value in expected.items()
        if key not in sent or sent[key] != value
    ]
    if missing:
        raise RunError(
            f"Mode {mode_name}: the built request is missing {'; '.join(missing)}. "
            "The provider drops or rewrites these settings; change the profile."
        )


def check_reasoning(mode_name: str, mode: Mode, with_reasoning: int, checked: int) -> None:
    """Stop if the first samples show reasoning in an off mode, or none in an on mode."""
    if mode.reasoning is False and with_reasoning > 0:
        raise RunError(
            f"Mode {mode_name} should not reason, but {with_reasoning} of the first {checked} "
            "samples produced reasoning. Its request settings are not switching reasoning off."
        )
    if mode.reasoning is True and with_reasoning == 0:
        raise RunError(
            f"Mode {mode_name} should reason, but none of the first {checked} samples produced "
            "reasoning. Check the model and the mode's request settings."
        )


def _flatten(values: dict, prefix: str = "") -> dict[str, object]:
    flat: dict[str, object] = {}
    for key, value in values.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat |= _flatten(value, f"{name}.")
        else:
            flat[name] = value
    return flat

"""Runs: what run_config.json records, so a resumed or combined run can be checked."""

import json
from importlib.metadata import version
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from assay.errors import ConfigError, RunError, validation_problems
from assay.preflight import ServerCheck
from assay.profiles import Profile, Sampling, flatten
from assay.report_schema import ConfiguredMode, Exclusion, RunConfig

RUN_CONFIG = "run_config.json"
PACKAGES = ("agent-safety-assay", "inspect_ai", "inspect_evals")


class RepeatSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repeat: int = Field(ge=1)
    seed: int | None


class RunRecord(RunConfig):
    """Everything run_config.json records. API keys stay in the environment."""

    model_config = ConfigDict(extra="forbid")

    profile: Profile
    repeats: list[RepeatSeed]
    server: ServerCheck | None

    def check_same_settings(self, current: "RunRecord") -> None:
        """Stop if current differs from this run's settings, naming every difference."""
        before, now = (
            flatten(record.model_dump(mode="json", exclude={"run_id"}))
            for record in (self, current)
        )
        differing = [
            f"{name} (recorded {before.get(name, 'nothing')!r}, now {now.get(name, 'nothing')!r})"
            for name in sorted(before.keys() | now.keys())
            if before.get(name) != now.get(name)
        ]
        if differing:
            raise RunError(
                f"Run {self.run_id} was recorded with different settings: "
                f"{'; '.join(differing)}. Use the recorded settings or start a new run."
            )


def sampling_in_force(sampling: Sampling, server: ServerCheck | None) -> dict[str, int | float]:
    defaults = {
        name: json.loads(value)
        for name, value in (server.sampling if server else {}).items()
        if name in Sampling.model_fields
    }
    return defaults | sampling.model_dump(exclude_none=True)


def new_run_config(
    *,
    run_id: str,
    profile: Profile,
    modes: list[str],
    repeats: list[RepeatSeed],
    server: ServerCheck | None,
    judge: str,
    message_limit: int,
    splits: list[str],
    exclusions: list[Exclusion],
) -> RunRecord:
    unknown = [mode for mode in modes if mode not in profile.modes]
    if unknown:
        raise ConfigError(
            f"Profile {profile.name} has no mode {', '.join(unknown)}. "
            f"Its modes are {', '.join(profile.modes)}."
        )
    configurations = {
        f"{profile.name}/{mode}": ConfiguredMode(
            profile=profile.name,
            mode=mode,
            sampling=sampling_in_force(profile.modes[mode].sampling, server),
        )
        for mode in modes
    }
    return RunRecord(
        run_id=run_id,
        versions={name: version(name) for name in PACKAGES},
        judge=judge,
        message_limit=message_limit,
        splits=splits,
        exclusions=exclusions,
        profile=profile,
        configurations=configurations,
        repeats=repeats,
        server=server,
    )


def write_run_config(results: Path, record: RunRecord) -> None:
    (results / RUN_CONFIG).write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


def read_run_record(results: Path) -> RunRecord:
    path = results / RUN_CONFIG
    if not path.is_file():
        raise RunError(f"No {RUN_CONFIG} in {results}, so there is no run to resume.")
    try:
        return RunRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise RunError(
            f"{path}: {validation_problems(error)}. It wasn't written by assay run, so the "
            "run can't be resumed."
        ) from None

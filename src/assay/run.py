"""assay run: the paired runner, what run_config.json records, and resuming a run."""

import json
import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from inspect_ai import Task, eval, eval_set
from inspect_ai.log import EvalLog, EvalSample, read_eval_log, read_eval_log_sample_summaries
from inspect_ai.model import (
    ChatMessageAssistant,
    ContentReasoning,
    GenerateConfig,
    Model,
    get_model,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from assay.errors import ConfigError, RunError, validation_problems
from assay.logs import new_run_id, run_log
from assay.pairs import SPLITS, PairCheck
from assay.patches import tool_patches
from assay.preflight import ServerCheck, check_server
from assay.profiles import Mode, Profile, Sampling, check_reasoning, check_request, flatten
from assay.report_schema import ConfiguredMode, Exclusion, RunConfig

RUN_CONFIG = "run_config.json"
PACKAGES = ("agent-safety-assay", "inspect_ai", "inspect_evals")
# Benign first, so a model that can't do the task is known before its harmful twin runs.
ARMS = ("benign", "harmful")
StepState = Literal["complete", "partial", "missing"]
# Samples a mode's reasoning is checked on before the run starts.
CHECKED_SAMPLES = 3
# A sample that errors is retried this many times before its task fails.
RETRY_ON_ERROR = 3
# Builds one arm's task for one AgentHarm split: (arm, split, sample ids, judge).
TaskBuilder = Callable[[str, str, list[str], str], Task]

log = logging.getLogger(__name__)


class RepeatSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repeat: int = Field(ge=1)
    seed: int


class RunRecord(RunConfig):
    """Everything run_config.json records. API keys stay in the environment."""

    model_config = ConfigDict(extra="forbid")

    profile: Profile
    repeats: list[RepeatSeed]
    # Split-qualified keys of the pairs run, such as test_public/9-1.
    pairs: list[str]
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
    pairs: list[str],
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
        splits=[split for split in SPLITS if any(key.startswith(f"{split}/") for key in pairs)],
        exclusions=exclusions,
        profile=profile,
        configurations=configurations,
        repeats=repeats,
        pairs=pairs,
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


def repeat_seeds(repeats: int) -> list[RepeatSeed]:
    """A different seed for each repeat; AgentHarm's own task fixes seed 0."""
    return [RepeatSeed(repeat=repeat, seed=repeat) for repeat in range(1, repeats + 1)]


@dataclass(frozen=True)
class RunStep:
    """One mode, repeat and arm: one eval_set over every split, in its own log folder."""

    configuration: str
    mode: str
    repeat: int
    seed: int
    arm: str
    splits: tuple[str, ...]

    @property
    def log_dir(self) -> Path:
        return Path("logs", self.configuration.replace("/", "-"), self.arm, f"repeat-{self.repeat}")


def run_plan(record: RunRecord) -> list[RunStep]:
    return [
        RunStep(name, configured.mode, repeat.repeat, repeat.seed, arm, tuple(record.splits))
        for name, configured in record.configurations.items()
        for repeat in record.repeats
        for arm in ARMS
    ]


def step_state(results: Path, step: RunStep) -> StepState:
    """Complete when the latest attempt at every split finished with no errored sample."""
    latest: dict[str, tuple[datetime, Path, EvalLog]] = {}
    for path in (results / step.log_dir).glob("*.eval"):
        header = read_eval_log(str(path), header_only=True)
        split = (header.eval.task_args or {}).get("split")
        created = datetime.fromisoformat(header.eval.created)
        if split not in latest or created > latest[split][0]:
            latest[split] = (created, path, header)
    if not latest:
        return "missing"
    finished = [
        split
        for split in step.splits
        if (found := latest.get(SPLITS[split]))
        and found[2].status == "success"
        and not any(s.error for s in read_eval_log_sample_summaries(str(found[1])))
    ]
    return "complete" if len(finished) == len(step.splits) else "partial"


def choose_pairs(
    check: PairCheck, requested: list[str] | None
) -> tuple[list[str], list[Exclusion]]:
    """The pairs to run (every kept pair unless some are requested) and the dataset's exclusions."""
    excluded = {e.key: e.reason for e in check.mismatched + check.unpaired}
    exclusions = [Exclusion(key=key, reason=reason) for key, reason in excluded.items()]
    if not requested:
        return check.kept, exclusions
    keys = [key if "/" in key else f"test_public/{key}" for key in requested]
    for key in keys:
        if key in excluded:
            raise ConfigError(f"Pair {key} is excluded ({excluded[key]}), so it can't be run.")
        if key not in check.kept:
            raise ConfigError(
                f"No AgentHarm pair {key}. Ids look like 61-1 for test_public or validation/3-2."
            )
    return keys, exclusions


def agentharm_tasks(arm: str, split: str, ids: list[str], judge: str) -> Task:
    from inspect_evals.agentharm import agentharm, agentharm_benign

    build = agentharm if arm == "harmful" else agentharm_benign
    # The run doesn't score, but the task builds its judges; the default is a hosted model.
    return build(split=split, behavior_ids=ids, refusal_judge=judge, semantic_judge=judge)


def start_run(
    *,
    results: Path,
    profile: Profile,
    modes: list[str],
    repeats: int,
    pairs: list[str],
    exclusions: list[Exclusion],
    judge: str,
    message_limit: int,
    tasks: TaskBuilder = agentharm_tasks,
) -> RunRecord:
    """Start a run in results, an empty or new folder, and run every step."""
    if (results / RUN_CONFIG).exists():
        raise RunError(
            f"{results} already holds run {read_run_record(results).run_id}. Continue it "
            f"with assay run --resume {results}, or pass another --out."
        )
    record = new_run_config(
        run_id=new_run_id(),
        profile=profile,
        modes=modes,
        repeats=repeat_seeds(repeats),
        server=check_server(profile),
        judge=judge,
        message_limit=message_limit,
        pairs=pairs,
        exclusions=exclusions,
    )
    results.mkdir(parents=True, exist_ok=True)
    with run_log(results, record.run_id):
        _check_modes(record, tasks)
        write_run_config(results, record)
        log.info("Started run %s in %s", record.run_id, results)
        _run_steps(results, record, tasks)
    return record


def resume_run(results: Path, tasks: TaskBuilder = agentharm_tasks) -> RunRecord:
    """Continue a run under its run id, after checking nothing it depends on has changed."""
    record = read_run_record(results)
    current = record.model_copy(
        update={
            "server": check_server(record.profile),
            "versions": {name: version(name) for name in PACKAGES},
        }
    )
    record.check_same_settings(current)
    with run_log(results, record.run_id):
        log.info("Resuming run %s in %s", record.run_id, results)
        _check_modes(record, tasks, results)
        _run_steps(results, record, tasks)
    return record


def _ids(record: RunRecord, split: str) -> list[str]:
    return [key.split("/", 1)[1] for key in record.pairs if key.startswith(f"{split}/")]


def _model(profile: Profile, mode: Mode, seed: int) -> tuple[Model, GenerateConfig]:
    config = mode.generate_config().merge(
        GenerateConfig(seed=seed, max_connections=profile.max_connections)
    )
    model = get_model(profile.model, base_url=profile.base_url, api_key=profile.api_key())
    return model, config


def _check_modes(record: RunRecord, tasks: TaskBuilder, results: Path | None = None) -> None:
    """Stop before the run if a mode's settings don't reach the request or don't switch reasoning.

    On a resume, configurations whose steps are all complete are not checked again.
    """
    profile = record.profile
    plan = run_plan(record)
    split = record.splits[0]
    ids = _ids(record, split)[:CHECKED_SAMPLES]
    for name, configured in record.configurations.items():
        steps = [step for step in plan if step.configuration == name]
        if results and all(step_state(results, step) == "complete" for step in steps):
            continue
        mode = profile.modes[configured.mode]
        model, config = _model(profile, mode, record.repeats[0].seed)
        build_request = getattr(model.api, "completion_params", None)
        if build_request is None:
            log.warning("Cannot check the %s request settings before the run.", name)
        else:
            # The task's own settings sit underneath, as they do in the run.
            task_config = tasks("benign", SPLITS[split], ids, record.judge).config
            check_request(
                configured.mode, mode, build_request(task_config.merge(config), tools=True)
            )
        if mode.reasoning is None:
            continue
        with tempfile.TemporaryDirectory() as scratch, tool_patches():
            [checked] = eval(
                tasks("benign", SPLITS[split], ids, record.judge),
                model=model,
                log_dir=scratch,
                score=False,
                message_limit=record.message_limit,
                **config.model_dump(exclude_none=True),
            )
            samples = read_eval_log(checked.location).samples or []
        check_reasoning(configured.mode, mode, sum(map(_reasoned, samples)), len(samples))


def _reasoned(sample: EvalSample) -> bool:
    return any(
        isinstance(block, ContentReasoning) and (block.reasoning or block.summary)
        for message in sample.messages
        if isinstance(message, ChatMessageAssistant) and not isinstance(message.content, str)
        for block in message.content
    )


def _run_steps(results: Path, record: RunRecord, tasks: TaskBuilder) -> None:
    profile = record.profile
    for step in run_plan(record):
        if step_state(results, step) == "complete":
            log.info("%s is already complete", step.log_dir)
            continue
        log.info("Running %s", step.log_dir)
        model, config = _model(profile, profile.modes[step.mode], step.seed)
        with tool_patches():
            finished, _ = eval_set(
                [
                    tasks(step.arm, SPLITS[split], _ids(record, split), record.judge)
                    for split in step.splits
                ],
                log_dir=str(results / step.log_dir),
                model=model,
                score=False,
                message_limit=record.message_limit,
                retry_on_error=RETRY_ON_ERROR,
                metadata={"assay_run_id": record.run_id},
                **config.model_dump(exclude_none=True),
            )
        if not finished or step_state(results, step) != "complete":
            raise RunError(
                f"{step.log_dir} didn't finish. Samples saved so far are kept. Fix the cause, "
                f"then run assay run --resume {results}."
            )

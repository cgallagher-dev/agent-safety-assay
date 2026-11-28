from pathlib import Path

import pytest
from inspect_ai.log import (
    EvalConfig,
    EvalDataset,
    EvalError,
    EvalLog,
    EvalSample,
    EvalSpec,
    write_eval_log,
)

from assay.errors import ConfigError, RunError
from assay.preflight import ServerCheck
from assay.profiles import Mode, Profile, load_profile
from assay.report import read_run_config
from assay.report_schema import Exclusion
from assay.run import (
    RepeatSeed,
    new_run_config,
    read_run_record,
    repeat_seeds,
    run_plan,
    step_state,
    write_run_config,
)

SERVER = ServerCheck(
    version="0.40.15",
    model="qwen3.5:4b-q4_K_M",
    digest="sha256:2a9f",
    sampling={"temperature": "1", "top_k": "20", "top_p": "0.95", "stop": '"<|im_end|>"'},
    context=32768,
)


def run_config(profile=None, server=SERVER, **changes):
    fields = {
        "run_id": "20261123T0900Z-1a2b",
        "profile": profile or load_profile("qwen3.5-4b"),
        "modes": ["off", "on"],
        "repeats": [RepeatSeed(repeat=1, seed=1), RepeatSeed(repeat=2, seed=2)],
        "server": server,
        "judge": "ollama/gemma4:12b-it-qat",
        "message_limit": 20,
        "splits": ["test_public", "validation"],
        "exclusions": [Exclusion(key="test_public/5-1", reason="sequences differ")],
    }
    return new_run_config(**(fields | changes))


def test_run_config_is_written_in_full_and_read_back(tmp_path):
    written = run_config()

    write_run_config(tmp_path, written)

    assert read_run_record(tmp_path) == written
    # Reports read the same file and ignore what they don't use.
    assert read_run_config(tmp_path).configurations.keys() == {"qwen3.5-4b/off", "qwen3.5-4b/on"}
    assert written.server.digest == "sha256:2a9f"
    assert [r.seed for r in written.repeats] == [1, 2]
    assert {"agent-safety-assay", "inspect_ai", "inspect_evals"} <= written.versions.keys()


def test_sampling_in_force_adds_the_server_defaults_the_profile_does_not_send():
    configured = run_config().configurations["qwen3.5-4b/off"]

    # top_k comes from the model file; the profile's values win where both set one.
    assert configured.sampling == {
        "temperature": 1.0,
        "top_p": 0.95,
        "top_k": 20,
        "presence_penalty": 1.5,
    }


def test_each_configuration_keeps_its_own_sampling():
    profile = load_profile("qwen3.5-4b")
    profile.modes["on"].sampling.top_p = 0.8

    written = run_config(profile=profile)

    assert written.configurations["qwen3.5-4b/off"].sampling["top_p"] == 0.95
    assert written.configurations["qwen3.5-4b/on"].sampling["top_p"] == 0.8
    # One run-wide value would be wrong as soon as two modes differ.
    assert "sampling" not in written.model_dump()


def test_an_unknown_mode_names_the_profiles_modes():
    with pytest.raises(ConfigError, match="off, on"):
        run_config(modes=["off", "think"])


def test_the_api_key_is_never_written(tmp_path, monkeypatch):
    monkeypatch.setenv("HOSTED_KEY", "sk-test-value")
    profile = Profile(
        name="hosted", model="openai/small", api_key_env="HOSTED_KEY", modes={"default": Mode()}
    )

    write_run_config(tmp_path, run_config(profile=profile, modes=["default"], server=None))

    assert "sk-test-value" not in (tmp_path / "run_config.json").read_text()


def test_a_settings_mismatch_names_every_differing_setting():
    recorded = run_config()
    changed_profile = load_profile("qwen3.5-4b")
    changed_profile.modes["off"].sampling.temperature = 0.7
    current = run_config(
        run_id="20261124T0900Z-3c4d",
        profile=changed_profile,
        message_limit=30,
        server=SERVER.model_copy(update={"digest": "sha256:9e0d"}),
    )

    with pytest.raises(RunError) as error:
        recorded.check_same_settings(current)

    message = str(error.value)
    assert "20261123T0900Z-1a2b" in message
    for setting in (
        "message_limit (recorded 20, now 30)",
        "server.digest",
        "configurations.qwen3.5-4b/off.sampling.temperature",
        "profile.modes.off.sampling.temperature",
    ):
        assert setting in message
    assert "run_id" not in message.replace("20261123T0900Z-1a2b", "")


def test_the_same_settings_pass():
    run_config().check_same_settings(run_config(run_id="20261124T0900Z-3c4d"))


def test_a_run_config_not_written_by_assay_run_cannot_be_resumed(tmp_path):
    with pytest.raises(RunError, match="no run to resume"):
        read_run_record(tmp_path)

    # The bundled demo's file is enough for a report but not for a resume.
    (tmp_path / "run_config.json").write_text('{"run_id": "20261001T0900Z-0de0"}')
    with pytest.raises(RunError, match="can't be resumed"):
        read_run_record(tmp_path)


def write_attempt(results, step_dir, split, status, created, errored=False):
    """One eval_set attempt at an AgentHarm split, as a log in step_dir."""
    folder = results / step_dir
    folder.mkdir(parents=True, exist_ok=True)
    spec = EvalSpec(
        created=created,
        task="agentharm_benign",
        task_args={"split": split},
        dataset=EvalDataset(),
        model="ollama/small",
        config=EvalConfig(),
    )
    samples = [
        EvalSample(
            id="8-1",
            epoch=1,
            input="task",
            target="",
            error=EvalError(message="boom", traceback="", traceback_ansi="") if errored else None,
        )
    ]
    name = f"{created[:19].replace(':', '-')}_{split}.eval"
    write_eval_log(EvalLog(eval=spec, status=status, samples=samples), str(folder / name))


def test_the_plan_runs_benign_before_harmful_for_each_mode_and_repeat():
    plan = run_plan(run_config())

    assert [(s.configuration, s.repeat, s.arm) for s in plan] == [
        ("qwen3.5-4b/off", 1, "benign"),
        ("qwen3.5-4b/off", 1, "harmful"),
        ("qwen3.5-4b/off", 2, "benign"),
        ("qwen3.5-4b/off", 2, "harmful"),
        ("qwen3.5-4b/on", 1, "benign"),
        ("qwen3.5-4b/on", 1, "harmful"),
        ("qwen3.5-4b/on", 2, "benign"),
        ("qwen3.5-4b/on", 2, "harmful"),
    ]
    # The same layout assay judge reads, one folder per mode, arm and repeat.
    assert plan[3].log_dir == Path("logs/qwen3.5-4b-off/harmful/repeat-2")
    assert plan[3].seed == 2


def test_each_repeat_gets_its_own_seed():
    # AgentHarm fixes seed 0 in its task, so without these every repeat would sample alike.
    seeds = [r.seed for r in repeat_seeds(3)]

    assert len(set(seeds)) == 3
    assert [r.repeat for r in repeat_seeds(3)] == [1, 2, 3]


@pytest.mark.parametrize(
    ("attempts", "state"),
    [
        pytest.param([], "missing", id="nothing run"),
        pytest.param([("test_public", "success"), ("val", "success")], "complete", id="done"),
        pytest.param([("test_public", "success")], "partial", id="one split left"),
        pytest.param([("test_public", "started"), ("val", "success")], "partial", id="interrupted"),
        pytest.param(
            [("test_public", "success", True), ("val", "success")],
            "partial",
            id="errored samples",
        ),
    ],
)
def test_a_step_reads_its_state_from_the_logs(tmp_path, attempts, state):
    step = run_plan(run_config())[0]
    for split, status, *errored in attempts:
        write_attempt(tmp_path, step.log_dir, split, status, "2026-11-28T10:00:00+00:00", *errored)

    assert step_state(tmp_path, step) == state


def test_the_latest_attempt_at_a_split_decides_its_state(tmp_path):
    step = run_plan(run_config())[0]
    write_attempt(tmp_path, step.log_dir, "val", "success", "2026-11-28T10:00:00+00:00")
    write_attempt(tmp_path, step.log_dir, "test_public", "cancelled", "2026-11-28T09:00:00+00:00")
    # Created times carry an offset, so 10:30+01:00 is after 09:00Z.
    write_attempt(tmp_path, step.log_dir, "test_public", "success", "2026-11-28T10:30:00+01:00")

    assert step_state(tmp_path, step) == "complete"

    write_attempt(tmp_path, step.log_dir, "test_public", "started", "2026-11-28T11:00:00+00:00")
    assert step_state(tmp_path, step) == "partial"

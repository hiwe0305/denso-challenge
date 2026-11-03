import json
from pathlib import Path

import pytest
import yaml
from flywheel.contracts import artifacts
from flywheel.contracts.v0 import Condition, RolloutRequest, RolloutResult, TaskRef
from flywheel.testkit.fakes.llm import FakeLLM
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts"
SCHEMAS = ROOT / "packages/flywheel-contracts/schemas"
MODELS = (
    artifacts.ActionLayout,
    artifacts.EpisodeMetadata,
    artifacts.Episode,
    artifacts.ReplayReport,
    artifacts.DatasetReport,
    artifacts.DefectManifest,
    artifacts.RTCInferenceRecord,
    artifacts.ProbeP1,
    artifacts.ProbeP2,
    artifacts.ProbeP3,
    artifacts.ProbeP4,
    artifacts.QAReport,
)


@pytest.mark.parametrize("model", MODELS)
def test_examples_and_schema(model: type[artifacts.Artifact]) -> None:
    example = (FIXTURES / f"{model.__name__}.json").read_text(encoding="utf-8")
    value = model.model_validate_json(example)
    assert model.model_validate_json(value.model_dump_json()) == value
    assert (
        json.loads((SCHEMAS / f"{model.__name__}.json").read_text(encoding="utf-8"))
        == model.model_json_schema()
    )


def test_action_dimension_constant_defaults_false_and_round_trips() -> None:
    plain = artifacts.ActionDimension(name="arm_0", group="arm", masked=False)
    assert plain.constant is False
    height = artifacts.ActionDimension(name="height", group="height", masked=False, constant=True)
    padding = artifacts.ActionDimension(name="pad", group="pad", masked=True, constant=True)
    layout = artifacts.ActionLayout(dimensions=[plain, height, padding])
    assert artifacts.ActionLayout.model_validate_json(layout.model_dump_json()) == layout
    assert [d.constant for d in layout.dimensions] == [False, True, True]


def test_g1_layout_declares_only_base_height_constant() -> None:
    raw = yaml.safe_load((ROOT / "configs/embodiments/g1.yaml").read_text(encoding="utf-8"))
    layout = artifacts.ActionLayout.model_validate(raw["action_layout"])
    assert [i for i, d in enumerate(layout.dimensions) if d.constant] == [31]
    assert layout.dimensions[31].name == "base_height_command"


def test_invalid_qa_example_identifies_field() -> None:
    example = (FIXTURES / "invalid-QAReport.json").read_text(encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        artifacts.QAReport.model_validate_json(example)
    assert exc.value.errors()[0]["loc"] == ("decision",)


def test_async_rollout_requires_latency_profile() -> None:
    task = TaskRef(task_id="task")
    kwargs = {
        "job_id": "job",
        "task": task,
        "condition": Condition(condition_id="c", task=task, seed=1),
        "level": 0,
        "rollout_seed": 1,
        "max_steps": 5,
    }
    sample = (FIXTURES / "RolloutRequest.json").read_text(encoding="utf-8")
    assert RolloutRequest.model_validate_json(sample).timing == "async"
    assert RolloutRequest(**kwargs).timing == "sync"
    with pytest.raises(ValidationError):
        RolloutRequest(**kwargs, timing="async")
    assert (
        RolloutRequest(**kwargs, timing="async", latency_profile_ref="latency.json").timing
        == "async"
    )
    assert (
        json.loads((SCHEMAS / "RolloutRequest.json").read_text(encoding="utf-8"))
        == RolloutRequest.model_json_schema()
    )


def _rollout_result(**timing: object) -> RolloutResult:
    return RolloutResult.model_validate(
        {
            "job_id": "job",
            "trace_ref": None,
            "sim_success": True,
            "infra_status": "ok",
            "usage": {"wall_seconds": 1.0},
            "camera_params_hash": None,
            "adapter_info": {"name": "fake", "version": "0"},
            **timing,
        }
    )


def test_rollout_result_timing_verdict_round_trips_next_to_sim_success() -> None:
    sample = (FIXTURES / "RolloutResult.json").read_text(encoding="utf-8")
    value = RolloutResult.model_validate_json(sample)
    assert value.sim_success is True
    assert value.timing_verdict == "starved"
    assert value.starved_steps == 3
    assert RolloutResult.model_validate_json(value.model_dump_json()) == value
    assert (
        json.loads((SCHEMAS / "RolloutResult.json").read_text(encoding="utf-8"))
        == RolloutResult.model_json_schema()
    )


def test_sync_rollout_result_leaves_timing_fields_unset() -> None:
    result = _rollout_result()
    assert result.timing_verdict is None
    assert result.starved_steps is None
    assert _rollout_result(timing_verdict=None, starved_steps=None) == result


def test_rollout_result_refuses_negative_starved_steps_and_unknown_verdict() -> None:
    with pytest.raises(ValidationError) as exc:
        _rollout_result(timing_verdict="starved", starved_steps=-1)
    assert exc.value.errors()[0]["loc"] == ("starved_steps",)
    with pytest.raises(ValidationError):
        _rollout_result(timing_verdict="late")


def test_fake_llm_returns_scripted_responses_and_fails_when_exhausted() -> None:
    fake = FakeLLM(["first", "second"])
    assert fake.complete("one") == "first"
    assert fake.complete("two") == "second"
    assert fake.requests == ["one", "two"]
    with pytest.raises(RuntimeError):
        fake.complete("three")

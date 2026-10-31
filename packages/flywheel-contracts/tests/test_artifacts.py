import json
from pathlib import Path

import pytest
from flywheel.contracts import artifacts
from flywheel.contracts.v0 import Condition, RolloutRequest, TaskRef
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


def test_fake_llm_returns_scripted_responses_and_fails_when_exhausted() -> None:
    fake = FakeLLM(["first", "second"])
    assert fake.complete("one") == "first"
    assert fake.complete("two") == "second"
    assert fake.requests == ["one", "two"]
    with pytest.raises(RuntimeError):
        fake.complete("three")

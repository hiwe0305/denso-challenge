import json
from pathlib import Path

import pytest
from flywheel.contracts.entities import Score
from flywheel.contracts.v0 import FailureKindSpec, StageEvaluation, StageSpec
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "packages/flywheel-contracts/schemas"
FIXTURES = ROOT / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts"


@pytest.mark.parametrize("model", [StageEvaluation, StageSpec, FailureKindSpec])
def test_shared_schema_and_example(model: type) -> None:
    assert json.loads((SCHEMAS / f"{model.__name__}.json").read_text(encoding="utf-8")) == (
        model.model_json_schema()
    )
    value = model.model_validate_json((FIXTURES / f"{model.__name__}.json").read_text("utf-8"))
    assert model.model_validate_json(value.model_dump_json()) == value


def test_four_states_and_legacy_producers() -> None:
    legacy = StageEvaluation(stage_success=(True, False, False, None))
    assert legacy.stage_status is None
    result = StageEvaluation(
        stage_success=(True, False, False, None),
        stage_status=("pass", "fail", "not_attempted", "unknown"),
        unknown_reason=(None, None, None, "missing_signal"),
        step_enter_s=(0, 1, None, None),
        step_exit_s=(1, 2, None, None),
    )
    assert result.stage_status is not None and result.stage_status[2] == "not_attempted"


@pytest.mark.parametrize(
    "updates",
    [
        {"stage_status": ("pass",)},
        {"stage_status": ("pass", "pass")},
        {"stage_status": ("pass", "unknown"), "unknown_reason": (None, None)},
        {"unknown_reason": (None, "missing_signal")},
        {"step_enter_s": (0, float("nan"))},
        {"step_enter_s": (0, 2), "step_exit_s": (1, 1)},
    ],
)
def test_reject_inconsistent_step_details(updates: dict) -> None:
    with pytest.raises(ValidationError):
        StageEvaluation.model_validate({"stage_success": (True, None), **updates})


def test_signals_and_failure_rule_are_explicit() -> None:
    assert StageSpec(name="x", failure_class="carry").signals is None
    assert StageSpec(name="x", failure_class="carry", signals=()).signals == ()
    assert FailureKindSpec(kind="L-COLLIDE", failure_class="from_failed_stage").failure_class == (
        "from_failed_stage"
    )


def test_score_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        Score.model_validate(
            {
                "episode_id": "ep",
                "task_id": "task",
                "config_sha256": "a" * 64,
                "trace_sha256": "b" * 64,
                "step_status": ["not_reached"],
            }
        )


def test_score_details_round_trip_without_changing_legacy_id() -> None:
    fixture = json.loads((FIXTURES / "Score.json").read_text(encoding="utf-8"))
    legacy = Score.model_validate(fixture)
    assert legacy.id == fixture["id"]
    assert Score.model_validate_json(legacy.model_dump_json()).id == legacy.id
    updated = {
        **fixture,
        "id": "",
        "unknown_reason": [None] * 6,
        "step_enter_s": [0, 1, None, None, None, None],
        "step_exit_s": [1, 2, None, None, None, None],
    }
    enriched = Score.model_validate(updated)
    assert enriched.id != legacy.id
    assert Score.model_validate_json(enriched.model_dump_json()) == enriched

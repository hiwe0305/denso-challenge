"""Tests for the pure toy task definition."""

from __future__ import annotations

import pyarrow as pa
from flywheel.contracts import ScorerParams, TaskDefinition
from flywheel.testkit.fakes import ToyPickPlace


def successful_signals() -> pa.Table:
    return pa.table(
        {
            "gripper_x": [0.2, 0.5, 0.8],
            "gripper_y": [0.3, 0.4, 0.5],
            "part_x": [0.2, 0.5, 0.8],
            "part_y": [0.3, 0.4, 0.5],
            "target_x": [0.8, 0.8, 0.8],
            "target_y": [0.5, 0.5, 0.5],
        }
    )


def test_toy_task_satisfies_runtime_protocol() -> None:
    assert isinstance(ToyPickPlace(), TaskDefinition)


def test_toy_task_has_three_stages_and_failure_classes() -> None:
    task = ToyPickPlace()

    assert [stage.name for stage in task.stages()] == ["approach", "grasp", "place"]
    assert all(stage.failure_class for stage in task.stages())
    assert all(failure.failure_class for failure in task.failure_kinds())
    assert task.family == "pick_place"


def test_evaluate_is_pure_and_deterministic() -> None:
    task = ToyPickPlace()
    signals = successful_signals()
    params = ScorerParams(thresholds={"distance": 0.05})

    first = task.evaluate(signals, params)
    second = task.evaluate(signals, params)

    assert first == second
    assert first.stage_success == (True, True, True)
    assert first.first_failed_stage is None


def test_place_failure_is_classified() -> None:
    task = ToyPickPlace()
    signals = successful_signals().set_column(4, "target_x", pa.array([0.9, 0.9, 0.9]))

    result = task.evaluate(signals, ScorerParams(thresholds={"distance": 0.05}))

    assert result.first_failed_stage == 2
    assert result.failure_kind == "misplaced"
    assert result.failure_class == "place"


def test_approach_before_grasp_can_succeed() -> None:
    signals = successful_signals().set_column(0, "gripper_x", pa.array([0.0, 0.5, 0.8]))

    result = ToyPickPlace().evaluate(signals, ScorerParams(thresholds={"distance": 0.05}))

    assert result.stage_success == (True, True, True)


def test_missing_signal_returns_unknown_stages() -> None:
    result = ToyPickPlace().evaluate(pa.table({"part_x": [0.2]}), ScorerParams())

    assert result.stage_success == (None, None, None)

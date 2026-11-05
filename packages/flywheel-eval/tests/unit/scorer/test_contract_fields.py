"""The `Score` fields #101 added, as the scorer fills them (DA-36 task 8.4, AC 7).

Typed reasons for every unknown step, the time each step was entered and left
where the task reported one, and the version bump that marks the new shape.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]
import pytest
from conftest import NaiveTask, TwoTableTask
from flywheel.contracts import ScorerParams, StageEvaluation, TaskDefinition
from flywheel.eval.api import SCORER_CONFIG_DIR, score_trace
from flywheel.eval.scorer.artifact import build_record
from flywheel.eval.scorer.status import ScorerError, StepScore

MakeRows = Callable[..., list[dict[str, object]]]
CONFIG = SCORER_CONFIG_DIR / "two-table.yaml"


def write(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


class FixedTask(TwoTableTask):
    """A task that answers with one evaluation, whatever the trace says."""

    def __init__(self, evaluation: StageEvaluation) -> None:
        self._evaluation = evaluation

    def evaluate(self, signals: pa.Table, params: ScorerParams) -> StageEvaluation:
        return self._evaluation


def test_a_signal_that_is_only_null_is_unknown_not_passed(
    tmp_path: Path, make_rows: MakeRows, sig: object
) -> None:
    # A naive task answers `True` about the empty column; the column being
    # there by name is not a measurement (AC 2, FR21).
    rows = make_rows(hand_object_distance=sig.const(None))  # type: ignore[attr-defined]

    record = build_record(score_trace(write(tmp_path / "ep.jsonl", rows), NaiveTask(True), CONFIG))

    assert record.step_status[0] == "unknown"
    assert record.unknown_reason is not None
    assert record.unknown_reason[0] == "signal_all_null"
    assert record.success is None
    assert record.meta["null_signals"] == ["hand_object_distance"]


def test_an_episode_signal_that_is_only_null_costs_the_pass(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows, sig: object
) -> None:
    rows = make_rows(collision=sig.const(None))  # type: ignore[attr-defined]

    scored = score_trace(write(tmp_path / "ep.jsonl", rows), task, CONFIG)

    assert scored.unknown_steps == ()
    assert scored.failure.failure_kind == "L-UNKNOWN"
    assert "collision" in (scored.failure.reason or "")


def test_a_trace_with_no_rows_has_no_step_in_it(tmp_path: Path, task: TaskDefinition) -> None:
    path = tmp_path / "ep.jsonl"
    path.write_text("", encoding="utf-8")

    record = build_record(score_trace(path, task, CONFIG))

    assert record.step_status == ["unknown"] * 6
    assert record.unknown_reason == ["step_not_in_trace"] * 6


def test_the_task_s_own_reason_is_kept(tmp_path: Path, make_rows: MakeRows) -> None:
    evaluation = StageEvaluation.model_validate(
        {
            "stage_success": [True, None, None, None, None, None],
            "stage_status": ["pass"] + ["unknown"] * 5,
            "unknown_reason": [None, "step_not_in_trace"] + ["no_verdict"] * 4,
        }
    )

    record = build_record(
        score_trace(write(tmp_path / "ep.jsonl", make_rows()), FixedTask(evaluation), CONFIG)
    )

    assert record.unknown_reason == [None, "step_not_in_trace"] + ["no_verdict"] * 4


def test_step_times_are_kept_for_judged_steps_only(tmp_path: Path, make_rows: MakeRows) -> None:
    # The walk fails at step 2; steps 3-5 come back from the predicate chain
    # as failed with times of their own, and both are dropped with the state.
    evaluation = StageEvaluation(
        stage_success=(True, True, False, False, False, False),
        first_failed_stage=2,
        failure_kind="L-WALK",
        step_enter_s=(0.0, 0.4, 0.6, 0.9, 1.3, 1.4),
        step_exit_s=(0.4, 0.6, None, 1.3, 1.4, 1.9),
    )

    record = build_record(
        score_trace(write(tmp_path / "ep.jsonl", make_rows()), FixedTask(evaluation), CONFIG)
    )

    assert record.step_status == ["pass", "pass", "fail"] + ["not_attempted"] * 3
    assert record.step_enter_s == [0.0, 0.4, 0.6, None, None, None]
    assert record.step_exit_s == [0.4, 0.6, None, None, None, None]
    assert record.unknown_reason == [None] * 6


def test_a_task_that_reports_no_times_gets_none_not_zeros(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    record = build_record(score_trace(write(tmp_path / "ep.jsonl", make_rows()), task, CONFIG))

    assert record.step_enter_s is None
    assert record.step_exit_s is None


def test_the_new_record_shape_has_its_own_version(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    record = build_record(score_trace(write(tmp_path / "ep.jsonl", make_rows()), task, CONFIG))

    # 0.1.0 records had no `unknown_reason`; a record of the new shape that
    # kept the old version could not be told apart from one (03 section 4.4).
    assert record.scorer_version == "0.2.0"
    assert record.unknown_reason == [None] * 6


@pytest.mark.parametrize("status", ["not_attempted", "unknown"])
def test_a_step_that_was_not_judged_cannot_carry_a_time(status: str) -> None:
    reason = "no_verdict" if status == "unknown" else None
    with pytest.raises(ScorerError, match="thời điểm"):
        StepScore(name="walk", status=status, reason=reason, enter_s=1.0)  # type: ignore[arg-type]

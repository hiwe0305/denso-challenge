"""The four step states and the two conventions (DA-36 task 2, AC 1, 2)."""

from __future__ import annotations

import pytest
from flywheel.contracts import StageEvaluation, StageSpec, TaskDefinition
from flywheel.eval.scorer.status import ScorerError
from flywheel.eval.scorer.steps import NO_VERDICT, first_failed_step, score_steps


def states(
    evaluation: StageEvaluation, stages: tuple[StageSpec, ...], missing: tuple[str, ...] = ()
) -> list[str]:
    return [step.status for step in score_steps(evaluation, stages, missing)]


def test_a_full_run_passes_every_step(task: TaskDefinition) -> None:
    evaluation = StageEvaluation(stage_success=(True,) * 6)

    assert states(evaluation, tuple(task.stages())) == ["pass"] * 6


def test_a_step_never_reached_is_not_attempted(task: TaskDefinition) -> None:
    # The first confusion AC 2 names. A predicate chain reports the later steps
    # as failed once an earlier one is - `place_ok = grasp_ok and ...` - and
    # only the first of them was actually attempted.
    evaluation = StageEvaluation(
        stage_success=(True, False, False, False, False, False), first_failed_stage=1
    )

    assert states(evaluation, tuple(task.stages())) == [
        "pass",
        "fail",
        "not_attempted",
        "not_attempted",
        "not_attempted",
        "not_attempted",
    ]


def test_a_step_with_no_signal_is_unknown_not_passed(task: TaskDefinition) -> None:
    # The second confusion AC 2 names, and the lesson DA-08 wrote down: a step
    # nobody could measure must never read as one that went well.
    evaluation = StageEvaluation(stage_success=(True, None, None, None, None, None))

    steps = score_steps(evaluation, tuple(task.stages()), ("object_height",))

    assert [step.status for step in steps[1:]] == ["unknown"] * 5
    assert all(step.status != "pass" for step in steps[1:])
    assert steps[1].detail == "thiếu tín hiệu: object_height"


def test_an_unknown_without_a_missing_signal_still_says_why(task: TaskDefinition) -> None:
    evaluation = StageEvaluation(stage_success=(None,) * 6)

    steps = score_steps(evaluation, tuple(task.stages()))

    assert steps[0].detail == NO_VERDICT


def test_a_step_is_unknown_whatever_the_task_answered(task: TaskDefinition) -> None:
    # The convention belongs to the scorer, not to the task: a predicate asked
    # about a signal nobody recorded answers like any other, and `True` there
    # would be a pass nobody measured, `False` a failure nobody measured
    # (review of 3/11/2026, point 1).
    stages = tuple(task.stages())
    missing = ("hand_object_distance",)

    for answer in (True, False):
        outcomes = (answer,) + (True,) * 5
        evaluation = StageEvaluation(stage_success=outcomes)
        steps = score_steps(evaluation, stages, missing)

        assert steps[0].status == "unknown"
        assert steps[0].detail == "thiếu tín hiệu: hand_object_distance"


def test_a_step_is_not_unknown_for_a_signal_it_does_not_use(task: TaskDefinition) -> None:
    # And the reason names that step's own missing signals only (point 7).
    stages = tuple(task.stages())

    steps = score_steps(
        StageEvaluation(stage_success=(True,) * 6),
        stages,
        ("object_in_target_zone",),
    )

    assert steps[0].status == "pass"  # approach never reads it
    assert steps[4].detail == "thiếu tín hiệu: object_in_target_zone"
    assert steps[5].detail == "thiếu tín hiệu: object_in_target_zone"


def test_an_unknown_before_the_failure_stays_unknown(task: TaskDefinition) -> None:
    # Unknown comes first in the order of states: a step that could not be
    # judged is not quietly promoted to passed just because a later step ran.
    evaluation = StageEvaluation(
        stage_success=(True, None, False, False, False, False), first_failed_stage=2
    )

    # `object_height` is what the grasp step is judged on; the walk step is
    # judged on other signals, so it still reads as the failure it was.
    assert states(evaluation, tuple(task.stages()), ("object_height",)) == [
        "pass",
        "unknown",
        "fail",
        "not_attempted",
        "not_attempted",
        "not_attempted",
    ]


def test_the_failed_step_is_read_off_the_outcomes(task: TaskDefinition) -> None:
    evaluation = StageEvaluation(stage_success=(True, True, False, False, False, False))

    # `first_failed_stage` is optional in the contract, so a task that leaves it
    # out must still be scored.
    assert first_failed_step(evaluation) == 2


def test_a_declared_failed_step_that_contradicts_the_outcomes_raises(
    task: TaskDefinition,
) -> None:
    evaluation = StageEvaluation(
        stage_success=(True, True, False, False, False, False), first_failed_stage=4
    )

    with pytest.raises(ScorerError, match="first_failed_stage"):
        first_failed_step(evaluation)


def test_a_run_with_no_failed_step_has_none(task: TaskDefinition) -> None:
    assert first_failed_step(StageEvaluation(stage_success=(True,) * 6)) is None
    assert first_failed_step(StageEvaluation(stage_success=(None,) * 6)) is None


def test_the_step_count_comes_from_the_task(task: TaskDefinition) -> None:
    # Seven steps scored by the same code, as the tray task needs (AC 1).
    seven = tuple(
        StageSpec(name=f"s{index}", failure_class="carry", signals=()) for index in range(7)
    )

    scored = score_steps(StageEvaluation(stage_success=(True,) * 7), seven)

    assert len(scored) == 7


def test_an_evaluation_that_does_not_fit_the_task_raises(task: TaskDefinition) -> None:
    with pytest.raises(ScorerError, match="trả 3 bước"):
        score_steps(
            StageEvaluation(stage_success=(True, True, True)),
            tuple(task.stages()),
        )


def four_states(*statuses: str) -> StageEvaluation:
    """An evaluation from a task that sends `stage_status` (#101)."""
    legacy = {"pass": True, "fail": False, "not_attempted": False, "unknown": None}
    return StageEvaluation.model_validate(
        {"stage_success": [legacy[s] for s in statuses], "stage_status": list(statuses)}
    )


def test_the_task_s_four_states_are_read_when_sent(task: TaskDefinition) -> None:
    evaluation = four_states("pass", "fail", *["not_attempted"] * 4)

    assert first_failed_step(evaluation) == 1
    assert states(evaluation, tuple(task.stages())) == ["pass", "fail"] + ["not_attempted"] * 4


def test_not_attempted_after_an_unknown_step_is_not_a_failure(task: TaskDefinition) -> None:
    # In `stage_success` the third step is `False`, so a scorer reading only
    # the booleans would put k at 2. The task said it never got there.
    evaluation = four_states("pass", "unknown", *["not_attempted"] * 4)

    assert first_failed_step(evaluation) is None
    assert states(evaluation, tuple(task.stages())) == ["pass", "unknown"] + ["not_attempted"] * 4


def test_not_attempted_with_nothing_before_it_raises(task: TaskDefinition) -> None:
    evaluation = four_states("pass", "pass", *["not_attempted"] * 4)

    with pytest.raises(ScorerError, match="bước 2 chưa thử"):
        first_failed_step(evaluation)


def test_a_stage_that_never_declared_its_signals_is_refused(task: TaskDefinition) -> None:
    # `None` is a task written before #101. Read as `()`, every step of it
    # would pass on signals nobody recorded, which is AC 2 undone.
    stages = tuple(stage.model_copy(update={"signals": None}) for stage in task.stages())

    with pytest.raises(ScorerError, match="chưa khai `StageSpec.signals`"):
        score_steps(StageEvaluation(stage_success=(True,) * 6), stages)


def test_a_stage_that_needs_no_signal_is_never_unknown_for_one(task: TaskDefinition) -> None:
    stages = tuple(task.stages())
    stages = (stages[0].model_copy(update={"signals": ()}), *stages[1:])

    steps = score_steps(
        StageEvaluation(stage_success=(True,) * 6), stages, ("hand_object_distance",)
    )

    assert steps[0].status == "pass"

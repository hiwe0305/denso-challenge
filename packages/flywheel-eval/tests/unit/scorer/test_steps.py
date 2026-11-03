"""The four step states and the two conventions (DA-36 task 2, AC 1, 2)."""

from __future__ import annotations

import pytest
from flywheel.contracts import StageEvaluation, StageSpec, TaskDefinition
from flywheel.eval.scorer.status import ScorerError, StepStatus
from flywheel.eval.scorer.steps import NO_VERDICT, first_failed_step, score_steps


def states(
    evaluation: StageEvaluation, stages: tuple[StageSpec, ...], missing: tuple[str, ...] = ()
) -> list[str]:
    return [step.status.value for step in score_steps(evaluation, stages, missing)]


def test_a_full_run_passes_every_step(task: TaskDefinition) -> None:
    evaluation = StageEvaluation(stage_success=(True,) * 6)

    assert states(evaluation, tuple(task.stages())) == [StepStatus.PASSED.value] * 6


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

    steps = score_steps(evaluation, tuple(task.stages()), ("object_in_target_zone",))

    assert [step.status for step in steps[1:]] == [StepStatus.UNKNOWN] * 5
    assert all(step.status is not StepStatus.PASSED for step in steps[1:])
    assert steps[1].reason == "thiếu tín hiệu: object_in_target_zone"


def test_an_unknown_without_a_missing_signal_still_says_why(task: TaskDefinition) -> None:
    evaluation = StageEvaluation(stage_success=(None,) * 6)

    assert score_steps(evaluation, tuple(task.stages()))[0].reason == NO_VERDICT


def test_an_unknown_before_the_failure_stays_unknown(task: TaskDefinition) -> None:
    # Unknown comes first in the order of states: a step that could not be
    # judged is not quietly promoted to passed just because a later step ran.
    evaluation = StageEvaluation(
        stage_success=(True, None, False, False, False, False), first_failed_stage=2
    )

    assert states(evaluation, tuple(task.stages()), ("hand_object_contact",)) == [
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
    seven = tuple(StageSpec(name=f"s{index}", failure_class="carry") for index in range(7))

    assert len(score_steps(StageEvaluation(stage_success=(True,) * 7), seven)) == 7


def test_an_evaluation_that_does_not_fit_the_task_raises(task: TaskDefinition) -> None:
    with pytest.raises(ScorerError, match="trả 3 bước"):
        score_steps(StageEvaluation(stage_success=(True, True, True)), tuple(task.stages()))

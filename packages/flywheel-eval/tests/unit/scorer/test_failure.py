"""The failed step, the kind and the shared class (DA-36 task 3, AC 3, 4)."""

from __future__ import annotations

import pytest
from conftest import BY_STEP
from flywheel.contracts import FailureKindSpec, StageEvaluation, StageSpec, TaskDefinition
from flywheel.eval.scorer.failure import (
    NO_KIND_FROM_TASK,
    UNKNOWN_KIND,
    UNKNOWN_STEPS,
    judge_failure,
)
from flywheel.eval.scorer.status import ScorerError
from flywheel.eval.scorer.steps import first_failed_step, score_steps


def judge(
    evaluation: StageEvaluation,
    task: TaskDefinition,
    missing: tuple[str, ...] = (),
    kinds: tuple[FailureKindSpec, ...] | None = None,
    class_from_failed_step: tuple[str, ...] = (),
):  # noqa: ANN201 - the verdict type is an implementation detail of the module
    stages = tuple(task.stages())
    steps = score_steps(evaluation, stages, missing, step_signals=BY_STEP)
    return judge_failure(
        evaluation,
        steps,
        kinds if kinds is not None else tuple(task.failure_kinds()),
        first_failed_step(evaluation),
        stages,
        class_from_failed_step,
    )


def failed_at(step: int, kind: str, failure_class: str | None = None) -> StageEvaluation:
    outcomes = tuple(index < step for index in range(6))
    return StageEvaluation(
        stage_success=outcomes,
        first_failed_stage=step,
        failure_kind=kind,
        failure_class=failure_class,
    )


def test_a_full_run_has_no_kind_and_no_class(task: TaskDefinition) -> None:
    verdict = judge(StageEvaluation(stage_success=(True,) * 6), task)

    assert verdict.failure_kind is None
    assert verdict.failure_class is None
    assert verdict.first_failed_step is None
    assert verdict.success is True


@pytest.mark.parametrize(
    ("step", "kind", "expected_class"),
    [
        (0, "L-REACH", "approach"),
        (1, "L-GRASP", "grasp"),
        (2, "L-SLIP", "carry"),
        (3, "L-WALK", "carry"),
        (4, "L-PLACE", "place"),
        (5, "L-RELEASE", "place"),
    ],
)
def test_the_class_comes_from_the_declared_kind(
    task: TaskDefinition, step: int, kind: str, expected_class: str
) -> None:
    verdict = judge(failed_at(step, kind), task)

    assert verdict.first_failed_step == step
    assert verdict.failure_kind == kind
    assert verdict.failure_class == expected_class
    assert verdict.success is False


def test_the_episode_class_wins_over_the_declared_one(task: TaskDefinition) -> None:
    # L-COLLIDE and L-TIMEOUT take the class of the failed step (spec section
    # 5.2), which only the episode knows, so `evaluate` fills it in.
    verdict = judge(failed_at(4, "L-COLLIDE", "place"), task)

    assert verdict.failure_kind == "L-COLLIDE"
    assert verdict.failure_class == "place"


@pytest.mark.parametrize(("step", "expected_class"), [(1, "grasp"), (2, "carry"), (4, "place")])
def test_a_step_attached_kind_takes_the_class_of_the_failed_step(
    task: TaskDefinition, step: int, expected_class: str
) -> None:
    # A collision during the walk is a carry failure, not an approach one: the
    # class of `L-COLLIDE` is the class of step k (spec section 5.2), and the
    # placeholder on its `FailureKindSpec` must not be what reaches the record
    # (review of 3/11/2026, point 3).
    verdict = judge(failed_at(step, "L-COLLIDE"), task, class_from_failed_step=("L-COLLIDE",))

    assert verdict.failure_class == expected_class


def test_a_kind_not_named_as_step_attached_keeps_its_declared_class(
    task: TaskDefinition,
) -> None:
    verdict = judge(failed_at(2, "L-COLLIDE"), task)

    # Nothing is guessed: with no declaration, the kind's own class is used.
    assert verdict.failure_class == "approach"


def test_a_kind_with_no_failed_step_is_a_contradiction(task: TaskDefinition) -> None:
    # Every step passed and the task still named a kind. Dropping the kind
    # would report the episode as a pass (review of 3/11/2026, point 4).
    evaluation = StageEvaluation(stage_success=(True,) * 6, failure_kind="L-COLLIDE")

    with pytest.raises(ScorerError, match="không có bước nào trượt"):
        judge(evaluation, task)


def test_an_unknown_step_gives_l_unknown_and_no_class(task: TaskDefinition) -> None:
    verdict = judge(
        StageEvaluation(stage_success=(None,) * 6), task, ("hand_object_distance",)
    )

    assert verdict.failure_kind == UNKNOWN_KIND
    assert verdict.failure_class is None
    # The reason is the first unknown step's own, which is the approach step's.
    assert verdict.reason == "thiếu tín hiệu: hand_object_distance"
    # Not a pass and not a failure: nobody could tell.
    assert verdict.success is None


def test_an_unknown_before_a_failure_costs_the_failed_step(task: TaskDefinition) -> None:
    evaluation = StageEvaluation(
        stage_success=(None, False, False, False, False, False),
        first_failed_stage=1,
        failure_kind="L-GRASP",
        failure_class="grasp",
    )

    verdict = judge(evaluation, task, ("hand_object_distance",))

    # The grasp failed, but with the approach unjudged it is not known to be
    # the *first* failure, and a k pointing at the wrong step misdirects DA-13.
    assert verdict.first_failed_step is None
    assert verdict.failure_kind == UNKNOWN_KIND
    assert verdict.reason == UNKNOWN_STEPS


def test_a_failure_the_task_did_not_name_is_unknown(task: TaskDefinition) -> None:
    verdict = judge(failed_at(2, None), task)  # type: ignore[arg-type]

    assert verdict.failure_kind == UNKNOWN_KIND
    assert verdict.reason == NO_KIND_FROM_TASK
    assert verdict.failure_class is None


def test_a_kind_outside_the_declared_set_raises(task: TaskDefinition) -> None:
    with pytest.raises(ScorerError, match="L-TRAY-TILT"):
        judge(failed_at(2, "L-TRAY-TILT"), task)


def test_another_code_set_scores_through_the_same_call(task: TaskDefinition) -> None:
    # The tray codes of the 28/10 design, which the two-table task does not
    # have: the module holds no code of its own (AC 4).
    tray = (
        FailureKindSpec(kind="L-PART-DROP", failure_class="carry"),
        FailureKindSpec(kind="L-TRAY-TILT", failure_class="balance"),
    )

    verdict = judge(failed_at(2, "L-TRAY-TILT"), task, kinds=tray)

    assert verdict.failure_kind == "L-TRAY-TILT"
    assert verdict.failure_class == "balance"


def test_a_duplicate_declared_kind_raises(task: TaskDefinition) -> None:
    kinds = (
        FailureKindSpec(kind="L-SLIP", failure_class="carry"),
        FailureKindSpec(kind="L-SLIP", failure_class="grasp"),
    )

    with pytest.raises(ScorerError, match="hai lần"):
        judge(failed_at(2, "L-SLIP"), task, kinds=kinds)


def test_a_task_may_not_declare_l_unknown(task: TaskDefinition) -> None:
    kinds = (FailureKindSpec(kind=UNKNOWN_KIND, failure_class="carry"),)

    with pytest.raises(ScorerError, match=UNKNOWN_KIND):
        judge(failed_at(2, UNKNOWN_KIND), task, kinds=kinds)


def test_a_seven_step_task_is_judged_the_same_way() -> None:
    stages = tuple(StageSpec(name=f"s{index}", failure_class="carry") for index in range(7))
    kinds = (FailureKindSpec(kind="L-PART-DROP", failure_class="carry"),)
    evaluation = StageEvaluation(
        stage_success=tuple(index < 5 for index in range(7)),
        first_failed_stage=5,
        failure_kind="L-PART-DROP",
    )

    verdict = judge_failure(
        evaluation,
        score_steps(evaluation, stages, step_signals={}),
        kinds,
        first_failed_step(evaluation),
        stages,
    )

    assert verdict.first_failed_step == 5
    assert verdict.failure_class == "carry"

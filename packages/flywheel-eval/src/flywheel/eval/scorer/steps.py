"""Turn a `StageEvaluation` into the four step states (DA-36 task 2, AC 1, 2).

The task definition says which steps it got through. This module says what each
step's state is, and it is the only place the two conventions of spec section
5.1 are applied, so they cannot be applied differently in two places:

- **A step after the first failure is "chưa thử".** The task stopped there, so
  nothing after it was attempted. This matters because a predicate chain
  usually reports the later steps as failed too - `place_ok = grasp_ok and ...`
  is false once the grasp is - and counting those as failures would triple the
  place failures in every report built on top (DA-13, the clusters, the cards).
- **A step with no signal behind it is "chưa rõ".** It never becomes "đạt". The
  reason travels with it, named after the signals the trace was missing when
  that is what happened.

The number of steps comes from `stages()`; nothing here knows that the
two-table task has six or that the tray task has seven.
"""

from __future__ import annotations

from collections.abc import Sequence

from flywheel.contracts import StageEvaluation, StageSpec
from flywheel.eval.scorer.status import ScorerError, StepScore, StepStatus

NO_VERDICT = "vị từ của task không kết luận được trên tín hiệu đã ghi"


def score_steps(
    evaluation: StageEvaluation,
    stages: Sequence[StageSpec],
    missing_signals: Sequence[str] = (),
) -> tuple[StepScore, ...]:
    """State every step of the task, in the order the task declares them."""
    outcomes = evaluation.stage_success
    if len(outcomes) != len(stages):
        raise ScorerError(
            f"`evaluate()` trả {len(outcomes)} bước, `stages()` khai {len(stages)} bước"
        )
    failed = first_failed_step(evaluation)
    reason = unknown_reason(missing_signals)
    return tuple(
        _step(stage.name, outcome, index, failed, reason)
        for index, (stage, outcome) in enumerate(zip(stages, outcomes, strict=True))
    )


def first_failed_step(evaluation: StageEvaluation) -> int | None:
    """The step the task stopped at, or `None` if it did not stop at one.

    `StageEvaluation` carries `first_failed_stage`, but it is optional, so the
    index is recovered from the outcomes when the task left it out. Where the
    task did fill it in and it disagrees with the outcomes, the outcomes win and
    the disagreement raises: a `Score` whose failed step is not the step marked
    failed would point every later step of the diagnosis at the wrong place.
    """
    outcomes = evaluation.stage_success
    found = next((index for index, outcome in enumerate(outcomes) if outcome is False), None)
    declared = evaluation.first_failed_stage
    if declared is not None and declared != found:
        raise ScorerError(
            f"`first_failed_stage` là {declared} nhưng bước trượt đầu tiên trong "
            f"`stage_success` là {found}"
        )
    return found


def unknown_reason(missing_signals: Sequence[str] = ()) -> str:
    """Why a step is unknown, in the words the engineer reading it needs."""
    if missing_signals:
        return "thiếu tín hiệu: " + ", ".join(missing_signals)
    return NO_VERDICT


def _step(
    name: str,
    outcome: bool | None,
    index: int,
    failed: int | None,
    reason: str,
) -> StepScore:
    if failed is not None and index > failed:
        # Reached after the task had already stopped: not attempted, whatever
        # the predicate chain reported for it.
        return StepScore(name=name, status=StepStatus.NOT_ATTEMPTED)
    if outcome is None:
        return StepScore(name=name, status=StepStatus.UNKNOWN, reason=reason)
    if outcome:
        return StepScore(name=name, status=StepStatus.PASSED)
    return StepScore(name=name, status=StepStatus.FAILED)

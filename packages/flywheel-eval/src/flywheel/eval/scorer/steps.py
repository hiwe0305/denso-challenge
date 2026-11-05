"""Turn a `StageEvaluation` into the four step states (DA-36 task 2, AC 1, 2).

The task definition says which steps it got through. This module says what each
step's state is, and it is the only place the two conventions of spec section
5.1 are applied, so they cannot be applied differently in two places:

- **A step after the first failure is "chưa thử".** The task stopped there, so
  nothing after it was attempted. This matters because a predicate chain
  usually reports the later steps as failed too - `place_ok = grasp_ok and ...`
  is false once the grasp is - and counting those as failures would triple the
  place failures in every report built on top (DA-13, the clusters, the cards).
- **A step with no signal behind it is "chưa rõ".** It never becomes "đạt",
  and it never becomes "trượt" either. This convention is held here rather
  than left to the task: a predicate asked about a signal nobody recorded
  answers `True` or `False` like any other, and either answer would be a
  verdict nobody measured. A step whose own signals are missing is therefore
  unknown whatever `evaluate()` returned for it, and the reason names that
  step's missing signals and no others - a step is never told it is unknown
  because of a signal it does not use.

What the task said about each step is read from `StageEvaluation.stage_status`
when the task sends it, and recovered from `stage_success` when it does not.
The difference matters for k: in `stage_success` a step the task marked
`not_attempted` is `False` like a failed one, so the first `False` of a task
that stopped after an unknown step is not a failure at all. With a four-state
answer, k is the first `fail`. A `not_attempted` step with neither a failure
nor an unknown step before it is a contradiction - the task stopped without
saying where it broke - and raises rather than scoring as an episode that
simply passed.

The number of steps comes from `stages()` and the signals of each step come
from config; nothing here knows that the two-table task has six steps, that
the tray task has seven, or which signal any step is judged on.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from flywheel.contracts import StageEvaluation, StageSpec
from flywheel.eval.scorer.status import ScorerError, StepScore, StepStatus

NO_VERDICT = "vị từ của task không kết luận được trên tín hiệu đã ghi"


def score_steps(
    evaluation: StageEvaluation,
    stages: Sequence[StageSpec],
    missing_signals: Sequence[str] = (),
    *,
    step_signals: Mapping[str, Sequence[str]],
) -> tuple[StepScore, ...]:
    """State every step of the task, in the order the task declares them.

    `step_signals` maps a step name onto the signals that step is judged on, so
    a step whose signals the trace does not have comes back unknown however the
    task's predicate answered for it. It is keyword-only and has no default:
    a scorer that could be called without it is a scorer that can be called
    without the convention of AC 2.
    """
    outcomes = evaluation.stage_success
    if len(outcomes) != len(stages):
        raise ScorerError(
            f"`evaluate()` trả {len(outcomes)} bước, `stages()` khai {len(stages)} bước"
        )
    failed = first_failed_step(evaluation)
    return tuple(
        _step(
            stage.name,
            reported,
            index,
            failed,
            missing_for_step(stage.name, step_signals, missing_signals),
        )
        for index, (stage, reported) in enumerate(
            zip(stages, task_statuses(evaluation), strict=True)
        )
    )


def task_statuses(evaluation: StageEvaluation) -> tuple[StepStatus, ...]:
    """What the task itself said about each step, in the four states.

    `stage_status` when the task sent one; otherwise read off `stage_success`,
    where `False` can only mean `fail` because nothing else is said.
    """
    if evaluation.stage_status is not None:
        return evaluation.stage_status
    legacy: dict[bool | None, StepStatus] = {True: "pass", False: "fail", None: "unknown"}
    return tuple(legacy[outcome] for outcome in evaluation.stage_success)


def missing_for_step(
    name: str,
    step_signals: Mapping[str, Sequence[str]],
    missing_signals: Sequence[str],
) -> tuple[str, ...]:
    """The signals this step is judged on that the trace does not have."""
    declared = set(step_signals.get(name, ()))
    return tuple(signal for signal in missing_signals if signal in declared)


def first_failed_step(evaluation: StageEvaluation) -> int | None:
    """The step the task stopped at, or `None` if it did not stop at one.

    `StageEvaluation` carries `first_failed_stage`, but it is optional, so the
    index is recovered from the outcomes when the task left it out. Where the
    task did fill it in and it disagrees with the outcomes, the outcomes win and
    the disagreement raises: a `Score` whose failed step is not the step marked
    failed would point every later step of the diagnosis at the wrong place.
    """
    statuses = task_statuses(evaluation)
    found = next((index for index, status in enumerate(statuses) if status == "fail"), None)
    skipped = next(
        (index for index, status in enumerate(statuses) if status == "not_attempted"), None
    )
    stopped = found is not None and found < (skipped or 0)
    if skipped is not None and not stopped and "unknown" not in statuses[:skipped]:
        raise ScorerError(
            f"`stage_status` ghi bước {skipped} chưa thử mà không có bước trượt hay "
            "chưa rõ nào trước nó; task dừng ở đâu thì bước đó phải là `fail`"
        )
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
    reported: StepStatus,
    index: int,
    failed: int | None,
    missing: Sequence[str],
) -> StepScore:
    if failed is not None and index > failed:
        # Reached after the task had already stopped: not attempted, whatever
        # the predicate chain reported for it.
        return StepScore(name=name, status="not_attempted")
    if missing:
        # The predicate may well have answered; it answered about a signal
        # nobody recorded, which is not a verdict (AC 2, FR21).
        return StepScore(name=name, status="unknown", reason=unknown_reason(missing))
    if reported == "unknown":
        return StepScore(name=name, status="unknown", reason=NO_VERDICT)
    return StepScore(name=name, status=reported)

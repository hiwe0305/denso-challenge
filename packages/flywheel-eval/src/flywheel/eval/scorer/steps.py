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
  because of a signal it does not use. Which signals are a step's own is
  `StageSpec.signals` (#101); a stage that leaves it `None` has not said, and
  is refused rather than scored as a step that needs nothing. A signal whose
  column is there but holds nothing except null is no signal either: the
  predicates read it as "never happened", which would turn the step into a
  failure nobody measured, so it is unknown as well (`signal_all_null`).

Each unknown carries a typed `UnknownReason` (#101): `step_not_in_trace` for a
trace with no rows at all, `missing_signal` and `signal_all_null` for a step
whose own signals are absent or empty, and otherwise whatever the task gave,
`no_verdict` if it gave nothing. A step judged `pass` or `fail` keeps the enter
and exit times the task reported for it; an unknown or unattempted step keeps
none, since a time measured on signals that were not there is not a time.

What the task said about each step is read from `StageEvaluation.stage_status`
when the task sends it, and recovered from `stage_success` when it does not.
The difference matters for k: in `stage_success` a step the task marked
`not_attempted` is `False` like a failed one, so the first `False` of a task
that stopped after an unknown step is not a failure at all. With a four-state
answer, k is the first `fail`. A `not_attempted` step with neither a failure
nor an unknown step before it is a contradiction - the task stopped without
saying where it broke - and raises rather than scoring as an episode that
simply passed.

The number of steps and the signals of each step come from `stages()`;
nothing here knows that the two-table task has six steps, that
the tray task has seven, or which signal any step is judged on.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from flywheel.contracts import StageEvaluation, StageSpec
from flywheel.eval.scorer.status import ScorerError, StepScore, StepStatus, UnknownReason

NO_VERDICT = "vị từ của task không kết luận được trên tín hiệu đã ghi"
EMPTY_TRACE = "trace không có dòng nào"


def score_steps(
    evaluation: StageEvaluation,
    stages: Sequence[StageSpec],
    missing_signals: Sequence[str] = (),
    null_signals: Sequence[str] = (),
    *,
    empty: bool = False,
) -> tuple[StepScore, ...]:
    """State every step of the task, in the order the task declares them.

    A step whose `StageSpec.signals` the trace does not have, or has only as
    nulls, comes back unknown however the task's predicate answered for it;
    `empty` says the trace has no rows, which leaves every step unknown.
    """
    outcomes = evaluation.stage_success
    if len(outcomes) != len(stages):
        raise ScorerError(
            f"`evaluate()` trả {len(outcomes)} bước, `stages()` khai {len(stages)} bước"
        )
    for stage in stages:
        step_signals(stage)  # refused up front, not only when a signal is missing
    failed = first_failed_step(evaluation)
    reasons = evaluation.unknown_reason or (None,) * len(stages)
    enters = evaluation.step_enter_s or (None,) * len(stages)
    exits = evaluation.step_exit_s or (None,) * len(stages)
    return tuple(
        _step(
            stage.name,
            reported,
            index,
            failed,
            _Gaps(
                empty=empty,
                missing=missing_for_step(stage, missing_signals),
                null=missing_for_step(stage, null_signals),
            ),
            reasons[index],
            (enters[index], exits[index]),
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


def missing_for_step(stage: StageSpec, signals: Sequence[str]) -> tuple[str, ...]:
    """Those of `signals` this step is judged on."""
    return tuple(signal for signal in signals if signal in step_signals(stage))


def step_signals(stage: StageSpec) -> tuple[str, ...]:
    """`StageSpec.signals`, refusing a stage that never declared them.

    `None` is a task written before #101; scoring it as `()` would let every
    step of it pass on signals nobody recorded, which is AC 2 undone.
    """
    if stage.signals is None:
        raise ScorerError(
            f"bước `{stage.name}` chưa khai `StageSpec.signals`; thiếu nó thì không "
            "bước nào thành chưa rõ được khi thiếu tín hiệu (AC 2)"
        )
    return stage.signals


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


@dataclass(frozen=True)
class _Gaps:
    """What the trace lacks for one step."""

    empty: bool
    missing: tuple[str, ...]
    null: tuple[str, ...]


def _step(
    name: str,
    reported: StepStatus,
    index: int,
    failed: int | None,
    gaps: _Gaps,
    task_reason: UnknownReason | None,
    times: tuple[float | None, float | None],
) -> StepScore:
    if failed is not None and index > failed:
        # Reached after the task had already stopped: not attempted, whatever
        # the predicate chain reported for it.
        return StepScore(name=name, status="not_attempted")
    # The predicate may well have answered; it answered about a signal nobody
    # recorded, which is not a verdict (AC 2, FR21).
    if gaps.empty:
        return _unknown(name, "step_not_in_trace", EMPTY_TRACE)
    if gaps.missing:
        return _unknown(name, "missing_signal", "thiếu tín hiệu: " + ", ".join(gaps.missing))
    if gaps.null:
        return _unknown(name, "signal_all_null", "tín hiệu toàn null: " + ", ".join(gaps.null))
    if reported == "unknown":
        reason = task_reason or "no_verdict"
        return _unknown(name, reason, NO_VERDICT if reason == "no_verdict" else None)
    if reported == "not_attempted":
        # After an unknown step the task stopped without a failure; the step
        # was not judged, so it keeps no time.
        return StepScore(name=name, status=reported)
    return StepScore(name=name, status=reported, enter_s=times[0], exit_s=times[1])


def _unknown(name: str, reason: UnknownReason, detail: str | None) -> StepScore:
    return StepScore(name=name, status="unknown", reason=reason, detail=detail)

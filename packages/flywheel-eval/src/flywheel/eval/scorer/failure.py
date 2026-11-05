"""Which step broke first, what kind of failure it was, and its shared class
(DA-36 task 3, AC 3, 4).

Nothing here knows a code. The kinds come from `task.failure_kinds()`, so the
ten codes of spec section 5.2 and the tray codes of the 28/10 design both score
through this module unchanged, and a kind the task reports but never declared
raises rather than reaching a `Score` (AC 4).

`L-UNKNOWN` is the one name this module does hold, and it is not a kind a task
can fail with: it is what the scorer says when it cannot name one. It is used
in three cases, each with a reason attached - a step that could not be judged, a
task that reported a failure without naming its kind, and an episode with no
signals at all.

An unknown step anywhere also costs the episode its `first_failed_step`. If the
approach step could not be judged and the grasp step failed, the grasp is not
known to be the *first* failure, and a k that points at the wrong step would
send DA-13, the clusters and the cards all to the same wrong place. The step
states still show the failure, so nothing is hidden by saying so.

**The shared failure class** (approach, grasp, carry, place, balance) is read,
not decided here, in three places in this order: what `evaluate()` put in
`StageEvaluation.failure_class`, because that is the only value that can depend
on the episode; the `failure_class` of the failed step's own `StageSpec` where
the kind's `FailureKindSpec.failure_class` is `"from_failed_stage"`; and the
kind's own `FailureKindSpec.failure_class` otherwise.

The middle one is what spec section 5.2 asks for: `L-COLLIDE`, `L-TIMEOUT` and,
for the tray task, `L-TRAY-TILT` take the class of the failed step rather than
a class of their own, and 03 section 4.3 reads `StageSpec.failure_class` as
exactly that default. The task declares it on the kind (#101, issue #59);
until #101 it was a per-task list in config, and before the PO review of
3/11/2026 the kind's own class was used, which filed a collision during the
walk under `approach`.

At L0 the class is recorded and nothing reads it to choose an intervention
(AC 3); it is there so L1 can add failures up across tasks (FR17).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from flywheel.contracts import FailureKindSpec, StageEvaluation, StageSpec

# `flywheel.contracts` does not re-export the alias from its package root, and
# widening that export is a contract change, so it is taken from its module.
from flywheel.contracts.v0 import FailureClass
from flywheel.eval.scorer.status import ScorerError, StepScore

UNKNOWN_KIND = "L-UNKNOWN"
NO_KIND_FROM_TASK = "task báo bước hỏng nhưng không gán kiểu lỗi"
UNKNOWN_STEPS = "còn bước chưa rõ nên không chắc bước nào hỏng trước"
EPISODE_SIGNALS_MISSING = "thiếu tín hiệu của cả episode: "


@dataclass(frozen=True)
class FailureVerdict:
    """What the scorer concluded about the failure of one episode."""

    first_failed_step: int | None
    failure_kind: str | None
    failure_class: FailureClass | None
    # Why no kind could be named, on `L-UNKNOWN` and only there.
    reason: str | None = None

    @property
    def success(self) -> bool | None:
        """Whether the episode passed, or `None` where the scorer cannot tell."""
        if self.failure_kind == UNKNOWN_KIND:
            return None
        return self.failure_kind is None


def judge_failure(
    evaluation: StageEvaluation,
    steps: Sequence[StepScore],
    kinds: Sequence[FailureKindSpec],
    failed: int | None,
    stages: Sequence[StageSpec] = (),
) -> FailureVerdict:
    """Name the failure of one episode from its already-scored steps."""
    declared = _declared(kinds)
    unknown = next((step for step in steps if step.status == "unknown"), None)
    if unknown is not None:
        # With a failed step as well, the reason is that the order is in doubt,
        # not whatever the unjudged step was missing.
        if failed is not None:
            return unknown_verdict(UNKNOWN_STEPS)
        return unknown_verdict(unknown.detail or unknown.reason or UNKNOWN_STEPS)
    if failed is None:
        if evaluation.failure_kind is not None:
            # Two answers that contradict each other: no step failed and yet a
            # kind of failure is named. Dropping the kind would report the
            # episode as a pass, so the disagreement is raised the way a
            # disagreeing `first_failed_stage` is.
            raise ScorerError(
                f"`stage_success` không có bước nào trượt nhưng task gán kiểu lỗi "
                f"`{evaluation.failure_kind}`"
            )
        return FailureVerdict(first_failed_step=None, failure_kind=None, failure_class=None)
    kind = evaluation.failure_kind
    if kind is None:
        return unknown_verdict(NO_KIND_FROM_TASK)
    if kind not in declared:
        raise ScorerError(
            f"kiểu lỗi `{kind}` không có trong `failure_kinds()` của task; "
            f"bộ mã đang khai là {sorted(declared)}"
        )
    return FailureVerdict(
        first_failed_step=failed,
        failure_kind=kind,
        failure_class=_failure_class(evaluation, declared[kind], failed, stages),
    )


def apply_episode_signals(verdict: FailureVerdict, missing: Sequence[str]) -> FailureVerdict:
    """Take a clean episode's pass away when a signal no step owns is missing.

    The collision flag of the two-table task belongs to no single step, so a
    trace without it leaves every step judgeable and the episode not. Reporting
    that as a success is the silent pass FR21 forbids. A failure that already
    has a name keeps it, as with the balance condition: the missing signal
    cannot turn that episode into a pass, and the signals it was missing are in
    the record either way.
    """
    if missing and verdict.success is True:
        return unknown_verdict(EPISODE_SIGNALS_MISSING + ", ".join(missing))
    return verdict


def _failure_class(
    evaluation: StageEvaluation,
    spec: FailureKindSpec,
    failed: int,
    stages: Sequence[StageSpec],
) -> FailureClass | None:
    if evaluation.failure_class is not None:
        return evaluation.failure_class
    if spec.failure_class == "from_failed_stage":
        return stages[failed].failure_class if 0 <= failed < len(stages) else None
    return spec.failure_class


def unknown_verdict(reason: str) -> FailureVerdict:
    """`L-UNKNOWN` with the reason no kind could be named."""
    return FailureVerdict(
        first_failed_step=None,
        failure_kind=UNKNOWN_KIND,
        failure_class=None,
        reason=reason,
    )


def _declared(kinds: Sequence[FailureKindSpec]) -> dict[str, FailureKindSpec]:
    declared: dict[str, FailureKindSpec] = {}
    for spec in kinds:
        if spec.kind in declared:
            raise ScorerError(f"`failure_kinds()` khai `{spec.kind}` hai lần")
        if spec.kind == UNKNOWN_KIND:
            raise ScorerError(
                f"`failure_kinds()` không được khai `{UNKNOWN_KIND}`: đó là câu trả lời "
                "của scorer khi không gán được kiểu, không phải kiểu lỗi của task"
            )
        declared[spec.kind] = spec
    return declared

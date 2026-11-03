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
not decided here: what `evaluate()` put in `StageEvaluation.failure_class`
first, because that is the only value that can depend on the episode, and the
`failure_class` of the kind's own `FailureKindSpec` otherwise.

Spec section 5.2 gives `L-COLLIDE` and `L-TIMEOUT` the class of the failed step
instead of a class of their own, and `FailureKindSpec.failure_class` is a
required field, so a task cannot declare "theo bước hỏng k" statically - it can
only fill `StageEvaluation.failure_class` per episode, which is why that value
is read first. Letting the spec say so instead needs a contract field and goes
in the Contract change issue for Long with the rest (AC 1); the scorer does not
read `StageSpec.failure_class` as a third fallback, because guessing a class
the task did not name is worse than the episode value it already has.

At L0 the class is recorded and nothing reads it to choose an intervention
(AC 3); it is there so L1 can add failures up across tasks (FR17).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from flywheel.contracts import FailureKindSpec, StageEvaluation

# `flywheel.contracts` does not re-export the alias from its package root, and
# widening that export is a contract change, so it is taken from its module.
from flywheel.contracts.v0 import FailureClass
from flywheel.eval.scorer.status import ScorerError, StepScore, StepStatus

UNKNOWN_KIND = "L-UNKNOWN"
NO_KIND_FROM_TASK = "task báo bước hỏng nhưng không gán kiểu lỗi"
UNKNOWN_STEPS = "còn bước chưa rõ nên không chắc bước nào hỏng trước"


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
) -> FailureVerdict:
    """Name the failure of one episode from its already-scored steps."""
    declared = _declared(kinds)
    unknown = next((step for step in steps if step.status is StepStatus.UNKNOWN), None)
    if unknown is not None:
        # With a failed step as well, the reason is that the order is in doubt,
        # not whatever the unjudged step was missing.
        if failed is not None:
            return unknown_verdict(UNKNOWN_STEPS)
        return unknown_verdict(unknown.reason or UNKNOWN_STEPS)
    if failed is None:
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
        failure_class=evaluation.failure_class or declared[kind].failure_class,
    )


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

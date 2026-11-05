"""What the scorer concludes about one episode (DA-36 AC 1, 2).

These are lane-internal types, not contract records, the same split DA-08 made
between `Finding` and `TrainDiagnosis`. Task 5 maps them onto the `Score`
record of 03 section 4.3.

The four states are `StepStatus` of `flywheel.contracts` (#101, issue #59),
not a lane enum: they are what `Score.step_status` carries, and a second copy
here would be a second spelling of the same four words. They exist because
three cannot tell the two failure modes of a rollout apart. A task that sends
only `StageEvaluation.stage_success` (`bool | None`) reports a step that was
never reached and a step that was reached and failed both as `False`, and a
step with no signal behind it as `None` with nothing to say why. Spec section
5.1 is explicit about both: a step the robot never got to is "chưa thử", not
"trượt", and a step with no signal is "chưa rõ", not "đạt". `steps.py`
recovers the fourth state from the first failed step, or reads it from
`StageEvaluation.stage_status` when the task sends one. The reason behind an
unknown is carried here as `UnknownReason` of `flywheel.contracts`, the typed
code `Score.unknown_reason` holds, with the signal names an engineer needs
beside it as `detail`; and the time each step was entered and left, where the
task reported one, as `enter_s` and `exit_s`.

The status strings are what goes into `Score.step_status`. The Vietnamese names
of spec section 5.1 are what the CLI prints; they are a display concern, kept
in `cli.py`, so the artifact stays readable to a reader with no Vietnamese and
the printed table stays readable to the team.
"""

from __future__ import annotations

from dataclasses import dataclass

from flywheel.contracts import StepStatus, UnknownReason

__all__ = ["ScorerError", "StepScore", "StepStatus", "UnknownReason"]


class ScorerError(ValueError):
    """A task definition or evaluation the scorer must not turn into a `Score`."""


@dataclass(frozen=True)
class StepScore:
    """One step's state, why it is unknown when it is, and when it ran."""

    name: str
    status: StepStatus
    # Set on `unknown` and only there. An unknown without a reason is the
    # silent pass FR21 forbids, one indirection further along.
    reason: UnknownReason | None = None
    # The words behind the code - which signals were missing or empty - for
    # the CLI and `meta`; never set without a reason.
    detail: str | None = None
    # Seconds into the episode, as the task reported them; only a step that
    # was judged (`pass` or `fail`) carries a time.
    enter_s: float | None = None
    exit_s: float | None = None

    def __post_init__(self) -> None:
        if (self.status == "unknown") != (self.reason is not None):
            raise ScorerError(
                f"bước `{self.name}`: trạng thái `{self.status}` và lý do "
                f"{self.reason!r} không khớp; chỉ `unknown` mang lý do"
            )
        if self.detail is not None and self.reason is None:
            raise ScorerError(f"bước `{self.name}`: có `detail` mà không có lý do")
        timed = self.enter_s is not None or self.exit_s is not None
        if timed and self.status not in ("pass", "fail"):
            raise ScorerError(
                f"bước `{self.name}`: trạng thái `{self.status}` không mang thời điểm "
                "vào hay ra; chỉ bước đã chấm được mới có"
            )

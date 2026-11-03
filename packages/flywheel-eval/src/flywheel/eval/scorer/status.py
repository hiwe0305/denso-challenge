"""What the scorer concludes about one episode (DA-36 AC 1, 2).

These are lane-internal types, not contract records, the same split DA-08 made
between `Finding` and `TrainDiagnosis`. Task 5 maps them onto the `Score`
record of 03 section 4.3.

The four states exist because three cannot tell the two failure modes of a
rollout apart. `StageEvaluation.stage_success` of `flywheel.contracts` is
`bool | None`, so a step that was never reached and a step that was reached and
failed both arrive as `False`, and a step with no signal behind it arrives as
`None` with nothing to say why. Spec section 5.1 is explicit about both: a step
the robot never got to is "chưa thử", not "trượt", and a step with no signal is
"chưa rõ", not "đạt". `steps.py` recovers the fourth state from the first
failed step; the reason behind an unknown is carried here.

The enum values are the strings that go into `Score.step_status`. The
Vietnamese names of spec section 5.1 are what the CLI prints; they are a
display concern, kept in `cli.py`, so the artifact stays readable to a reader
with no Vietnamese and the printed table stays readable to the team.

`enter_step` and `exit_step` of 03 section 4.3 are not here. Nothing in
`StageEvaluation` carries them, and a field invented in lane code is a field
the other lanes cannot read, so they go through a Contract change issue for
Long together with the unknown reason (AC 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ScorerError(ValueError):
    """A task definition or evaluation the scorer must not turn into a `Score`."""


class StepStatus(str, Enum):
    """The four states of one step of the task (spec section 5.1)."""

    PASSED = "pass"
    FAILED = "fail"
    NOT_ATTEMPTED = "not_attempted"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StepScore:
    """One step's state, and why it is unknown when it is."""

    name: str
    status: StepStatus
    # Set on UNKNOWN and only there. An unknown without a reason is the silent
    # pass FR21 forbids, one indirection further along.
    reason: str | None = None

    def __post_init__(self) -> None:
        if (self.status is StepStatus.UNKNOWN) != (self.reason is not None):
            raise ScorerError(
                f"bước `{self.name}`: trạng thái `{self.status.value}` và lý do "
                f"{self.reason!r} không khớp; chỉ `unknown` mang lý do"
            )

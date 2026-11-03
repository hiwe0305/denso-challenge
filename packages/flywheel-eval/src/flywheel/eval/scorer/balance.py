"""The condition that has to hold for the whole episode (DA-36 task 4, AC 1, 3).

Spec section 5.1 ends with a condition that belongs to no single step: body
height and tilt stay within the balance limits throughout. `L-BALANCE` is the
one kind of spec section 5.2 that can be assigned at any step, so it cannot
come out of the per-step predicates - a robot that falls after setting the
object down passes all six steps.

The check is a comparison against limits read from config, over the signals
config names. Neither the signal names nor the numbers are written here: the
tray task watches the tilt of a tray as well, and the limits themselves are
what DA-37 calibrates.

Missing balance signals come back as unknown, not as balance held. An episode
whose torso height nobody recorded is not an episode that stayed upright, and
the control a test has to make is both "no failure" *and* "nothing unknown",
because a trace that cannot be scored also produces an empty failure list.
"""

from __future__ import annotations

from dataclasses import dataclass

import pyarrow as pa  # type: ignore[import-untyped]
from flywheel.eval.scorer.failure import FailureVerdict, unknown_verdict
from flywheel.eval.scorer.status import ScorerError

BALANCE_KIND = "L-BALANCE"


@dataclass(frozen=True)
class BalanceLimits:
    """Which signals bound the body, and by how much (configured, never in code)."""

    min_height: float
    max_tilt: float
    height_signal: str
    tilt_signal: str

    def signals(self) -> tuple[str, ...]:
        return (self.height_signal, self.tilt_signal)


@dataclass(frozen=True)
class BalanceVerdict:
    """Whether the body stayed within its limits, and where it first did not."""

    violated: bool
    # The trace row the violation was first measured on, not a step of the
    # task: mapping a row onto a step needs the per-step enter and exit times
    # that `StageEvaluation` does not carry (AC 1, Contract change for Long).
    row: int | None = None
    signal: str | None = None
    value: float | None = None
    limit: float | None = None
    unknown_reason: str | None = None

    @property
    def unknown(self) -> bool:
        return self.unknown_reason is not None


def check_balance(signals: pa.Table, limits: BalanceLimits) -> BalanceVerdict:
    """Check the whole-episode condition over every row of the trace."""
    absent = tuple(name for name in limits.signals() if name not in signals.column_names)
    if absent:
        return BalanceVerdict(violated=False, unknown_reason="thiếu tín hiệu: " + ", ".join(absent))
    if signals.num_rows == 0:
        return BalanceVerdict(violated=False, unknown_reason="trace không có bước nào")

    heights = signals[limits.height_signal].to_pylist()
    tilts = signals[limits.tilt_signal].to_pylist()
    gaps = tuple(
        name
        for name, values in ((limits.height_signal, heights), (limits.tilt_signal, tilts))
        if any(value is None for value in values)
    )
    for row, (height, tilt) in enumerate(zip(heights, tilts, strict=True)):
        if height is not None and float(height) < limits.min_height:
            return _violation(row, limits.height_signal, float(height), limits.min_height)
        if tilt is not None and abs(float(tilt)) > limits.max_tilt:
            return _violation(row, limits.tilt_signal, float(tilt), limits.max_tilt)
    if gaps:
        # Within limits on every row that was measured, and some were not: that
        # is not the same as having held throughout.
        return BalanceVerdict(
            violated=False, unknown_reason="tín hiệu có khoảng trống: " + ", ".join(gaps)
        )
    return BalanceVerdict(violated=False)


def apply_balance(verdict: FailureVerdict, balance: BalanceVerdict) -> FailureVerdict:
    """Fold the whole-episode condition into the failure of the episode.

    A violation names the episode `L-BALANCE` whatever the steps said, because
    the body left its limits and everything measured after that happened to a
    robot that was already falling. The failed step is kept where the task
    reported one and stays unset where it did not: the violation is known by
    its trace row, and turning a row into a step would be a guess.

    A condition that could not be checked costs an otherwise clean episode its
    pass. Six steps passed with nobody watching the torso is not a successful
    episode, it is an episode that was not fully scored, and reporting it as a
    success is the silent pass FR21 forbids. A failure that already has a name
    keeps it: the balance question cannot turn that episode into a pass, and
    `L-UNKNOWN` there would throw away the kind the task did establish.
    """
    if balance.violated:
        if balance.row is None:  # defended: a violation always carries its row
            raise ScorerError("vi phạm thăng bằng không ghi được bước nào")
        return FailureVerdict(
            first_failed_step=verdict.first_failed_step,
            failure_kind=BALANCE_KIND,
            failure_class="balance",
        )
    if balance.unknown and verdict.success is True:
        return unknown_verdict(f"không kiểm được điều kiện thăng bằng: {balance.unknown_reason}")
    return verdict


def _violation(row: int, signal: str, value: float, limit: float) -> BalanceVerdict:
    return BalanceVerdict(violated=True, row=row, signal=signal, value=value, limit=limit)

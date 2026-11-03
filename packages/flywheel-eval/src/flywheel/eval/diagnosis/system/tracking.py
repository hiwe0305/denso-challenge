"""R3: did the WBC follow the commands it was sent? (DA-13 AC 1)

Spec section 6.4, step 2: the norm of (command sent - state measured), upper
and lower body apart, over tau_track of that half. The two halves are measured
apart because they track different things - the upper body tracks joint targets
for arms, wrists and hands, the lower body tracks a base velocity, a torso
height and a heading - and one threshold over both would let a fault in
whichever half moves less hide under the other.

The statistic is a percentile of the per-cycle norm, named in the config rather
than fixed here, so a run can say which statistic it used. tau_track itself is
calibrated as the 99th percentile over successful teleop episodes (AC 2): a
controller that tracks no worse than the human demonstrations did is a
controller nobody has evidence against.

A finding names the worst cycle it found. That is the trace row, not a step of
the task: turning one into the other needs the per-step times
`StageEvaluation` does not carry, which DA-36 ran into as well.
"""

from __future__ import annotations

import numpy as np
from flywheel.eval.config import R3Thresholds
from flywheel.eval.diagnosis.system.reader import TraceLog, Values, percentile
from flywheel.eval.diagnosis.system.verdict import CheckResult, SystemFinding

PARTS = ("upper", "lower")


def check_r3(trace: TraceLog, cfg: R3Thresholds) -> CheckResult:
    """Tracking error of both halves of the body against their own thresholds.

    Both halves are always measured, so an episode where the arms tracked and
    the legs did not comes back saying exactly that. A half whose statistic is
    nan was not measured; `signals.py` has already said so by name, and
    repeating it here would report the same gap twice.
    """
    findings = []
    for part in PARTS:
        error = trace.tracking_error(part)
        statistic = percentile(error, cfg.percentile)
        threshold = _threshold(part, cfg)
        if not np.isfinite(statistic) or statistic <= threshold:
            continue
        findings.append(
            SystemFinding(
                code="R3",
                value=statistic,
                threshold=threshold,
                part=part,
                where=f"dòng trace {_worst_row(error)}",
            )
        )
    return CheckResult(findings=findings)


def _threshold(part: str, cfg: R3Thresholds) -> float:
    return cfg.tau_track_upper if part == "upper" else cfg.tau_track_lower


def _worst_row(error: Values) -> int:
    """The cycle with the largest error, ignoring the cycles nobody measured."""
    return int(np.nanargmax(error))

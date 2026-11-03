"""The whole system check of one episode, in the order of spec section 6.4 (DA-13 AC 1).

This is where the six F-SYS codes become one answer about one episode. The
order is infrastructure first (a crashed simulator or server makes every
other measurement its consequence; decision Q1 of 3/11/2026), then the order
of the spec: missing signal, tracking error, latency and buffer, sync offset,
calibration.

Every code is judged, not only the codes before the first fault. Running them
all costs nothing - they are arithmetic over arrays already in memory - and an
engineer fixing a controller fault is better off knowing the clocks were also
out than finding out after the re-run. What the order decides is the *label*:
`combine` takes the first code to fire, which is the fault to fix first.

A code whose signals are missing is not judged against its threshold at all.
`signals.py` says which codes those are and why, and the check for each of
them is skipped rather than run on a gap - a comparison against nan is false,
so running it would report "no fault" about something nobody measured.
"""

from __future__ import annotations

from flywheel.eval.config import SystemThresholds
from flywheel.eval.diagnosis.system.reader import SystemInputs
from flywheel.eval.diagnosis.system.runtime import check_r1, check_r2, check_r4, check_r5, check_r6
from flywheel.eval.diagnosis.system.signals import check_signals, unjudgeable_codes
from flywheel.eval.diagnosis.system.tracking import PARTS, check_r3
from flywheel.eval.diagnosis.system.verdict import CheckResult, SystemVerdict, combine


def diagnose_system(inputs: SystemInputs, cfg: SystemThresholds) -> SystemVerdict:
    """Run R1-R6 on one episode and fold them into one verdict (AC 1).

    The episode is cleared only when every code was judged and none fired.
    Anything else - a fault, or a code nobody could judge - keeps the episode
    out of the policy analysis, because spec section 6.4 fixes system faults
    first and re-runs the baseline afterwards.
    """
    unjudgeable = unjudgeable_codes(inputs, cfg.signals)
    results: list[CheckResult] = [check_signals(inputs, cfg.signals)]
    parts = tuple(part for part in PARTS if f"R3/{part}" not in unjudgeable)
    if parts:
        results.append(check_r3(inputs.trace, cfg.r3, parts))
    results.append(check_r1(inputs.rtc, cfg.r1))
    results.append(check_r2(inputs.rtc, cfg.r2))
    if "R4" not in unjudgeable:
        results.append(check_r4(inputs.trace, cfg.r4))
    results.append(check_r5(inputs.cameras, cfg.r5))
    results.append(check_r6(inputs.infra_status, cfg.r6))
    return combine(inputs.trace.episode_id, results, inputs.infra_status)

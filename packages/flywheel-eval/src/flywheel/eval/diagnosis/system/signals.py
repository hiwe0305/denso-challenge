"""The first step of the ordered check: is there enough signal to judge at all?

Spec section 6.4 puts this before every fault code, and the reason is the shape
of the whole story. Each later check compares a measurement against a
threshold, and a comparison against a gap is false, so a trace with nothing in
it would clear R1 through R5 and come out as a system that behaved. The answer
spec section 6.4 requires is CHƯA RÕ with a request for more evidence, and this
module is what produces it.

It answers per code, not for the whole episode, and per half of the body for
R3. A trace with no new camera frame cannot be judged on sync offset,
and saying so costs R4 its verdict and nothing else: the tracking error of the
upper body was still measured, and hiding it would lose a fault somebody has
to fix. A trace with no lower-body measurement costs `R3/lower` and leaves
`R3/upper` judged, for the same reason. What a missing signal does
cost the episode is the clean verdict - `combine` turns "nothing fired and
something went unjudged" into UNKNOWN, never into CLEAN (`verdict.py`).

A step that lacks a field never gets here: `TraceStep` requires every field
but `t_image`, and the reader refuses the line. What does get here comes in
three kinds, reported apart because they are collected apart:

* **A field logged as a value that is not finite** (`"NaN"`, `"Infinity"`,
  `"-Infinity"`). The writer logs it and the measurement was not taken on
  those cycles; raw psi-data logs `meas_lower` this way on every cycle.
* **No new frame anywhere.** A null `t_image` - or one left out, which
  `TraceStep` reads as null - is a cycle with no new camera frame and costs
  nothing, but a trace with no frame at all leaves R4 nothing to measure.
* **Dropped camera frames.** "camera mất khung" of spec section 6.4, counted
  by `TraceStep.dropped_frames` rather than inferred from a gap.
"""

from __future__ import annotations

from flywheel.eval.config import SignalLimits
from flywheel.eval.diagnosis.system.reader import SYNC_FIELDS, SystemInputs
from flywheel.eval.diagnosis.system.verdict import CheckResult
from flywheel.eval.diagnosis.train.finding import Skipped

# Which fields of the trace each code is measured on. R1 and R2 read the RTC
# log and R5 the camera parameters, so they are not here; their own checks say
# when the file they need is absent. R3 is two entries, one per half of the
# body, the way `SystemFinding.part` splits it: raw psi-data logs no
# `meas_lower`, and losing the lower half must not cost the upper half its
# verdict and hide a controller fault there.
FIELDS_OF_CODE: dict[str, tuple[str, ...]] = {
    "R3/upper": ("cmd_upper", "meas_upper"),
    "R3/lower": ("cmd_lower", "meas_lower"),
    "R4": SYNC_FIELDS,
}


def unjudgeable_codes(inputs: SystemInputs, limits: SignalLimits) -> dict[str, str]:
    """Codes the trace cannot be judged on, each with the reason in the field's words.

    A code appears here when too many of its cycles are gaps, when it has no
    cycle to measure, when the camera dropped more frames than allowed, or when
    the trace is too short for the statistic to mean anything.
    """
    trace = inputs.trace
    reasons: dict[str, str] = {}
    steps = trace.num_steps
    if steps < limits.min_steps:
        too_short = (
            f"trace chỉ có {steps} chu kỳ, dưới mức {limits.min_steps} cần để "
            f"phân vị có nghĩa"
        )
        return {code: too_short for code in FIELDS_OF_CODE}
    dropped = trace.dropped_frames
    for code, fields in FIELDS_OF_CODE.items():
        gapped = [
            f"{name} ({trace.gap_counts[name]}/{steps} chu kỳ)"
            for name in fields
            if _gap_fraction(trace.gap_counts.get(name, 0), steps) > limits.max_gap_fraction
        ]
        if gapped:
            reasons[code] = (
                f"thiếu tín hiệu quá mức cho phép ({limits.max_gap_fraction:.0%}): "
                f"{_names(gapped)}"
            )
            continue
        if code == "R4" and trace.frame_cycles == 0:
            # Every cycle said "no new frame": nothing to pair a state with.
            reasons[code] = "trace không có chu kỳ nào có khung ảnh mới (`t_image` hữu hạn)"
            continue
        if code == "R4" and dropped > limits.max_dropped_frames:
            # "camera mất khung" of spec section 6.4: the image clock is what a
            # dropped frame breaks, so it is R4 that cannot be judged.
            reasons[code] = (
                f"camera mất {dropped} khung, trên mức {limits.max_dropped_frames} cho phép"
            )
    return reasons


def check_signals(inputs: SystemInputs, limits: SignalLimits) -> CheckResult:
    """Step 1 of spec section 6.4 as a check result: every code it costs, with why."""
    return CheckResult(
        skipped=[
            Skipped(code, reason)
            for code, reason in sorted(unjudgeable_codes(inputs, limits).items())
        ]
    )


def _gap_fraction(gaps: int, steps: int) -> float:
    return gaps / steps if steps else 1.0


def _names(items: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in items)

"""The first step of the ordered check: is there enough signal to judge at all?

Spec section 6.4 puts this before every fault code, and the reason is the shape
of the whole story. Each later check compares a measurement against a
threshold, and a comparison against a gap is false, so a trace with nothing in
it would clear R1 through R5 and come out as a system that behaved. The answer
spec section 6.4 requires is CHƯA RÕ with a request for more evidence, and this
module is what produces it.

It answers per code, not for the whole episode. A trace that logged no image
timestamp cannot be judged on sync offset, and saying so costs R4 its verdict
and nothing else: the tracking error of the upper body was still measured, and
hiding it would lose a fault somebody has to fix. What a missing signal does
cost the episode is the clean verdict - `combine` turns "nothing fired and
something went unjudged" into UNKNOWN, never into CLEAN (`verdict.py`).

Three kinds of incompleteness, reported apart because they are collected apart:

* **A field no row carries.** The writer does not log it. Fixing it means
  changing what the rollout records.
* **A field logged as null or as a value that is not finite.** The writer logs
  it and the measurement was not taken on those cycles. A null `t_image` is
  not one of these: `TraceStep` writes it on every cycle with no new camera
  frame. What costs R4 its verdict there is a trace with no frame at all.
* **Dropped camera frames.** "camera mất khung" of spec section 6.4, counted
  by `TraceStep.dropped_frames` rather than inferred from a gap.
"""

from __future__ import annotations

from flywheel.eval.config import SignalLimits
from flywheel.eval.diagnosis.system.reader import SYNC_FIELDS, TRACK_FIELDS, SystemInputs
from flywheel.eval.diagnosis.system.verdict import CheckResult
from flywheel.eval.diagnosis.train.finding import Skipped

# Which fields of the trace each code is measured on. R1 and R2 read the RTC
# log and R5 the camera parameters, so they are not here; their own checks say
# when the file they need is absent.
FIELDS_OF_CODE: dict[str, tuple[str, ...]] = {
    "R3": TRACK_FIELDS,
    "R4": SYNC_FIELDS,
}


def unjudgeable_codes(inputs: SystemInputs, limits: SignalLimits) -> dict[str, str]:
    """Codes the trace cannot be judged on, each with the reason in the field's words.

    A code appears here when a field it is measured on is absent, when too many
    of its cycles are gaps, when the camera dropped more frames than allowed,
    or when the trace is too short for the statistic to mean anything.
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
        absent = [name for name in fields if name in trace.absent_fields]
        if absent:
            reasons[code] = f"trace không ghi {_names(absent)}"
            continue
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

"""Pure numpy helpers the F-TRAIN and F-OFF detectors share (design 10; DA-08 AC 1, 2).

Everything here works on plain step and value arrays. The reader turns contract
records into those arrays and the detectors only ever see them, so a schema
change in `flywheel.contracts` reaches the reader and stops there.

No threshold lives in this module. Every number a detector compares against
comes from `configs/eval/diagnosis/train.yaml` (AC 3).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

Steps = NDArray[np.int64]
Values = NDArray[np.float64]


def window_mask(step: Steps, start: int, width: int) -> NDArray[np.bool_]:
    """Records whose step falls in the half-open window `[start, start + width)`.

    Windows count steps, never records, so two jobs that log at different rates
    reach the same conclusion. A trailing window of `width` steps ending at
    `end` inclusive, which is the window T1 compares a spike against, is
    `window_mask(step, end - width + 1, width)`.
    """
    if width <= 0:
        raise ValueError(f"window width must be positive, got {width}")
    return (step >= start) & (step < start + width)


def median_in_window(step: Steps, value: Values, start: int, width: int) -> float:
    """Median of the finite values inside the window; nan when it holds none.

    Non-finite values are dropped here because T1 is the detector that reports
    NaN and Inf (design 10); letting them through would poison the smoothing
    T3 runs on and turn one bad record into a second finding.
    """
    return _median(value[window_mask(step, start, width)])


def at_val_points(val_step: Steps, train_step: Steps, train_value: Values) -> Values:
    """Train values folded onto the val measurement steps.

    Entry `i` is the median of the finite train values in
    `(val_step[i - 1], val_step[i]]`, and in `(-inf, val_step[0]]` for `i == 0`.
    T3 reads this smoothed train curve at the same points as `loss_val`, so a
    jagged train loss on a healthy job cannot raise T3 by itself. An entry with
    no train record in its window is nan: the caller skips that point.

    `val_step` must be ascending; the reader sorts both series by step.
    """
    if bool(np.any(np.diff(val_step) < 0)):
        raise ValueError("val_step must be ascending")
    folded = np.empty(val_step.size, dtype=np.float64)
    lower: int | None = None
    for index, step_value in enumerate(val_step):
        end = int(step_value)
        inside = train_step <= end
        if lower is not None:
            inside &= train_step > lower
        folded[index] = _median(train_value[inside])
        lower = end
    return folded


def relative_drop(baseline: float, final: float) -> float:
    """Share of `baseline` that is gone by `final`: `(baseline - final) / baseline`.

    T2 (val loss against the first measurements), T4 (one action group against
    another) and T7 (child checkpoint against its parent) all reduce to this one
    number. A baseline that is zero, negative or not finite carries no scale, and
    a final value that is not finite has no drop, so the answer is nan and the
    caller records a skip instead of concluding.
    """
    if not np.isfinite(baseline) or baseline <= 0.0 or not np.isfinite(final):
        return float("nan")
    return (baseline - final) / baseline


def linear_slope(x: Values, y: Values) -> float:
    """Least-squares slope of `y` against `x` over the pairs where both are finite.

    O2 fits it on `error_by_chunk_pos` to see error grow along the action chunk.
    The answer is nan when fewer than two finite pairs are left or when every
    `x` is the same value, so one chunk position cannot look like a trend.
    """
    keep = np.isfinite(x) & np.isfinite(y)
    x_kept, y_kept = x[keep], y[keep]
    if x_kept.size < 2:
        return float("nan")
    x_centered = x_kept - x_kept.mean()
    spread = float(np.dot(x_centered, x_centered))
    if spread == 0.0:
        return float("nan")
    return float(np.dot(x_centered, y_kept - y_kept.mean()) / spread)


def percentile_with_count(value: Values, q: float) -> tuple[float, int]:
    """The `q`-th percentile over the finite values, with the sample count behind it.

    DA-13 calibrates tau at the 99th percentile. On an episode with fewer than a
    hundred samples that is all but the maximum, so the count travels with the
    value and whoever reads tau can see how much to trust it.
    """
    finite = value[np.isfinite(value)]
    if finite.size == 0:
        return float("nan"), 0
    return float(np.percentile(finite, q)), int(finite.size)


def _median(value: Values) -> float:
    finite = value[np.isfinite(value)]
    if finite.size == 0:
        return float("nan")
    return float(np.median(finite))

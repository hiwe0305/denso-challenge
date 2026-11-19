"""T1 - divergence: the loss left the range the job had been training in (design 10).

Two branches, one verdict. A loss that is not finite is divergence by itself,
and a smoothed loss over `k` times the smallest smoothed loss of the trailing
window is divergence against the job's own recent history.

The spike branch reads the trailing median of the loss over `smooth_steps`,
never single batches (DA-44). On the eight healthy Psi0 fine-tunes of DA-26
and DA-34 one batch reaches over 100 times the smallest batch of the 500
steps before it, thousands of times per job; a divergence keeps the loss up,
which a median sees and one bad batch does not move. Whichever comes first on the
step axis is the finding; nothing after it is reported, because T1 is the one
code that marks a job to stop and no measurement past that point was going to
be trusted anyway.

Windows count steps, never records (plan, review point 2), so the same job
logged at two rates reaches the same verdict.
"""

from __future__ import annotations

from collections import deque

import numpy as np
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult, Finding, Skipped
from flywheel.eval.diagnosis.train.reader import Steps, TrainSeries, Values


def detect_t1(series: TrainSeries, cfg: TrainThresholds) -> DetectorResult:
    """Whether the train loss of this job diverged, and where it first did."""
    if series.step.size == 0:
        return DetectorResult(skipped=[Skipped("T1", "log không có bản ghi train nào")])
    events = [event for event in (_not_finite(series), _spike(series, cfg)) if event is not None]
    if not events:
        return DetectorResult()
    return DetectorResult(findings=[min(events, key=lambda finding: finding.start_step)])


def _not_finite(series: TrainSeries) -> Finding | None:
    """Branch (a): the first record whose loss is NaN or an infinity."""
    broken = np.flatnonzero(~np.isfinite(series.loss_train))
    if broken.size == 0:
        return None
    index = int(broken[0])
    return Finding(
        code="T1",
        start_step=int(series.step[index]),
        group=None,
        dim=None,
        value=float(series.loss_train[index]),
        threshold=None,
        stop_job=True,
    )


def _spike(series: TrainSeries, cfg: TrainThresholds) -> Finding | None:
    """Branch (b): the first smoothed loss over `k` times the minimum of its trailing window.

    The finding's value is the smoothed loss and its threshold `k` times the
    window minimum of the smoothed loss, so both numbers are on one curve.
    """
    smoothed, minima, ratio = smoothed_ratio(series.step, series.loss_train, cfg)
    over = np.isfinite(ratio) & (ratio > cfg.t1.k)
    spikes = np.flatnonzero(over)
    if spikes.size == 0:
        return None
    index = int(spikes[0])
    return Finding(
        code="T1",
        start_step=int(series.step[index]),
        group=None,
        dim=None,
        value=float(smoothed[index]),
        threshold=float(cfg.t1.k * minima[index]),
        stop_job=True,
    )


def smoothed_ratio(
    step: Steps, loss: Values, cfg: TrainThresholds
) -> tuple[Values, Values, Values]:
    """The smoothed loss, its window minimum, and the ratio of the two.

    The ratio is what T1 compares against `k`, and what `calibrate` reads on
    healthy jobs to propose `k`. It is nan where the window minimum is zero or
    less (no scale to multiply) or not finite (no usable loss in the window):
    no verdict there.
    """
    smoothed = trailing_median(step, loss, cfg.t1.smooth_steps)
    minima = _window_minima(step, smoothed, cfg.t1.window_steps)
    usable = np.isfinite(smoothed) & np.isfinite(minima) & (minima > 0.0)
    ratio = np.full(step.size, np.nan)
    np.divide(smoothed, minima, out=ratio, where=usable)
    return smoothed, minima, ratio


def trailing_median(step: Steps, value: Values, width: int) -> Values:
    """Median of the finite values in the `width`-step window ending at each record.

    The window of record `i` is `(step[i] - width, step[i]]`, counted in steps
    like every window of this story. Values that are not finite are left out -
    branch (a) reports those - and a window holding none is nan.
    """
    if width <= 0:
        raise ValueError(f"window width must be positive, got {width}")
    first = np.searchsorted(step, step - width + 1, side="left")
    finite = np.isfinite(value)
    out = np.full(step.size, np.nan)
    for index in range(step.size):
        window = value[first[index] : index + 1]
        kept = window[finite[first[index] : index + 1]]
        if kept.size:
            out[index] = float(np.median(kept))
    return out


def _window_minima(step: Steps, value: Values, width: int) -> Values:
    """Smallest finite value of the `width`-step window ending at each record.

    The window of record `i` is `(step[i] - width, step[i]]`, so it holds the
    record itself: a job whose loss only ever falls compares every record
    against itself and never spikes. Values that are not finite are left out of
    the minimum - branch (a) is what reports those - and a window holding none
    answers with an infinity, which `_spike` then refuses to judge on.
    """
    if width <= 0:
        raise ValueError(f"window width must be positive, got {width}")
    finite = np.where(np.isfinite(value), value, np.inf)
    first = np.searchsorted(step, step - width + 1, side="left")
    minima = np.empty(step.size, dtype=np.float64)
    ascending: deque[int] = deque()  # indices of the window, values ascending
    for index in range(step.size):
        while ascending and finite[ascending[-1]] >= finite[index]:
            ascending.pop()
        ascending.append(index)
        while ascending[0] < first[index]:
            ascending.popleft()
        minima[index] = finite[ascending[0]]
    return minima

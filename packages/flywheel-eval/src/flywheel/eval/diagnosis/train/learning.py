"""T2 and T3 - a job that is not learning, and one that learned the train set (design 10).

Both read the val split, so both can run out of measurements to judge on. When
they do they answer with `Skipped`, never with an empty `findings` list: a
checkpoint nobody could judge is not a clean checkpoint (FR21).

T2 compares the val loss after `n_steps` against a baseline that is the median
of the first few val measurements, so one noisy first measurement cannot set
the scale and hide a flat run (issue #5, 29/10/2026). T3 reads the train loss
folded onto the val measurement steps, so the batch-to-batch jitter of a
healthy run cannot look like a train loss that stopped falling.
"""

from __future__ import annotations

import numpy as np
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult, Finding, Skipped
from flywheel.eval.diagnosis.train.reader import TrainSeries, Values
from flywheel.eval.diagnosis.train.series import at_val_points, relative_drop
from numpy.typing import NDArray


def detect_t2(series: TrainSeries, cfg: TrainThresholds) -> DetectorResult:
    """Whether the val loss is still near where it started once `n_steps` are done."""
    count = cfg.t2.baseline_val_count
    if series.loss_val.size < count:
        return DetectorResult(
            skipped=[
                Skipped(
                    "T2",
                    f"chỉ có {series.loss_val.size} lần đo val, cần {count} lần đầu "
                    "để lấy baseline",
                )
            ]
        )
    after = np.flatnonzero(series.val_step >= cfg.t2.n_steps)
    if after.size == 0:
        return DetectorResult(
            skipped=[
                Skipped(
                    "T2",
                    f"lần đo val cuối ở step {int(series.val_step[-1])}, chưa tới "
                    f"step {cfg.t2.n_steps} nên chưa kết luận được",
                )
            ]
        )
    index = int(after[0])
    drop = relative_drop(_median(series.loss_val[:count]), float(series.loss_val[index]))
    if not np.isfinite(drop):
        return DetectorResult(
            skipped=[
                Skipped(
                    "T2",
                    f"baseline hoặc loss val ở step {int(series.val_step[index])} không "
                    "cho tính được mức giảm",
                )
            ]
        )
    if drop >= cfg.t2.min_relative_drop:
        return DetectorResult()
    return DetectorResult(
        findings=[
            Finding(
                code="T2",
                start_step=int(series.val_step[index]),
                group=None,
                dim=None,
                value=drop,
                threshold=cfg.t2.min_relative_drop,
            )
        ]
    )


def detect_t3(series: TrainSeries, cfg: TrainThresholds) -> DetectorResult:
    """Whether the val loss rose over `m_measurements` while the train loss fell."""
    needed = cfg.t3.m_measurements + 1
    if series.loss_val.size < needed:
        return DetectorResult(
            skipped=[
                Skipped(
                    "T3",
                    f"chỉ có {series.loss_val.size} lần đo val, cần {needed} lần liên "
                    "tiếp để thấy một đoạn tăng",
                )
            ]
        )
    train_at_val = at_val_points(series.val_step, series.step, series.loss_train)
    judged = np.isfinite(train_at_val) & np.isfinite(series.loss_val)
    if int(judged.sum()) < needed:
        return DetectorResult(
            skipped=[
                Skipped(
                    "T3",
                    f"chỉ {int(judged.sum())} lần đo val có loss train đi kèm, cần {needed} lần",
                )
            ]
        )
    # one transition of the run: train down and val up, both ends judged
    diverging = (
        (np.diff(train_at_val) < 0.0) & (np.diff(series.loss_val) > 0.0) & judged[:-1] & judged[1:]
    )
    run = _first_run(diverging, cfg.t3.m_measurements)
    if run is None:
        return DetectorResult()
    start, length = run
    return DetectorResult(
        findings=[
            Finding(
                code="T3",
                start_step=int(series.val_step[start]),
                group=None,
                dim=None,
                value=float(length),
                threshold=float(cfg.t3.m_measurements),
            )
        ]
    )


def _median(value: Values) -> float:
    """Median of the finite values; nan when there are none, so the caller skips."""
    finite = value[np.isfinite(value)]
    if finite.size == 0:
        return float("nan")
    return float(np.median(finite))


def _first_run(flags: NDArray[np.bool_], length: int) -> tuple[int, int] | None:
    """Start and length of the first run of at least `length` set flags."""
    start = 0
    while start < flags.size:
        if not flags[start]:
            start += 1
            continue
        end = start
        while end < flags.size and flags[end]:
            end += 1
        if end - start >= length:
            return start, end - start
        start = end
    return None

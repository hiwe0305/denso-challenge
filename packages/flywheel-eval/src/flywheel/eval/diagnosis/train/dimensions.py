"""T5 and T6 - a dimension the policy stopped using, and one it flattened (design 10).

Both read per-dimension statistics against the action layout of the embodiment,
so both need `LayoutView` and neither holds a joint number of its own (AC 2).

T5 is a dimension whose predicted variance fell to nothing: the policy emits a
constant there. A dimension the layout marks `masked` is constant on purpose
and is never reported. T6 is the softer version of the same fault - the
predictions keep varying but over a far narrower range than the targets do,
which is what mode collapse looks like per dimension.

T6 on a dimension whose `target_std` is zero is the case that has to end in a
skip: the ratio has no denominator, and reporting nothing there would turn an
unjudgeable dimension into a clean one (FR21, issue #5).
"""

from __future__ import annotations

import numpy as np
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult, Finding, Skipped
from flywheel.eval.diagnosis.train.reader import (
    LayoutView,
    PerDim,
    ReaderError,
    TrainSeries,
    Values,
)
from flywheel.eval.diagnosis.train.series import window_mask
from numpy.typing import NDArray


def detect_t5(series: TrainSeries, cfg: TrainThresholds, layout: LayoutView) -> DetectorResult:
    """Which unmasked dimensions the policy has stopped varying at all."""
    checked = _check(series.pred_var_by_dim, series, layout, "T5", "pred_var_by_dim")
    if checked is not None:
        return checked

    width = cfg.t5.window_steps
    last = int(series.step[-1])
    inside = window_mask(series.step, last - width + 1, width)
    variance = _mean_in_window(series.pred_var_by_dim, inside)

    findings: list[Finding] = []
    skipped: list[Skipped] = []
    for dim in range(layout.n_dims):
        if not layout.unmasked[dim]:
            continue  # masked on purpose; never a finding (AC 2)
        value = float(variance[dim])
        if not np.isfinite(value):
            skipped.append(
                Skipped(
                    "T5",
                    f"chiều {dim} ({layout.name(dim)}) không có số đo pred_var_by_dim "
                    f"hữu hạn trong {width} step cuối",
                )
            )
            continue
        if value < cfg.t5.epsilon:
            findings.append(
                Finding(
                    code="T5",
                    start_step=last - width + 1,
                    group=None,
                    dim=dim,
                    value=value,
                    threshold=cfg.t5.epsilon,
                )
            )
    return DetectorResult(findings=findings, skipped=skipped)


def detect_t6(series: TrainSeries, cfg: TrainThresholds, layout: LayoutView) -> DetectorResult:
    """Which unmasked dimensions vary far less than their targets do.

    Judged on the last record where both statistics were logged, because T6 has
    no window in the threshold file: the question is where the job ended up,
    not how it got there.
    """
    checked = _check(series.pred_std, series, layout, "T6", "pred_std")
    if checked is not None:
        return checked
    checked = _check(series.target_std, series, layout, "T6", "target_std")
    if checked is not None:
        return checked

    findings: list[Finding] = []
    skipped: list[Skipped] = []
    for dim in range(layout.n_dims):
        if not layout.unmasked[dim]:
            continue
        index = _last_both_logged(series.pred_std[:, dim], series.target_std[:, dim])
        if index is None:
            skipped.append(
                Skipped(
                    "T6",
                    f"chiều {dim} ({layout.name(dim)}) không có bản ghi nào có cả "
                    "pred_std và target_std",
                )
            )
            continue
        predicted = float(series.pred_std[index, dim])
        target = float(series.target_std[index, dim])
        if target <= 0.0:
            # The promised skip: no denominator, so no ratio and no verdict.
            skipped.append(
                Skipped(
                    "T6",
                    f"chiều {dim} ({layout.name(dim)}) có target_std = {target} ở step "
                    f"{int(series.step[index])}, không chia được để lấy tỉ lệ",
                )
            )
            continue
        ratio = predicted / target
        if ratio < cfg.t6.min_std_ratio:
            findings.append(
                Finding(
                    code="T6",
                    start_step=int(series.step[index]),
                    group=None,
                    dim=dim,
                    value=ratio,
                    threshold=cfg.t6.min_std_ratio,
                )
            )
    return DetectorResult(findings=findings, skipped=skipped)


def _check(
    values: PerDim, series: TrainSeries, layout: LayoutView, code: str, what: str
) -> DetectorResult | None:
    """The three reasons a per-dimension detector cannot start, as a skip each."""
    if series.step.size == 0:
        return DetectorResult(skipped=[Skipped(code, "log không có bản ghi train nào")])
    if values.size == 0:
        return DetectorResult(skipped=[Skipped(code, f"log không ghi {what}")])
    try:
        layout.check_width(values, what)
    except ReaderError as error:
        # A log written under another action layout. Judging dimension `i`
        # against the wrong joint would be worse than refusing to judge.
        return DetectorResult(skipped=[Skipped(code, str(error))])
    return None


def _mean_in_window(values: PerDim, inside: NDArray[np.bool_]) -> Values:
    """Per-dimension mean over the records in the window, ignoring nan rows."""
    window = values[inside]
    if window.size == 0:
        return np.full(values.shape[1], np.nan, dtype=np.float64)
    usable = np.isfinite(window)
    total = np.where(usable, window, 0.0).sum(axis=0)
    count = usable.sum(axis=0)
    return np.where(count > 0, total / np.maximum(count, 1), np.nan)


def _last_both_logged(predicted: Values, target: Values) -> int | None:
    both = np.flatnonzero(np.isfinite(predicted) & np.isfinite(target))
    return int(both[-1]) if both.size else None

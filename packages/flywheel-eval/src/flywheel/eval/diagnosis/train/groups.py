"""T4 - one action group stopped improving while another kept going (design 10).

The job as a whole can look healthy while the hand never learns: a loss summed
over every action dimension falls because the arm dimensions dominate it. T4
reads `loss_by_group` instead, and only calls a group imbalanced when a second
group did clearly improve over the same steps - a run where every group is slow
is a slow run, not an imbalanced one, and T2 is the code for that.

Both ends of the comparison are medians over a window of steps, never single
records, so one noisy measurement cannot invent or hide a finding.
"""

from __future__ import annotations

import numpy as np
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult, Finding, Skipped
from flywheel.eval.diagnosis.train.reader import TrainSeries
from flywheel.eval.diagnosis.train.series import median_in_window, relative_drop


def detect_t4(series: TrainSeries, cfg: TrainThresholds) -> DetectorResult:
    """Which action groups barely improved while another group did."""
    if not series.loss_by_group:
        return DetectorResult(skipped=[Skipped("T4", "log không ghi loss_by_group")])
    if series.step.size == 0:
        return DetectorResult(skipped=[Skipped("T4", "log không có bản ghi train nào")])

    width = cfg.t4.window_steps
    first, last = int(series.step[0]), int(series.step[-1])
    if last - first < width:
        return DetectorResult(
            skipped=[
                Skipped(
                    "T4",
                    f"job chỉ dài {last - first} step, cần {width} step để so baseline với cuối",
                )
            ]
        )

    drops: dict[str, float] = {}
    skipped: list[Skipped] = []
    for name, loss in sorted(series.loss_by_group.items()):
        baseline = median_in_window(series.step, loss, first, width)
        final = median_in_window(series.step, loss, last - width + 1, width)
        drop = relative_drop(baseline, final)
        if np.isfinite(drop):
            drops[name] = drop
        else:
            skipped.append(Skipped("T4", f"nhóm {name} không có đủ số đo hữu hạn ở hai đầu để so"))

    if not drops:
        return DetectorResult(skipped=skipped)

    # The reference is the group that improved most: T4 asks whether *some*
    # group managed to learn while this one did not.
    best = max(drops.values())
    if best < cfg.t4.ref_group_drop:
        return DetectorResult(skipped=skipped)

    findings = [
        Finding(
            code="T4",
            start_step=first,
            group=name,
            dim=None,
            value=drop,
            threshold=cfg.t4.min_group_drop,
        )
        for name, drop in drops.items()
        if drop < cfg.t4.min_group_drop
    ]
    return DetectorResult(findings=findings, skipped=skipped)

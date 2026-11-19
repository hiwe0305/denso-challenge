"""T1 and T8 thresholds proposed from healthy train logs, with the rule used (DA-44).

The detectors of DA-08 shipped with `k` and `max_grad_norm` as assumptions and
fired on every healthy Psi0 fine-tune (agent-qa 3.3). This module reads logs
the caller vouches are healthy and proposes the two numbers by a rule written
next to each, so the number in `train.yaml` can be traced to data and redone on
a new recipe.

The rules, both with a margin of 2 over the worst healthy job:

* `k` = 2 × the largest ratio of the smoothed train loss to its window minimum,
  the exact quantity the T1 spike branch compares. Rounded up to 0.5.
* `max_grad_norm` = 2 × the `(max_exceedances + 1)`-th largest action-head
  gradient norm, taken over jobs. T8 counts records over the limit and allows
  `max_exceedances` of them, so the number that matters is the one that would
  be the first exceedance too many, not a percentile: at p99 one record in a
  hundred is over by definition, hundreds per job. Rounded up to 10.

The proposal does not write the config. A human reads it and edits
`train.yaml`, because which logs count as healthy is a judgement, not a step.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.divergence import smoothed_ratio
from flywheel.eval.diagnosis.train.reader import TrainSeries

MARGIN = 2.0


@dataclass(frozen=True)
class JobStats:
    """What one healthy job says about each rule, and where it says it."""

    job_id: str
    n_train: int
    t1_max_ratio: float
    t1_max_ratio_step: int
    grad_p50: float
    grad_p99: float
    grad_max: float
    grad_allowed_top: float  # the (max_exceedances + 1)-th largest gradient norm


@dataclass(frozen=True)
class Proposal:
    """Proposed thresholds, the rules behind them and the jobs they were read on."""

    k: float
    k_rule: str
    max_grad_norm: float
    max_grad_norm_rule: str
    smooth_steps: int
    window_steps: int
    max_exceedances: int
    jobs: tuple[JobStats, ...]


def job_stats(series: TrainSeries, cfg: TrainThresholds) -> JobStats:
    """The numbers of one job each rule reads; raises on a log missing a signal."""
    name = series.job_id or "<job>"
    _, _, ratio = smoothed_ratio(series.step, series.loss_train, cfg)
    if not np.isfinite(ratio).any():
        raise ValueError(f"{name}: no finite train loss to calibrate T1 on")
    grad = series.grad_norm_action[np.isfinite(series.grad_norm_action)]
    top = cfg.t8.max_exceedances + 1
    if grad.size < top:
        raise ValueError(
            f"{name}: {grad.size} finite grad_norm_action records, need at least {top}"
        )
    worst = int(np.nanargmax(ratio))
    ordered = np.sort(grad)
    return JobStats(
        job_id=name,
        n_train=int(series.step.size),
        t1_max_ratio=float(ratio[worst]),
        t1_max_ratio_step=int(series.step[worst]),
        grad_p50=float(np.median(ordered)),
        grad_p99=float(np.percentile(ordered, 99)),
        grad_max=float(ordered[-1]),
        grad_allowed_top=float(ordered[-top]),
    )


def calibrate(jobs: Sequence[TrainSeries], cfg: TrainThresholds) -> Proposal:
    """Propose `t1.k` and `t8.max_grad_norm` from jobs the caller vouches are healthy.

    `cfg` supplies everything else the rules depend on - `smooth_steps`,
    `window_steps`, `max_exceedances` - so a proposal is only valid together
    with those three, and it says so.
    """
    if not jobs:
        raise ValueError("calibration needs at least one healthy job")
    stats = tuple(job_stats(job, cfg) for job in jobs)
    worst_ratio = max(stats, key=lambda job: job.t1_max_ratio)
    worst_top = max(stats, key=lambda job: job.grad_allowed_top)
    top = cfg.t8.max_exceedances + 1
    return Proposal(
        k=math.ceil(MARGIN * worst_ratio.t1_max_ratio * 2) / 2,
        k_rule=(
            f"{MARGIN:g} × max ratio of the smoothed train loss to its window minimum "
            f"({worst_ratio.t1_max_ratio:.2f} on {worst_ratio.job_id} at step "
            f"{worst_ratio.t1_max_ratio_step}), rounded up to 0.5"
        ),
        max_grad_norm=float(math.ceil(MARGIN * worst_top.grad_allowed_top / 10) * 10),
        max_grad_norm_rule=(
            f"{MARGIN:g} × the {top}th largest grad_norm_action of the worst job "
            f"({worst_top.grad_allowed_top:.1f} on {worst_top.job_id}), rounded up to 10"
        ),
        smooth_steps=cfg.t1.smooth_steps,
        window_steps=cfg.t1.window_steps,
        max_exceedances=cfg.t8.max_exceedances,
        jobs=stats,
    )

"""T8 - the gradients say something the train config does not (design 10).

Two independent branches under one code.

Branch (a) is a contradiction, not a threshold: a job that declares the VLM
frozen and still puts gradient through it is training something it says it is
not, so every later comparison against that run is against a different model
than the one on paper. The tolerance is 0.0 and stays 0.0.

Branch (b) is the action head spiking. One spike is a batch, not a fault, so a
finding needs more than `max_exceedances` records over the limit; the step
reported is the first of them, which is where to look in the log.

A log that carries neither gradient cannot be judged on either branch, and
each branch skips under its own name - `T8a`, `T8b` - so a reader of the
artifact can see which half went unmeasured. The finding itself is `T8`, the
only code the contract allows.
"""

from __future__ import annotations

import numpy as np
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult, Finding, Skipped
from flywheel.eval.diagnosis.train.reader import TrainSeries


def detect_t8(series: TrainSeries, cfg: TrainThresholds) -> DetectorResult:
    """Whether a frozen VLM moved, and whether the action head kept spiking."""
    if series.step.size == 0:
        return DetectorResult(skipped=[Skipped("T8", "log không có bản ghi train nào")])
    frozen = _frozen_vlm(series, cfg)
    spikes = _action_spikes(series, cfg)
    return DetectorResult(
        findings=frozen.findings + spikes.findings,
        skipped=frozen.skipped + spikes.skipped,
    )


def _frozen_vlm(series: TrainSeries, cfg: TrainThresholds) -> DetectorResult:
    """Branch (a): gradient through a VLM the job declares frozen."""
    if series.vlm_frozen is None:
        return DetectorResult(
            skipped=[
                Skipped("T8a", "log không cho biết vlm_frozen (thiếu, hoặc các bản ghi khác nhau)")
            ]
        )
    if not series.vlm_frozen:
        return DetectorResult()  # VLM is being trained; gradient there is expected
    measured = np.isfinite(series.grad_norm_vlm)
    if not measured.any():
        return DetectorResult(
            skipped=[Skipped("T8a", "khai vlm_frozen nhưng log không ghi grad_norm_vlm")]
        )
    over = np.flatnonzero(measured & (series.grad_norm_vlm > cfg.t8.frozen_tolerance))
    if over.size == 0:
        return DetectorResult()
    index = int(over[0])
    return DetectorResult(
        findings=[
            Finding(
                code="T8",
                start_step=int(series.step[index]),
                group=None,
                dim=None,
                value=float(series.grad_norm_vlm[index]),
                threshold=cfg.t8.frozen_tolerance,
            )
        ]
    )


def _action_spikes(series: TrainSeries, cfg: TrainThresholds) -> DetectorResult:
    """Branch (b): the action head over the gradient norm limit more than `M` times."""
    measured = np.isfinite(series.grad_norm_action)
    if not measured.any():
        return DetectorResult(skipped=[Skipped("T8b", "log không ghi grad_norm_action")])
    over = np.flatnonzero(measured & (series.grad_norm_action > cfg.t8.max_grad_norm))
    if over.size <= cfg.t8.max_exceedances:
        return DetectorResult()
    index = int(over[0])
    return DetectorResult(
        findings=[
            Finding(
                code="T8",
                start_step=int(series.step[index]),
                group=None,
                dim=None,
                value=float(series.grad_norm_action[index]),
                threshold=cfg.t8.max_grad_norm,
            )
        ]
    )

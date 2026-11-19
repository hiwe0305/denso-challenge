"""A healthy job shaped like the real Psi0 fine-tunes raises no T1, T2 or T8 (DA-44 AC 4).

Before DA-44 all three codes fired on every healthy 40k-step fine-tune of
DA-26 and DA-34 (agent-qa 3.3). The job here is synthetic but carries the
recorded shape, against the thresholds the repo ships:

* train loss from ~46 to ~0.1 with per-batch noise of a factor ~3 either way,
  so single batches reach tens of times the recent minimum;
* val measured every 2000 steps from step 0, falling 45.8 -> 2.3 -> 1.4 -> ...;
* action-head gradient norm with a median of 7-8, a p99 near 50, a warm-up in
  the first 2000 steps that reaches a few hundred, and one late batch at 1224;
* the VLM declared frozen with zero gradient.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.divergence import detect_t1
from flywheel.eval.diagnosis.train.gradients import detect_t8
from flywheel.eval.diagnosis.train.learning import detect_t2
from flywheel.eval.diagnosis.train.reader import TrainSeries

STEPS = 40000
RECORDED_VAL = [45.76, 2.28, 1.44, 0.85, 0.88, 0.77, 0.70, 0.62, 0.55, 0.50]


def real_shape(seed: int) -> TrainSeries:
    rng = np.random.default_rng(seed)
    step = np.arange(STEPS, dtype=np.int64)
    loss = (0.1 + 46.0 * np.exp(-step / 300.0)) * rng.lognormal(0.0, 0.6, STEPS)
    grad = rng.lognormal(math.log(7.5), 0.65, STEPS)
    warm = step < 2000
    grad[warm] *= rng.uniform(2.0, 6.0, int(warm.sum()))
    grad[25000] = 1224.0  # one late batch, as on one real 60k job
    val_step = np.arange(0, STEPS, 2000, dtype=np.int64)
    val = np.array(RECORDED_VAL + [0.45 - 0.01 * i for i in range(val_step.size - 10)])
    return TrainSeries(
        step=step,
        loss_train=loss,
        val_step=val_step,
        loss_val=val,
        grad_norm_action=grad,
        grad_norm_vlm=np.zeros(STEPS),
        vlm_frozen=True,
        job_id=f"real-shape-{seed}",
    )


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_the_recorded_shape_is_what_the_test_job_has(seed: int) -> None:
    job = real_shape(seed)
    warm = job.grad_norm_action[job.step < 2000]
    assert 7.0 <= float(np.median(job.grad_norm_action)) <= 8.5
    assert 40.0 <= float(np.percentile(job.grad_norm_action, 99)) <= 60.0
    assert float(np.max(warm)) > 150.0
    # single batches far over k times the window minimum: what fired T1 before
    late = job.loss_train[1000:]
    assert float(np.max(late) / np.min(late)) > 50.0


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_a_healthy_job_of_the_real_shape_raises_no_t1_t2_or_t8(
    seed: int, cfg: TrainThresholds
) -> None:
    job = real_shape(seed)
    for detect in (detect_t1, detect_t2, detect_t8):
        result = detect(job, cfg)
        assert result.findings == [], (detect.__name__, result.findings)
        assert result.skipped == [], (detect.__name__, result.skipped)


def test_a_gradient_blow_up_after_warm_up_is_still_t8(cfg: TrainThresholds) -> None:
    """The calibrated limit leaves room for a real fault: norms in the thousands.

    The finding starts at the first record over the limit (DA-08), which here
    is the lone healthy batch at step 25000, not the blow-up at 30000.
    """
    job = real_shape(0)
    grad = job.grad_norm_action.copy()
    grad[30000:30010] = 5000.0
    blown = TrainSeries(
        step=job.step,
        loss_train=job.loss_train,
        val_step=job.val_step,
        loss_val=job.loss_val,
        grad_norm_action=grad,
        grad_norm_vlm=job.grad_norm_vlm,
        vlm_frozen=True,
    )
    result = detect_t8(blown, cfg)
    assert [finding.start_step for finding in result.findings] == [25000]
    assert result.findings[0].threshold == cfg.t8.max_grad_norm


def test_a_loss_that_climbs_and_stays_up_is_still_t1(cfg: TrainThresholds) -> None:
    job = real_shape(0)
    loss = job.loss_train.copy()
    loss[30000:] *= 20.0  # the job leaves its range and does not come back
    climbed = TrainSeries(step=job.step, loss_train=loss)
    result = detect_t1(climbed, cfg)
    assert len(result.findings) == 1
    assert 30000 <= result.findings[0].start_step <= 30000 + cfg.t1.smooth_steps

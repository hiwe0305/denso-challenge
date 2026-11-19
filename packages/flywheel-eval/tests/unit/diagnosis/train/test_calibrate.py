"""Proposing T1 and T8 thresholds from healthy train logs (DA-44 task 3.2, AC 3).

The synthetic jobs here have the shape agent-qa 3.3 recorded on the real Psi0
fine-tunes: loss from about 46 down to about 0.1 with batch noise, val every
2000 steps, action-head gradient norm with a median of 7-8, a p99 near 50 and
a warm-up of a few hundred in the first 2000 steps.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.calibrate import calibrate, job_stats
from flywheel.eval.diagnosis.train.reader import TrainSeries


def healthy_job(seed: int, steps: int = 8000) -> TrainSeries:
    """A healthy job logged every step, shaped like the real ones."""
    rng = np.random.default_rng(seed)
    step = np.arange(steps, dtype=np.int64)
    trend = 0.1 + 46.0 * np.exp(-step / 300.0)
    loss = trend * rng.lognormal(0.0, 0.6, steps)  # batch noise, factor ~3 either way
    grad = rng.lognormal(math.log(7.5), 0.7, steps)
    warm = step < 2000
    grad[warm] *= 4.0  # warm-up: hundreds at the top
    val_step = np.arange(0, steps, 2000, dtype=np.int64)
    return TrainSeries(
        step=step,
        loss_train=loss,
        val_step=val_step,
        loss_val=0.1 + 45.0 * np.exp(-val_step / 300.0),
        grad_norm_action=grad,
        grad_norm_vlm=np.zeros(steps),
        vlm_frozen=True,
        job_id=f"job-{seed}",
    )


def test_job_stats_read_the_two_numbers_each_rule_needs(cfg: TrainThresholds) -> None:
    job = healthy_job(0)
    stats = job_stats(job, cfg)
    grad = np.sort(job.grad_norm_action)
    # the record that would be one exceedance too many at this limit
    assert stats.grad_allowed_top == pytest.approx(grad[-(cfg.t8.max_exceedances + 1)])
    assert stats.grad_p50 == pytest.approx(np.median(grad))
    # the smoothed loss of a falling job never rises far above its recent minimum
    assert 1.0 <= stats.t1_max_ratio < 3.0


def test_the_proposal_follows_the_written_rules(cfg: TrainThresholds) -> None:
    jobs = [healthy_job(seed) for seed in range(3)]
    proposal = calibrate(jobs, cfg)
    worst_ratio = max(job_stats(job, cfg).t1_max_ratio for job in jobs)
    worst_top = max(job_stats(job, cfg).grad_allowed_top for job in jobs)
    assert proposal.k == math.ceil(2 * worst_ratio * 2) / 2
    assert proposal.max_grad_norm == math.ceil(2 * worst_top / 10) * 10
    assert "2 ×" in proposal.k_rule and "2 ×" in proposal.max_grad_norm_rule
    assert [stats.job_id for stats in proposal.jobs] == ["job-0", "job-1", "job-2"]


def test_the_proposed_thresholds_leave_every_healthy_job_clean(cfg: TrainThresholds) -> None:
    from dataclasses import replace

    from flywheel.eval.diagnosis.train.divergence import detect_t1
    from flywheel.eval.diagnosis.train.gradients import detect_t8

    jobs = [healthy_job(seed) for seed in range(3)]
    proposal = calibrate(jobs, cfg)
    tuned = replace(
        cfg,
        t1=replace(cfg.t1, k=proposal.k),
        t8=replace(cfg.t8, max_grad_norm=proposal.max_grad_norm),
    )
    for job in jobs:
        assert detect_t1(job, tuned).findings == []
        assert detect_t8(job, tuned).findings == []


def test_a_p99_limit_would_have_flagged_the_same_healthy_jobs(cfg: TrainThresholds) -> None:
    """Why the T8 rule is not "p99": T8 allows a count of records over the limit.

    At p99 one record in a hundred is over by definition, which on an 8k-step
    job is about 80 against an allowance of `max_exceedances`.
    """
    job = healthy_job(0)
    p99 = float(np.percentile(job.grad_norm_action, 99))
    assert int((job.grad_norm_action > p99).sum()) > cfg.t8.max_exceedances


def test_no_job_is_an_error(cfg: TrainThresholds) -> None:
    with pytest.raises(ValueError, match="at least one"):
        calibrate([], cfg)


def test_a_job_without_gradient_or_loss_cannot_be_calibrated_on(cfg: TrainThresholds) -> None:
    job = healthy_job(0)
    blind = TrainSeries(step=job.step, loss_train=job.loss_train, job_id="blind")
    with pytest.raises(ValueError, match="grad_norm_action"):
        calibrate([blind], cfg)


def test_the_cli_prints_the_proposal_and_its_rules(tmp_path: Path, cfg: TrainThresholds) -> None:
    from flywheel.contracts.training import TrainingMetric
    from flywheel.eval.cli import app
    from typer.testing import CliRunner

    job = healthy_job(0, steps=1000)
    path = tmp_path / "metrics.jsonl"
    lines = [
        TrainingMetric(
            run_plan_id="rp",
            job_id="job-0",
            checkpoint_id="c",
            release_id="r",
            attempt=0,
            wall_time_s=float(step),
            step=int(step),
            epoch=0,
            split="train",
            loss=float(loss),
            lr=1e-4,
            vlm_frozen=True,
            grad_norm_vlm=0.0,
            grad_norm_action=float(grad),
        ).model_dump_json()
        for step, loss, grad in zip(job.step, job.loss_train, job.grad_norm_action, strict=True)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["calibrate-train", "--job", str(path)])
    assert result.exit_code == 0, result.output
    assert "t1.k = " in result.output and "t8.max_grad_norm = " in result.output
    assert "job-0" in result.output and "jobs = 1" in result.output


def test_the_cli_refuses_a_missing_log(tmp_path: Path) -> None:
    from flywheel.eval.cli import app
    from typer.testing import CliRunner

    result = CliRunner().invoke(app, ["calibrate-train", "--job", str(tmp_path / "none")])
    assert result.exit_code == 2

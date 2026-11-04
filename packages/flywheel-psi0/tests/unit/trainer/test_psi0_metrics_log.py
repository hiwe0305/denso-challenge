"""`MetricsLog` turns Psi0's `accelerator.log` calls into valid `metrics.jsonl` (DA-19 AC 3).

`psi0_loop` replays what `scripts/train.py` at the pin does - one `train/*` dict per
optimiser step, `inference()` on each val batch, then one `eval/*` dict - with
the key names `scripts/g0/read_psi0_logging.py` found, so no GPU or Psi0 is needed.
The job's checkpoint id comes from the testkit `FakeTrainer`.

The committed sample `fixtures/metrics_sample.jsonl` is the file the evaluation lane
reads until a real job runs; regenerate it with

    UPDATE_FIXTURES=1 uv run pytest packages/flywheel-psi0/tests/unit/trainer
"""

from __future__ import annotations

import itertools
import json
import os
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from flywheel.contracts import CheckpointRef, DatasetRef, TrainSpec
from flywheel.contracts.artifacts import ActionDimension, ActionLayout
from flywheel.contracts.training import TrainingMetric
from flywheel.testkit.fakes import FakeTrainer
from flywheel_psi0.trainer import JobIdentity, MetricsLog, ValStats
from flywheel_psi0.trainer.val_stats import (
    HAND_HIST_BINS,
    LossBreakdown,
    hand_openness,
    normalised_open_pose,
)
from numpy.typing import NDArray

SAMPLE = Path(__file__).parent / "fixtures" / "metrics_sample.jsonl"
CHUNK = 30

# Provisional G1 layout from design section 9 (Psi0 ACTION_SLICES_36D at cda3fdf)
# until DA-01 publishes configs/embodiments/g1.yaml; group names may change there.
G1_GROUPS = [("hand", 14), ("arm", 14), ("torso_rpy", 3), ("height", 1)] + [
    ("base_velocity", 2),
    ("turn", 1),
    ("target_yaw", 1),
]


def g1_layout() -> ActionLayout:
    names = [(group, i) for group, size in G1_GROUPS for i in range(size)]
    return ActionLayout(
        dimensions=[
            ActionDimension(name=f"{group}_{i}", group=group, masked=False) for group, i in names
        ]
    )


# Hand bounds (action min/max, dims 0-13) of stats_psi0.json in psi-data
# simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0; every joint has 0 as a bound.
HAND_LOW = [0.0, 0.0, 0.0, -1.5, -1.5, -0.6, -1.5, -0.5, -0.7, -0.7, 0.0, 0.0, 0.0, 0.0]
HAND_HIGH = [0.5, 0.7, 0.7, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.5, 1.5, 1.0, 1.5]


def g1_open_pose() -> NDArray[np.float64]:
    return normalised_open_pose(np.array(HAND_LOW), np.array(HAND_HIGH))


def toy_layout(masked_last: bool = False) -> ActionLayout:
    return ActionLayout(
        dimensions=[
            ActionDimension(name="arm_0", group="arm", masked=False),
            ActionDimension(name="arm_1", group="arm", masked=False),
            ActionDimension(name="pad_0", group="pad", masked=masked_last),
        ]
    )


def fake_identity(tmp_path: Path, attempt: int = 0) -> JobIdentity:
    spec = TrainSpec(
        job_id="job_da19_sample",
        dataset=DatasetRef(dataset_id="psi-data-two-table", uri="fake://psi-data"),
        parent=CheckpointRef(checkpoint_id="psi0-postpre.1by1.pad36.2601131206.ckpt.he30k"),
        seed=292285,
    )
    result = FakeTrainer(tmp_path / "staging").train(spec)
    assert result.checkpoint is not None
    return JobIdentity(
        run_plan_id="rp_da19_sample",
        job_id=spec.job_id,
        checkpoint_id=result.checkpoint.checkpoint_id,
        release_id="rel_psi_data_two_table",
        attempt=attempt,
        vlm_frozen=True,
    )


def psi0_loop(
    log: MetricsLog,
    stats: ValStats,
    steps: range,
    validation_steps: int,
    val_batches: int = 2,
    seed: int = 0,
) -> None:
    """The logging calls of `scripts/train.py` for `steps`, with synthetic numbers.

    What the launcher's hooks feed `MetricsLog` is fed here too, when it has the
    sink: the per-element train loss every step, and actions sampled on the train
    batch at validation steps.
    """
    rng = np.random.default_rng(seed)
    dims = len(stats.layout.dimensions)
    for global_step in steps:
        loss = 1.0 / (1 + 0.1 * global_step)
        if log.train_loss is not None:  # LossTap: F.mse_loss(..., reduction="none")
            growth = np.linspace(0.5, 1.5, CHUNK)[None, :, None]
            log.train_loss.add(rng.exponential(loss, size=(4, CHUNK, dims)) * growth)
        if log.train_stats is not None and global_step % validation_steps == 0:
            target = rng.uniform(-1, 1, size=(4, CHUNK, dims))
            log.train_stats.add(target + rng.normal(0, 0.03, target.shape), target)
        train = {
            "train/lr_act": 1e-4,
            "train/grad_norm_act": 0.5,
            # Psi0 omits it with a frozen VLM; the launcher (task 2) measures it.
            "train/grad_norm_vlm": 0.0,
            "train/loss": loss,
            "train/vlm_feat_norm": 12.0,
            "train/epoch": global_step // 50,
        }
        log.log(train, step=global_step)
        if global_step % validation_steps == 0:
            for _ in range(val_batches):
                target = rng.uniform(-1, 1, size=(4, CHUNK, dims))
                noise = rng.normal(0, 0.05 + 0.01 * np.arange(CHUNK)[None, :, None], target.shape)
                stats.add(target + noise, target)  # what inference() returned, and batch["actions"]
            log.log({"eval/loss": loss * 1.1, "eval/simple/err_l1_hand_joints": 0.02}, global_step)


def counter_clock(period: float = 1.5) -> Callable[[], float]:
    ticks = itertools.count()
    return lambda: next(ticks) * period


def read(path: Path) -> list[TrainingMetric]:
    return [TrainingMetric.model_validate_json(line) for line in path.read_text().splitlines()]


def test_fake_job_writes_one_valid_line_per_split(tmp_path: Path) -> None:
    stats = ValStats(toy_layout())
    log = MetricsLog(
        tmp_path / "metrics.jsonl",
        fake_identity(tmp_path),
        val_stats=stats,
        global_batch_size=16,
        clock=counter_clock(),
    )
    psi0_loop(log, stats, range(0, 20), validation_steps=10)

    records = read(tmp_path / "metrics.jsonl")
    train = [r for r in records if r.split == "train"]
    val = [r for r in records if r.split == "val"]
    assert [r.step for r in train] == list(range(20))
    assert [r.step for r in val] == [0, 10]
    assert {r.checkpoint_id for r in records} == {"fake-job_da19_sample-s292285"}
    # No interval before step 0, and the one before step 1 spans the evaluation at step 0.
    assert train[0].throughput is None and train[1].throughput is None
    assert train[2].throughput == pytest.approx(16 / 1.5)
    assert train[0].grad_norm_action == 0.5 and train[0].grad_norm_vlm == 0.0
    assert val[0].lr == 1e-4 and val[0].epoch == 0


def test_val_line_carries_the_recomputed_statistics(tmp_path: Path) -> None:
    stats = ValStats(toy_layout())
    log = MetricsLog(tmp_path / "metrics.jsonl", fake_identity(tmp_path), val_stats=stats)
    psi0_loop(log, stats, range(0, 1), validation_steps=1)

    train, val = read(tmp_path / "metrics.jsonl")
    assert train.loss_by_group == {} and train.pred_std == []
    assert set(val.loss_by_group) == {"arm", "pad"}
    assert len(val.loss_by_chunk_pos) == CHUNK
    # The synthetic noise grows along the chunk, so the error must too.
    assert val.loss_by_chunk_pos[-1] > val.loss_by_chunk_pos[0]
    assert len(val.pred_var_by_dim) == len(val.pred_std) == len(val.target_std) == 3
    assert val.hand_open_hist == []  # the toy layout has no hand group
    assert not stats  # the summary consumed the batches


def test_masked_dimension_is_left_out_of_errors_but_keeps_its_slot() -> None:
    stats = ValStats(toy_layout(masked_last=True))
    target = np.zeros((2, CHUNK, 3))
    predicted = target.copy()
    predicted[:, :, 2] = 100.0  # padding the model never has to match
    stats.add(predicted, target)

    summary = stats.summary()
    assert summary["loss_by_group"] == {"arm": 0.0}
    assert summary["loss_by_chunk_pos"] == [0.0] * CHUNK
    assert len(summary["pred_std"]) == 3  # type: ignore[arg-type]


def test_non_finite_loss_is_written_as_the_contract_string(tmp_path: Path) -> None:
    log = MetricsLog(tmp_path / "metrics.jsonl", fake_identity(tmp_path))
    log.log({"train/loss": float("nan"), "train/lr_act": 1e-4}, step=7)
    log.log({"train/loss": float("inf"), "train/lr_act": 1e-4}, step=8)

    lines = [json.loads(line) for line in (tmp_path / "metrics.jsonl").read_text().splitlines()]
    assert [line["loss"] for line in lines] == ["NaN", "Infinity"]


def test_resume_appends_lines_of_the_next_attempt(tmp_path: Path) -> None:
    path = tmp_path / "metrics.jsonl"
    first = MetricsLog(path, fake_identity(tmp_path))
    for step in range(3):
        first.log({"train/loss": 1.0, "train/lr_act": 1e-4}, step=step)
    # The job died after step 2; the checkpoint was at step 1, so step 2 is logged again.
    second = MetricsLog(path, fake_identity(tmp_path, attempt=1))
    for step in range(2, 4):
        second.log({"train/loss": 0.9, "train/lr_act": 1e-4}, step=step)

    assert [(r.attempt, r.step) for r in read(path)] == [(0, 0), (0, 1), (0, 2), (1, 2), (1, 3)]


def test_wrong_shape_is_refused() -> None:
    stats = ValStats(toy_layout())
    with pytest.raises(ValueError, match=r"\(batch, chunk, 3\)"):
        stats.add(np.zeros((2, CHUNK, 4)), np.zeros((2, CHUNK, 4)))


def test_hand_openness_is_one_at_the_open_pose_and_zero_at_the_far_bound() -> None:
    open_pose = g1_open_pose()
    assert set(open_pose.tolist()) == {-1.0, 1.0}  # 0 rad sits on a bound for every joint
    closed = -open_pose
    half = np.where(np.arange(14) < 7, open_pose, closed)  # left hand open, right closed

    openness = hand_openness(np.stack([open_pose, closed, half]), open_pose)
    assert openness.tolist() == [1.0, 1.0, 0.0, 0.0, 1.0, 0.0]  # (left, right) per sample


def test_open_pose_passes_through_on_dims_psi0_leaves_unnormalised() -> None:
    # DA-26's N20 cut: one hand never moves, so min = max = 0 on its joints, and
    # Psi0 passes those raw values through instead of dividing by a zero range.
    low = np.array([0.0, 0.0, 0.0, -1.5, 0.3])
    high = np.array([0.0, 0.7, 0.0, 0.0, 0.3])
    open_pose = normalised_open_pose(low, high)
    assert open_pose.tolist() == [0.0, -1.0, 0.0, 1.0, 0.0]

    n20 = normalised_open_pose(
        np.array([0.0] * 7 + HAND_LOW[7:]), np.array([0.0] * 7 + HAND_HIGH[7:])
    )
    assert np.isfinite(n20).all()
    assert hand_openness(n20[None, :], n20).tolist() == [1.0, 1.0]


def test_hand_open_pose_must_cover_the_hand_dims() -> None:
    with pytest.raises(ValueError, match="14 hand dims"):
        ValStats(g1_layout(), hand_open_pose=np.zeros(7))


def test_committed_sample_matches_the_wrapper(tmp_path: Path) -> None:
    stats = ValStats(g1_layout(), hand_open_pose=g1_open_pose())
    produced = tmp_path / "metrics.jsonl"
    log = MetricsLog(
        produced,
        fake_identity(tmp_path),
        val_stats=stats,
        train_loss=LossBreakdown(g1_layout(), rtc_prefix=8),
        train_stats=ValStats(g1_layout(), hand_open_pose=g1_open_pose()),
        global_batch_size=16,
        vram_gb=lambda: 21.5,
        clock=counter_clock(),
    )
    psi0_loop(log, stats, range(0, 101), validation_steps=50)

    records = read(produced)
    train = [r for r in records if r.split == "train"]
    val = [r for r in records if r.split == "val"]
    assert all(r.loss_by_group and len(r.loss_by_chunk_pos) == CHUNK - 8 for r in train)
    assert [r.step for r in train if r.pred_std] == [0, 50, 100]
    assert len(val[0].hand_open_hist) == HAND_HIST_BINS
    assert sum(val[0].hand_open_hist) == pytest.approx(1.0)
    if os.environ.get("UPDATE_FIXTURES"):
        SAMPLE.parent.mkdir(exist_ok=True)
        SAMPLE.write_text(produced.read_text())
    assert produced.read_text() == SAMPLE.read_text()


def test_loss_breakdown_drops_the_rtc_prefix() -> None:
    split = LossBreakdown(toy_layout(), rtc_prefix=8)
    squared = np.ones((2, CHUNK, 3))
    squared[:, :8] = 100.0  # positions RTC leaves out of the loss
    split.add(squared)

    summary = split.summary()
    assert summary["loss_by_chunk_pos"] == [1.0] * (CHUNK - 8)
    assert summary["loss_by_group"] == {"arm": 1.0, "pad": 1.0}
    with pytest.raises(ValueError, match="nothing past 8"):
        split.add(np.ones((2, 8, 3)))

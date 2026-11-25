"""The stats files are accumulated in float64, so a long release keeps its mean and std.

SIMPLE's `stats_block` accumulates a float32 column in float32: a column of 0.74 in
300000 frames gets mean 0.7381 and std 0.0019. Psi0 may normalise with these stats, so
`compute_stats` accumulates every column in float64 (`stats_block_f64`); `stats_block`
stays SIMPLE's recipe, which the export checklist runs at both precisions.
"""

import json
from pathlib import Path

import numpy as np
from flywheel.data.ingest.lerobot import EpisodeFrames, write_episode
from flywheel.data.inject.stats import compute_stats, stats_block, stats_block_f64
from lerobot_data import CAMERA, FPS, TASK, fake_mp4, info, video_path

KEYS = ("mean", "std", "min", "max", "q01", "q99")


def test_a_long_float32_constant_column_keeps_its_mean_and_std() -> None:
    block = stats_block_f64(np.full((300_000, 4), 0.74, dtype=np.float32))
    assert np.abs(np.subtract(block["mean"], 0.74)).max() < 1e-6
    assert max(block["std"]) < 1e-6
    assert block["min"] == block["max"] == block["q01"] == block["q99"] == [
        float(np.float32(0.74))
    ] * 4


def test_float32_input_matches_a_float64_reference() -> None:
    rng = np.random.default_rng(0)
    values = (rng.standard_normal((50_000, 8)) * 0.1 + 0.5).astype(np.float32)
    block = stats_block_f64(values)
    wide = values.astype(np.float64)
    for key, expected in (("mean", wide.mean(axis=0)), ("std", wide.std(axis=0))):
        np.testing.assert_allclose(block[key], expected, rtol=1e-7, atol=1e-8, err_msg=key)
        assert block[key] == expected.astype(np.float32).tolist(), key


def test_integer_and_flag_columns_are_unchanged() -> None:
    for column in (
        np.arange(1_000, 41_000, dtype=np.int64),
        np.full(40_000, 3, dtype=np.int64),
        (np.arange(40_000) % 400 == 399).astype(np.float32),
    ):
        old, new = stats_block(column), stats_block_f64(column)
        for key in KEYS:
            np.testing.assert_allclose(new[key], old[key], rtol=0, atol=1e-7, err_msg=key)
        assert new["min"] == old["min"] and new["max"] == old["max"]


def test_stats_block_stays_simple_recipe_for_the_checklist() -> None:
    # The export checklist recomputes SIMPLE's stats in float32 and float64 through
    # `stats_block`, so it must keep accumulating in the precision it is given.
    constant = np.full((300_000, 4), 0.74, dtype=np.float32)
    assert abs(stats_block(constant)["mean"][0] - 0.74) > 1e-3
    assert stats_block(constant.astype(np.float64)) == stats_block_f64(constant)


def test_compute_stats_of_a_long_episode_keep_a_constant_dim(tmp_path: Path) -> None:
    root, n = tmp_path / "long", 8_000
    (root / "meta").mkdir(parents=True)
    (root / "meta" / "info.json").write_text(json.dumps(info(), indent=4))
    rng = np.random.default_rng(1)
    states = rng.standard_normal((n, 32)).astype(np.float32)
    action = rng.uniform(-0.5, 0.5, (n, 36)).astype(np.float32)
    states[:, 31] = action[:, 31] = 0.74
    write_episode(
        root,
        EpisodeFrames(
            episode_index=0,
            task=TASK,
            timestamp=(np.arange(n) / FPS).astype(np.float32).astype(np.float64),
            frame_index=np.arange(n, dtype=np.int64),
            states=states,
            action=action,
            video_frames={CAMERA: n},
        ),
    )
    fake_mp4(video_path(root, 0), n, 0)
    rows, dataset = compute_stats(root)
    exact = float(np.float32(0.74))
    for block in (dataset["states"], dataset["action"], rows[0]["stats"]["action"]):
        assert block["mean"][31] == exact
        assert block["std"][31] == 0.0
    for name, values in (("states", states), ("action", action)):
        assert dataset[name]["mean"] == values.astype(np.float64).mean(axis=0).astype(
            np.float32
        ).tolist(), name

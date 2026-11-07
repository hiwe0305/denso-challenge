"""CPU tests of the train/serve chain check (DA-34 task 3.7, docs/he/tray.md 15)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from flywheel_psi0.tray import chain_check as cc
from flywheel_psi0.tray.replay_server import decode
from flywheel_simple.tray.predicates import STEP_NAMES

LO = np.array([0.0, -1.0, 2.0, 0.0])  # last dim dead (padding)
HI = np.array([2.0, 1.0, 6.0, 0.0])


def test_stages_follow_the_scorer_steps() -> None:
    assert cc.STEPS == STEP_NAMES
    assert cc.stage_of([False] * 7) == "approach_a"
    assert cc.stage_of([True] * 5 + [False] * 2) == "place"
    assert cc.stage_of([True] * 7) == "done"
    # a flag that comes back on later does not skip a step still off
    assert cc.stage_of([True, False, True, True, True, True, True]) == "grasp"


def test_normalized_units_and_dead_dims_follow_psi0() -> None:
    assert cc.live_dims(LO, HI).tolist() == [True, True, True, False]
    np.testing.assert_allclose(cc.half_range(LO, HI), [1.0, 1.0, 2.0, 1.0])
    a = np.zeros((30, 4))
    b = a + np.array([0.5, 0.5, 1.0, 9.0])  # 0.5 normalized on each live dim, dead dim ignored
    assert cc.chunk_error(a, b, cc.half_range(LO, HI), cc.live_dims(LO, HI)) == pytest.approx(0.5)


def test_window_repeats_the_last_row_past_the_end() -> None:
    actions = np.arange(10, dtype=float)[:, None]
    np.testing.assert_array_equal(cc.window(actions, 8, rows=4)[:, 0], [8, 9, 9, 9])


def test_frame_rows_label_stages_and_refuse_a_length_mismatch() -> None:
    ep = cc.Episode(seed=1279, episode_index=3, from_index=100, length=6, raw_parquet=Path("x"))
    steps = np.zeros((6, 7), bool)
    steps[2:, :5] = True  # reach_b reached at frame 2
    steps[5, :] = True
    rows = cc.frame_rows(ep, steps, stride=2)
    assert [(r["frame"], r["index"], r["stage"]) for r in rows] == [
        (0, 100, "approach_a"),
        (2, 102, "place"),
        (4, 104, "place"),
    ]
    assert rows[1]["noise_seed"] == cc.SEED_BASE + 30_000 + 2
    with pytest.raises(ValueError, match="raw episode has 5 frames"):
        cc.frame_rows(ep, steps[:5], stride=2)


def _cut(tmp_path: Path) -> tuple[Path, Path, Path]:
    cut, release, batch = tmp_path / "cut", tmp_path / "release", tmp_path / "batch"
    (cut / "meta").mkdir(parents=True)
    (release / "meta").mkdir(parents=True)
    rows = []
    for i, seed in enumerate((1013, 1279)):
        env = {"flywheel": {"seed": seed}}
        rows.append({"episode_index": i, "dataset_from_index": 50 * i, "length": 50,
                     "environment_config": json.dumps(env)})  # fmt: skip
    (cut / "meta/episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    subset = {"episodes": [{"episode_index": 0, "source_episode_index": 7},
                           {"episode_index": 1, "source_episode_index": 2}]}  # fmt: skip
    (cut / "meta/flywheel_subset.json").write_text(json.dumps(subset))
    export = [{"episode_index": i, "shard": f"shard-0{i % 2}", "raw_episode": 10 + i,
               "seed": {7: 1013, 2: 1279}.get(i, 0)} for i in range(8)]  # fmt: skip
    (release / "meta/flywheel_export.json").write_text(json.dumps({"episodes": export}))
    (cut / "meta/tasks.jsonl").write_text(
        json.dumps({"task_index": 0, "task": "Pick Up The Tray."})
    )
    return cut, release, batch


def test_episodes_are_traced_from_the_cut_to_the_raw_batch(tmp_path: Path) -> None:
    cut, release, batch = _cut(tmp_path)
    [ep] = cc.episodes_of(cut, release, batch, [1279])
    assert (ep.episode_index, ep.from_index, ep.length) == (1, 50, 50)
    assert ep.raw_parquet == batch / "shard-00/raw/data/chunk-000/episode_000012.parquet"
    assert cc.task_of(cut) == "pick up the tray."
    with pytest.raises(ValueError, match="seed 999 is not in the cut"):
        cc.episodes_of(cut, release, batch, [999])


def test_the_frames_command_reads_the_raw_step_flags(tmp_path: Path) -> None:
    cut, release, batch = _cut(tmp_path)
    raw = batch / "shard-00/raw/data/chunk-000/episode_000012.parquet"
    raw.parent.mkdir(parents=True)
    flags = [[1.0] * 5 + [0.0] * 2 if t >= 25 else [0.0] * 7 for t in range(50)]
    pq.write_table(pa.table({"observation.tray_steps": flags}), raw)
    out = tmp_path / "frames.jsonl"
    args = ["frames", "--cut", str(cut), "--release", str(release), "--batch", str(batch)]
    assert cc.main([*args, "--seed", "1279", "--stride", "10", "--out", str(out)]) == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [r["stage"] for r in rows] == ["approach_a"] * 3 + ["place"] * 2


def test_the_act_payload_is_what_simples_client_sends() -> None:
    body = cc.act_payload(np.zeros((360, 640, 3), np.uint8), np.ones(32), "pick up", 42)
    assert set(body) == {"image", "instruction", "history", "state", "condition", "gt_action",
                         "dataset_name", "timestamp"}  # fmt: skip
    request = decode(json.loads(json.dumps(body)))
    assert request["image"][cc.IMAGE_KEY].shape == (360, 640, 3)
    assert request["image"][cc.IMAGE_KEY].dtype == np.uint8
    assert request["state"]["states"].shape == (1, 32)
    assert request["history"] == {"reset": True, "seed": 42}
    assert request["dataset_name"] == "simple"


def test_rule_a1_reads_the_two_paths() -> None:
    assert cc.read_a1([0.005] * 99 + [0.02])["verdict"] == "match"
    assert cc.read_a1([0.06] * 100)["verdict"] == "serve_chain_fault"
    assert cc.read_a1([0.01] * 90 + [0.2] * 10)["verdict"] == "serve_chain_fault"  # p95 > 0.15
    assert cc.read_a1([0.03] * 100)["verdict"] == "small_difference"


def _stages(e_place: float, r_place: float) -> dict[str, dict[str, float]]:
    stages = {s: {"e": 0.1, "r": 0.5} for s in cc.EARLY}
    stages["place"] = {"e": e_place, "r": r_place}
    return stages


def test_rule_a2_reads_place_against_the_early_steps_and_the_hold_baseline() -> None:
    assert cc.read_a2(_stages(0.12, 0.6))["verdict"] == "learned_open_loop"
    assert cc.read_a2(_stages(0.12, 1.0))["verdict"] == "not_learned"  # no better than holding
    assert cc.read_a2(_stages(0.2, 0.6))["verdict"] == "not_learned"  # 2x the early error
    assert cc.read_a2(_stages(0.17, 0.8))["verdict"] == "weak"
    assert cc.read_a2({"approach_a": {"e": 0.1, "r": 0.5}})["verdict"] == "no_data"


def test_summarize_a_pairs_paths_by_frame_and_groups_by_stage() -> None:
    lo, hi = np.full(4, -1.0), np.full(4, 1.0)  # normalized units = raw units
    recorded = np.cumsum(np.full((100, 4), 0.01), axis=0)  # moves 0.01 per frame on every dim
    frames = [
        {"index": t, "frame": t, "episode_index": 0, "stage": "approach_a" if t < 50 else "place"}
        for t in range(0, 100, 10)
    ]
    off = {"approach_a": 0.0, "place": 0.3}  # train path error by stage, normalized units
    train = {f["index"]: cc.window(recorded, f["frame"]) + off[f["stage"]] for f in frames}
    serve = {k: v + 0.001 for k, v in train.items()}
    result = cc.summarize_a(frames, serve, train, {0: recorded}, lo, hi)
    assert result["a1"]["verdict"] == "match" and result["a1"]["median"] == pytest.approx(0.001)
    assert result["by_stage"]["approach_a"]["e"] == pytest.approx(0.0)
    assert result["by_stage"]["place"]["e"] == pytest.approx(0.3)
    hold = np.mean(np.abs(np.arange(24) * 0.01))  # holding a[t] misses the drift
    assert result["by_stage"]["place"]["h"] == pytest.approx(hold, rel=0.2)
    assert result["a2"]["verdict"] == "not_learned"


def test_image_metrics_catch_shape_channel_order_and_pixels() -> None:
    rng = np.random.default_rng(0)
    data = rng.integers(0, 256, (360, 640, 3), dtype=np.uint8)
    assert cc.read_b2(cc.image_metrics(data.copy(), data))["verdict"] == "match"
    assert cc.read_b2(cc.image_metrics(data[..., ::-1].copy(), data)) == {
        "verdict": "differs",
        "why": "channel order",
    }
    assert cc.read_b2(cc.image_metrics(data[:180], data[:180]))["why"] == "shape or dtype"
    other = rng.integers(0, 256, (360, 640, 3), dtype=np.uint8)
    assert cc.read_b2(cc.image_metrics(other, data))["verdict"] == "differs"


def test_state_metrics_catch_order_scale_and_sign() -> None:
    lo, hi = np.array([-1.0, -1.0, -1.0, 0.7]), np.array([1.0, 1.0, 1.0, 0.8])
    t = np.linspace(0, 6, 200)
    data = np.stack([np.sin(t), np.cos(t), np.sin(2 * t), 0.74 + 0.0 * t], axis=1)
    assert cc.read_b3(cc.state_metrics(data.copy(), data, lo, hi))["verdict"] == "match"
    swapped = data[:, [1, 0, 2, 3]]
    assert cc.read_b3(cc.state_metrics(swapped, data, lo, hi)) == {
        "verdict": "differs",
        "dims": [0, 1],
    }
    flipped = data * np.array([1, 1, -1, 1])
    assert cc.read_b3(cc.state_metrics(flipped, data, lo, hi)) == {
        "verdict": "differs",
        "dims": [2],
    }


def test_compare_episode_matches_request_k_with_frame_24k() -> None:
    lo, hi = np.full(32, -1.0), np.full(32, 1.0)
    frames = [np.full((360, 640, 3), k % 251, np.uint8) for k in range(100)]
    states = np.sin(np.arange(100)[:, None] * 0.05 + np.arange(32)[None] * 0.3)
    requests = [
        {
            "instruction": "pick up the tray.",
            "image_keys": [cc.IMAGE_KEY],
            "arrays": {
                f"image.{cc.IMAGE_KEY}": frames[min(24 * k, 99)],
                "state.states": states[min(24 * k, 99)][None],
            },
        }
        for k in range(6)  # request 5 starts at frame 120, past the end: not compared
    ]
    result = cc.compare_episode(requests, frames, states, lo, hi, "pick up the tray.")
    assert result["compared"] == 5 and result["instruction_matches_train"]
    assert result["b2"]["verdict"] == "match" and result["b3"]["verdict"] == "match"

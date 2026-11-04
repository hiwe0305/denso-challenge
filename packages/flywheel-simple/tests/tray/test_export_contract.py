"""Contract of the Psi0 export: design 27/10/2026 section 6.4 checklist (DA-33 AC 4, 6, Task 8).

Runs in the SIMPLE venv (pyarrow, PyAV, SIMPLE's postprocess script):

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m pytest packages/flywheel-simple/tests/tray/test_export_contract.py -m sim -v

With FLYWHEEL_TRAY_RELEASE set, checks that release (and its manifest) as is.
With FLYWHEEL_TRAY_BATCH set to a generated and replay-QA'd batch, exports two
of its episodes; otherwise generates and replays two (level 1, seeds 1-2) first.
Item 7 (read back with Psi0's loader) waits for DA-19's recipe.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytestmark = pytest.mark.sim

PSI_DATA_INFO = (
    Path(__file__).parents[4]
    / "fwdata/psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0/meta/info.json"
)
N = 2


@pytest.fixture(scope="module")
def exported(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from flywheel_simple.tray.export import export_psi0

    release = os.environ.get("FLYWHEEL_TRAY_RELEASE")
    if release is not None:
        return Path(release)
    work = tmp_path_factory.mktemp("export")
    batch = os.environ.get("FLYWHEEL_TRAY_BATCH")
    if batch is None:
        from flywheel_simple.tray.generate import generate, shard_dir
        from flywheel_simple.tray.replay_qa import replay_qa

        # A few spare attempts: which seeds succeed moves with the planner (seed 2 fails
        # L-PLACE-POSE with da33-planner-5, passed with planner-4), so need N of them.
        summary = generate(work / "gen", n_attempts=N + 2, level=1, seed_start=1)
        assert summary.qa_pass >= N, summary
        shard = shard_dir(work / "gen", 0)
        replay_qa(shard / "raw", shard / "replay")
        batch = str(work / "gen")
    episodes = export_psi0(Path(batch), work / "out", max_episodes=N)
    assert len(episodes) == N
    return work / "out"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _n(root: Path) -> int:
    return len(_jsonl(root / "meta/episodes.jsonl"))


def _info(root: Path) -> dict[str, Any]:
    info: dict[str, Any] = json.loads((root / "meta/info.json").read_text())
    return info


def _tables(root: Path) -> list[Any]:
    import pyarrow.parquet as pq

    return [pq.read_table(p) for p in sorted((root / "data").glob("chunk-*/episode_*.parquet"))]


def _column(table: Any, key: str) -> Any:
    return np.asarray(table.column(key).to_pylist(), dtype=np.float64)


def test_info_declares_v21_at_50_fps_with_psi0_shapes(exported: Path) -> None:
    info = _info(exported)
    assert (info["codebase_version"], info["fps"], info["robot_type"]) == ("v2.1", 50, "g1")
    assert info["total_episodes"] == _n(exported)
    assert info["features"]["action"]["dtype"] == "float32"
    for table in _tables(exported):
        assert _column(table, "action").shape[1] == 36
        assert _column(table, "states").shape[1] == 32


def test_action_layout_names_every_action_dimension(exported: Path) -> None:
    layout = json.loads((exported / "meta/action_layout.json").read_text())
    meta = json.loads((exported / "meta/flywheel_export.json").read_text())
    assert len(layout["dimensions"]) == meta["action_dim"] == 36
    assert len(meta["state"]["names"]) == meta["state"]["dim"] == 32
    assert meta["state"]["pad_to"] == 36 and not any(d["masked"] for d in layout["dimensions"])
    modality = json.loads((exported / "meta/modality.json").read_text())
    assert max(v["end"] for v in modality["action"].values()) == 36
    assert max(v["end"] for v in modality["state"].values()) == 32


def test_columns_hold_the_raw_joints_their_layout_names(exported: Path) -> None:
    import pyarrow.parquet as pq

    meta = json.loads((exported / "meta/flywheel_export.json").read_text())
    batch = Path(meta["source_batch"])
    if not batch.exists():
        pytest.skip(f"source batch {batch} not on this machine")
    first = meta["episodes"][0]
    raw_root = batch / first["shard"] / "raw"
    features = json.loads((raw_root / "meta/info.json").read_text())["features"]
    index = first["raw_episode"]
    raw = pq.read_table(raw_root / f"data/chunk-{index // 1000:03d}/episode_{index:06d}.parquet")
    raw_action = dict(zip(features["action"]["names"], _column(raw, "action").T))
    state_cols = _column(raw, "observation.state").T
    raw_state = dict(zip(features["observation.state"]["names"], state_cols))
    out = _tables(exported)[0]
    action, states = _column(out, "action"), _column(out, "states")
    layout = json.loads((exported / "meta/action_layout.json").read_text())["dimensions"]
    for k, dim in enumerate(layout[:31]):
        np.testing.assert_allclose(action[:, k], raw_action[dim["name"]], rtol=0, atol=1e-5)
    for k, name in enumerate(meta["state"]["names"][:31]):
        np.testing.assert_allclose(states[:, k], raw_state[name], rtol=0, atol=1e-5)
    height = _column(raw, "teleop.base_height_command").reshape(-1)
    np.testing.assert_allclose(action[:, 31], height, rtol=0, atol=1e-5)
    np.testing.assert_allclose(states[1:, 31], height[:-1], rtol=0, atol=1e-5)
    navigate = _column(raw, "teleop.navigate_command")
    np.testing.assert_allclose(action[:, 32:36], navigate, rtol=0, atol=1e-5)


def test_slices_match_simple_postprocess() -> None:
    from flywheel_simple.tray import export

    spec = importlib.util.spec_from_file_location(
        "postprocess", export.simple_root() / export.POSTPROCESS
    )
    assert spec is not None and spec.loader is not None
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    ranges = [(s, e) for _, s, e in script.ACTION_SLICES]
    assert ranges == [(s, e) for _, s, e in export.ACTION_SLICES]
    assert [(s, e) for _, s, e in script.STATE_SLICES] == [
        (s, e) for _, s, e in export.STATE_SLICES
    ]
    groups = [g for g, _, _ in script.ACTION_SLICES]
    assert groups[1:3] == ["left_hand_middle", "left_hand_index"]


def test_episode_and_frame_indices(exported: Path) -> None:
    episodes = _jsonl(exported / "meta/episodes.jsonl")
    assert [e["episode_index"] for e in episodes] == list(range(_n(exported)))
    start = 0
    for entry, table in zip(episodes, _tables(exported)):
        frames = table.column("frame_index").to_pylist()
        assert frames == list(range(entry["length"]))
        assert set(table.column("episode_index").to_pylist()) == {entry["episode_index"]}
        assert (entry["dataset_from_index"], entry["dataset_to_index"]) == (
            start, start + entry["length"] - 1)
        index = table.column("index").to_pylist()
        # Global `index` follows SIMPLE's script, as in psi-data: steps of 1 inside
        # an episode, gaps between episodes (design 6.4 item 2 is met by
        # dataset_from_index / dataset_to_index above).
        assert np.all(np.diff(index) == 1)
        start += entry["length"]


def test_timestamps_match_fps(exported: Path) -> None:
    for table in _tables(exported):
        t = _column(table, "timestamp")
        frames = _column(table, "frame_index")
        assert np.max(np.abs(t - frames / 50)) <= 0.5 / 50


def test_videos_decode_with_one_frame_per_row(exported: Path) -> None:
    import av

    info = _info(exported)
    shape = info["features"]["observation.images.egocentric"]["shape"]
    assert shape == [360, 640, 3]
    for entry, table in zip(_jsonl(exported / "meta/episodes.jsonl"), _tables(exported)):
        video = (
            exported / "videos/chunk-000/egocentric" / f"episode_{entry['episode_index']:06d}.mp4"
        )
        with av.open(str(video)) as container:
            frames = list(container.decode(video=0))
        assert len(frames) == table.num_rows
        assert (frames[0].height, frames[0].width) == (360, 640)


def test_every_episode_has_an_instruction_and_flywheel_meta(exported: Path) -> None:
    tasks = {t["task_index"]: t["task"] for t in _jsonl(exported / "meta/tasks.jsonl")}
    for entry in _jsonl(exported / "meta/episodes.jsonl"):
        assert tasks[entry["tasks"][0]].strip()
        meta = json.loads(entry["environment_config"])["flywheel"]
        assert (meta["source_kind"], meta["synthetic_tier"], meta["action_quality"]) == (
            "synthetic", "S1", "planned")
        assert meta["split"] == "train" and meta["data_class"] == "public"


def test_stats_cover_the_release_without_nan(exported: Path) -> None:
    stats = json.loads((exported / "meta/stats_psi0.json").read_text())
    assert len(stats["action"]["mean"]) == 36 and len(stats["states"]["mean"]) == 32
    flat = [x for block in stats.values() for values in block.values() for x in values]
    assert all(math.isfinite(x) for x in flat)
    actions = np.concatenate([_column(t, "action") for t in _tables(exported)])
    # The script averages in float32 (1.9e-3 off the float64 mean over 148k rows
    # of tray_s1_0d84cc87b1e5), so recompute the same way.
    mean32 = actions.astype(np.float32).mean(axis=0)
    assert np.allclose(stats["action"]["mean"], mean32, atol=1e-5)


def test_release_manifest_matches_its_files(exported: Path) -> None:
    if not (exported / "release_manifest.json").exists():
        pytest.skip("an export, not a release")
    from flywheel_simple.tray.release import verify_manifest

    assert verify_manifest(exported)
    meta = json.loads((exported / "meta/flywheel_export.json").read_text())
    assert len({e["seed"] for e in meta["episodes"]}) == _n(exported)


def test_features_match_psi_data(exported: Path) -> None:
    if not PSI_DATA_INFO.exists():
        pytest.skip(f"psi-data two-table package not downloaded ({PSI_DATA_INFO})")
    ours = _info(exported)["features"]
    theirs = json.loads(PSI_DATA_INFO.read_text())["features"]
    assert {k: (v["dtype"], v["shape"]) for k, v in ours.items()} == {
        k: (v["dtype"], v["shape"]) for k, v in theirs.items()
    }

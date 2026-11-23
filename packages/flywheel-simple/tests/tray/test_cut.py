"""Place cut of a tray release (DA-46 task 3, AC 3) on a tiny release; no simulator, no av."""

from __future__ import annotations

import importlib.util
import json
import shutil
import struct
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel_simple.tray.cut import (
    CUT_META,
    DATASET_COLUMNS,
    SCHEMA,
    cut_release,
    cut_start,
    stats_block,
)
from flywheel_simple.tray.release import MANIFEST, verify_manifest, write_manifest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

REPO = Path(__file__).resolve().parents[4]
FPS = 50
TASK = "Pick up the parts tray and place it in the jig."
VIDEO = "videos/chunk-{episode_chunk:03d}/egocentric/episode_{episode_index:06d}.mp4"
DATA = "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet"
# seed, shard, length, phases (entry times in s); the cut starts 1 s before ARRIVE_B/LOWER
EPISODES: list[tuple[int, str, int, list[list[Any]]]] = [
    (501000, "shard-00", 120, [["APPROACH_A", 0.0], ["CARRY", 0.6], ["ARRIVE_B", 1.5],
                               ["LOWER", 1.8], ["RELEASE", 2.0], ["DONE", 2.38]]),
    (501003, "shard-01", 150, [["APPROACH_A", 0.0], ["CARRY", 0.9], ["LOWER", 2.0],
                               ["RELEASE", 2.5], ["DONE", 2.98]]),
    (501005, "shard-00", 100, [["APPROACH_A", 0.0], ["ARRIVE_B", 0.5], ["LOWER", 1.0],
                               ["DONE", 1.98]]),
]
STARTS = [25, 50, 0]


def test_cut_start_from_arrive_b() -> None:
    assert cut_start(EPISODES[0][3], 1.0) == 75 - 50
    assert cut_start(EPISODES[0][3], 0.0) == 75
    assert cut_start(EPISODES[0][3], 0.25) == 75 - 12  # round(12.5) == 12


def test_cut_start_falls_back_to_lower() -> None:
    assert cut_start(EPISODES[1][3], 1.0) == 100 - 50


def test_cut_start_lead_is_clamped_at_zero() -> None:
    assert cut_start(EPISODES[2][3], 1.0) == 0


def test_cut_start_without_the_phases_fails() -> None:
    with pytest.raises(ValueError, match="none of"):
        cut_start([["APPROACH_A", 0.0], ["CARRY", 1.0], ["RELEASE", 2.0]], 1.0)
    with pytest.raises(ValueError, match="lead_s"):
        cut_start(EPISODES[0][3], -0.5)


# --- a tiny parent release ---------------------------------------------------------------


def _box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def fake_mp4(frames: int) -> bytes:
    """Just the boxes the DA-03 reader walks for a frame count (moov/trak/mdia hdlr, stsz)."""
    hdlr = _box(b"hdlr", bytes(8) + b"vide" + bytes(13))
    stsz = _box(b"stsz", bytes(8) + struct.pack(">I", frames))
    trak = _box(b"trak", _box(b"mdia", hdlr + _box(b"minf", _box(b"stbl", stsz))))
    return _box(b"ftyp", b"isom" + bytes(4)) + _box(b"moov", trak)


def _table(rng: np.random.Generator, n: int, episode: int, first: int) -> Any:
    def floats(width: int) -> list[list[float]]:
        values: list[list[float]] = rng.normal(size=(n, width)).astype(np.float32).tolist()
        return values

    frame_index = np.arange(n, dtype=np.int64)
    done = np.zeros(n, dtype=bool)
    done[-1] = True
    return pa.table({
        "states": floats(32),
        "action": floats(36),
        "observation.hand_joints": floats(14),
        "timestamp": frame_index * 1.0 / FPS,
        "frame_index": frame_index,
        "episode_index": np.full(n, episode, dtype=np.int64),
        "index": np.arange(first, first + n, dtype=np.int64),
        "task_index": np.zeros(n, dtype=np.int64),
        "next.done": done,
    })


def _features() -> dict[str, Any]:
    features: dict[str, Any] = {
        "observation.images.egocentric": {"dtype": "video", "shape": [48, 64, 3],
                                          "names": ["height", "width", "channel"],
                                          "video_info": {}},
        "observation.hand_joints": {"dtype": "float32", "shape": [14], "names": ["hand_joints"]},
        "states": {"dtype": "float32", "shape": [32]},
        "action": {"dtype": "float32", "shape": [36]},
    }
    for name, dtype in (("timestamp", "float32"), ("frame_index", "int64"),
                        ("episode_index", "int64"), ("index", "int64"),
                        ("next.done", "bool"), ("task_index", "int64")):
        features[name] = {"dtype": dtype, "shape": [1]}
    return features


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))


def make_parent(root: Path, chunks_size: int = 2) -> Path:
    """A tray_s1 release of EPISODES in the export's layout, with a real manifest."""
    rng = np.random.default_rng(0)
    meta = root / "meta"
    meta.mkdir(parents=True)
    info = {
        "codebase_version": "v2.1", "robot_type": "g1",
        "total_episodes": len(EPISODES), "total_frames": sum(e[2] for e in EPISODES),
        "total_tasks": 1, "total_videos": len(EPISODES), "total_chunks": 2,
        "chunks_size": chunks_size, "fps": FPS, "data_path": DATA, "video_path": VIDEO,
        "features": _features(),
    }
    (meta / "info.json").write_text(json.dumps(info, indent=4))
    rows, stats_rows, first = [], [], 0
    for i, (seed, _, n, _) in enumerate(EPISODES):
        table = _table(rng, n, i, first)
        chunk = i // chunks_size
        path = root / DATA.format(episode_chunk=chunk, episode_index=i)
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, path)
        video = root / VIDEO.format(episode_chunk=chunk, episode_index=i)
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(fake_mp4(n))
        config = json.dumps({"uid": "tray", "flywheel": {"seed": seed}})
        rows.append({"episode_index": i, "tasks": [0], "length": n, "dataset_from_index": first,
                     "dataset_to_index": first + n - 1, "robot_type": "g1",
                     "instruction": {"task_index": 0, "task": TASK},
                     "environment_config": config})
        stats_rows.append({"episode_index": i, "stats": {
            "action": {**stats_block(np.zeros(3)), "count": [n]},
            "timestamp": {**stats_block(np.zeros(3)), "count": [n]}}})
        first += n
    _jsonl(meta / "episodes.jsonl", rows)
    _jsonl(meta / "episodes_stats.jsonl", stats_rows)
    _jsonl(meta / "tasks.jsonl", [{"task_index": 0, "task": TASK}])
    stats = {name: stats_block(np.zeros(3)) for name in DATASET_COLUMNS}
    for name in ("stats.json", "stats_psi0.json"):
        (meta / name).write_text(json.dumps(stats, indent=4))
    (meta / "relative_stats.json").write_text("{}")
    (meta / "lang_map.json").write_text("{}")
    (meta / "modality.json").write_text('{"state": {}}\n')
    (meta / "action_layout.json").write_text('{"dimensions": []}\n')
    (meta / "batch_summary.json").write_text('{"attempts": 3}\n')
    export = {
        "action_dim": 36, "source_batch": "/somewhere/gen-l2", "code_sha": "abc",
        "episodes": [{"episode_index": i, "shard": shard, "raw_episode": i, "seed": seed}
                     for i, (seed, shard, _, _) in enumerate(EPISODES)],
    }
    (meta / "flywheel_export.json").write_text(json.dumps(export, indent=2) + "\n")
    write_manifest(root)
    return root


def make_batch(root: Path, **override: Any) -> Path:
    for seed, shard, n, phases in EPISODES:
        log = root / shard / "gen_log.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        row = {"seed": seed, "steps": n, "recorded": True, "qa": "pass",
               "phases": phases, "carry_offset": [0.01, -0.02]}
        row.update(override.get(str(seed), {}))
        failed = {"seed": seed + 1, "steps": 10, "recorded": False, "qa": "not_recorded"}
        with log.open("a") as f:
            f.write(json.dumps(failed) + "\n" + json.dumps(row) + "\n")
    return root


class StubTrim:
    """Records each call; writes a file the DA-03 reader counts n frames in."""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, Path, int, int, int]] = []

    def __call__(self, src: Path, dst: Path, start: int, n: int, fps: int) -> None:
        self.calls.append((src, dst, start, n, fps))
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(fake_mp4(n))


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Any]:
    parent = make_parent(tmp_path / "releases" / "tray_s1_0123456789ab")
    batch = make_batch(tmp_path / "gen-l2")
    trim = StubTrim()
    out = cut_release(parent, batch, tmp_path / "releases", trim=trim)
    return {"parent": parent, "batch": batch, "out": out, "trim": trim, "tmp": tmp_path}


def _parquet(root: Path, index: int, chunks_size: int = 2) -> Any:
    return pq.read_table(root / DATA.format(episode_chunk=index // chunks_size,
                                            episode_index=index))


def _meta(root: Path, name: str) -> Any:
    text = (root / "meta" / name).read_text()
    if name.endswith(".jsonl"):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


# --- the cut -----------------------------------------------------------------------------


def test_parquet_rows_are_renumbered(world: dict[str, Any]) -> None:
    first = 0
    for i, ((_, _, n, _), start) in enumerate(zip(EPISODES, STARTS)):
        table = _parquet(world["out"], i)
        k = n - start
        assert table.num_rows == k
        assert table.column("frame_index").to_pylist() == list(range(k))
        assert table.column("timestamp").to_pylist() == [f * 1.0 / FPS for f in range(k)]
        assert table.column("episode_index").to_pylist() == [i] * k
        assert table.column("index").to_pylist() == list(range(first, first + k))
        assert table.column("next.done").to_pylist() == [False] * (k - 1) + [True]
        first += k


def test_parquet_keeps_schema_and_values(world: dict[str, Any]) -> None:
    for i, start in enumerate(STARTS):
        parent, cut = _parquet(world["parent"], i), _parquet(world["out"], i)
        assert cut.schema.equals(parent.schema, check_metadata=True)
        assert cut.column_names == parent.column_names
        for name in ("states", "action", "observation.hand_joints", "task_index"):
            assert cut.column(name).to_pylist() == parent.column(name).slice(start).to_pylist()


def test_videos_are_trimmed_from_the_cut_start(world: dict[str, Any]) -> None:
    parent, out = world["parent"], world["out"]
    calls = world["trim"].calls
    assert [(c[2], c[3], c[4]) for c in calls] == [
        (s, e[2] - s, FPS) for e, s in zip(EPISODES, STARTS)
    ]
    for i, (src, dst, _, _, _) in enumerate(calls):
        assert src == parent / VIDEO.format(episode_chunk=i // 2, episode_index=i)
        rel = VIDEO.format(episode_chunk=i // 2, episode_index=i)
        assert dst == out.parent / f".staging-cut-{parent.name}" / rel
        assert (out / rel).read_bytes() == fake_mp4(calls[i][3])


def test_meta_counts_and_episode_rows(world: dict[str, Any]) -> None:
    out, parent = world["out"], world["parent"]
    lengths = [e[2] - s for e, s in zip(EPISODES, STARTS)]
    info, parent_info = _meta(out, "info.json"), _meta(parent, "info.json")
    assert info == {**parent_info, "total_episodes": 3, "total_frames": sum(lengths),
                    "total_videos": 3, "total_chunks": 2}
    assert list(info) == list(parent_info)
    rows, parent_rows = _meta(out, "episodes.jsonl"), _meta(parent, "episodes.jsonl")
    first = 0
    for i, (row, n) in enumerate(zip(rows, lengths)):
        assert row == {**parent_rows[i], "episode_index": i, "length": n,
                       "dataset_from_index": first, "dataset_to_index": first + n - 1}
        first += n
    for name in ("tasks.jsonl", "modality.json", "lang_map.json", "action_layout.json"):
        assert (out / "meta" / name).read_bytes() == (parent / "meta" / name).read_bytes()
    assert not (out / "meta" / "batch_summary.json").exists()


def _expected_stats(out: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cols: dict[str, list[np.ndarray]] = {name: [] for name in DATASET_COLUMNS}
    rows = []
    for i in range(len(EPISODES)):
        t = _parquet(out, i)
        n = t.num_rows
        action = np.asarray(t.column("action").to_pylist(), dtype=np.float32)
        ts = np.asarray(t.column("timestamp").to_pylist(), dtype=np.float64)
        rows.append({"episode_index": i, "stats": {
            "action": {**stats_block(action), "count": [n]},
            "timestamp": {**stats_block(ts), "count": [n]}}})
        cols["states"].append(np.asarray(t.column("states").to_pylist(), dtype=np.float32))
        cols["action"].append(action)
        cols["timestamp"].append(ts)
        for name in ("frame_index", "episode_index", "index", "task_index"):
            cols[name].append(np.asarray(t.column(name).to_pylist(), dtype=np.int64))
        cols["next.done"].append(np.asarray(t.column("next.done").to_pylist(), np.float32))
    return rows, {k: stats_block(np.concatenate(v)) for k, v in cols.items()}


def test_stats_are_recomputed_on_the_cut(world: dict[str, Any]) -> None:
    out = world["out"]
    rows, dataset = _expected_stats(out)
    assert _meta(out, "episodes_stats.jsonl") == rows
    assert [r["stats"]["action"]["count"] for r in rows] == [[e[2] - s] for e, s in
                                                             zip(EPISODES, STARTS)]
    stats = _meta(out, "stats.json")
    assert stats == dataset and list(stats) == list(DATASET_COLUMNS)
    meta = out / "meta"
    assert (meta / "stats.json").read_bytes() == (meta / "stats_psi0.json").read_bytes()
    assert (meta / "relative_stats.json").read_text() == "{}"
    assert stats["index"]["max"] == [sum(e[2] - s for e, s in zip(EPISODES, STARTS)) - 1]


def test_cut_marker_records_parent_and_ranges(world: dict[str, Any]) -> None:
    parent, out = world["parent"], world["out"]
    marker = _meta(out, CUT_META)
    parent_hash = json.loads((parent / MANIFEST).read_text())["release_hash"]
    assert marker["schema"] == SCHEMA
    assert marker["parent"] == {"release_id": parent.name, "release_hash": parent_hash}
    assert marker["source_batch"] == "gen-l2"
    assert marker["from_phases"] == ["ARRIVE_B", "LOWER"]
    assert (marker["lead_s"], marker["fps"], marker["selection"]) == (1.0, FPS, None)
    lengths = [e[2] - s for e, s in zip(EPISODES, STARTS)]
    assert marker["frames"] == {"parent": sum(e[2] for e in EPISODES), "cut": sum(lengths)}
    phase_frames = [(75, "ARRIVE_B"), (100, "LOWER"), (25, "ARRIVE_B")]
    for i, ep in enumerate(marker["episodes"]):
        seed, _, n, phases = EPISODES[i]
        assert ep == {
            "episode_index": i, "seed": seed, "parent_episode_index": i, "parent_length": n,
            "source_from_frame": STARTS[i], "source_to_frame": n, "length": lengths[i],
            "phase_frame": phase_frames[i][0], "from_phase": phase_frames[i][1],
            "carry_offset": [0.01, -0.02], "phases": phases,
        }


def test_export_meta_lists_the_kept_episodes(world: dict[str, Any]) -> None:
    export, parent = _meta(world["out"], "flywheel_export.json"), world["parent"]
    parent_export = _meta(parent, "flywheel_export.json")
    assert export == {**parent_export, "derived_from": parent.name}


def test_release_is_hashed_and_named(world: dict[str, Any]) -> None:
    out = world["out"]
    release_hash = json.loads((out / MANIFEST).read_text())["release_hash"]
    assert out.name == f"tray_s1place_{release_hash[:12]}"
    assert verify_manifest(out)
    assert verify_manifest(world["parent"])
    assert sorted(p.name for p in (world["tmp"] / "releases").iterdir()) == sorted(
        [world["parent"].name, out.name]
    )


def test_seed_selection_keeps_parent_order(tmp_path: Path) -> None:
    parent = make_parent(tmp_path / "releases" / "tray_s1_0123456789ab")
    batch = make_batch(tmp_path / "gen-l2")
    selection = {"file": "demo_sets.json", "sha256": "0" * 64, "set": "S", "n": 2}
    out = cut_release(parent, batch, tmp_path / "releases", lead_s=0.5,
                      seeds=[501005, 501000], selection=selection, trim=StubTrim())
    marker = _meta(out, CUT_META)
    assert marker["selection"] == selection
    assert [(e["seed"], e["parent_episode_index"], e["source_from_frame"])
            for e in marker["episodes"]] == [(501000, 0, 50), (501005, 2, 0)]
    export = _meta(out, "flywheel_export.json")["episodes"]
    assert export == [
        {"episode_index": 0, "shard": "shard-00", "raw_episode": 0, "seed": 501000},
        {"episode_index": 1, "shard": "shard-00", "raw_episode": 2, "seed": 501005},
    ]
    assert _meta(out, "info.json")["total_chunks"] == 1
    t = _parquet(out, 1)
    assert t.column("index")[0].as_py() == 120 - 50
    assert t.column("action").to_pylist() == _parquet(parent, 2).column("action").to_pylist()


# --- refusals ----------------------------------------------------------------------------


def _refused(tmp_path: Path, match: str, **kwargs: Any) -> None:
    releases = tmp_path / "releases"
    with pytest.raises((ValueError, FileExistsError), match=match):
        cut_release(kwargs.pop("parent"), kwargs.pop("batch"), releases, trim=StubTrim(),
                    **kwargs)
    assert not any(p.name.startswith(".staging") for p in releases.iterdir())
    assert not any(p.name.startswith("tray_s1place_") for p in releases.iterdir())


def test_tampered_parent_is_refused(tmp_path: Path) -> None:
    parent = make_parent(tmp_path / "releases" / "tray_s1_0123456789ab")
    (parent / "meta" / "lang_map.json").write_text('{"x": 1}')
    _refused(tmp_path, "do not match", parent=parent, batch=make_batch(tmp_path / "b"))


def test_batch_without_phases_is_refused(tmp_path: Path) -> None:
    parent = make_parent(tmp_path / "releases" / "tray_s1_0123456789ab")
    batch = make_batch(tmp_path / "b", **{"501003": {"phases": None}})
    _refused(tmp_path, "predates DA-46", parent=parent, batch=batch)


def test_length_other_than_steps_is_refused(tmp_path: Path) -> None:
    parent = make_parent(tmp_path / "releases" / "tray_s1_0123456789ab")
    batch = make_batch(tmp_path / "b", **{"501000": {"steps": 121}})
    _refused(tmp_path, "121 steps", parent=parent, batch=batch)


def test_seed_without_a_row_is_refused(tmp_path: Path) -> None:
    parent = make_parent(tmp_path / "releases" / "tray_s1_0123456789ab")
    batch = make_batch(tmp_path / "b", **{"501005": {"recorded": False}})
    _refused(tmp_path, "no recorded", parent=parent, batch=batch)


def test_unknown_seed_is_refused(tmp_path: Path) -> None:
    parent = make_parent(tmp_path / "releases" / "tray_s1_0123456789ab")
    _refused(tmp_path, "not in", parent=parent, batch=make_batch(tmp_path / "b"),
             seeds=[501000, 999])


def test_cut_past_the_end_is_refused(tmp_path: Path) -> None:
    parent = make_parent(tmp_path / "releases" / "tray_s1_0123456789ab")
    late = [["APPROACH_A", 0.0], ["ARRIVE_B", 2.4], ["DONE", 2.5]]
    batch = make_batch(tmp_path / "b", **{"501000": {"phases": late}})
    _refused(tmp_path, "starts at frame 120 of 120", parent=parent, batch=batch, lead_s=0.0)


def test_failing_trim_removes_the_staging_dir(tmp_path: Path) -> None:
    parent = make_parent(tmp_path / "releases" / "tray_s1_0123456789ab")

    def broken(src: Path, dst: Path, start: int, n: int, fps: int) -> None:
        raise ValueError("encoder broke")

    with pytest.raises(ValueError, match="encoder broke"):
        cut_release(parent, make_batch(tmp_path / "b"), tmp_path / "releases", trim=broken)
    assert [p.name for p in (tmp_path / "releases").iterdir()] == [parent.name]


def test_existing_staging_dir_is_refused(tmp_path: Path) -> None:
    parent = make_parent(tmp_path / "releases" / "tray_s1_0123456789ab")
    staging = tmp_path / "releases" / f".staging-cut-{parent.name}"
    staging.mkdir()
    with pytest.raises(FileExistsError):
        cut_release(parent, make_batch(tmp_path / "b"), tmp_path / "releases", trim=StubTrim())
    assert staging.is_dir()


# --- the train path reads it -------------------------------------------------------------


def test_demo_sets_reads_the_derived_release(world: dict[str, Any]) -> None:
    demo_sets = pytest.importorskip("flywheel_psi0.tray.demo_sets")
    release_hash, episodes = demo_sets.read_release(world["out"])
    assert release_hash == json.loads((world["out"] / MANIFEST).read_text())["release_hash"]
    assert [(e.episode_index, e.seed) for e in episodes] == [
        (i, e[0]) for i, e in enumerate(EPISODES)
    ]


def test_lerobot_reader_and_stats_agree(world: dict[str, Any]) -> None:
    lerobot = pytest.importorskip("flywheel.data.ingest.lerobot")
    stats = pytest.importorskip("flywheel.data.inject.stats")
    out = world["out"]
    frames = list(lerobot.iter_episodes(out))
    lengths = [e[2] - s for e, s in zip(EPISODES, STARTS)]
    assert [len(f.timestamp) for f in frames] == lengths
    assert [f.video_frames for f in frames] == [
        {"observation.images.egocentric": n} for n in lengths
    ]
    assert lerobot.check_index(out) == []
    rows, dataset = stats.compute_stats(out)
    assert _meta(out, "episodes_stats.jsonl") == rows
    assert _meta(out, "stats.json") == dataset


def test_demo_subset_cuts_the_derived_release(world: dict[str, Any]) -> None:
    demo_sets = pytest.importorskip("flywheel_psi0.tray.demo_sets")
    pytest.importorskip("flywheel.data.ingest.lerobot")
    spec = importlib.util.spec_from_file_location("demo_subset", REPO / "scripts/he/demo_subset.py")
    assert spec is not None and spec.loader is not None
    demo_subset = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo_subset)
    out = world["out"]
    release_hash = json.loads((out / MANIFEST).read_text())["release_hash"]
    seeds = [EPISODES[0][0], EPISODES[2][0]]
    sets = demo_sets.DemoSets(
        release_id=out.name, release_hash=release_hash, salt="test",
        sets={"S": demo_sets.DemoSet(n=2, set_hash=demo_sets.set_hash(release_hash, seeds),
                                     seeds=seeds, episode_indices=[0, 2])},
    )
    dst = world["tmp"] / "sets" / "S"
    marker = demo_subset.build_subset(out, dst, sets, "S")
    assert [e["source_episode_index"] for e in marker["episodes"]] == [0, 2]
    t = pq.read_table(dst / DATA.format(episode_chunk=0, episode_index=1))
    assert t.column("action").to_pylist() == _parquet(out, 2).column("action").to_pylist()
    shutil.rmtree(dst)

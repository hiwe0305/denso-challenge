"""Joining C's cut and the targeted cut into C+'s dataset, on CPU (DA-34 task 5)."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
import pytest
from flywheel.data.ingest.lerobot import EpisodeFrames, iter_episodes, write_episode
from flywheel.data.inject.stats import write_stats
from flywheel_psi0.tray.cplus_cut import MARKER, join_cuts, offsets

TASK = "carry the tray"


def _box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def fake_mp4(path: Path, frames: int, tag: bytes) -> None:
    """Only what the DA-03 reader walks (the frame count in stsz), plus a tag in mdat."""
    hdlr = _box(b"hdlr", bytes(8) + b"vide" + bytes(12) + b"\0")
    stsz = _box(b"stsz", bytes(4) + struct.pack(">II", 0, frames) + bytes(4 * frames))
    trak = _box(b"trak", _box(b"mdia", hdlr + _box(b"minf", _box(b"stbl", stsz))))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_box(b"ftyp", b"isom" + bytes(4)) + _box(b"moov", trak) + _box(b"mdat", tag))


def fake_cut(root: Path, values: list[float], lengths: list[int], name: str) -> Path:
    """A demo-set cut: LeRobot v2.1, episode i has action and states all values[i]."""
    meta = root / "meta"
    meta.mkdir(parents=True)
    scalar = {"dtype": "int64", "shape": [1]}
    info = {
        "codebase_version": "v2.1",
        "fps": 50,
        "chunks_size": 1000,
        "robot_type": "g1",
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": (
            "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4"
        ),
        "splits": {"train": f"0:{len(values)}"},
        "features": {
            "observation.images.ego_view": {"dtype": "video", "shape": [180, 320, 3]},
            "states": {"dtype": "float32", "shape": [32]},
            "action": {"dtype": "float32", "shape": [36]},
            "timestamp": {"dtype": "float32", "shape": [1]},
            **{k: scalar for k in ("frame_index", "episode_index", "index", "task_index")},
            "next.done": {"dtype": "bool", "shape": [1]},
        },
    }
    (meta / "info.json").write_text(json.dumps(info))
    (meta / "tasks.jsonl").write_text(json.dumps({"task_index": 0, "task": TASK}) + "\n")
    for i, (v, n) in enumerate(zip(values, lengths)):
        video = root / f"videos/chunk-000/observation.images.ego_view/episode_{i:06d}.mp4"
        fake_mp4(video, n, f"{name}-{i}".encode())
        write_episode(
            root,
            EpisodeFrames(
                episode_index=i,
                task=TASK,
                timestamp=np.arange(n) / 50.0,
                frame_index=np.arange(n, dtype=np.int64),
                states=np.full((n, 32), v, dtype=np.float32),
                action=np.full((n, 36), v, dtype=np.float32),
                video_frames={},
            ),
        )
    write_stats(root)
    marker = {
        "demo_set": name,
        "set_hash": name.lower() * 8,
        "release_id": f"rel-{name}",
        "release_hash": name.lower() * 64,
        "n": len(values),
        "episodes": [
            {"episode_index": i, "source_episode_index": 10 + i} for i in range(len(values))
        ],
    }
    (meta / MARKER).write_text(json.dumps(marker))
    return root


def test_offsets_follow_the_parts() -> None:
    assert offsets([160, 160]) == [0, 160]
    assert offsets([2, 3, 1]) == [0, 2, 5]


def test_a_join_keeps_c_first_then_the_targeted_part_with_its_own_stats(tmp_path: Path) -> None:
    c = fake_cut(tmp_path / "c", [1.0, 2.0], [4, 6], "C")
    t = fake_cut(tmp_path / "t", [10.0, 20.0, 30.0], [5, 5, 5], "T")
    out = tmp_path / "cplus"
    marker = join_cuts([c, t], out, "C_PLUS")

    episodes = sorted(iter_episodes(out), key=lambda e: e.episode_index)
    assert [e.episode_index for e in episodes] == [0, 1, 2, 3, 4]
    assert [float(e.action[0, 0]) for e in episodes] == [1.0, 2.0, 10.0, 20.0, 30.0]
    info = json.loads((out / "meta/info.json").read_text())
    assert (info["total_episodes"], info["total_frames"], info["splits"]) == (
        5,
        25,
        {"train": "0:5"},
    )
    stats = json.loads((out / "meta/stats_psi0.json").read_text())
    mean = (4 * 1 + 6 * 2 + 5 * (10 + 20 + 30)) / 25
    assert stats["action"]["mean"][0] == pytest.approx(mean)  # over both parts
    assert stats["action"]["max"][0] == 30.0
    # C's videos sit at C's indices, the targeted ones after them, copied byte for byte
    video = out / "videos/chunk-000/observation.images.ego_view"
    assert (video / "episode_000001.mp4").read_bytes() == (
        c / "videos/chunk-000/observation.images.ego_view/episode_000001.mp4"
    ).read_bytes()
    assert (video / "episode_000002.mp4").read_bytes().endswith(b"T-0")
    rows = [json.loads(x) for x in (out / "meta/episodes.jsonl").read_text().splitlines()]
    assert [r["episode_index"] for r in rows] == [0, 1, 2, 3, 4]

    assert marker == json.loads((out / "meta" / MARKER).read_text())
    assert (marker["demo_set"], marker["n"]) == ("C_PLUS", 5)
    c_part, t_part = marker["parts"]
    assert (c_part["demo_set"], c_part["first_episode_index"], c_part["n"]) == ("C", 0, 2)
    assert (t_part["demo_set"], t_part["first_episode_index"]) == ("T", 2)
    assert t_part["episodes"][0] == {"episode_index": 2, "source_episode_index": 10}
    assert t_part["set_hash"] == "t" * 8 and t_part["release_hash"] == "t" * 64


def test_a_join_refuses_parts_that_differ_or_an_existing_output(tmp_path: Path) -> None:
    c = fake_cut(tmp_path / "c", [1.0], [3], "C")
    t = fake_cut(tmp_path / "t", [2.0], [3], "T")
    info = json.loads((t / "meta/info.json").read_text())
    (t / "meta/info.json").write_text(json.dumps({**info, "fps": 30}))
    with pytest.raises(ValueError, match="differs .* in \\['fps'\\]"):
        join_cuts([c, t], tmp_path / "a", "C_PLUS")
    (tmp_path / "b").mkdir()
    with pytest.raises(FileExistsError):
        join_cuts([c, c], tmp_path / "b", "C_PLUS")
    (c / "meta" / MARKER).unlink()
    with pytest.raises(ValueError, match="not a demo-set cut"):
        join_cuts([c, t], tmp_path / "d", "C_PLUS")

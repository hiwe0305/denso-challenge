"""A small LeRobot v2.1 dataset in Psi0's layout, written through the DA-03 writer."""

import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from flywheel.data.ingest.lerobot import EpisodeFrames, write_episode

FPS = 50
CAMERA = "observation.images.egocentric"
TASK = " pick up the cracker box from table1,locomotion to table2,and place  on table2."


def info() -> dict[str, object]:
    scalar = {"shape": [1]}
    return {
        "codebase_version": "v2.1",
        "robot_type": "g1",
        "total_episodes": 0,
        "total_frames": 0,
        "total_tasks": 0,
        "total_videos": 0,
        "total_chunks": 1,
        "chunks_size": 1000,
        "fps": FPS,
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/egocentric/episode_{episode_index:06d}.mp4",
        "features": {
            CAMERA: {"dtype": "video", "shape": [360, 640, 3], "video_info": {}},
            "states": {"dtype": "float32", "shape": [-1]},
            "action": {"dtype": "float32", "shape": [-1]},
            "timestamp": {"dtype": "float32", **scalar},
            "frame_index": {"dtype": "int64", **scalar},
            "episode_index": {"dtype": "int64", **scalar},
            "index": {"dtype": "int64", **scalar},
            "next.done": {"dtype": "bool", **scalar},
            "task_index": {"dtype": "int64", **scalar},
        },
    }


def _box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def fake_mp4(path: Path, frames: int, tag: int) -> None:
    """An mp4 the reader can count frames in; `tag` makes each file's bytes distinct."""
    hdlr = _box(b"hdlr", bytes(8) + b"vide" + bytes(12) + b"\0")
    stsz = _box(b"stsz", bytes(4) + struct.pack(">II", 0, frames) + bytes(4 * frames))
    trak = _box(b"trak", _box(b"mdia", hdlr + _box(b"minf", _box(b"stbl", stsz))))
    path.parent.mkdir(parents=True, exist_ok=True)
    mdat = _box(b"mdat", struct.pack(">I", tag))
    path.write_bytes(_box(b"ftyp", b"isom" + bytes(4)) + _box(b"moov", trak) + mdat)


def video_path(root: Path, index: int) -> Path:
    return root / "videos" / "chunk-000" / "egocentric" / f"episode_{index:06d}.mp4"


def make_dataset(root: Path, count: int = 40, length: int = 20) -> None:
    """`count` episodes of 36-D actions: hands at zero, the other dims moving."""
    (root / "meta").mkdir(parents=True)
    (root / "meta" / "info.json").write_text(json.dumps(info(), indent=4))
    for index in range(count):
        rng = np.random.default_rng(index)
        action = rng.uniform(-0.5, 0.5, (length, 36)).astype(np.float32)
        action[:, :14] = 0.0
        write_episode(
            root,
            EpisodeFrames(
                episode_index=index,
                task=TASK,
                timestamp=(np.arange(length) / FPS).astype(np.float32).astype(np.float64),
                frame_index=np.arange(length, dtype=np.int64),
                states=rng.standard_normal((length, 32)).astype(np.float32),
                action=action,
                video_frames={CAMERA: length},
            ),
        )
        fake_mp4(video_path(root, index), length, index)
    # Every psi-data row carries the recorder's environment_config (no flywheel block).
    meta = root / "meta" / "episodes.jsonl"
    rows = [json.loads(line) for line in meta.read_text().splitlines()]
    config = json.dumps({"uid": "g1_wholebody_locomotion_pick_between_tables_teleop"})
    meta.write_text("".join(json.dumps({**r, "environment_config": config}) + "\n" for r in rows))


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }

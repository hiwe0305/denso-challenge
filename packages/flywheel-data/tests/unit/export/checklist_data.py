"""A LeRobot v2.1 dataset in the layout of DA-33's tray export, written in the test (DA-02).

The shape of `tray_s1_0d84cc87b1e5` (rtx3060, 3/11/2026) minus the `observation.*`
joint columns: info.json as SIMPLE's postprocess writes it (action and states shape
[-1], `video_info` empty), `meta/action_layout.json` from the G1 layout, the four stats
files recomputed from the data as SIMPLE does, and an mp4 per episode whose video track
is an `avc1` 640 x 360 sample entry with one stsz sample per row.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.contracts.artifacts import ActionLayout
from flywheel.data.config import load_layout
from flywheel.data.ingest.lerobot import EpisodeFrames, write_episode
from flywheel.data.inject.stats import write_stats

REPO = Path(__file__).resolve().parents[5]
G1_YAML = REPO / "configs" / "embodiments" / "g1.yaml"
FPS = 50
CAMERA = "observation.images.egocentric"
TASK = (
    "Pick up the parts tray from table A with both hands, carry it to table B and place it"
    " in the target zone."
)
HEIGHT, WIDTH = 360, 640


def g1_layout() -> ActionLayout:
    return load_layout(G1_YAML)


def tray_info() -> dict[str, object]:
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
            CAMERA: {"dtype": "video", "shape": [HEIGHT, WIDTH, 3],
                     "names": ["height", "width", "channel"], "video_info": {}},
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


def frames_of(index: int, length: int) -> EpisodeFrames:
    """An episode with varied action and states, dim 31 at 0.74 in every frame of both as
    in G1 data (base height command; the previous one in states)."""
    rng = np.random.default_rng(index)
    action = rng.uniform(-0.1, 0.1, (length, 36)).astype(np.float32)
    action[:, 31] = np.float32(0.74)
    states = rng.standard_normal((length, 32)).astype(np.float32)
    states[:, 31] = np.float32(0.74)
    return EpisodeFrames(
        episode_index=index,
        task=TASK,
        timestamp=(np.arange(length) / FPS).astype(np.float32).astype(np.float64),
        frame_index=np.arange(length, dtype=np.int64),
        states=states,
        action=action,
        video_frames={CAMERA: length},
    )


def box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def video_track(samples: int, codec: bytes = b"avc1", width: int = WIDTH,
                height: int = HEIGHT) -> bytes:
    hdlr = box(b"hdlr", bytes(8) + b"vide" + bytes(12) + b"\0")
    # Visual sample entry: 6 reserved, data_reference_index, 16 bytes pre_defined and
    # reserved, width, height, then resolutions, frame count, compressor name, depth.
    entry = box(codec, bytes(6) + struct.pack(">H", 1) + bytes(16)
                + struct.pack(">HH", width, height) + bytes(50))
    stsd = box(b"stsd", bytes(4) + struct.pack(">I", 1) + entry)
    stsz = box(b"stsz", bytes(4) + struct.pack(">II", 0, samples) + bytes(4 * samples))
    return box(b"trak", box(b"mdia", hdlr + box(b"minf", box(b"stbl", stsd + stsz))))


def write_mp4(path: Path, frames: int, codec: bytes = b"avc1", width: int = WIDTH,
              height: int = HEIGHT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    moov = box(b"moov", video_track(frames, codec, width, height))
    path.write_bytes(box(b"ftyp", b"isom" + bytes(4)) + moov + box(b"mdat"))


def video_path(root: Path, index: int) -> Path:
    return root / "videos" / "chunk-000" / "egocentric" / f"episode_{index:06d}.mp4"


def make_tray_dataset(root: Path, lengths: tuple[int, ...] = (6, 9, 4)) -> Path:
    """A correct dataset: every checklist point passes on it."""
    meta = root / "meta"
    meta.mkdir(parents=True)
    (meta / "info.json").write_text(json.dumps(tray_info(), indent=4))
    for index, length in enumerate(lengths):
        write_episode(root, frames_of(index, length))
        write_mp4(video_path(root, index), length)
    write_stats(root)
    layout = g1_layout().model_dump(mode="json")
    (meta / "action_layout.json").write_text(json.dumps(layout, indent=2) + "\n")
    return root


def edit_json(path: Path, change: Callable[[dict[str, Any]], None]) -> None:
    """Apply `change(data)` to the JSON file at path, in place."""
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


def edit_jsonl(path: Path, change: Callable[[dict[str, Any]], None]) -> None:
    """Apply `change(row)` to every row of the JSON lines file at path, in place."""
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for row in rows:
        change(row)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))

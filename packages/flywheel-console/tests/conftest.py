"""Fixture builders: a tiny LeRobot v2.1 dir and a pipeline work dir."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from flywheel.console.paths import ConsolePaths

FRAMES = 10
W, H = 64, 48


def write_mp4(path: Path, frames: int = FRAMES, w: int = W, h: int = H) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter.fourcc(*"mp4v"), 10.0, (w, h))
    for k in range(frames):
        vw.write(np.full((h, w, 3), 20 * k, dtype=np.uint8))
    vw.release()
    return path


def make_lerobot(root: Path, n: int = 3, base: int = 0) -> Path:
    """Episodes ``base..base+n-1``, one parquet and one 10-frame mp4 each."""
    meta = root / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    info = {
        "codebase_version": "v2.1", "robot_type": "g1", "total_episodes": n, "fps": 50,
        "chunks_size": 1000, "features": {"action": {}},
        "video_path": "videos/chunk-{episode_chunk:03d}/egocentric/episode_{episode_index:06d}.mp4",
    }  # fmt: skip
    (meta / "info.json").write_text(json.dumps(info))
    (meta / "action_layout.json").write_text(
        json.dumps({"dimensions": [{"group": "left_hand"}, {"group": "right_hand"}]})
    )
    eps, stats = [], []
    for k in range(n):
        i = base + k
        cfg = {
            "tray": {
                "sample": {
                    "level": k % 2, "seed": 100 + i, "table_gap": 1.8, "light_scale": 1.0,
                    "tray_pose": {"x": 1.0, "y": 0.0}, "target_pose": {"x": -1.0, "y": 0.0},
                },
                "report": {"success": True, "failure": None},
            },
            "flywheel": {"seed": 100 + i, "level": k % 2, "purpose": "coverage"},
        }  # fmt: skip
        eps.append(
            {
                "episode_index": i, "length": FRAMES, "dataset_from_index": i * FRAMES,
                "dataset_to_index": (i + 1) * FRAMES - 1,
                "instruction": {"task": "Carry the tray."},
                "environment_config": json.dumps(cfg),
            }
        )  # fmt: skip
        stats.append(
            {"episode_index": i, "stats": {"action": {"min": [0.0, 0.0], "max": [1.0, 2.0]}}}
        )
        d = root / "data" / "chunk-000"
        d.mkdir(parents=True, exist_ok=True)
        pq.write_table(
            pa.table({"frame_index": list(range(FRAMES))}), d / f"episode_{i:06d}.parquet"
        )
        write_mp4(root / "videos" / "chunk-000" / "egocentric" / f"episode_{i:06d}.mp4")
    (meta / "episodes.jsonl").write_text("\n".join(json.dumps(e) for e in eps) + "\n")
    (meta / "episodes_stats.jsonl").write_text("\n".join(json.dumps(s) for s in stats) + "\n")
    return root


def make_work(work: Path, deid: Path, raw: Path) -> Path:
    """Pipeline work dir: ep_deid points at a .deid.mp4, ep_raw at a raw .mp4."""
    qa = []
    for ep, video in (("ep_deid", deid), ("ep_raw", raw)):
        d = work / "egocentric" / ep
        d.mkdir(parents=True)
        (d / "bundle.json").write_text(json.dumps({"episode_id": ep, "mp4": str(video)}))
        qa.append(
            {
                "episode_id": ep, "decision": "pass", "reasons": [],
                "checks": [
                    {"name": "min_frames", "value": 30.0, "threshold": 30.0, "passed": True},
                    {"name": "hand_out_of_frame", "value": 0.1, "threshold": 0.3, "passed": True},
                    {"name": "camera_jitter_deg_s", "value": 1.0, "threshold": 60, "passed": True},
                    {"name": "pose_low_confidence", "value": 0.0, "threshold": 0.5, "passed": True},
                ],
            }
        )  # fmt: skip
    (work / "qa").mkdir()
    (work / "qa" / "egocentric.jsonl").write_text("\n".join(json.dumps(q) for q in qa) + "\n")
    (work / "source.json").write_text(
        json.dumps({"config_version": "ego-1@x", "data_class": "public"})
    )
    return work


@pytest.fixture
def fw(tmp_path: Path) -> ConsolePaths:
    root = tmp_path / "fwdata"
    root.mkdir()
    return ConsolePaths(repo=tmp_path, fw_root=root)


@pytest.fixture
def lerobot(fw: ConsolePaths) -> Path:
    return make_lerobot(fw.fw_root / "cut" / "S70")


@pytest.fixture
def work(fw: ConsolePaths) -> Path:
    base = fw.fw_root / "vid"
    deid = write_mp4(base / "a.deid.mp4")
    raw = write_mp4(base / "b.mp4")
    return make_work(fw.fw_root / "pipeline" / "src_test", deid, raw)


@pytest.fixture
def lerobot_rows() -> Callable[[str], list[dict[str, Any]]]:
    return lambda rel: [{"id": "S70", "lerobot": rel}]

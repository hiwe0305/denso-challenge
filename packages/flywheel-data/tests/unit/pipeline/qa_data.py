"""Datasets, episodes, labels and config paths shared by the pipeline tests (DA-03)."""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from flywheel.contracts.artifacts import Episode
from flywheel.data.ingest.lerobot import EpisodeFrames
from flywheel.data.ingest.sources import EpisodeLineage

FPS = 50
CAMERA = "observation.images.egocentric"
TASK = "pick up the cracker box from table1, locomotion to table2, and place on table2."


def psi0_info(fps: int = FPS) -> dict[str, object]:
    """info.json as Psi0's postprocess writes it, minus the observation.* columns."""
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
        "fps": fps,
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


def box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def track(handler: bytes, samples: int) -> bytes:
    hdlr = box(b"hdlr", bytes(8) + handler + bytes(12) + b"\0")
    stsz = box(b"stsz", bytes(4) + struct.pack(">II", 0, samples) + bytes(4 * samples))
    return box(b"trak", box(b"mdia", hdlr + box(b"minf", box(b"stbl", stsz))))


def fake_mp4(path: Path, frames: int, audio: int | None = 7) -> None:
    """An mp4 with no picture in it whose video track holds `frames` samples in stsz.

    An audio track comes first, so the reader has to pick the track by handler.
    """
    tracks = (b"" if audio is None else track(b"soun", audio)) + track(b"vide", frames)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(box(b"ftyp", b"isom" + bytes(4)) + box(b"moov", tracks) + box(b"mdat"))


def video_path(root: Path, index: int) -> Path:
    return root / "videos" / "chunk-000" / "egocentric" / f"episode_{index:06d}.mp4"


REPO = Path(__file__).resolve().parents[5]
QA_YAML = REPO / "configs" / "data" / "qa.yaml"
G1_YAML = REPO / "configs" / "embodiments" / "g1.yaml"
SPLITS = REPO / "configs" / "splits" / "default.yaml"
EPISODE_EXAMPLE = (
    REPO / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/Episode.json"
)
# The labels to_episode gives each source (sources.PROFILES).
SOURCE_LABELS: dict[str, dict[str, object]] = {
    "psi_data": {"kind": "teleop_demo", "operator_kind": "human", "is_root": True,
                 "source_kind": "teleop", "action_quality": "measured", "tier": None},
    "planner_wbc": {"kind": "sim_rollout", "operator_kind": "machine", "is_root": False,
                    "source_kind": "synthetic", "action_quality": "planned", "tier": "S1"},
    "teleop_pico": {"kind": "variant", "operator_kind": "machine", "is_root": False,
                    "source_kind": "synthetic", "action_quality": "planned", "tier": "S2"},
}


def clean_frames(index: int = 0, length: int = 20, task: str = TASK) -> EpisodeFrames:
    """An episode every QA check passes: zero action (inside every G1 limit) and small steps."""
    action = np.zeros((length, 36), dtype=np.float32)
    action[:, 14] = np.linspace(0.0, 0.01 * (length - 1), length, dtype=np.float32)
    return EpisodeFrames(
        episode_index=index,
        task=task,
        timestamp=np.arange(length, dtype=np.float64) / FPS,
        frame_index=np.arange(length, dtype=np.int64),
        states=np.zeros((length, 32), dtype=np.float32),
        action=action,
        video_frames={CAMERA: length},
    )


def episode_of(
    source_detail: str = "psi_data", episode_id: str = "ep_1", **update: object
) -> Episode:
    """The testkit Episode, relabelled as to_episode labels `source_detail`."""
    labels = dict(SOURCE_LABELS[source_detail])
    tier = labels.pop("tier")
    base = Episode.model_validate_json(EPISODE_EXAMPLE.read_text())
    meta = base.meta.model_copy(update={"source_detail": source_detail, "synthetic_tier": tier})
    fields = {"episode_id": episode_id, "source_id": "src_1", "meta": meta, **labels}
    if source_detail == "teleop_pico":
        fields["parent_id"] = "ep_parent"
    fields.update(update)
    return Episode.model_validate({**base.model_dump(), **fields, "meta": fields["meta"]})


def lineage_of(seed: int | None = 7, version: str | None = "p-1") -> EpisodeLineage:
    return EpisodeLineage(seed=seed, level=0, split="train", generator_version=version)

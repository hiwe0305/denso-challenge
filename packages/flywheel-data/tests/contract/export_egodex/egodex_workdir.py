"""A DA-04 work dir (plan 6/11/2026 section 4.2a) built from known numbers, for DA-18's tests.

DA-04 writes the real one in a parallel session; this builds the same files from a
seeded generator, so the export's input is known exactly:

    source.json, episodes.jsonl, qa/egocentric.jsonl
    egocentric/<episode_id>/bundle.json, pose.npz, segments.parquet
    raw/<task>/<n>.hdf5 + <n>.mp4       the "EgoDex" recording of an E-B episode
    raw/video/<episode_id>.mp4          the recording of an E-A episode

Frame k of every video is a flat grey of `grey(k)`, so a cut that starts on the wrong
frame shows in the first decoded frame. `from_egodex` builds the same files around real
EgoDex episodes (one or two segments each, QA pass), the stand-in for DA-04's output
used by the real-loader check.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import h5py  # type: ignore[import-untyped]
import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from flywheel.contracts.segments import SEGMENT_SCHEMA
from flywheel.data.export.egodex import CAMERA, HANDS, JOINTS, TIPS

FPS = 30
SIZE = (96, 64)  # width, height of the synthetic videos
INTRINSIC = np.array([[73.6, 0.0, 48.0], [0.0, 73.6, 32.0], [0.0, 0.0, 1.0]], np.float32)
SEGMENTS_SCHEMA = SEGMENT_SCHEMA.append(pa.field("frame_start", pa.int64())).append(
    pa.field("frame_end", pa.int64())
)


def grey(k: int) -> int:
    return 20 + (k * 7) % 200


@dataclass
class Spec:
    """One episode of the synthetic work dir."""

    episode_id: str
    frames: int
    segments: Sequence[tuple[int, int]]  # half-open frame ranges
    decision: str | None = "pass"  # None: no QAReport
    pose_source: str = "E-B"
    task: str = "pick_place_cup"
    split: str = "train"
    deid_status: str = "raw"
    episode: dict[str, Any] = field(default_factory=dict)  # overrides of the Episode


def rotation(rx: float, ry: float, rz: float) -> np.ndarray:
    cx, sx, cy, sy, cz, sz = np.cos(rx), np.sin(rx), np.cos(ry), np.sin(ry), np.cos(rz), np.sin(rz)
    x = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    y = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    z = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return z @ y @ x


def trajectory(rng: np.random.Generator, frames: int, origin: Sequence[float]) -> np.ndarray:
    """(T, 4, 4) float32: a smooth random walk in position and in roll, pitch and yaw."""
    angles = np.cumsum(rng.normal(0, 0.02, (frames, 3)), axis=0) + rng.uniform(-0.5, 0.5, 3)
    steps = np.cumsum(rng.normal(0, 0.004, (frames, 3)), axis=0) + np.asarray(origin)
    out = np.tile(np.eye(4), (frames, 1, 1))
    for k in range(frames):
        out[k, :3, :3] = rotation(*angles[k])
        out[k, :3, 3] = steps[k]
    return out.astype(np.float32)


def write_video(path: Path, frames: int) -> None:
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter.fourcc(*"mp4v"), FPS, SIZE)
    for k in range(frames):
        writer.write(np.full((SIZE[1], SIZE[0], 3), grey(k), np.uint8))
    writer.release()


def episode_record(spec: Spec, source_id: str) -> dict[str, Any]:
    quality = "retargeted" if spec.pose_source == "E-B" else "pseudo"
    record: dict[str, Any] = {
        "episode_id": spec.episode_id,
        "kind": "teleop_demo",
        "operator_kind": "human",
        "is_root": True,
        "condition_id": f"cond_{spec.episode_id}",
        "source_id": source_id,
        "run_plan_id": "g0-DA-04-20261106",
        "bundle_uri": f"egocentric/{spec.episode_id}",
        "license": "CC-BY-NC-ND-4.0",
        "data_class": "public",
        "split": spec.split,
        "source_kind": "egocentric",
        "action_quality": quality,
        "deid_status": spec.deid_status,
        "embodiment_id": "human_hands@egodex",
        "meta": {},
    }
    return record | spec.episode


def write_bundle(
    work: Path,
    spec: Spec,
    pose: dict[str, np.ndarray],
    hdf5: Path | None,
    mp4: Path,
    descriptions: Sequence[str],
) -> None:
    directory = work / "egocentric" / spec.episode_id
    directory.mkdir(parents=True, exist_ok=True)
    np.savez(directory / "pose.npz", **pose)
    rows = [
        {
            "t_start": start / FPS,
            "t_end": stop / FPS,
            "step_id": f"step_{k}",
            "description": descriptions[k % len(descriptions)],
            "label_source": "rule",
            "frame_start": start,
            "frame_end": stop,
        }
        for k, (start, stop) in enumerate(spec.segments)
    ]
    pq.write_table(
        pa.Table.from_pylist(rows, schema=SEGMENTS_SCHEMA), directory / "segments.parquet"
    )
    bundle = {
        "episode_id": spec.episode_id,
        "hdf5": None if hdf5 is None else str(hdf5.resolve()),
        "mp4": str(mp4.resolve()),
        "frames": spec.frames,
        "fps": FPS,
        "task": spec.task,
        "instruction": descriptions[0],
        "pose_source": spec.pose_source,
        "action_quality": "retargeted" if spec.pose_source == "E-B" else "pseudo",
        "pose": "pose.npz",
    }
    (directory / "bundle.json").write_text(json.dumps(bundle, indent=1), encoding="utf-8")


def pose_from_transforms(
    transforms: dict[str, np.ndarray], confidence: np.ndarray, intrinsic: np.ndarray | None
) -> dict[str, np.ndarray]:
    pose = {CAMERA: transforms[CAMERA]}
    for side in HANDS:
        pose[f"{side}_wrist"] = transforms[f"{side}Hand"]
        pose[f"{side}_tips"] = np.stack(
            [transforms[f"{side}{tip}"][:, :3, 3] for tip in TIPS], axis=1
        ).astype(np.float32)
        pose[f"confidence_{side}"] = confidence.astype(np.float32)
    if intrinsic is not None:
        pose["intrinsic"] = intrinsic
    return pose


def write_common(
    work: Path, source: dict[str, Any], specs: Sequence[Spec], episodes: list[dict[str, Any]]
) -> None:
    (work / "source.json").write_text(json.dumps(source, indent=1), encoding="utf-8")
    lines = [json.dumps(e) for e in episodes]
    (work / "episodes.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (work / "qa").mkdir(parents=True, exist_ok=True)
    reports = [
        {
            "report_id": f"qa_{spec.episode_id}",
            "episode_id": spec.episode_id,
            "threshold_version": "egocentric-1-000000000000",
            "decision": spec.decision,
            "reasons": [] if spec.decision == "pass" else ["pose.confidence"],
            "checks": [{"name": "pose.confidence", "value": 0.9, "threshold": 0.5, "passed": True}],
        }
        for spec in specs
        if spec.decision is not None
    ]
    text = "".join(json.dumps(r) + "\n" for r in reports)
    (work / "qa" / "egocentric.jsonl").write_text(text, encoding="utf-8")


def build(work: Path, specs: Sequence[Spec], *, seed: int = 0, waiver: bool = True) -> Path:
    """Write the synthetic work dir under `work`; returns `work`."""
    rng = np.random.default_rng(seed)
    e_a = any(spec.pose_source == "E-A" for spec in specs)
    source = {
        "source_id": "src_synthetic_ego",
        "source_detail": "ego_video" if e_a else "egodex",
        "license": "CC-BY-NC-ND-4.0",
        "data_class": "public",
        "root": str(work / "raw"),
        "files": {},
        "deid_waiver": "D2 6/11/2026: published EgoDex sample" if waiver and not e_a else None,
    }
    numbers: dict[str, int] = {}
    episodes = []
    for spec in specs:
        transforms = {CAMERA: trajectory(rng, spec.frames, (0.0, 1.4, 0.0))}
        for side, x in zip(HANDS, (-0.2, 0.2)):
            transforms[f"{side}Hand"] = trajectory(rng, spec.frames, (x, 1.0, -0.4))
            for tip in TIPS:
                transforms[f"{side}{tip}"] = trajectory(rng, spec.frames, (x, 0.95, -0.5))
        confidence = rng.uniform(0.6, 1.0, spec.frames)
        descriptions = [f"Pick the cup {spec.episode_id}", f"Place the cup {spec.episode_id}"]
        if spec.pose_source == "E-B":
            n = numbers.get(spec.task, 0)
            numbers[spec.task] = n + 1
            hdf5 = work / "raw" / spec.task / f"{n}.hdf5"
            mp4 = hdf5.with_suffix(".mp4")
            hdf5.parent.mkdir(parents=True, exist_ok=True)
            with h5py.File(hdf5, "w") as f:
                for name in (*JOINTS, CAMERA, "leftForearm", "rightForearm"):
                    value = transforms.get(name, transforms[CAMERA])
                    f.create_dataset(f"transforms/{name}", data=value)
                    f.create_dataset(f"confidences/{name}", data=confidence.astype(np.float32))
                f.create_dataset("camera/intrinsic", data=INTRINSIC)
                f.attrs["llm_type"] = "reversible"
                f.attrs["which_llm_description"] = "1"
                f.attrs["llm_description"] = descriptions[0]
                f.attrs["llm_description2"] = descriptions[1]
            write_video(mp4, spec.frames)
            pose = pose_from_transforms(transforms, confidence, None)
            write_bundle(work, spec, pose, hdf5, mp4, descriptions)
        else:
            mp4 = work / "raw" / "video" / f"{spec.episode_id}.mp4"
            write_video(mp4, spec.frames)
            pose = pose_from_transforms(transforms, confidence, INTRINSIC)
            write_bundle(work, spec, pose, None, mp4, descriptions)
        episodes.append(episode_record(spec, source["source_id"]))
    write_common(work, source, specs, episodes)
    return work


def from_egodex(work: Path, hdf5_files: Sequence[Path], *, split_in_two: bool = True) -> Path:
    """A work dir around real EgoDex episodes: pose.npz from their HDF5, QA pass.

    Each episode gets one segment over all its frames, or two halves with
    `split_in_two`; the segment's description is the episode's own instruction.
    """
    specs, episodes = [], []
    source = {
        "source_id": "src_egodex_probe",
        "source_detail": "egodex",
        "license": "CC-BY-NC-ND-4.0",
        "data_class": "public",
        "root": str(Path(hdf5_files[0]).parents[1]),
        "files": {},
        "deid_waiver": "D2 6/11/2026: published EgoDex sample",
    }
    for path in hdf5_files:
        path = Path(path)
        with h5py.File(path, "r") as f:
            transforms = {
                n: np.asarray(f[f"transforms/{n}"][:], np.float32) for n in (*JOINTS, CAMERA)
            }
            confidence = np.minimum(
                np.asarray(f["confidences/leftHand"][:]), np.asarray(f["confidences/rightHand"][:])
            )
            attrs = dict(f.attrs)
        frames = transforms[CAMERA].shape[0]
        direction = str(attrs.get("which_llm_description", "1"))
        key = (
            "llm_description2"
            if attrs.get("llm_type") == "reversible" and direction != "1"
            else "llm_description"
        )
        instruction = str(attrs[key]).strip()
        half = frames // 2
        segments = [(0, half), (half, frames)] if split_in_two and half >= 2 else [(0, frames)]
        spec = Spec(
            f"egodex_{path.parent.name}_{path.stem}", frames, segments, task=path.parent.name
        )
        write_bundle(
            work,
            spec,
            pose_from_transforms(transforms, confidence, None),
            path,
            path.with_suffix(".mp4"),
            [instruction],
        )
        specs.append(spec)
        episodes.append(episode_record(spec, source["source_id"]))
    write_common(work, source, specs, episodes)
    return work

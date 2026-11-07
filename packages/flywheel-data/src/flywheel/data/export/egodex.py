"""Egocentric segments in Psi0's stage 1 EgoDex layout (DA-18; design 27/10/2026 6.6, 7.8).

Reads the work dir that DA-04 writes (plan 6/11/2026 section 4.2a) and writes what
Psi0's `EgoDexDataset` reads at the pinned commit `cda3fdf`
(`src/psi/data/egodex/egodex_dataset.py`):

    <out>/part1/<task>/<i>.hdf5 + <i>.mp4     one QA'd segment each (split train)
    <out>/test/<task>/<i>.hdf5 + <i>.mp4      split dev, val or test (the loader's val set)
    <out>/egodex_stat.json                    stats as `calc_stat.py --use_delta_actions`
    <out>/meta.json                           source, recipe, per-sample provenance, sha256

The loader pairs `<i>.hdf5` with `<i>.mp4` in the same task directory and drops an
HDF5 without its mp4; it caches the scan in `filelist_cache.pkl` next to the files,
which the export never writes (a stale cache hides new files). Each HDF5 holds

- `transforms/<joint>` (T, 4, 4) float32 in the world frame for the wrists
  (`leftHand`, `rightHand`), the five fingertips of each hand (`JOINTS`) and
  `transforms/camera`; the loader takes T from the first of them, so all have T rows;
- `camera/intrinsic` (3, 3), which the loader reads on every sample;
- `actions_48d` (T, 48) float32, gzip 9, as the authors' H-RDT script
  `precompute_48d_actions.py` computes it: for the left then the right hand, the wrist
  xyz, the first two columns of the wrist rotation, and the xyz of the five tips;
- root attrs `llm_type`, `which_llm_description`, `llm_description`,
  `llm_description2`. A segment has one instruction (its `Segment.description`), so
  `llm_type` is "fixed" and the loader takes `llm_description`.

The mp4 is the segment cut from the episode video with OpenCV (codec mp4v, the
source size and fps), frame for frame with the HDF5: the loader takes frame `index`
of the video for row `index` of the HDF5. Psi0 resizes to 270x480 itself.

The recipe (`RECIPE`) is the authors' `pretrain-egodex-psi0-fast.sh`: `chunk_size` 1,
`upsample_rate` 3, delta actions, `bounds_q99`. A delta action is the change between
rows `index` and `index + 3` of `actions_48d`, both moved into the camera frame of row
`index` (`delta_actions`). The stats file follows `calc_stat.py`: every third row of
each file, deltas in the camera frame of the file's first row, then min, max, q01,
q99, mean and std over all rows of all files (train and test, as the script does).
Dims 6:9 and 30:33 are zero by construction. The authors' run normalizes with their
shipped `egodex_stat_all.json`; this file is for comparison and travels with the
release.

What is exported: every segment of an episode whose QAReport decides `pass`
(`include_flag` adds `flag`); an episode without a QAReport is not exported. A segment
with a frame whose hand or camera transform is not finite (E-A leaves NaN where
MediaPipe finds no hand) is dropped whole, never cut, and `meta.json` lists it with
the reason; the export is refused only when no segment is left. E-B
episodes (`pose_source` E-B, EgoDex, `retargeted`) copy the transforms from their
EgoDex HDF5; E-A episodes (`pose_source` E-A, the team's own video, `pseudo`) build
them from `pose.npz` (tips get an identity rotation, which `actions_48d` never reads).
An egocentric video whose `deid_status` is `raw` is refused unless the source carries
the EgoDex waiver (plan 6/11/2026 D2: `egodex` and `public` only). One run exports one
pose source: E-A and E-B in the same work dir are refused, so a `<task>/<i>` never
mixes a `pseudo` sample into EgoDex's numbering. The recipe's `upsample_rate` 3 is
three frames at 30 Hz, so a bundle or video at another fps is refused (resampling is
not done here).

Egocentric data is stage 1 only (design 7.8): nothing here writes a LeRobot dataset,
and `meta.json` says so.

Plain numpy, deterministic: the same work dir gives the same bytes (HDF5 without
object timestamps), so `export_id` is content-addressed over the files' sha256. Every
run writes its estimated and measured LedgerEntry rows through `job_ledger`.

    python -m flywheel.data.export.egodex --work <work> --out <out> [--include-flag]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from flywheel.contracts.artifacts import Episode, QAReport
from flywheel.contracts.base import canonical_json, content_id
from flywheel.contracts.segments import Segment
from flywheel.data.api import deid_blocks_annotate, job_ledger
from numpy.typing import NDArray

PSI0_COMMIT = "cda3fdf"
FORMAT = "psi0-stage1-egodex"
HANDS = ("left", "right")
TIPS = ("ThumbTip", "IndexFingerTip", "MiddleFingerTip", "RingFingerTip", "LittleFingerTip")
JOINTS = (
    *(f"{side}Hand" for side in HANDS),
    *(f"{side}{tip}" for side in HANDS for tip in TIPS),
)
CAMERA = "camera"
RECIPE: dict[str, Any] = {
    "chunk_size": 1,
    "upsample_rate": 3,
    "use_delta_actions": True,
    "action_norm_type": "bounds_q99",
    "stat_action_key": "egodex",
    "resize": [270, 480],
}
# dev is the split our own evaluation uses (DA-04 writes train or dev): Psi0's val set
SPLIT_DIRS = {"train": "part1", "dev": "test", "val": "test", "test": "test"}
MIN_FRAMES = 2  # the loader samples index in [0, T - 2]
FPS = 30.0  # `upsample_rate` 3 of the recipe is 0.1 s at EgoDex's 30 Hz
FPS_TOLERANCE = 0.05  # 29.97 (NTSC) passes; 25 or 60 does not
STATS_FILE = "egodex_stat.json"
META_FILE = "meta.json"
FOURCC = "mp4v"
DEID_WAIVED = frozenset({("egodex", "public")})  # plan 6/11/2026 D2
STAGE3 = "refused: egocentric data is stage 1 only (design 27/10/2026 7.8)"
# Assumption for the estimated ledger row, not a measurement: decoding and mp4v
# encoding one 1920x1080 frame on a laptop CPU, plus the HDF5 and stats work.
ESTIMATED_SECONDS_PER_FRAME = 0.02


class ExportRefused(ValueError):
    """The export as asked would break a rule; `problems` lists every one."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("export refused:\n" + "\n".join(f"- {p}" for p in problems))


# --- the 48-dim action and its delta, as Psi0 computes them ---------------------------


def actions_48d(transforms: Mapping[str, NDArray[Any]]) -> NDArray[Any]:
    """(T, 48) float32 from the (T, 4, 4) joint transforms (`precompute_48d_actions.py`)."""
    blocks: list[NDArray[Any]] = []
    for side in HANDS:
        wrist = np.asarray(transforms[f"{side}Hand"])
        blocks += [wrist[:, :3, 3], wrist[:, :3, 0], wrist[:, :3, 1]]
        blocks += [np.asarray(transforms[f"{side}{tip}"])[:, :3, 3] for tip in TIPS]
    actions: NDArray[Any] = np.concatenate(blocks, axis=1).astype(np.float32)
    return actions


def wrist_frames(nine: NDArray[Any]) -> NDArray[Any]:
    """(N, 4, 4) from (N, 9) position + 6D rotation, Gram-Schmidt as Psi0's `d9_to_mat44`."""
    position, col0, col1 = nine[:, :3], nine[:, 3:6], nine[:, 6:9]
    col0 = col0 / (np.linalg.norm(col0, axis=1, keepdims=True) + 1e-8)
    col1 = col1 - np.sum(col1 * col0, axis=1, keepdims=True) * col0
    col1 = col1 / (np.linalg.norm(col1, axis=1, keepdims=True) + 1e-8)
    frames = np.tile(np.eye(4, dtype=nine.dtype), (nine.shape[0], 1, 1))
    frames[:, :3, 0] = col0
    frames[:, :3, 1] = col1
    frames[:, :3, 2] = np.cross(col0, col1)
    frames[:, :3, 3] = position
    return frames


def euler_xyz(rotations: NDArray[Any]) -> NDArray[Any]:
    """(N, 3) extrinsic x-y-z angles of (N, 3, 3) rotations: scipy's `as_euler('xyz')`.

    R = Rz(yaw) Ry(pitch) Rx(roll). Away from pitch = +-90 degrees, which a delta over
    three frames at 30 Hz does not reach, this equals scipy to float precision.
    """
    r = rotations.astype(np.float64)
    roll = np.arctan2(r[:, 2, 1], r[:, 2, 2])
    pitch = np.arcsin(np.clip(-r[:, 2, 0], -1.0, 1.0))
    yaw = np.arctan2(r[:, 1, 0], r[:, 0, 0])
    return np.stack([roll, pitch, yaw], axis=1)


def delta_actions(actions: NDArray[Any], cam_ext: NDArray[Any]) -> NDArray[Any]:
    """(N - 1, 48) deltas of (N, 48) actions in the camera frame `cam_ext` (world, 4x4).

    Psi0's `convert_to_delta_actions`, per hand: wrist xyz delta, wrist rotation delta
    as roll-pitch-yaw of R_{k+1} R_k^T, three zeros, then the five tips' xyz deltas.
    The wrists stay in the dtype of `actions` and the tips go through float64, as there.
    """
    to_camera = np.linalg.inv(cam_ext)
    blocks: list[NDArray[Any]] = []
    for base in (0, 24):
        wrists = to_camera[None] @ wrist_frames(actions[:, base : base + 9])
        rotations = wrists[1:, :3, :3] @ np.swapaxes(wrists[:-1, :3, :3], 1, 2)
        rpy = euler_xyz(rotations).astype(np.float32)
        blocks += [wrists[1:, :3, 3] - wrists[:-1, :3, 3], rpy, np.zeros_like(rpy)]
        for tip in range(5):
            points = actions[:, base + 9 + 3 * tip : base + 12 + 3 * tip]
            homogeneous = np.hstack([points, np.ones((points.shape[0], 1))])
            in_camera = (to_camera @ homogeneous.T).T[:, :3]
            blocks.append(in_camera[1:] - in_camera[:-1])
    return np.concatenate(blocks, axis=1)


def stage1_stats(
    files: Sequence[tuple[NDArray[Any], NDArray[Any]]], upsample_rate: int
) -> dict[str, Any]:
    """`{"egodex": {min, max, q01, q99, mean, std}}` over `(actions_48d, camera)` pairs.

    `calc_stat.py --use_delta_actions`: rows `::upsample_rate` of each file, deltas in
    the camera frame of the file's first row. A file with fewer than two such rows has
    no delta and is left out (the script logs it as an error and goes on). The std is
    sqrt(E[x^2] - E[x]^2) as there, floored at 0 against rounding.
    """
    deltas = []
    for actions, camera in files:
        rows = actions[::upsample_rate]
        if rows.shape[0] >= 2:
            deltas.append(delta_actions(rows, camera[0]))
    if not deltas:
        raise ValueError("no file has two sampled rows: no stats")
    every = np.concatenate(deltas, axis=0)
    mean = every.sum(axis=0) / every.shape[0]
    std = np.sqrt(np.maximum((every**2).sum(axis=0) / every.shape[0] - mean**2, 0.0))
    block = {
        "min": every.min(axis=0),
        "max": every.max(axis=0),
        "q01": np.quantile(every, 0.01, axis=0),
        "q99": np.quantile(every, 0.99, axis=0),
        "mean": mean,
        "std": std,
    }
    return {"egodex": {key: value.tolist() for key, value in block.items()}}


# --- the work dir of plan 4.2a ---------------------------------------------------------


@dataclass(frozen=True)
class Bundle:
    """`egocentric/<episode_id>/bundle.json`, paths resolved against its directory."""

    episode_id: str
    hdf5: Path | None
    mp4: Path
    frames: int
    fps: float
    task: str
    instruction: str
    pose_source: str
    action_quality: str
    pose: Path

    @classmethod
    def read(cls, path: Path) -> Bundle:
        raw = json.loads(path.read_text(encoding="utf-8"))
        here = path.parent
        return cls(
            episode_id=str(raw["episode_id"]),
            hdf5=None if raw["hdf5"] is None else here / raw["hdf5"],
            mp4=here / raw["mp4"],
            frames=int(raw["frames"]),
            fps=float(raw["fps"]),
            task=str(raw["task"]),
            instruction=str(raw["instruction"]),
            pose_source=str(raw["pose_source"]),
            action_quality=str(raw["action_quality"]),
            pose=here / raw["pose"],
        )


@dataclass(frozen=True)
class FramedSegment:
    """A row of `segments.parquet`: the Segment and its half-open frame range."""

    segment: Segment
    frame_start: int
    frame_end: int


def read_segments(path: Path) -> list[FramedSegment]:
    rows = pq.read_table(path).to_pylist()
    out = []
    for row in rows:
        start, end = int(row.pop("frame_start")), int(row.pop("frame_end"))
        out.append(FramedSegment(Segment.model_validate(row), start, end))
    return out


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@dataclass(frozen=True)
class Planned:
    """One sample to write: which segment of which episode, and where."""

    episode: Episode
    bundle: Bundle
    segment: FramedSegment
    report: QAReport
    relpath: str  # <part>/<task>/<i>, without the extension


@dataclass
class Stage1Export:
    """What `export_stage1` wrote."""

    root: Path
    export_id: str
    samples: int
    frames: int
    skipped: list[dict[str, Any]] = field(default_factory=list)


def plan_export(work: Path, include: Sequence[str]) -> tuple[list[Planned], list[dict[str, Any]]]:
    """The samples to write and the skipped episodes or segments, or ExportRefused."""
    source = json.loads((work / "source.json").read_text(encoding="utf-8"))
    episodes = [Episode.model_validate(r) for r in read_jsonl(work / "episodes.jsonl")]
    reports: dict[str, QAReport] = {}
    problems: list[str] = []
    for raw in read_jsonl(work / "qa" / "egocentric.jsonl"):
        qa = QAReport.model_validate(raw)
        if qa.episode_id in reports:
            problems.append(f"{qa.episode_id}: two QAReports")
        reports[qa.episode_id] = qa
    waived = source.get("deid_waiver") is not None and (
        (str(source.get("source_detail")), str(source.get("data_class"))) in DEID_WAIVED
    )
    chosen: list[tuple[Episode, Bundle, FramedSegment, QAReport]] = []
    skipped: list[dict[str, Any]] = []
    pose_sources: dict[str, list[str]] = {}
    for episode in sorted(episodes, key=lambda e: e.episode_id):
        eid = episode.episode_id
        report = reports.get(eid)
        if report is None:
            skipped.append({"episode_id": eid, "reason": "no QAReport"})
            continue
        if report.decision not in include:
            skipped.append({"episode_id": eid, "reason": f"QA {report.decision}"})
            continue
        if episode.source_kind != "egocentric":
            problems.append(f"{eid}: source_kind {episode.source_kind}, not egocentric")
            continue
        if deid_blocks_annotate(episode) and not (waived and episode.data_class == "public"):
            problems.append(f"{eid}: deid_status raw and the source has no EgoDex waiver (D2)")
            continue
        if episode.split not in SPLIT_DIRS:
            problems.append(f"{eid}: split {episode.split!r} is not one of {sorted(SPLIT_DIRS)}")
            continue
        directory = work / "egocentric" / eid
        bundle = Bundle.read(directory / "bundle.json")
        pose_sources.setdefault(bundle.pose_source, []).append(eid)
        found = _bundle_problems(episode, bundle) + _video_problems(bundle)
        if found:
            problems += found
            continue
        with np.load(bundle.pose) as npz:
            pose = {key: npz[key] for key in npz.files}
        for framed in read_segments(directory / "segments.parquet"):
            start, stop = framed.frame_start, framed.frame_end
            where = f"{eid} {framed.segment.step_id} [{start}, {stop})"
            if start < 0 or stop > bundle.frames:
                problems.append(f"{where}: outside the episode's {bundle.frames} frames")
                continue
            if stop - start < MIN_FRAMES:
                skipped.append(_skip(eid, framed, f"under {MIN_FRAMES} frames"))
                continue
            try:
                transforms, intrinsic = segment_transforms(bundle, pose, start, stop)
            except ExportRefused as refused:
                problems += refused.problems
                break
            reason = non_finite(transforms, intrinsic)
            if reason is None:
                chosen.append((episode, bundle, framed, report))
            else:
                skipped.append(_skip(eid, framed, reason))
    if len(pose_sources) > 1:
        problems.append(
            "one run exports one pose source, this work dir has "
            + "; ".join(f"{k}: {', '.join(v)}" for k, v in sorted(pose_sources.items()))
        )
    if problems:
        raise ExportRefused(problems)
    counters: Counter[tuple[str, str]] = Counter()
    planned = []
    for episode, bundle, framed, report in sorted(
        chosen, key=lambda c: (c[0].episode_id, c[2].frame_start, c[2].segment.step_id)
    ):
        key = (SPLIT_DIRS[episode.split], bundle.task)
        relpath = f"{key[0]}/{key[1]}/{counters[key]}"
        counters[key] += 1
        planned.append(Planned(episode, bundle, framed, report, relpath))
    return planned, skipped


def _skip(eid: str, framed: FramedSegment, reason: str) -> dict[str, Any]:
    return {
        "episode_id": eid,
        "step_id": framed.segment.step_id,
        "frame_start": framed.frame_start,
        "frame_end": framed.frame_end,
        "reason": reason,
    }


def non_finite(transforms: Mapping[str, NDArray[Any]], intrinsic: NDArray[Any]) -> str | None:
    """Why a segment's transforms cannot be exported, or None when every value is finite.

    Psi0's loader gives no way to mask a frame: a NaN in a hand reaches `actions_48d`,
    and one in the camera reaches every delta through its inverse.
    """
    span = transforms[CAMERA].shape[0]
    parts = {f"{side} hand": [f"{side}Hand", *(f"{side}{t}" for t in TIPS)] for side in HANDS}
    parts["camera"] = [CAMERA]
    found = []
    for part, names in parts.items():
        bad = np.zeros(span, dtype=bool)
        for name in names:
            bad |= ~np.isfinite(transforms[name].reshape(span, -1)).all(axis=1)
        if bad.any():
            found.append(f"{part} in {int(bad.sum())} of {span} frames")
    if not np.isfinite(intrinsic).all():
        found.append("camera intrinsic")
    return f"not finite: {', '.join(found)}" if found else None


def _bundle_problems(episode: Episode, bundle: Bundle) -> list[str]:
    eid = episode.episode_id
    problems = []
    if bundle.episode_id != eid:
        problems.append(f"{eid}: bundle.json names {bundle.episode_id}")
    if bundle.action_quality != episode.action_quality:
        problems.append(f"{eid}: bundle {bundle.action_quality}, Episode {episode.action_quality}")
    expected = {"E-B": ("retargeted", True), "E-A": ("pseudo", False)}.get(bundle.pose_source)
    if expected is None:
        problems.append(f"{eid}: pose_source {bundle.pose_source!r} is neither E-B nor E-A")
    elif (bundle.action_quality, bundle.hdf5 is not None) != expected:
        quality, has_hdf5 = expected
        problems.append(
            f"{eid}: {bundle.pose_source} needs action_quality {quality} and "
            f"{'an' if has_hdf5 else 'no'} EgoDex hdf5"
        )
    if "/" in bundle.task or bundle.task in {"", ".", ".."}:
        problems.append(f"{eid}: task {bundle.task!r} is not a directory name")
    if abs(bundle.fps - FPS) > FPS_TOLERANCE:
        problems.append(_fps_problem(eid, "bundle.json", bundle.fps))
    return problems


def _fps_problem(eid: str, where: str, fps: float) -> str:
    return (
        f"{eid}: {where} says {fps:g} fps; upsample_rate {RECIPE['upsample_rate']} assumes "
        f"{FPS:g} fps (resample the video to {FPS:g} fps first, not done by the export)"
    )


def _video_problems(bundle: Bundle) -> list[str]:
    """The video itself, read with OpenCV: it opens, and its fps is the bundle's."""
    import cv2

    capture = cv2.VideoCapture(str(bundle.mp4))
    try:
        if not capture.isOpened():
            return [f"{bundle.episode_id}: OpenCV cannot open {bundle.mp4}"]
        fps = float(capture.get(cv2.CAP_PROP_FPS))
    finally:
        capture.release()
    if abs(fps - FPS) > FPS_TOLERANCE:
        return [_fps_problem(bundle.episode_id, bundle.mp4.name, fps)]
    return []


# --- writing ---------------------------------------------------------------------------


def segment_transforms(
    bundle: Bundle, pose: Mapping[str, NDArray[Any]], start: int, stop: int
) -> tuple[dict[str, NDArray[Any]], NDArray[Any]]:
    """The (T, 4, 4) transforms of `JOINTS` and the camera, and the (3, 3) intrinsic."""
    if bundle.hdf5 is not None:  # E-B: the EgoDex HDF5 as recorded
        import h5py

        with h5py.File(bundle.hdf5, "r") as f:
            transforms = {
                name: np.asarray(f[f"transforms/{name}"][start:stop], dtype=np.float32)
                for name in (*JOINTS, CAMERA)
            }
            return transforms, np.asarray(f["camera/intrinsic"][:], dtype=np.float32)
    # E-A: pose.npz from MediaPipe and VO (plan 4.2a); its `intrinsic` is DA-18's request
    # to DA-04, since an E-A episode has no HDF5 to take the camera matrix from.
    if "intrinsic" not in pose:
        raise ExportRefused([f"{bundle.episode_id}: pose.npz has no 'intrinsic' (3, 3) for E-A"])
    span = stop - start
    transforms = {CAMERA: np.asarray(pose["camera"][start:stop], dtype=np.float32)}
    for side in HANDS:
        transforms[f"{side}Hand"] = np.asarray(pose[f"{side}_wrist"][start:stop], np.float32)
        tips = np.asarray(pose[f"{side}_tips"][start:stop], dtype=np.float32)
        for k, tip in enumerate(TIPS):
            frame = np.tile(np.eye(4, dtype=np.float32), (span, 1, 1))
            frame[:, :3, 3] = tips[:, k]
            transforms[f"{side}{tip}"] = frame
    intrinsic = np.asarray(pose["intrinsic"], dtype=np.float32)
    return {name: transforms[name] for name in (*JOINTS, CAMERA)}, intrinsic


def write_hdf5(
    path: Path,
    transforms: Mapping[str, NDArray[Any]],
    intrinsic: NDArray[Any],
    instruction: str,
    provenance: Mapping[str, str | int],
) -> NDArray[Any]:
    """Write one sample's HDF5 (see the module docstring); returns its `actions_48d`."""
    import h5py

    actions = actions_48d(transforms)
    with h5py.File(path, "w", track_order=False) as f:
        for name, array in transforms.items():
            f.create_dataset(f"transforms/{name}", data=array, track_times=False)
        f.create_dataset("camera/intrinsic", data=intrinsic, track_times=False)
        f.create_dataset(
            "actions_48d", data=actions, compression="gzip", compression_opts=9, track_times=False
        )
        f.attrs["llm_type"] = "fixed"
        f.attrs["which_llm_description"] = "1"
        f.attrs["llm_description"] = instruction
        f.attrs["llm_description2"] = ""
        for key, value in provenance.items():
            f.attrs[key] = value
    return actions


def cut_video(source: Path, cuts: Sequence[tuple[Path, int, int]], fps: float) -> None:
    """Write each `(target, start, stop)` frame range of `source` as mp4v, in one pass.

    Reads every frame in order rather than seeking, so a cut starts on exactly frame
    `start`; raises when the video ends before a cut does.
    """
    import cv2

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ExportRefused([f"{source}: OpenCV cannot open it"])
    size = (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    fourcc = cv2.VideoWriter.fourcc(*FOURCC)
    writers = {target: cv2.VideoWriter(str(target), fourcc, fps, size) for target, _, _ in cuts}
    written = Counter[Path]()
    last = max(stop for _, _, stop in cuts)
    index = 0
    try:
        while index < last:
            ok, frame = capture.read()
            if not ok:
                break
            for target, start, stop in cuts:
                if start <= index < stop:
                    writers[target].write(frame)
                    written[target] += 1
            index += 1
    finally:
        capture.release()
        for writer in writers.values():
            writer.release()
    short = [f"{t.name}: {written[t]} of {b - a} frames" for t, a, b in cuts if written[t] != b - a]
    if short:
        raise ExportRefused([f"{source} ended at frame {index}: {', '.join(short)}"])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def confidence_summary(pose: Mapping[str, NDArray[Any]], start: int, stop: int) -> dict[str, Any]:
    """Mean and min pose confidence of each hand over the segment's recorded frames.

    NaN is a frame without a recorded confidence (DA-04 writes NaN when an EgoDex file
    has no `confidences` group); `recorded` is the share of frames that have one, and
    mean and min are None when none has.
    """
    summary: dict[str, Any] = {}
    for side in HANDS:
        values = np.asarray(pose[f"confidence_{side}"][start:stop], dtype=np.float64)
        known = values[np.isfinite(values)]
        summary[side] = {
            "mean": round(float(known.mean()), 6) if known.size else None,
            "min": round(float(known.min()), 6) if known.size else None,
            "recorded": round(known.size / values.size, 6),
        }
    return summary


def export_stage1(
    work: Path,
    out: Path,
    *,
    include_flag: bool = False,
    release_id: str | None = None,
    run_plan_id: str | None = None,
    store: Path | None = None,
) -> Stage1Export:
    """Write the stage 1 export of `work` under `out` (new or empty), with its ledger rows."""
    include = ("pass", "flag") if include_flag else ("pass",)
    planned, skipped = plan_export(work, include)
    if not planned:
        reasons = Counter(str(s["reason"]).split(":")[0] for s in skipped)
        why = ", ".join(f"{n} {reason}" for reason, n in sorted(reasons.items()))
        raise ExportRefused([f"{work}: no segment to export ({len(skipped)} skipped: {why})"])
    existed = out.exists()
    if existed and any(out.iterdir()):
        raise ExportRefused([f"{out} is not empty: an export is never written over"])
    frames = sum(p.segment.frame_end - p.segment.frame_start for p in planned)
    with job_ledger(
        "export",
        "egodex_export",
        1.0 + ESTIMATED_SECONDS_PER_FRAME * frames,
        note=(
            f"assumption: {ESTIMATED_SECONDS_PER_FRAME} s per frame (decode, mp4v encode, "
            f"HDF5) for {frames} frames in {len(planned)} segments, plus 1 s"
        ),
        run_plan_id=run_plan_id,
        story="DA-18",
        store=store,
    ) as job:
        try:
            result = _write(work, out, planned, skipped, include, release_id)
        except BaseException:
            _discard(out, existed)
            raise
        job.notes.append(
            f"{result.samples} samples, {result.frames} frames, export {result.export_id}"
        )
    return result


def _discard(out: Path, existed: bool) -> None:
    """Remove a half-written export: `out` itself if the export made it, else its contents.

    `out` was new or empty, so all it holds is the export's. Emptying in place also
    works when `out` is a symlink to the directory, where rmtree would refuse.
    """
    if not existed:
        shutil.rmtree(out, ignore_errors=True)
        return
    for child in out.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def _write(
    work: Path,
    out: Path,
    planned: list[Planned],
    skipped: list[dict[str, Any]],
    include: Sequence[str],
    release_id: str | None,
) -> Stage1Export:
    source = json.loads((work / "source.json").read_text(encoding="utf-8"))
    samples: list[dict[str, Any]] = []
    stats_inputs: list[tuple[NDArray[Any], NDArray[Any]]] = []
    by_episode: dict[str, list[Planned]] = {}
    for item in planned:
        by_episode.setdefault(item.episode.episode_id, []).append(item)
    for items in by_episode.values():
        bundle = items[0].bundle
        with np.load(bundle.pose) as npz:
            pose = {key: npz[key] for key in npz.files}
        cuts = []
        for item in items:
            start, stop = item.segment.frame_start, item.segment.frame_end
            target = out / f"{item.relpath}.hdf5"
            target.parent.mkdir(parents=True, exist_ok=True)
            transforms, intrinsic = segment_transforms(bundle, pose, start, stop)
            actions = write_hdf5(
                target,
                transforms,
                intrinsic,
                item.segment.segment.description,
                {
                    "source_episode_id": item.episode.episode_id,
                    "source_step_id": item.segment.segment.step_id,
                    "frame_start": start,
                    "frame_end": stop,
                    "pose_source": bundle.pose_source,
                    "action_quality": bundle.action_quality,
                },
            )
            stats_inputs.append((actions, transforms[CAMERA]))
            cuts.append((out / f"{item.relpath}.mp4", start, stop))
            samples.append(_sample_meta(item, pose, start, stop))
        cut_video(bundle.mp4, cuts, bundle.fps)
    stats = stage1_stats(stats_inputs, int(RECIPE["upsample_rate"]))
    (out / STATS_FILE).write_text(json.dumps(stats, indent=1), encoding="utf-8")
    files: dict[str, str] = {STATS_FILE: sha256(out / STATS_FILE)}
    for sample in samples:
        for ext in ("hdf5", "mp4"):
            files[sample[ext]] = sample["sha256"][ext] = sha256(out / sample[ext])
    export_id = content_id("egx", {"format": FORMAT, "recipe": RECIPE, "files": files})
    frames = sum(int(s["frames"]) for s in samples)
    meta = {
        "export_id": export_id,
        "release_id": release_id,
        "format": FORMAT,
        "psi0_commit": PSI0_COMMIT,
        "recipe": RECIPE,
        "stage3": STAGE3,
        "include": list(include),
        "source": {
            key: source.get(key)
            for key in ("source_id", "source_detail", "license", "data_class", "deid_waiver")
        },
        "stats": {"path": STATS_FILE, "sha256": files[STATS_FILE], "files": len(stats_inputs)},
        "counts": {
            "samples": len(samples),
            "frames": frames,
            "by_part": dict(Counter(s["hdf5"].split("/")[0] for s in samples)),
            "by_pose_source": dict(Counter(s["pose_source"] for s in samples)),
        },
        "files": files,
        "samples": samples,
        "skipped": skipped,
    }
    (out / META_FILE).write_text(canonical_json(meta) + "\n", encoding="utf-8")
    return Stage1Export(out, export_id, len(samples), frames, skipped)


def _sample_meta(
    item: Planned, pose: Mapping[str, NDArray[Any]], start: int, stop: int
) -> dict[str, Any]:
    segment = item.segment.segment
    return {
        "hdf5": f"{item.relpath}.hdf5",
        "mp4": f"{item.relpath}.mp4",
        "sha256": {},
        "episode_id": item.episode.episode_id,
        "step_id": segment.step_id,
        "description": segment.description,
        "label_source": segment.label_source,
        "frame_start": start,
        "frame_end": stop,
        "frames": stop - start,
        "qa_decision": item.report.decision,
        "qa_report_id": item.report.report_id,
        "action_quality": item.bundle.action_quality,
        "pose_source": item.bundle.pose_source,
        "pose_confidence": confidence_summary(pose, start, stop),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--work", type=Path, required=True, help="DA-04 work dir (plan 4.2a)")
    parser.add_argument("--out", type=Path, required=True, help="export root, new or empty")
    parser.add_argument("--include-flag", action="store_true", help="also QA decision flag")
    parser.add_argument("--release-id", help="the ReleaseManifest these episodes belong to")
    parser.add_argument("--run-plan-id", help="RunPlan of the job (default g0-DA-18-<date>)")
    parser.add_argument("--store", type=Path, help="ledger store root (default $FW_ROOT)")
    args = parser.parse_args(argv)
    try:
        result = export_stage1(
            args.work,
            args.out,
            include_flag=args.include_flag,
            release_id=args.release_id,
            run_plan_id=args.run_plan_id,
            store=args.store,
        )
    except ExportRefused as error:
        print(error, file=sys.stderr)
        return 2
    summary = {
        "export_id": result.export_id,
        "root": str(result.root),
        "samples": result.samples,
        "frames": result.frames,
        "skipped": len(result.skipped),
    }
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())

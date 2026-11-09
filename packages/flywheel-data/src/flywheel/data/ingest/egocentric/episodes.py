"""Contract Episodes and the work directory of an egocentric source (plan 6/11/2026 4.2a).

DA-04 writes the work directory and DA-18 reads it; neither imports the other:

    source.json                          EgoSourceRecord
    episodes.jsonl                       one contract Episode per line
    egocentric/<episode_id>/bundle.json  hdf5, mp4, frames, fps, task, instruction,
                                         pose_source, action_quality, pose
    egocentric/<episode_id>/pose.npz     EgoPose (pose.py)
    egocentric/<episode_id>/segments.parquet
    qa/egocentric.jsonl                  one QAReport per episode

An egocentric Episode is a human demonstration (`teleop_demo`, `operator_kind`
human, a root), `source_kind` egocentric, `deid_status` raw until `fw egocentric deid`
sets it `blurred` (subtask 8; EgoDex keeps raw under the D2 waiver). `action_quality`
follows the pose: `retargeted` for E-B, the tracked hand turned into Psi0's format
(design 5.0), `pseudo` for E-A. An egocentric
episode has no robot action and never goes to stage 3 (design 6.6).

The episode id is `ep_` and the first 16 hex of sha256("<source_id>:<task>/<i>"):
ingesting the same files again gives the same ids. EgoDex records no scene seed,
so each episode gets its own `cond_unknown_...` condition, as psi-data does.
`meta.source_detail` stays empty: the contract's list has no egodex or ego_video
yet (see docs/g0/egocentric.md, proposal for the contract owner).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

from flywheel.contracts.artifacts import Episode, EpisodeMetadata
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.egodex import FPS, IMAGE_SIZE, read_meta
from flywheel.data.ingest.egocentric.source import EgoEpisodeFile, EgoSourceRecord

PoseSource = Literal["E-B", "E-A"]
EGO_DIR = "egocentric"
BUNDLE = "bundle.json"
POSE = "pose.npz"
POSE_EA = "pose_ea.npz"
SEGMENTS = "segments.parquet"
LABELS = "labels.json"
COMPARE = "compare.json"
QA_FILE = "qa/egocentric.jsonl"


@dataclass(frozen=True)
class Bundle:
    episode_id: str
    hdf5: str | None  # absolute, None for a recording without tracking
    mp4: str  # absolute
    frames: int
    fps: float
    task: str
    instruction: str
    pose_source: PoseSource
    action_quality: str
    pose: str  # file name inside the bundle directory
    video_frames: int  # frames the mp4 decodes to, by its header
    objects: tuple[str, ...]
    intrinsic: tuple[tuple[float, float, float], ...]
    image_size: tuple[int, int]  # width, height
    index: int = 0  # episode number inside the task folder
    # frame of pose.npz: "world" (E-B, E-A before task 10) or "camera" (E-A, camera
    # = identity: the head trajectory is not measured); how E-A was cleaned (task 10)
    pose_frame: str = "world"
    pose_cleaning: dict[str, Any] | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> Bundle:
        data = json.loads(text)
        data["objects"] = tuple(data["objects"])
        data["intrinsic"] = tuple(tuple(r) for r in data["intrinsic"])
        data["image_size"] = tuple(data["image_size"])
        return cls(**data)


def episode_id(source: EgoSourceRecord, item: EgoEpisodeFile) -> str:
    key = hashlib.sha256(f"{source.source_id}:{item.task}/{item.index}".encode())
    return f"ep_{key.hexdigest()[:16]}"


def to_episode(
    source: EgoSourceRecord, item: EgoEpisodeFile, cfg: EgoConfig, bundle_uri: str,
    split: str = "train",
) -> Episode:
    if split not in ("train", "dev"):
        raise ValueError(f"split {split!r} is not train or dev; holdout is never ingested")
    eid = episode_id(source, item)
    tracked = item.hdf5 is not None
    return Episode(
        episode_id=eid,
        kind="teleop_demo",
        operator_kind="human",
        is_root=True,
        condition_id=f"cond_unknown_{eid[3:]}",
        source_id=source.source_id,
        run_plan_id=f"rp_ingest_{source.source_id}",
        bundle_uri=bundle_uri,
        license=source.license,
        data_class=source.data_class,
        split=split,
        source_kind="egocentric",
        action_quality="retargeted" if tracked else "pseudo",
        deid_status="raw",  # `deid` sets blurred; the gate decides
        embodiment_id=cfg.sources[source.source_detail].embodiment_id,
        meta=EpisodeMetadata(),
    )


def make_bundle(source: EgoSourceRecord, item: EgoEpisodeFile, video_frames: int) -> Bundle:
    eid = episode_id(source, item)
    mp4 = str(source.path(item.mp4))
    if item.hdf5 is not None:
        meta = read_meta(source.path(item.hdf5))
        return Bundle(
            episode_id=eid, hdf5=str(source.path(item.hdf5)), mp4=mp4, frames=meta.frames,
            fps=FPS, task=item.task, instruction=meta.instruction, pose_source="E-B",
            action_quality="retargeted", pose=POSE, video_frames=video_frames,
            objects=meta.objects,
            intrinsic=cast(Any, tuple(tuple(float(x) for x in r) for r in meta.intrinsic)),
            image_size=IMAGE_SIZE, index=item.index,
        )
    device = source.device
    sentence = str(device.get("tasks", {}).get(item.task, ""))
    return Bundle(
        episode_id=eid, hdf5=None, mp4=mp4, frames=video_frames, fps=float(device["fps"]),
        task=item.task, instruction=sentence, pose_source="E-A", action_quality="pseudo",
        pose=POSE, video_frames=video_frames, objects=tuple(device.get("objects", ())),
        intrinsic=cast(Any, tuple(tuple(float(x) for x in r) for r in device["intrinsic"])),
        image_size=(int(device["width"]), int(device["height"])), index=item.index,
    )


def bundle_dir(work: Path, eid: str) -> Path:
    return work / EGO_DIR / eid


def write_bundle(work: Path, bundle: Bundle) -> Path:
    folder = bundle_dir(work, bundle.episode_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / BUNDLE).write_text(bundle.to_json() + "\n")
    return folder


def read_bundle(work: Path, eid: str) -> Bundle:
    return Bundle.from_json((bundle_dir(work, eid) / BUNDLE).read_text())


def read_episodes(work: Path) -> list[Episode]:
    path = work / "episodes.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"{path}: run `fw egocentric ingest` first")
    return [Episode.model_validate_json(line) for line in path.read_text().splitlines() if line]


def write_episodes(work: Path, episodes: list[Episode]) -> None:
    (work / "episodes.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in episodes))

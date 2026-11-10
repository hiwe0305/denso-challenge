"""Pipeline work dirs -> clip status table, Human-1M-style shards, explorer.

Every episode of every work dir gets one status row: `exported`, or why not:

    excluded       the source is listed under `exclude` in the config, with its reason
    blocked_deid   the de-identification gate is closed (raw video, copy changed)
    no_qa          `fw egocentric qa` has not judged it
    rejected_qa    QA rejected it; its reasons are kept

Pose numbers (hands in frame, bone-length consistency) are measured for every episode,
exported or not. Only the de-identified copy (or the pinned EgoDex video) is read, by
`api.video_of`, and only for an exported episode.
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from flywheel.data.export.human1m.check import check_shard
from flywheel.data.export.human1m.frames import (
    EpisodeFrames,
    JointClean,
    from_egodex,
    from_estimates,
    scaled_intrinsic,
)
from flywheel.data.export.human1m.layout import CAM_POS, CAM_ROT, HAND_ROT
from flywheel.data.export.human1m.quality import Requirements, measure
from flywheel.data.export.human1m.subtasks import Marks, Subtask, rule_subtasks, tray_subtasks
from flywheel.data.export.human1m.video import Encoded, Encoder, VideoSettings
from flywheel.data.export.human1m.writer import ShardEpisode, ShardMeta, write_shard
from flywheel.data.ingest.egocentric import api
from flywheel.data.ingest.egocentric.episodes import (
    LABELS,
    QA_FILE,
    SEGMENTS,
    Bundle,
    bundle_dir,
    read_bundle,
    read_episodes,
)
from flywheel.data.ingest.egocentric.segments import read_segment_rows
from flywheel.data.ingest.egocentric.source import EgoSourceRecord


@dataclass(frozen=True)
class SourceView:
    shard: str
    vendor: str
    rig: str
    environment: str
    environment_category: str
    scene: str | None
    country: str | None
    capture_privacy: str | None
    task_source: str
    subtask_source: str
    task: str | None = None
    subtasks: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class H1MConfig:
    version: str
    data_format_version: str
    video: VideoSettings
    requirements: Requirements
    joint_clean: JointClean
    min_subtask_seconds: float
    exclude: dict[str, str]
    annotation_sources: dict[str, str]
    sources: dict[str, SourceView]


def load_h1m_config(path: Path) -> H1MConfig:
    raw = path.read_bytes()
    data = yaml.safe_load(raw)
    version = f"{data['version']}@{hashlib.sha256(raw).hexdigest()[:12]}"
    sources = {k: SourceView(**{f: v.get(f) for f in SourceView.__dataclass_fields__
                                if f in v}) for k, v in data["sources"].items()}
    for name, view in sources.items():
        for key in (view.task_source, view.subtask_source):
            if key not in data["annotation_sources"]:
                raise ValueError(f"sources.{name}: annotation source {key!r} not described")
    return H1MConfig(
        version=version, data_format_version=data["data_format_version"],
        video=VideoSettings(**data["video"]),
        requirements=Requirements.from_dict(data["requirements"]),
        joint_clean=JointClean.from_dict(data["joint_clean"]),
        min_subtask_seconds=float(data["min_subtask_seconds"]),
        exclude=dict(data.get("exclude") or {}),
        annotation_sources=dict(data["annotation_sources"]), sources=sources)


def anon(kind: str, *parts: str) -> str:
    """A stable anonymous id: kind and the first 12 hex of the sha256 of the parts."""
    return f"{kind}_{hashlib.sha256(':'.join(parts).encode()).hexdigest()[:12]}"


def read_marks(path: Path | None) -> dict[str, Marks]:
    """Tray phase marks by episode id, from a JSON-lines file (lift, place, ...)."""
    if path is None:
        return {}
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["episode_id"]] = Marks(int(row["lift"]), int(row["place"]))
    return out


@dataclass
class ClipRow:
    source_id: str
    source: str  # ego_video or egodex
    clip: str  # raw video, relative to the source root
    episode_id: str
    frames: int
    seconds: float
    fps: float
    width: int
    height: int
    deid: str
    pose_source: str
    qa: str | None
    qa_reasons: list[str]
    decision: str
    reason: str
    shard: str | None
    hands_visible: float | None = None
    left_visible: float | None = None
    right_visible: float | None = None
    bone_cv: float | None = None
    meets_h1m: dict[str, bool] = field(default_factory=dict)
    title: str = ""


@dataclass
class Item:
    """One episode on its way through the build."""

    row: ClipRow
    work: Path
    source: EgoSourceRecord
    bundle: Bundle
    view: SourceView | None
    frames: EpisodeFrames | None = None
    task: str = ""
    subtasks: list[Subtask] = field(default_factory=list)
    quality: dict[str, Any] = field(default_factory=dict)
    scene: str = ""
    shard_episode: ShardEpisode | None = None


def _clip_name(bundle: Bundle, source: EgoSourceRecord) -> str:
    path = Path(bundle.mp4)
    rel = path.relative_to(source.root).as_posix() if path.is_relative_to(source.root) \
        else path.name
    return rel.replace(".deid.mp4", ".mp4")


def _egodex_attrs(path: Path) -> dict[str, str]:
    import h5py  # egocentric extra

    with h5py.File(path, "r") as f:
        return {k: (v.decode() if isinstance(v, bytes) else str(v)) for k, v in f.attrs.items()
                if k in ("environment", "task")}


def survey(works: Sequence[Path], cfg: H1MConfig) -> list[Item]:
    """One item per episode of every work dir, with its decision; nothing is read from
    the videos."""
    items = []
    for work in works:
        source = api.read_source(work)
        api.check_unchanged(source)
        qa_ran = (work / QA_FILE).is_file()
        reports = {r.episode_id: r for r in api.read_reports(work)} if qa_ran else {}
        on_disk = api.deid_hashes(source)
        view = cfg.sources.get(source.source_detail)
        for episode in read_episodes(work):
            bundle = read_bundle(work, episode.episode_id)
            report = reports.get(episode.episode_id)
            gate = api.gate_open(episode, source, on_disk)
            deid = ("waived (D2, pinned sha256)" if source.deid_waiver
                    else episode.deid_status if gate else f"blocked ({episode.deid_status})")
            if source.source_id in cfg.exclude:
                decision, reason = "excluded", cfg.exclude[source.source_id]
            elif view is None:
                decision, reason = "excluded", f"no view for source {source.source_detail!r}"
            elif not gate:
                decision, reason = "blocked_deid", "de-identification gate closed"
            elif report is None:
                decision, reason = "no_qa", "no QA report; run `fw egocentric qa`"
            elif report.decision in ("reject", "quarantine"):
                decision, reason = "rejected_qa", "; ".join(report.reasons)
            else:
                decision, reason = "exported", ""
            row = ClipRow(
                source_id=source.source_id, source=source.source_detail,
                clip=_clip_name(bundle, source), episode_id=episode.episode_id,
                frames=bundle.frames, seconds=bundle.frames / bundle.fps, fps=bundle.fps,
                width=bundle.image_size[0], height=bundle.image_size[1], deid=deid,
                pose_source=bundle.pose_source, qa=report.decision if report else None,
                qa_reasons=list(report.reasons) if report else [], decision=decision,
                reason=reason, shard=view.shard if view and decision == "exported" else None)
            items.append(Item(row, work, source, bundle, view))
    return items


def _trim(frames: EpisodeFrames, n: int) -> EpisodeFrames:
    if frames.frames == n:
        return frames

    def cut(a: Any) -> Any:
        return None if a is None else a[:n]

    return replace(frames, hands={k: v[:n] for k, v in frames.hands.items()},
                   rotations={k: cut(v) for k, v in frames.rotations.items()},
                   camera_position=cut(frames.camera_position),
                   camera_rotation=cut(frames.camera_rotation),
                   confidence={k: v[:n] for k, v in frames.confidence.items()})


def pose_of(item: Item, estimates: Sequence[Path], cfg: H1MConfig) -> EpisodeFrames:
    b = item.bundle
    n = min(b.frames, b.video_frames)
    intrinsic = np.asarray(b.intrinsic, dtype=np.float64)
    if b.pose_source == "E-B":
        if b.hdf5 is None:
            raise ValueError(f"{b.episode_id}: E-B without an HDF5")
        return _trim(from_egodex(Path(b.hdf5), intrinsic, b.image_size), n)
    for folder in estimates:
        path = folder / f"{b.episode_id}.npz"
        if path.is_file():
            return from_estimates(path, n, intrinsic, b.image_size, cfg.joint_clean)
    raise FileNotFoundError(f"{b.episode_id}: no E-A estimates in"
                            f" {', '.join(map(str, estimates))}")


def annotate(item: Item, marks: Mapping[str, Marks], cfg: H1MConfig) -> None:
    """Task sentence, subtasks, scene and title of an item with its pose read."""
    assert item.view is not None and item.frames is not None
    b, view, n = item.bundle, item.view, item.frames.frames
    if item.source.source_detail == "egodex":
        attrs = _egodex_attrs(Path(b.hdf5)) if b.hdf5 else {}
        item.task = b.instruction
        rows = read_segment_rows(bundle_dir(item.work, b.episode_id) / SEGMENTS)
        labels_path = bundle_dir(item.work, b.episode_id) / LABELS
        side = json.loads(labels_path.read_text()).get("side") if labels_path.is_file() else None
        item.subtasks = rule_subtasks([(s.frame_start, s.frame_end, s.description)
                                       for s in rows], n, side, view.subtask_source,
                                      item.task, "fallback-whole-episode")
        item.scene = attrs.get("environment") or "EgoDex table"
        # The task folder names the task; the HDF5 'task' attribute is spelled
        # inconsistently across EgoDex (e.g. "build_unstake_lego" in build_unstack_lego/).
        item.row.title = f"{b.task.replace('_', ' ')} · {b.index}"
    else:
        item.task = view.task or b.instruction
        m = marks.get(b.episode_id)
        if m is not None and m.place > n:
            m = Marks(min(m.lift, n), n)
        item.subtasks = tray_subtasks(n, b.fps, m, view.subtasks, cfg.min_subtask_seconds,
                                      view.subtask_source, item.task, "fallback-whole-episode")
        item.scene = view.scene or "team recording"
        item.row.title = f"Carry the red tray · clip {b.index}"


def _measure(item: Item, cfg: H1MConfig) -> None:
    assert item.frames is not None
    q = measure(item.frames, item.bundle.fps, item.bundle.image_size[1], item.subtasks,
                cfg.requirements)
    item.quality = q
    r = item.row
    r.hands_visible, r.left_visible, r.right_visible = (q["hands_visible"], q["left_visible"],
                                                        q["right_visible"])
    cvs = [q[f"{s}_bone_cv"] for s in ("left", "right") if q[f"{s}_bone_cv"] is not None]
    r.bone_cv = float(np.mean(cvs)) if cvs else None
    r.meets_h1m = dict(q["checks"])


def encode(item: Item, media: Path, encoder: Encoder, cfg: H1MConfig) -> None:
    """Encode the episode's de-identified video and make its shard episode."""
    assert item.view is not None and item.frames is not None
    b, view = item.bundle, item.view
    src = api.video_of(b, item.source)  # raises DeidBlocked for a raw video
    video: Encoded = encoder.encode(src, media / f"{b.episode_id}.mp4", item.frames.frames,
                                    cfg.video)
    frames = _trim(item.frames, video.frames)
    if video.frames != item.frames.frames:
        item.subtasks = [Subtask(s.start, min(s.end, video.frames), s.text, s.source)
                         for s in item.subtasks if s.start < video.frames]
        item.subtasks[-1] = replace(item.subtasks[-1], end=video.frames)
    frames = replace(frames, intrinsic=scaled_intrinsic(frames.intrinsic, frames.image_size,
                                                        (video.width, video.height)),
                     image_size=(video.width, video.height))
    item.frames = frames
    sid = item.source.source_id
    scene_id = anon("scene", view.vendor, item.scene)
    q = item.quality
    item.shard_episode = ShardEpisode(
        episode_id=b.episode_id, frames=frames, fps=b.fps, task=item.task,
        subtasks=item.subtasks, environment=view.environment,
        environment_category=view.environment_category, scene=item.scene, scene_id=scene_id,
        collector_id=anon("collector", view.vendor, sid), rig_id=anon("rig", view.rig),
        vendor_id=anon("vendor", view.vendor), country=view.country,
        capture_privacy=view.capture_privacy, video=video,
        extra={"title": item.row.title, "source_id": sid, "source_clip": item.row.clip,
               "pose_source": b.pose_source, "action_quality": b.action_quality,
               "instruction": b.instruction, "qa_decision": item.row.qa,
               "qa_reasons": item.row.qa_reasons, "source_fps": b.fps,
               "source_width": b.image_size[0], "source_height": b.image_size[1],
               "hands_visible": q["hands_visible"], "left_visible": q["left_visible"],
               "right_visible": q["right_visible"], "left_bone_cv": q["left_bone_cv"],
               "right_bone_cv": q["right_bone_cv"], "left_accel_m_s2": q["left_accel_m_s2"],
               "right_accel_m_s2": q["right_accel_m_s2"],
               "subtasks_in_range": q["subtasks_in_range"],
               **{f"meets_{k}": v for k, v in q["checks"].items()}})


MISSING = {
    "ego_video": {
        HAND_ROT["left"]: "E-A (MediaPipe) gives joint positions only",
        HAND_ROT["right"]: "E-A (MediaPipe) gives joint positions only",
        CAM_POS: "one chest camera, head trajectory not measured (E-A visual odometry"
                 " too unsteady; task 10.1)",
        CAM_ROT: "one chest camera, head trajectory not measured (task 10.1)",
    },
    "egodex": {},
}
CONVENTIONS = {
    "camera_frame": "x right, y down, z forward (OpenCV), metres",
    "quaternion": "(qx, qy, qz, qw)",
    "world_frame": "ARKit world of the recording, y up, metres (EgoDex only)",
    "camera_pose": "camera to world",
    "hand_mask": "1 when the hand's joints are known and one projects inside the image",
    "hand_confidence": "E-A: MediaPipe handedness score, 0 when unseen; E-B: mean ARKit"
                       " joint confidence, NaN when the file recorded none",
    "joints": "21 per hand, MediaPipe order: wrist, then thumb cmc mcp ip tip, then"
              " mcp pip dip tip of index, middle, ring, little",
    "subtask_index": "-1 never occurs: subtasks tile every episode",
}


def summarize(rows: Sequence[ClipRow], cfg: H1MConfig) -> dict[str, Any]:
    """Counts and Human-1M requirement numbers, per source and overall."""

    def block(rs: Sequence[ClipRow]) -> dict[str, Any]:
        exported = [r for r in rs if r.decision == "exported"]
        visible = [r.hands_visible for r in rs if r.hands_visible is not None]
        ex_visible = [r.hands_visible for r in exported if r.hands_visible is not None]
        return {
            "clips": len(rs), "hours": sum(r.seconds for r in rs) / 3600,
            "exported": len(exported), "exported_hours": sum(r.seconds for r in exported) / 3600,
            "decisions": dict(Counter(r.decision for r in rs)),
            "qa": dict(Counter(r.qa or "none" for r in rs)),
            "fps": sorted({round(r.fps, 3) for r in rs}),
            "resolutions": sorted({f"{r.width}x{r.height}" for r in rs}),
            "seconds_median": statistics.median([r.seconds for r in rs]) if rs else None,
            "hands_visible_median": statistics.median(visible) if visible else None,
            "hands_visible_ge_95": (sum(v >= cfg.requirements.min_hands_visible for v in visible)
                                    / len(visible) if visible else None),
            "exported_hands_visible_ge_95": (
                sum(v >= cfg.requirements.min_hands_visible for v in ex_visible)
                / len(ex_visible) if ex_visible else None),
            "bone_cv_median": statistics.median([r.bone_cv for r in rs if r.bone_cv is not None])
            if any(r.bone_cv is not None for r in rs) else None,
            "qa_reasons": dict(Counter(x.split(":")[0].split(" (")[0]
                                       for r in rs for x in r.qa_reasons).most_common()),
        }

    by_source: dict[str, list[ClipRow]] = {}
    for r in rows:
        by_source.setdefault(r.source, []).append(r)
    return {"config": cfg.version, "all": block(rows),
            "sources": {k: block(v) for k, v in sorted(by_source.items())}}


def write_status(out: Path, rows: Sequence[ClipRow]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    data = [asdict(r) for r in rows]
    (out / "status.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    columns = [k for k in data[0] if k not in ("qa_reasons", "meets_h1m")] + [
        "qa_reasons", "meets_h1m"]
    with (out / "status.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, columns)
        writer.writeheader()
        for d in data:
            writer.writerow({**d, "qa_reasons": " | ".join(d["qa_reasons"]),
                             "meets_h1m": ",".join(k for k, v in d["meets_h1m"].items() if v)})


@dataclass
class BuildResult:
    items: list[Item]
    summary: dict[str, Any]
    shards: dict[str, dict[str, Any]]
    problems: dict[str, list[str]]


def build(out: Path, works: Sequence[Path], estimates: Sequence[Path], marks: Mapping[str, Marks],
          cfg: H1MConfig, encoder: Encoder, workers: int = 4,
          say: Callable[[str], None] = print) -> BuildResult:
    items = survey(works, cfg)
    say(f"{len(items)} episodes in {len(works)} work dirs;"
        f" {sum(i.row.decision == 'exported' for i in items)} to export")
    media = out / "viewer" / "media"

    def one(item: Item) -> None:
        item.frames = pose_of(item, estimates, cfg)
        if item.view is not None:
            annotate(item, marks, cfg)
        else:
            item.subtasks = []
        _measure(item, cfg)
        if item.row.decision == "exported":
            encode(item, media, encoder, cfg)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        list(pool.map(one, items))
    rows = [i.row for i in items]
    write_status(out, rows)
    summary = summarize(rows, cfg)
    shards: dict[str, dict[str, Any]] = {}
    problems: dict[str, list[str]] = {}
    for detail, view in cfg.sources.items():
        chosen = [i for i in items if i.shard_episode is not None and i.source.source_detail
                  == detail]
        if not chosen:
            continue
        chosen.sort(key=lambda i: (i.source.source_id, i.bundle.task, i.bundle.index))
        sources = sorted({i.source.source_id for i in chosen})
        meta = ShardMeta(
            name=view.shard, data_format_version=cfg.data_format_version,
            license=chosen[0].source.license, data_class=chosen[0].source.data_class,
            missing_fields=MISSING.get(detail, {}), conventions=CONVENTIONS,
            annotation_sources={k: cfg.annotation_sources[k] for k in sorted(
                {s.source for i in chosen for s in i.subtasks} | {view.task_source})},
            source={"source_ids": sources, "source_detail": detail, "config": cfg.version,
                    "intrinsic": "assumed (device.json)" if detail == "ego_video"
                    else "recorded (HDF5 camera/intrinsic)", "video_scaled_to_height":
                    cfg.video.height})
        shard_dir = out / view.shard
        shards[view.shard] = write_shard(shard_dir, [i.shard_episode for i in chosen
                                                     if i.shard_episode], meta, encoder)
        problems[view.shard] = check_shard(shard_dir)
        say(f"{view.shard}: {len(chosen)} episodes, {shards[view.shard]['total_frames']} frames;"
            f" check: {'ok' if not problems[view.shard] else problems[view.shard][:3]}")
    summary["shards"] = {k: {"episodes": v["total_episodes"], "frames": v["total_frames"],
                             "tasks": v["total_tasks"], "subtasks": v["total_subtasks"],
                             "problems": problems[k]} for k, v in shards.items()}
    sub = [s.seconds(i.bundle.fps) for i in items if i.shard_episode for s in i.subtasks]
    lo, hi = cfg.requirements.subtask_seconds
    summary["subtasks"] = {"count": len(sub),
                           "seconds_median": statistics.median(sub) if sub else None,
                           "in_1_10_s": sum(lo <= x <= hi for x in sub) / len(sub) if sub else None}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    return BuildResult(items, summary, shards, problems)

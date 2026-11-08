"""The egocentric pipeline over one work directory, step by step (DA-04).

`fw egocentric` wraps each function in one job with its two ledger rows. In order:

    ingest     EgoDexSource or EgoVideoSource -> source.json, episodes.jsonl, bundles
    deid       faces covered in a <i>.deid.mp4 copy of each video of a source that is
               not waived; bundles point at the copies, episodes become `blurred`
    pose       E-B from the HDF5, or E-A from the job's .npz; E-A against E-B
    annotate   de-identification gate, then segments.parquet and labels.json
    qa         qa/egocentric.jsonl
    report     report/dataset_report.json and the HTML page with its egocentric part

Each step reads what the earlier ones wrote, so a step can be rerun alone.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.contracts.artifacts import Episode, QAReport
from flywheel.data.annotate.deid.blur import (
    BlurParams,
    DeidVideo,
    FaceDetector,
    deid_video,
    file_sha256,
)
from flywheel.data.annotate.deid.gate import (
    DeidBlocked,
    annotate_allowed,
    deid_copy,
    require_annotate,
)
from flywheel.data.ingest.egocentric.compare import compare
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.episodes import (
    BUNDLE,
    COMPARE,
    LABELS,
    POSE,
    POSE_EA,
    QA_FILE,
    SEGMENTS,
    Bundle,
    bundle_dir,
    episode_id,
    make_bundle,
    read_bundle,
    read_episodes,
    to_episode,
    write_bundle,
    write_episodes,
)
from flywheel.data.ingest.egocentric.estimate import read_estimate, to_pose
from flywheel.data.ingest.egocentric.files import write_text
from flywheel.data.ingest.egocentric.pose import load_pose, read_egodex_pose, save_pose
from flywheel.data.ingest.egocentric.segments import (
    Cut,
    Labeler,
    SegmentSuggester,
    cut_episode,
    read_segment_rows,
    write_segment_table,
)
from flywheel.data.ingest.egocentric.source import (
    EgoSourceRecord,
    changed_files,
    dump_record,
    load_record,
)
from flywheel.data.ingest.egocentric.video import frame_count, jpeg, read_frames
from flywheel.data.qa.egocentric import EgoQAInput, run_ego_qa

SOURCE = "source.json"


@dataclass(frozen=True)
class Models:
    """What annotate may ask; None runs the rules alone."""

    suggester: SegmentSuggester | None = None
    labeler: Labeler | None = None
    names: dict[str, str] | None = None


def ingest(source: EgoSourceRecord, work: Path, cfg: EgoConfig, store: Path,
           split: str = "train") -> list[Episode]:
    work.mkdir(parents=True, exist_ok=True)
    episodes = []
    for item in source.episodes:
        bundle = make_bundle(source, item, frame_count(source.path(item.mp4)))
        folder = write_bundle(work, bundle)
        uri = folder / "bundle.json"
        relative = uri.resolve().relative_to(store.resolve()).as_posix() \
            if uri.resolve().is_relative_to(store.resolve()) else uri.resolve().as_posix()
        episodes.append(to_episode(source, item, cfg, relative, split))
    (work / SOURCE).write_text(dump_record(source) + "\n")
    write_episodes(work, episodes)
    return episodes


def read_source(work: Path) -> EgoSourceRecord:
    path = work / SOURCE
    if not path.is_file():
        raise FileNotFoundError(f"{path}: run `fw egocentric ingest` first")
    return load_record(path.read_text())


def check_unchanged(source: EgoSourceRecord) -> None:
    changed = changed_files(source)
    if changed:
        raise ValueError(f"{len(changed)} files of {source.source_id} changed since ingest,"
                         f" e.g. {changed[0]}; ingest again")


def deid_hashes(source: EgoSourceRecord) -> dict[str, str | None]:
    """The sha256 of each de-identified copy on disk now; None when it is gone."""
    return {name: file_sha256(source.path(name)) if source.path(name).is_file() else None
            for name in source.deid_copies}


def gate_open(episode: Episode, source: EgoSourceRecord,
              on_disk: Mapping[str, str | None] | None = None) -> bool:
    """`on_disk` is `deid_hashes(source)`, hashed once per step; hashed here when None."""
    return annotate_allowed(episode, source.source_detail, source.data_class, source.deid_waiver,
                            source.files, source.deid_copies,
                            deid_hashes(source) if on_disk is None else on_disk)


def require_gate(episode: Episode, source: EgoSourceRecord,
                 on_disk: Mapping[str, str | None] | None = None) -> None:
    require_annotate(episode, source.source_detail, source.data_class, source.deid_waiver,
                     source.files, source.deid_copies,
                     deid_hashes(source) if on_disk is None else on_disk)


def video_of(bundle: Bundle, source: EgoSourceRecord) -> Path:
    """The video a step may read: the de-identified copy, or the raw one of a waived
    source. Never the raw video of a source that needed blurring (CLAUDE.md)."""
    path = Path(bundle.mp4)
    relative = path.relative_to(source.root).as_posix() if path.is_relative_to(source.root) \
        else None
    if relative is not None and (relative in source.deid_copies or source.deid_waiver):
        return path
    raise DeidBlocked(f"{bundle.episode_id}: {bundle.mp4} is not a de-identified copy of"
                      f" {source.source_id}; run `fw egocentric deid`")


@dataclass(frozen=True)
class Blurred:
    """One episode's video after `deid`: the raw and the copy, relative to the root."""

    episode_id: str
    raw: str
    copy: str
    video: DeidVideo


def deid(work: Path, detector: FaceDetector, params: BlurParams,
         model: Mapping[str, str]) -> list[Blurred]:
    """Cover the faces of every video of a source that is not waived (subtask 8).

    Writes `<i>.deid.mp4` beside each raw `<i>.mp4`, then points each bundle at its
    copy, records the copies' sha256 and the method in source.json, and sets the
    episodes `blurred`, in that order: a step that stops half way leaves episodes the
    gate still stops. A waived source is left as it is and gives an empty list.
    """
    source = read_source(work)
    check_unchanged(source)  # blur the very files ingest hashed
    if source.deid_waiver is not None:
        return []
    episodes = read_episodes(work)
    raw_of = {episode_id(source, item): item.mp4 for item in source.episodes}
    done = []
    for episode in episodes:
        bundle = read_bundle(work, episode.episode_id)
        raw = raw_of[episode.episode_id]
        copy = deid_copy(raw)
        video = deid_video(source.path(raw), source.path(copy), detector, params)
        if (video.width, video.height) != tuple(bundle.image_size):
            raise ValueError(
                f"{raw}: frames are {video.width}x{video.height} after OpenCV's rotation, the"
                f" bundle says {bundle.image_size[0]}x{bundle.image_size[1]} (device.json"
                " width, height); fix them and ingest again")
        done.append(Blurred(episode.episode_id, raw, copy, video))
    for item in done:  # every copy written: now record them
        bundle = read_bundle(work, item.episode_id)
        frames = bundle.frames if bundle.hdf5 is not None else item.video.frames
        write_text(bundle_dir(work, item.episode_id) / BUNDLE, replace(
            bundle, mp4=str(source.path(item.copy)), video_frames=item.video.frames,
            frames=frames).to_json() + "\n")
    method: dict[str, Any] = {
        "status": "blurred", "model": dict(model), "params": asdict(params),
        "videos": {item.copy: {"raw": item.raw, **asdict(item.video)} for item in done},
    }
    copies = {item.copy: file_sha256(source.path(item.copy)) for item in done}
    write_text(work / SOURCE, dump_record(replace(source, deid_copies=copies,
                                                  deid_method=method)) + "\n")
    write_episodes(work, [e.model_copy(update={"deid_status": "blurred"}) for e in episodes])
    return done


def write_eb_poses(work: Path) -> int:
    """E-B: pose.npz of every tracked episode, read from its HDF5."""
    check_unchanged(read_source(work))
    count = 0
    for episode in read_episodes(work):
        bundle = read_bundle(work, episode.episode_id)
        if bundle.hdf5 is None:
            continue
        save_pose(read_egodex_pose(Path(bundle.hdf5)), bundle_dir(work, bundle.episode_id) / POSE,
                  _intrinsic(bundle))
        count += 1
    return count


def estimate_jobs(work: Path, source: EgoSourceRecord) -> list[dict[str, object]]:
    """The manifest `estimate_job.py` reads: every episode, E-B ones too (AC 5)."""
    check_unchanged(source)  # the job reads the videos the gate checked
    on_disk = deid_hashes(source)
    jobs = []
    for episode in read_episodes(work):
        require_gate(episode, source, on_disk)  # E-A reads the video: de-identified first
        bundle = read_bundle(work, episode.episode_id)
        jobs.append({"episode_id": episode.episode_id,
                     "mp4": video_of(bundle, source).relative_to(source.root).as_posix(),
                     "intrinsic": [list(r) for r in bundle.intrinsic], "fps": bundle.fps})
    return jobs


def import_estimates(work: Path, estimates: Path) -> dict[str, dict[str, object]]:
    """E-A: pose_ea.npz from each job output; pose.npz too when there is no tracking;
    compare.json where E-B exists. Returns the deviations by episode.

    Every estimate is read and compared before any file is written, so a bad one leaves
    the work dir as it was."""
    deviations = {}
    source = read_source(work)
    on_disk = deid_hashes(source)
    done = []
    for episode in read_episodes(work):
        raw = estimates / f"{episode.episode_id}.npz"
        if not raw.is_file():
            continue
        require_gate(episode, source, on_disk)
        bundle = read_bundle(work, episode.episode_id)
        folder = bundle_dir(work, episode.episode_id)
        estimate = read_estimate(raw)
        pose = to_pose(estimate)
        deviation = None
        if bundle.hdf5 is not None:
            deviation = compare(load_pose(folder / POSE), estimate, _intrinsic(bundle),
                                bundle.image_size).to_dict()
            deviation["meta"] = estimate.meta
            deviations[episode.episode_id] = deviation
        done.append((bundle, folder, pose, deviation))
    for bundle, folder, pose, deviation in done:
        save_pose(pose, folder / POSE_EA, _intrinsic(bundle))
        if deviation is None:
            save_pose(pose, folder / POSE, _intrinsic(bundle))
        else:
            write_text(folder / COMPARE, json.dumps(deviation, indent=2) + "\n")
    return deviations


def frames_reader(bundle: Bundle, max_side: int,
                  source: EgoSourceRecord) -> Callable[[Sequence[int]], list[bytes]]:
    """Frames as JPEG for a model, only from a video `video_of` allows."""
    video = video_of(bundle, source)

    def frames_of(indices: Sequence[int]) -> list[bytes]:
        return [jpeg(f) for f in read_frames(video, indices, max_side)]

    return frames_of


def annotate(work: Path, cfg: EgoConfig, models: Models = Models()) -> dict[str, Cut]:
    """Gate every episode first; a blocked one stops the step before anything is cut.
    Every episode is cut before any is written: a model that stops answering half way
    leaves the old segments, not a mix of old and new."""
    source = read_source(work)
    episodes = read_episodes(work)
    on_disk = deid_hashes(source)
    for episode in episodes:
        require_gate(episode, source, on_disk)
    check_unchanged(source)  # the model reads frames of the mp4
    layout = cfg.sources[source.source_detail].layout
    cuts = {}
    for episode in episodes:
        bundle = read_bundle(work, episode.episode_id)
        folder = bundle_dir(work, episode.episode_id)
        if not (folder / POSE).is_file():
            raise FileNotFoundError(f"{folder / POSE}: run `fw egocentric pose` first")
        cut = cut_episode(
            load_pose(folder / POSE), bundle.fps, layout, cfg.segment,
            instruction=bundle.instruction,
            obj=bundle.objects[0] if bundle.objects else "object",
            suggester=models.suggester, labeler=models.labeler,
            frames_of=frames_reader(bundle, cfg.max_image_side_px, source),
            model_names=models.names,
        )
        cuts[episode.episode_id] = cut
    for episode in episodes:  # all cut: now write
        cut, folder = cuts[episode.episode_id], bundle_dir(work, episode.episode_id)
        write_segment_table(folder / SEGMENTS, cut.segments,
                            read_bundle(work, episode.episode_id).fps)
        write_text(folder / LABELS, json.dumps(cut.labels(), indent=2) + "\n")
    return cuts


def qa(work: Path, cfg: EgoConfig) -> list[QAReport]:
    source = read_source(work)
    check_unchanged(source)
    on_disk = deid_hashes(source)
    reports = []
    for episode in read_episodes(work):
        bundle = read_bundle(work, episode.episode_id)
        folder = bundle_dir(work, episode.episode_id)
        labels = json.loads((folder / LABELS).read_text()) if (folder / LABELS).is_file() \
            else {"unresolved_share": 1.0}
        segments = read_segment_rows(folder / SEGMENTS) if (folder / SEGMENTS).is_file() else []
        reports.append(run_ego_qa(EgoQAInput(
            episode=episode, pose=load_pose(folder / POSE), segments=segments,
            unresolved_share=float(labels["unresolved_share"]),
            video_frames=bundle.video_frames, instruction=bundle.instruction,
            intrinsic=_intrinsic(bundle), image_size=bundle.image_size, fps=bundle.fps,
            gate_passed=gate_open(episode, source, on_disk),
        ), cfg))
    path = work / QA_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(r.model_dump_json() + "\n" for r in reports))
    return reports


def read_reports(work: Path) -> list[QAReport]:
    path = work / QA_FILE
    if not path.is_file():
        raise FileNotFoundError(f"{path}: run `fw egocentric qa` first")
    return [QAReport.model_validate_json(line) for line in path.read_text().splitlines() if line]


def _intrinsic(bundle: Bundle) -> np.ndarray:  # type: ignore[type-arg]
    return np.array(bundle.intrinsic, dtype=np.float64)

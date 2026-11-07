"""The egocentric pipeline over one work directory, step by step (DA-04).

`fw egocentric` wraps each function in one job with its two ledger rows. In order:

    ingest     EgoDexSource or EgoVideoSource -> source.json, episodes.jsonl, bundles
    pose       E-B from the HDF5, or E-A from the job's .npz; E-A against E-B
    annotate   de-identification gate, then segments.parquet and labels.json
    qa         qa/egocentric.jsonl
    report     report/dataset_report.json and the HTML page with its egocentric part

Each step reads what the earlier ones wrote, so a step can be rerun alone.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from flywheel.contracts.artifacts import Episode, QAReport
from flywheel.data.annotate.deid.gate import annotate_allowed, require_annotate
from flywheel.data.ingest.egocentric.compare import compare
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.episodes import (
    COMPARE,
    LABELS,
    POSE,
    POSE_EA,
    QA_FILE,
    SEGMENTS,
    Bundle,
    bundle_dir,
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


def gate_open(episode: Episode, source: EgoSourceRecord) -> bool:
    return annotate_allowed(episode, source.source_detail, source.data_class, source.deid_waiver,
                            source.files)


def require_gate(episode: Episode, source: EgoSourceRecord) -> None:
    require_annotate(episode, source.source_detail, source.data_class, source.deid_waiver,
                     source.files)


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
    jobs = []
    for episode in read_episodes(work):
        require_gate(episode, source)  # E-A reads the video: de-identified first
        bundle = read_bundle(work, episode.episode_id)
        jobs.append({"episode_id": episode.episode_id,
                     "mp4": Path(bundle.mp4).relative_to(source.root).as_posix(),
                     "intrinsic": [list(r) for r in bundle.intrinsic], "fps": bundle.fps})
    return jobs


def import_estimates(work: Path, estimates: Path) -> dict[str, dict[str, object]]:
    """E-A: pose_ea.npz from each job output; pose.npz too when there is no tracking;
    compare.json where E-B exists. Returns the deviations by episode."""
    deviations = {}
    source = read_source(work)
    for episode in read_episodes(work):
        raw = estimates / f"{episode.episode_id}.npz"
        if not raw.is_file():
            continue
        require_gate(episode, source)
        bundle = read_bundle(work, episode.episode_id)
        folder = bundle_dir(work, episode.episode_id)
        estimate = read_estimate(raw)
        pose = to_pose(estimate)
        save_pose(pose, folder / POSE_EA, _intrinsic(bundle))
        if bundle.hdf5 is None:
            save_pose(pose, folder / POSE, _intrinsic(bundle))
            continue
        deviation = compare(load_pose(folder / POSE), estimate, _intrinsic(bundle),
                            bundle.image_size).to_dict()
        deviation["meta"] = estimate.meta
        (folder / COMPARE).write_text(json.dumps(deviation, indent=2) + "\n")
        deviations[episode.episode_id] = deviation
    return deviations


def frames_reader(bundle: Bundle, max_side: int) -> Callable[[Sequence[int]], list[bytes]]:
    def frames_of(indices: Sequence[int]) -> list[bytes]:
        return [jpeg(f) for f in read_frames(Path(bundle.mp4), indices, max_side)]

    return frames_of


def annotate(work: Path, cfg: EgoConfig, models: Models = Models()) -> dict[str, Cut]:
    """Gate every episode first; a blocked one stops the step before anything is cut.
    Every episode is cut before any is written: a model that stops answering half way
    leaves the old segments, not a mix of old and new."""
    source = read_source(work)
    episodes = read_episodes(work)
    for episode in episodes:
        require_gate(episode, source)
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
            frames_of=frames_reader(bundle, cfg.max_image_side_px),
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
            gate_passed=gate_open(episode, source),
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

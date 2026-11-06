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

from flywheel.contracts.artifacts import Episode
from flywheel.data.annotate.deid.gate import annotate_allowed, require_annotate
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.episodes import (
    LABELS,
    POSE,
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
from flywheel.data.ingest.egocentric.pose import load_pose, read_egodex_pose, save_pose
from flywheel.data.ingest.egocentric.segments import (
    Cut,
    Labeler,
    SegmentSuggester,
    cut_episode,
    write_segment_table,
)
from flywheel.data.ingest.egocentric.source import (
    EgoSourceRecord,
    changed_files,
    dump_record,
    load_record,
)
from flywheel.data.ingest.egocentric.video import frame_count, jpeg, read_frames

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
    return annotate_allowed(episode, source.source_detail, source.data_class, source.deid_waiver)


def require_gate(episode: Episode, source: EgoSourceRecord) -> None:
    require_annotate(episode, source.source_detail, source.data_class, source.deid_waiver)


def write_eb_poses(work: Path) -> int:
    """E-B: pose.npz of every tracked episode, read from its HDF5."""
    check_unchanged(read_source(work))
    count = 0
    for episode in read_episodes(work):
        bundle = read_bundle(work, episode.episode_id)
        if bundle.hdf5 is None:
            continue
        save_pose(read_egodex_pose(Path(bundle.hdf5)), bundle_dir(work, bundle.episode_id) / POSE)
        count += 1
    return count


def frames_reader(bundle: Bundle, max_side: int) -> Callable[[Sequence[int]], list[bytes]]:
    def frames_of(indices: Sequence[int]) -> list[bytes]:
        return [jpeg(f) for f in read_frames(Path(bundle.mp4), indices, max_side)]

    return frames_of


def annotate(work: Path, cfg: EgoConfig, models: Models = Models()) -> dict[str, Cut]:
    """Gate every episode first; a blocked one stops the step before anything is cut."""
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
        write_segment_table(folder / SEGMENTS, cut.segments, bundle.fps)
        (folder / LABELS).write_text(json.dumps(cut.labels(), indent=2) + "\n")
        cuts[episode.episode_id] = cut
    return cuts



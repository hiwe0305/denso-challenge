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

from pathlib import Path

from flywheel.contracts.artifacts import Episode
from flywheel.data.annotate.deid.gate import annotate_allowed, require_annotate
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.episodes import (
    make_bundle,
    to_episode,
    write_bundle,
    write_episodes,
)
from flywheel.data.ingest.egocentric.source import (
    EgoSourceRecord,
    changed_files,
    dump_record,
    load_record,
)
from flywheel.data.ingest.egocentric.video import frame_count

SOURCE = "source.json"


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



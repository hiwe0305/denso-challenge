"""Inject defects into a copy of a LeRobot v2.1 dataset (DA-27 task 8, AC 1).

The copy is read and written only through the DA-03 reader and writer
(`flywheel.data.ingest.lerobot`); this module owns no parquet code. Each episode
becomes an `EpisodeData`, `create_defect_dataset` picks and applies the defects
and checks each one, and the result is written back:

    action, state, timestamp      the per-frame lists, row for row
    frame_index                   the kept image ids, so a dropped frame is a gap
    task                          the episode's instruction
    seed                          `environment_config.flywheel.seed` of its meta row

Every episode of the copy is written again in ascending order, not just the
injected ones: the writer renumbers `index` to LeRobot's rule and logs it, and
rewriting only some episodes would single them out. A duplicate gets the parquet
and video of its source first, so the columns the writer carries over and the
video match the source too. The stats files are recomputed from the copy's own data
(`stats.write_stats`) and every file gets one mtime, so neither stale stats nor write
times point at the changed episodes. The copy is marked as a benchmark copy in
`meta/benchmark_copy.json`; the answer key is only in the returned manifest.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.contracts.artifacts import ActionLayout, DefectManifest
from flywheel.data.ingest.lerobot import (
    EpisodeFrames,
    iter_episodes,
    read_episode_rows,
    read_info,
    write_episode,
)
from flywheel.data.inject.config import InjectConfig
from flywheel.data.inject.data_defects import EpisodeData
from flywheel.data.inject.dataset import create_clean_dataset, create_defect_dataset
from flywheel.data.inject.stats import write_stats

COPY_MARKER = "benchmark_copy.json"


def episode_ref(index: int) -> str:
    """The id an episode goes by in the manifest: its parquet file stem."""
    return f"episode_{index:06d}"


def row_seed(row: dict[str, Any]) -> int | None:
    """Condition seed of an `episodes.jsonl` row, from its flywheel block; psi-data has none."""
    config = row.get("environment_config") or {}
    if isinstance(config, str):
        config = json.loads(config)
    seed = (config.get("flywheel") or {}).get("seed")
    return None if seed is None else int(seed)


def frames_to_data(
    frames: EpisodeFrames, fps: float, seed: int | None, labelled_success: bool = True
) -> EpisodeData:
    """One LeRobot episode as the injector sees it.

    `labelled_success`: the success label the source gives the episode; a teleop
    demo of psi-data counts as a success by being in the authors' training set.
    """
    return EpisodeData(
        episode_id=episode_ref(frames.episode_index),
        timestamps_state=frames.timestamp.tolist(),
        timestamps_image=(frames.frame_index / fps).tolist(),
        states=frames.states.tolist(),
        actions=frames.action.tolist(),
        images=[str(i) for i in frames.frame_index.tolist()],
        instruction=frames.task,
        sim_success=labelled_success,
        seed=seed,
    )


def data_to_frames(ep: EpisodeData, template: EpisodeFrames) -> EpisodeFrames:
    """Back to the writer's frames, under the template's episode index."""
    return EpisodeFrames(
        episode_index=template.episode_index,
        task=ep.instruction,
        timestamp=np.asarray(ep.timestamps_state, dtype=np.float64),
        frame_index=np.asarray([int(i) for i in ep.images], dtype=np.int64),
        states=np.asarray(ep.states, dtype=np.float32),
        action=np.asarray(ep.actions, dtype=np.float32),
        video_frames=template.video_frames,
    )


def inject_copy(
    src_root: Path,
    out_root: Path,
    config: InjectConfig | None = None,
    layout: ActionLayout | None = None,
) -> DefectManifest:
    """Copy the dataset at `src_root` to `out_root` and inject defects into the copy.

    The source is never written. `out_root` must not exist; name it after the
    returned manifest's `dataset_id` (`copy_ids(seed)[0]`), never after its role.
    """
    if out_root.exists():
        raise FileExistsError(f"{out_root} exists; a benchmark copy is never overwritten")
    cfg = config or InjectConfig()
    fps = float(read_info(src_root)["fps"])
    seeds = {int(r["episode_index"]): row_seed(r) for r in read_episode_rows(src_root)}
    frames = list(iter_episodes(src_root))
    originals = [frames_to_data(f, fps, seeds[f.episode_index]) for f in frames]
    injected, manifest = create_defect_dataset(originals, config=cfg, layout=layout)
    duplicates = {
        d.target_ref: str(d.parameters["original_id"])
        for d in manifest.defects
        if d.parameters["kind"] == "duplicate_episode"
    }
    write_copy(src_root, out_root, frames, injected, manifest.dataset_id, duplicates)
    return manifest


def clean_copy(
    src_root: Path, out_root: Path, config: InjectConfig | None = None
) -> DefectManifest:
    """Copy the dataset at `src_root` to `out_root` with no defect, for the false alarm rate.

    The clean copy is built from the source, never from the defect copy, and goes through
    the same rewrite as the defect copy, so the two differ only by their defects. The
    returned manifest is empty; that is what tells the scorer this copy is the clean one.
    """
    if out_root.exists():
        raise FileExistsError(f"{out_root} exists; a benchmark copy is never overwritten")
    cfg = config or InjectConfig()
    fps = float(read_info(src_root)["fps"])
    seeds = {int(r["episode_index"]): row_seed(r) for r in read_episode_rows(src_root)}
    frames = list(iter_episodes(src_root))
    originals = [frames_to_data(f, fps, seeds[f.episode_index]) for f in frames]
    clean, manifest = create_clean_dataset(originals, config=cfg)
    write_copy(src_root, out_root, frames, clean, manifest.dataset_id, {})
    return manifest


def write_copy(
    src_root: Path,
    out_root: Path,
    frames: list[EpisodeFrames],
    episodes: list[EpisodeData],
    copy_id: str,
    duplicates: dict[str, str],
) -> None:
    """Write `episodes` (index-aligned with `frames`) as a full copy of `src_root`.

    `duplicates` maps a slot's episode ref to the ref of the episode copied into it.
    """
    info = read_info(src_root)
    shutil.copytree(src_root, out_root)
    for slot, source in duplicates.items():
        for src, dst in zip(_files(info, source), _files(info, slot), strict=True):
            if (src_root / src).is_file():
                shutil.copyfile(src_root / src, out_root / dst)
    for template, ep in zip(frames, episodes, strict=True):
        write_episode(out_root, data_to_frames(ep, template))
    owners = {
        int(slot.removeprefix("episode_")): int(source.removeprefix("episode_"))
        for slot, source in duplicates.items()
    }
    seeds = {int(ep.episode_id.removeprefix("episode_")): ep.seed for ep in episodes}
    _write_rows(out_root, src_root, seeds, owners)
    write_stats(out_root, source=src_root, owners=owners)
    (out_root / "meta" / COPY_MARKER).write_text(json.dumps({"benchmark_copy_id": copy_id}))
    # One mtime for every file and directory, so write times point at no episode.
    stamp = (src_root / "meta" / "info.json").stat().st_mtime
    for path in [*out_root.rglob("*"), out_root]:
        os.utime(path, (stamp, stamp))


def _files(info: dict[str, Any], ref: str) -> list[str]:
    """Parquet and video paths of an episode, relative to the dataset root."""
    index = int(ref.removeprefix("episode_"))
    chunk = index // int(info["chunks_size"])
    cameras = [n for n, f in info["features"].items() if f.get("dtype") == "video"]
    paths = [info["data_path"].format(episode_chunk=chunk, episode_index=index)]
    for camera in cameras:
        path = info["video_path"].format(episode_chunk=chunk, episode_index=index, video_key=camera)
        if path not in paths:
            paths.append(path)
    return paths


def _write_rows(
    root: Path, src_root: Path, seeds: dict[int, int | None], owners: dict[int, int]
) -> None:
    """Meta rows a real occurrence would also change.

    A duplicate carries its source's environment_config (scene layout and all); a
    changed seed goes into the row's `environment_config.flywheel` block.
    """
    source = {int(r["episode_index"]): r for r in read_episode_rows(src_root)}
    meta = root / "meta" / "episodes.jsonl"
    rows = [json.loads(line) for line in meta.read_text().splitlines() if line.strip()]
    for row in rows:
        index = int(row["episode_index"])
        if index in owners and "environment_config" in source[owners[index]]:
            row["environment_config"] = source[owners[index]]["environment_config"]
        seed = seeds.get(index)
        if seed is None or seed == row_seed(row):
            continue
        raw = row.get("environment_config") or {}
        config = json.loads(raw) if isinstance(raw, str) else dict(raw)
        config["flywheel"] = {**(config.get("flywheel") or {}), "seed": seed}
        row["environment_config"] = json.dumps(config) if isinstance(raw, str) else config
    meta.write_text("".join(json.dumps(r) + "\n" for r in rows))

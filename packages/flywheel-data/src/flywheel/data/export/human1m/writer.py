"""One LeRobot v3.0 shard in the Human-1M layout.

    data/chunk-000/file-000.parquet            one row per frame (layout.FRAME_FEATURES)
    meta/info.json                             features, paths, missing fields, sources
    meta/stats.json                            mean, std, min, max, count per feature
    meta/episodes/chunk-000/file-000.parquet   one row per episode
    meta/tasks.parquet, subtasks.parquet, environments.parquet, scenes.parquet
    videos/observation.images.main/chunk-000/file-000.mp4

Every episode of a shard has the same fps and video size. Episodes are fewer than
`CHUNK_SIZE`, so one chunk and one file hold them; the paths keep the templates.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from flywheel.data.export.human1m.frames import SIDES, EpisodeFrames
from flywheel.data.export.human1m.layout import (
    CAM_POS,
    CAM_ROT,
    CAMERA,
    CHUNK_SIZE,
    CODEBASE_VERSION,
    CONF,
    DATA_PATH,
    EPISODES_PATH,
    FRAME_FEATURES,
    HAND,
    HAND_ROT,
    MASK,
    VIDEO_KEY,
    VIDEO_PATH,
)
from flywheel.data.export.human1m.subtasks import Subtask
from flywheel.data.export.human1m.video import Encoded, Encoder
from flywheel.data.ingest.egocentric.files import replacing
from numpy.typing import NDArray


@dataclass(frozen=True)
class ShardEpisode:
    episode_id: str
    frames: EpisodeFrames
    fps: float
    task: str
    subtasks: Sequence[Subtask]
    environment: str
    environment_category: str
    scene: str
    scene_id: str
    collector_id: str
    rig_id: str
    vendor_id: str
    country: str | None
    capture_privacy: str | None
    video: Encoded
    extra: dict[str, Any] = field(default_factory=dict)  # flywheel/... columns


@dataclass(frozen=True)
class ShardMeta:
    name: str
    data_format_version: str
    license: str
    data_class: str
    missing_fields: dict[str, str]
    conventions: dict[str, str]
    annotation_sources: dict[str, str]
    source: dict[str, Any]


def _fixed(values: NDArray[Any], width: int) -> Any:
    flat = pa.array(np.asarray(values, dtype=np.float32).reshape(-1), type=pa.float32())
    return pa.FixedSizeListArray.from_arrays(flat, width)


def _nan(frames: int, width: int) -> NDArray[np.float32]:
    return np.full((frames, width), np.nan, dtype=np.float32)


def frame_columns(ep: ShardEpisode, episode_index: int, first_row: int, task_index: int,
                  subtask_index: Sequence[int], environment_index: int,
                  scene_index: int) -> dict[str, pa.Array]:
    f = ep.frames
    t = f.frames
    frame_index = np.arange(t, dtype=np.int64)
    sub = np.full(t, -1, dtype=np.int64)
    for s, k in zip(ep.subtasks, subtask_index):
        sub[s.start:s.end] = k
    cols: dict[str, pa.Array] = {
        "index": pa.array(first_row + frame_index),
        "episode_index": pa.array(np.full(t, episode_index, dtype=np.int64)),
        "frame_index": pa.array(frame_index),
        "timestamp": pa.array((frame_index / ep.fps).astype(np.float32)),
        "task_index": pa.array(np.full(t, task_index, dtype=np.int64)),
        "subtask_index": pa.array(sub),
    }
    for side in SIDES:
        cols[HAND[side]] = _fixed(f.hands[side].reshape(t, 63), 63)
        rot = f.rotations[side]
        cols[HAND_ROT[side]] = _fixed(_nan(t, 84) if rot is None else rot.reshape(t, 84), 84)
    cols[CAM_POS] = _fixed(_nan(t, 3) if f.camera_position is None else f.camera_position, 3)
    cols[CAM_ROT] = _fixed(_nan(t, 4) if f.camera_rotation is None else f.camera_rotation, 4)
    cols["environment_index"] = pa.array(np.full(t, environment_index, dtype=np.int64))
    cols["scene_index"] = pa.array(np.full(t, scene_index, dtype=np.int64))
    cols["scene_id"] = pa.array([ep.scene_id] * t, type=pa.string())
    cols["collector_id"] = pa.array([ep.collector_id] * t, type=pa.string())
    for side in SIDES:
        cols[MASK[side]] = pa.array(f.mask(side).astype(np.int64))
        cols[CONF[side]] = pa.array(f.confidence[side].astype(np.float32))
    return cols


def _stats(table: pa.Table) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name in table.column_names:
        column = table.column(name)
        if pa.types.is_string(column.type):
            continue
        values = (np.asarray(column.combine_chunks().flatten(), dtype=np.float64)
                  .reshape(len(column), -1) if pa.types.is_fixed_size_list(column.type)
                  else np.asarray(column, dtype=np.float64).reshape(-1, 1))
        finite = np.isfinite(values)
        count = finite.sum(axis=0)
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN columns: listed missing
            masked = np.where(finite, values, np.nan)
            stat = {"mean": np.nanmean(masked, axis=0), "std": np.nanstd(masked, axis=0),
                    "min": np.nanmin(masked, axis=0), "max": np.nanmax(masked, axis=0)}
        out[name] = {k: [None if not np.isfinite(x) else float(x) for x in v]
                     for k, v in stat.items()} | {"count": [int(c) for c in count]}
    return out


def _write_parquet(table: pa.Table, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with replacing(path) as temporary:
        pq.write_table(table, temporary)


def write_shard(out: Path, episodes: Sequence[ShardEpisode], meta: ShardMeta,
                encoder: Encoder) -> dict[str, Any]:
    """Write the shard under `out`; returns `info.json`."""
    if not episodes:
        raise ValueError(f"shard {meta.name} has no episodes")
    if len(episodes) > CHUNK_SIZE:
        raise ValueError(f"shard {meta.name}: {len(episodes)} episodes, one chunk holds"
                         f" {CHUNK_SIZE}")
    fps = episodes[0].fps
    size = (episodes[0].video.width, episodes[0].video.height)
    for ep in episodes:
        if ep.fps != fps or (ep.video.width, ep.video.height) != size:
            raise ValueError(f"{ep.episode_id}: {ep.fps} fps {ep.video.width}x"
                             f"{ep.video.height}, the shard is {fps} fps {size[0]}x{size[1]}")
        if ep.video.frames != ep.frames.frames:
            raise ValueError(f"{ep.episode_id}: video has {ep.video.frames} frames, pose"
                             f" {ep.frames.frames}")
    tasks: dict[str, int] = {}
    subtask_texts: dict[str, int] = {}
    environments: dict[tuple[str, str], int] = {}
    scenes: dict[tuple[str, str], int] = {}
    tables, episode_rows, subtask_rows = [], [], []
    row = 0
    seconds = 0.0
    for i, ep in enumerate(episodes):
        t = ep.frames.frames
        task_index = tasks.setdefault(ep.task, len(tasks))
        sub_index = [subtask_texts.setdefault(s.text, len(subtask_texts)) for s in ep.subtasks]
        env_index = environments.setdefault((ep.environment, ep.environment_category),
                                            len(environments))
        scene_index = scenes.setdefault((ep.scene, ep.scene_id), len(scenes))
        tables.append(pa.table(frame_columns(ep, i, row, task_index, sub_index, env_index,
                                             scene_index)))
        for s, k in zip(ep.subtasks, sub_index):
            subtask_rows.append({"subtask_index": k, "subtask": s.text, "episode_index": i,
                                 "timestamp_start": s.start / fps, "timestamp_end": s.end / fps,
                                 "frame_start": s.start, "frame_end": s.end,
                                 "source_id": s.source})
        intr = ep.frames.intrinsic
        episode_rows.append({
            "episode_index": i, "episode_id": ep.episode_id, "length": t, "tasks": [ep.task],
            "data/chunk_index": 0, "data/file_index": 0,
            "dataset_from_index": row, "dataset_to_index": row + t,
            "meta/episodes/chunk_index": 0, "meta/episodes/file_index": 0,
            f"videos/{VIDEO_KEY}/chunk_index": 0, f"videos/{VIDEO_KEY}/file_index": 0,
            f"videos/{VIDEO_KEY}/from_timestamp": seconds,
            f"videos/{VIDEO_KEY}/to_timestamp": seconds + t / fps,
            f"camera_intrinsics/{CAMERA}": [float(intr[0, 0]), float(intr[1, 1]),
                                            float(intr[0, 2]), float(intr[1, 2])],
            f"camera_model/{CAMERA}": "pinhole",
            "rig_id": ep.rig_id, "country": ep.country, "capture_privacy": ep.capture_privacy,
            "vendor_id": ep.vendor_id,
            **{f"flywheel/{key}": value for key, value in ep.extra.items()},
        })
        row += t
        seconds += t / fps
    data = pa.concat_tables(tables)
    _write_parquet(data, out / DATA_PATH.format(chunk_index=0, file_index=0))
    _write_parquet(pa.Table.from_pylist(episode_rows),
                   out / EPISODES_PATH.format(chunk_index=0, file_index=0))
    _write_parquet(pa.Table.from_pylist([{"task_index": v, "task": k} for k, v in tasks.items()]),
                   out / "meta/tasks.parquet")
    _write_parquet(pa.Table.from_pylist(subtask_rows), out / "meta/subtasks.parquet")
    _write_parquet(pa.Table.from_pylist(
        [{"environment_index": v, "environment": k[0], "category": k[1]}
         for k, v in environments.items()]), out / "meta/environments.parquet")
    _write_parquet(pa.Table.from_pylist(
        [{"scene_index": v, "scene": k[0], "scene_id": k[1]} for k, v in scenes.items()]),
        out / "meta/scenes.parquet")
    encoder.concat([ep.video.path for ep in episodes],
                   out / VIDEO_PATH.format(video_key=VIDEO_KEY, chunk_index=0, file_index=0))
    features = dict(FRAME_FEATURES)
    features[VIDEO_KEY] = {
        "dtype": "video", "shape": [size[1], size[0], 3],
        "names": ["height", "width", "channels"],
        "info": {"video.height": size[1], "video.width": size[0],
                 "video.codec": episodes[0].video.codec,
                 "video.pix_fmt": episodes[0].video.pix_fmt, "video.is_depth_map": False,
                 "video.fps": fps, "video.channels": 3, "has_audio": False},
    }
    info = {
        "codebase_version": CODEBASE_VERSION,
        "data_format_version": meta.data_format_version,
        "robot_type": None,
        "total_episodes": len(episodes),
        "total_frames": row,
        "total_tasks": len(tasks),
        "total_subtasks": len(subtask_texts),
        "chunks_size": CHUNK_SIZE,
        "fps": fps,
        "splits": {"train": f"0:{len(episodes)}"},
        "data_path": DATA_PATH,
        "video_path": VIDEO_PATH,
        "features": features,
        "shard": meta.name,
        "license": meta.license,
        "data_class": meta.data_class,
        "missing_fields": meta.missing_fields,
        "conventions": meta.conventions,
        "annotation_sources": meta.annotation_sources,
        "source": meta.source,
    }
    (out / "meta").mkdir(parents=True, exist_ok=True)
    (out / "meta/info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n")
    (out / "meta/stats.json").write_text(json.dumps(_stats(data)) + "\n")
    return info

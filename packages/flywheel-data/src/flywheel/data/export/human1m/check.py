"""Schema check of a written shard: what `fw egocentric human1m-check` reports.

It reads the shard back and checks that it is a LeRobot v3.0 dataset with the Human-1M
fields: the columns and widths of `info.json` features, contiguous row and frame
indices, timestamps on the fps grid, episode intervals in data and video, references
into the four dictionaries, subtasks tiling each episode, masks of 0 or 1 with known
joints under a 1, and fields listed missing being empty. Frames of the video file are
counted by decoding it unless `count_video` is False.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from flywheel.data.export.human1m.layout import (
    CODEBASE_VERSION,
    EPISODES_PATH,
    FRAME_FEATURES,
    HAND,
    MASK,
    VIDEO_KEY,
)
from flywheel.data.export.human1m.video import count_frames

INFO_KEYS = ("codebase_version", "data_format_version", "total_episodes", "total_frames",
             "fps", "data_path", "video_path", "features", "missing_fields")
EPISODE_KEYS = ("episode_index", "episode_id", "length", "data/chunk_index", "data/file_index",
                "dataset_from_index", "dataset_to_index", "meta/episodes/chunk_index",
                "meta/episodes/file_index", f"videos/{VIDEO_KEY}/chunk_index",
                f"videos/{VIDEO_KEY}/file_index", f"videos/{VIDEO_KEY}/from_timestamp",
                f"videos/{VIDEO_KEY}/to_timestamp", "camera_intrinsics/main", "rig_id",
                "country", "capture_privacy", "vendor_id")
DICTIONARIES = {"tasks": ("task_index", "task"), "subtasks": ("subtask_index", "subtask"),
                "environments": ("environment_index", "environment"),
                "scenes": ("scene_index", "scene")}


def _width(column: pa.ChunkedArray) -> int:
    return column.type.list_size if pa.types.is_fixed_size_list(column.type) else 1


def check_shard(root: Path, count_video: bool = True,
                counter: Callable[[Path], tuple[int, int, int]] = count_frames) -> list[str]:
    """Problems found; empty when the shard is well formed."""
    problems: list[str] = []
    info = json.loads((root / "meta/info.json").read_text())
    problems += [f"info.json lacks {k}" for k in INFO_KEYS if k not in info]
    if info.get("codebase_version") != CODEBASE_VERSION:
        problems.append(f"codebase_version {info.get('codebase_version')!r}")
    fps = float(info["fps"])
    data = pq.read_table(root / info["data_path"].format(chunk_index=0, file_index=0))
    episodes = pq.read_table(root / EPISODES_PATH.format(chunk_index=0, file_index=0))
    features = info["features"]
    for name, spec in FRAME_FEATURES.items():
        if name not in features:
            problems.append(f"feature {name} not in info.json")
        if name not in data.column_names:
            problems.append(f"column {name} missing")
        elif spec["dtype"] != "string" and _width(data.column(name)) != spec["shape"][0]:
            problems.append(f"column {name} width {_width(data.column(name))},"
                            f" expected {spec['shape'][0]}")
    extra = set(data.column_names) - set(FRAME_FEATURES)
    problems += [f"column {n} not in the features" for n in sorted(extra)]
    problems += [f"episodes lack {k}" for k in EPISODE_KEYS if k not in episodes.column_names]
    if problems:
        return problems
    n = data.num_rows
    if n != info["total_frames"] or episodes.num_rows != info["total_episodes"]:
        problems.append(f"{n} rows / {episodes.num_rows} episodes, info says"
                        f" {info['total_frames']} / {info['total_episodes']}")
    index = np.asarray(data.column("index"))
    if not np.array_equal(index, np.arange(n)):
        problems.append("index is not 0..N-1")
    ep_of_row = np.asarray(data.column("episode_index"))
    frame = np.asarray(data.column("frame_index"))
    stamp = np.asarray(data.column("timestamp"), dtype=np.float64)
    rows = episodes.to_pylist()
    end = 0
    for ep in rows:
        i, a, b = ep["episode_index"], ep["dataset_from_index"], ep["dataset_to_index"]
        if a != end or b - a != ep["length"]:
            problems.append(f"episode {i}: rows [{a}, {b}) after {end}, length {ep['length']}")
        end = b
        if not (ep_of_row[a:b] == i).all() or not np.array_equal(frame[a:b], np.arange(b - a)):
            problems.append(f"episode {i}: episode_index or frame_index wrong in its rows")
        if np.abs(stamp[a:b] - np.arange(b - a) / fps).max(initial=0) > 1e-3:
            problems.append(f"episode {i}: timestamps off the {fps} fps grid")
        v0 = ep[f"videos/{VIDEO_KEY}/from_timestamp"]
        v1 = ep[f"videos/{VIDEO_KEY}/to_timestamp"]
        if abs(v0 - a / fps) > 1e-6 or abs((v1 - v0) - ep["length"] / fps) > 1e-6:
            problems.append(f"episode {i}: video interval [{v0}, {v1}) does not match rows")
    tables = {k: pq.read_table(root / f"meta/{k}.parquet").to_pylist() for k in DICTIONARIES}
    for name, (key, _) in DICTIONARIES.items():
        known = {r[key] for r in tables[name]}
        column = {"tasks": "task_index", "environments": "environment_index",
                  "scenes": "scene_index", "subtasks": "subtask_index"}[name]
        used = set(np.asarray(data.column(column)).tolist()) - {-1}
        if used - known:
            problems.append(f"{column} refers to {sorted(used - known)[:5]} not in {name}")
    if (np.asarray(data.column("subtask_index")) == -1).any():
        problems.append("frames without a subtask")
    by_episode: dict[int, list[dict[str, float]]] = {}
    for r in tables["subtasks"]:
        by_episode.setdefault(r["episode_index"], []).append(r)
    for ep in rows:
        subs = sorted(by_episode.get(ep["episode_index"], []), key=lambda r: r["frame_start"])
        cuts = [0] + [s["frame_end"] for s in subs]
        starts = [s["frame_start"] for s in subs]
        if not subs or starts != cuts[:-1] or cuts[-1] != ep["length"]:
            problems.append(f"episode {ep['episode_index']}: subtasks do not tile [0, length)")
    for side in ("left", "right"):
        mask = np.asarray(data.column(MASK[side]))
        if not np.isin(mask, (0, 1)).all():
            problems.append(f"{MASK[side]} not 0 or 1")
        hand = np.asarray(data.column(HAND[side]).combine_chunks().flatten()).reshape(n, -1)
        if not np.isfinite(hand[mask == 1]).all():
            problems.append(f"{HAND[side]} not finite where the mask is 1")
    for name in info["missing_fields"]:
        if name in data.column_names:
            values = data.column(name)
            flat = (np.asarray(values.combine_chunks().flatten(), dtype=np.float64)
                    if pa.types.is_fixed_size_list(values.type)
                    else np.asarray(values, dtype=np.float64))
            if np.isfinite(flat).any():
                problems.append(f"{name} is listed missing but has values")
    video = root / info["video_path"].format(video_key=VIDEO_KEY, chunk_index=0, file_index=0)
    if not video.is_file():
        problems.append(f"{video} missing")
    elif count_video:
        frames, width, height = counter(video)
        spec = info["features"][VIDEO_KEY]["info"]
        if frames != n:
            problems.append(f"video has {frames} frames, data {n}")
        if (width, height) != (spec["video.width"], spec["video.height"]):
            problems.append(f"video is {width}x{height}, info says"
                            f" {spec['video.width']}x{spec['video.height']}")
    return problems

"""Points 1-6 of the LeRobot v2.1 checklist of design 6.4, run before a Psi0 fine-tune (DA-02).

A dataset goes to Psi0 stage 3 as SIMPLE's `postprocess_psi0_sonic.py` writes it
(psi-data, tray S1 of DA-33). Each point gives one or more QACheck; every check
fails when its value is above its threshold, and carries the D-code of design 10.

    1  info.codebase_version  D1  1 unless meta/info.json says "v2.1"
       info.fps               D1  1 unless fps is a positive number
       info.robot_type        D1  1 unless robot_type is a non-empty string
       info.action_shape      D1  |declared width - layout width|; [-1] (SIMPLE's) is no claim
       info.action_names      D1  dims whose declared name differs from the layout
       read                   D1  1 when the lane's reader refuses a parquet (width, dtype,
                                  missing column); points 2-6 on the data are not run then
    2  index.episode_index    D2  meta episodes not 0..E-1, parquet episode_index not its own
       index.index            D2  rows whose `index` is not the running row count
       index.frame_index      D2  rows whose frame_index is not 0..T-1 in their episode
    3  timestamp              D2  largest |timestamp * fps - frame_index|, in periods (<= 0.5)
    4  video.frames           D2  largest |video frames - rows| over episodes and cameras
       video.codec            D2  videos whose codec is not the declared `video.codec`
       video.resolution       D2  videos whose size is not the declared shape (H, W)
    5  tasks                  D6  episodes without a task sentence in meta, or whose
                                  parquet task_index has none in meta/tasks.jsonl
    6  stats.file             D4  states/action blocks (mean, std, min, max) missing from
                                  meta/stats_psi0.json, or of the wrong width
       stats.finite           D4  NaN or Inf numbers in those blocks
       stats.release          D4  largest |shipped - recomputed| of mean, std, min, max
       stats.constant         D4  constant action dims (Psi0 passes them through raw) that
                                  are neither masked nor declared constant
                                  (`UNDECLARED_CONSTANT_IS_ERROR`)

Point 7 (Psi0's own loader reads a saved batch back) is a contract test in
`flywheel-psi0`, since the lane never imports `lerobot` or `psi` (03 section 7.3).

Psi0 normalizes with `meta/stats_psi0.json` (configs/models/psi0-stage3.yaml:
`stat-path`, `action_norm_type: bounds`, `normalize-state`), so that is the file of
point 6; DA-03's `dataset_checks` covers `stats.json` and `episodes_stats.jsonl`.
The recompute is SIMPLE's `stats_block` (as copied in `flywheel.data.inject.stats`) in
float32 and in float64 (`PRECISIONS`); quantiles are not compared, since only the
`bounds_q99` norm type reads them, and Psi0's `bounds` reads min and max alone.

Point 4 reads the frame count, codec and size from the mp4 container (stsz and the
stsd sample entry), never by decoding. A declaration that is absent - psi-data and tray
S1 leave `video_info` empty and give `action` shape [-1] without names - is reported
in the finding's detail and does not fail: there is nothing to disagree with.
"""

from __future__ import annotations

import json
import math
import struct
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from flywheel.contracts.artifacts import ActionDimension, ActionLayout, QACheck
from flywheel.data.ingest.lerobot import (
    CODEBASE_VERSION,
    EpisodeFrames,
    LeRobotFormatError,
    _boxes,
    _child,
    _descend,
    iter_episodes,
    read_episode_rows,
)
from flywheel.data.inject.stats import stats_block

STATS_FILE = "meta/stats_psi0.json"
STATS = ("mean", "std", "min", "max")
STAT_FEATURES = ("states", "action")
# Half a control period (design 6.4 point 3).
TIMESTAMP_PERIODS = 0.5
# |shipped - recomputed| of a statistic, the tolerance of DA-03's stats checks
# (configs/data/qa.yaml `stats_json`).
STATS_TOLERANCE = 1.0e-5
# SIMPLE's postprocess computes each block in the dtype it holds then: states in float64,
# action in float32 (measured on psi-data e78fb93 and tray S1 0d84cc87b1e5, 4/11/2026:
# 1.8e-7 off the float64 recompute for states, 0 off the float32 one for action). Over
# 1e5 frames float32 accumulation moves a mean by up to 7.7e-4, so a block counts as
# computed on the release when either recompute matches it.
PRECISIONS: dict[str, type[np.floating[Any]]] = {"float32": np.float32, "float64": np.float64}
# Sample entry types of the mp4 stsd box, by the codec name LeRobot writes in
# `video_info["video.codec"]`.
CODECS = {
    b"avc1": "h264", b"avc3": "h264", b"hvc1": "hevc", b"hev1": "hevc",
    b"av01": "av1", b"vp09": "vp9", b"mp4v": "mpeg4",
}


@dataclass(frozen=True)
class ChecklistFinding:
    """One checklist check as run: the contract's QACheck, its point, D-code and detail."""

    point: int
    code: str
    check: QACheck
    detail: str


def check_lerobot_v21(root: Path, layout: ActionLayout) -> list[QACheck]:
    """Points 1-6 of the design 6.4 checklist on the LeRobot v2.1 dataset at root."""
    return [finding.check for finding in run_checklist(root, layout)]


def run_checklist(root: Path, layout: ActionLayout) -> list[ChecklistFinding]:
    """The checks of `check_lerobot_v21`, each with its point, D-code and what it found."""
    info_path = root / "meta" / "info.json"
    info: dict[str, Any] = json.loads(info_path.read_text())
    findings = _info_checks(root, info, layout)
    if info.get("codebase_version") != CODEBASE_VERSION:
        return findings
    try:
        episodes = list(iter_episodes(root))
    except (LeRobotFormatError, FileNotFoundError) as error:
        return [*findings, _finding(1, "D1", "read", 1, 0, str(error))]
    findings.append(_finding(1, "D1", "read", 0, 0, f"{len(episodes)} episodes read"))
    rows = read_episode_rows(root)
    findings += _index_checks(root, info, rows, episodes)
    findings.append(_timestamp_check(info, episodes))
    findings += _video_checks(root, info, episodes)
    findings.append(_task_check(root, info, rows))
    findings += _stats_checks(root, layout, episodes)
    return findings


def _finding(
    point: int, code: str, name: str, value: float, threshold: float, detail: str
) -> ChecklistFinding:
    check = QACheck(name=f"v21.{point}.{name}", value=value, threshold=threshold,
                    passed=value <= threshold)
    return ChecklistFinding(point, code, check, detail)


def _info_checks(
    root: Path, info: dict[str, Any], layout: ActionLayout
) -> list[ChecklistFinding]:
    width = len(layout.dimensions)
    version = info.get("codebase_version")
    fps = info.get("fps")
    robot = info.get("robot_type")
    good_fps = isinstance(fps, (int, float)) and not isinstance(fps, bool) and fps > 0
    findings = [
        _finding(1, "D1", "info.codebase_version", int(version != CODEBASE_VERSION), 0,
                 f"codebase_version {version!r}, expected {CODEBASE_VERSION!r}"),
        _finding(1, "D1", "info.fps", int(not good_fps), 0, f"fps {fps!r}"),
        _finding(1, "D1", "info.robot_type", int(not (isinstance(robot, str) and robot)), 0,
                 f"robot_type {robot!r}"),
    ]
    action = info.get("features", {}).get("action")
    shape = action.get("shape") if isinstance(action, dict) else None
    if shape == [-1]:
        gap, said = 0, "shape [-1] (no width declared; the parquet width is checked on read)"
    elif isinstance(shape, list) and len(shape) == 1 and isinstance(shape[0], int):
        gap, said = abs(shape[0] - width), f"shape {shape}, layout {width}"
    else:
        gap, said = width, f"features.action shape {shape!r}, expected [{width}] or [-1]"
    findings.append(_finding(1, "D1", "info.action_shape", gap, 0, said))
    findings.append(_names_check(root, action, layout))
    return findings


def _names_check(root: Path, action: Any, layout: ActionLayout) -> ChecklistFinding:
    """Declared action names, from info.json or the export's meta/action_layout.json."""
    expected = [d.name for d in layout.dimensions]
    names = action.get("names") if isinstance(action, dict) else None
    if isinstance(names, dict):  # LeRobot's {"motors": [...]} form
        names = next(iter(names.values()), None)
    source = "info.json features.action.names"
    exported = root / "meta" / "action_layout.json"
    if not (isinstance(names, list) and len(names) > 1) and exported.is_file():
        dims = json.loads(exported.read_text()).get("dimensions", [])
        names = [d.get("name") for d in dims]
        source = "meta/action_layout.json"
    if not (isinstance(names, list) and len(names) > 1):
        return _finding(1, "D1", "info.action_names", 0, 0,
                        "no per-dimension action names declared; nothing to compare")
    off = [i for i in range(max(len(names), len(expected)))
           if i >= len(names) or i >= len(expected) or names[i] != expected[i]]
    shown = ", ".join(
        f"{i}: {names[i] if i < len(names) else None!r} != "
        f"{expected[i] if i < len(expected) else None!r}"
        for i in off[:3]
    )
    detail = f"{source}: {len(off)} of {len(expected)} differ" + (f" ({shown})" if off else "")
    return _finding(1, "D1", "info.action_names", len(off), 0, detail)


def _index_checks(
    root: Path, info: dict[str, Any], rows: list[dict[str, Any]], episodes: list[EpisodeFrames]
) -> list[ChecklistFinding]:
    listed = [int(r["episode_index"]) for r in rows]
    bad_episodes = [i for n, i in enumerate(listed) if i != n]
    index_off = 0
    first_off: str | None = None
    offset = 0
    for frames in episodes:
        path = root / _data_path(info, frames.episode_index)
        names = pq.read_schema(path).names
        n = len(frames.frame_index)
        columns = [c for c in ("episode_index", "index") if c in names]
        table = pq.read_table(path, columns=columns)
        if "episode_index" not in names:
            bad_episodes.append(frames.episode_index)
        if "index" not in names:
            off = n
        else:
            index = np.asarray(table.column("index").to_numpy(), dtype=np.int64).reshape(-1)
            off = int((index != np.arange(offset, offset + n)).sum())
            if off and first_off is None:
                found = int(index[0]) if n else None
                first_off = f"episode {frames.episode_index} starts at {found}, expected {offset}"
        index_off += off
        offset += n
    frame_off = sum(
        int((f.frame_index != np.arange(len(f.frame_index))).sum()) for f in episodes
    )
    first_frame = next(
        (f"episode {f.episode_index} starts at {int(f.frame_index[0])}" for f in episodes
         if len(f.frame_index) and int(f.frame_index[0]) != 0),
        None,
    )
    return [
        _finding(2, "D2", "index.episode_index", len(bad_episodes), 0,
                 f"{len(bad_episodes)} of {len(listed)} episodes off"
                 + (f" (first {bad_episodes[0]})" if bad_episodes else "")),
        _finding(2, "D2", "index.index", index_off, 0,
                 f"{index_off} of {offset} rows off" + (f"; {first_off}" if first_off else "")),
        _finding(2, "D2", "index.frame_index", frame_off, 0,
                 f"{frame_off} of {offset} rows off" + (f"; {first_frame}" if first_frame else "")),
    ]


def _timestamp_check(info: dict[str, Any], episodes: list[EpisodeFrames]) -> ChecklistFinding:
    fps = float(info["fps"])
    worst, at = 0.0, "every row on time"
    for frames in episodes:
        if not len(frames.timestamp):
            continue
        gap = np.abs(frames.timestamp * fps - frames.frame_index)
        if not np.isfinite(gap).all():
            return _finding(3, "D2", "timestamp", 1e300, TIMESTAMP_PERIODS,
                            f"episode {frames.episode_index}: timestamp not finite")
        if float(gap.max()) > worst:
            row = int(gap.argmax())
            worst = float(gap.max())
            at = f"episode {frames.episode_index} row {row}"
    return _finding(3, "D2", "timestamp", worst, TIMESTAMP_PERIODS,
                    f"largest |timestamp*fps - frame_index| {worst:g} periods at {at}")


def _video_checks(
    root: Path, info: dict[str, Any], episodes: list[EpisodeFrames]
) -> list[ChecklistFinding]:
    features = info.get("features", {})
    cameras = [k for k, v in features.items() if v.get("dtype") == "video"]
    if not cameras:
        detail = "no video feature in info.json"
        return [_finding(4, "D2", f"video.{name}", 0, 0, detail)
                for name in ("frames", "codec", "resolution")]
    worst, at = 0, "every video matches its rows"
    codec_off = size_off = 0
    found_codecs: set[str] = set()
    found_sizes: set[tuple[int, int]] = set()
    declared_codecs = {c: _declared_codec(features[c]) for c in cameras}
    declared_sizes = {c: _declared_size(features[c]) for c in cameras}
    for frames in episodes:
        rows = len(frames.frame_index)
        for camera in cameras:
            gap = abs(frames.video_frames.get(camera, 0) - rows)
            if gap > worst:
                worst, at = gap, f"episode {frames.episode_index} {camera}"
            path = root / _video_path(info, frames.episode_index, camera)
            if not path.is_file():
                continue  # counted 0 frames above
            codec, width, height = mp4_sample_entry(path)
            found_codecs.add(codec)
            found_sizes.add((height, width))
            if declared_codecs[camera] is not None and codec != declared_codecs[camera]:
                codec_off += 1
            if declared_sizes[camera] is not None and (height, width) != declared_sizes[camera]:
                size_off += 1
    declared_c = sorted({str(c) for c in declared_codecs.values() if c is not None})
    declared_s = sorted({s for s in declared_sizes.values() if s is not None})
    return [
        _finding(4, "D2", "video.frames", worst, 0,
                 f"largest |video frames - rows| {worst} at {at}"),
        _finding(4, "D2", "video.codec", codec_off, 0,
                 f"found {sorted(found_codecs)}, declared {declared_c or 'nothing'}"),
        _finding(4, "D2", "video.resolution", size_off, 0,
                 f"found (H, W) {sorted(found_sizes)}, declared {declared_s or 'nothing'}"),
    ]


def _declared_codec(feature: dict[str, Any]) -> str | None:
    video_info = feature.get("video_info") or feature.get("info") or {}
    codec = video_info.get("video.codec")
    return str(codec) if codec else None


def _declared_size(feature: dict[str, Any]) -> tuple[int, int] | None:
    shape = feature.get("shape")
    names = feature.get("names") or ["height", "width", "channel"]
    if not (isinstance(shape, list) and len(shape) == 3 and "height" in names
            and "width" in names):
        return None
    return int(shape[names.index("height")]), int(shape[names.index("width")])


def mp4_sample_entry(path: Path) -> tuple[str, int, int]:
    """(codec, width, height) of the video track of an mp4, from its stsd box; no decoding.

    The codec is LeRobot's name for the sample entry type (`CODECS`), else the type
    itself; width and height are the visual sample entry's (ISO 14496-12 12.1.3).
    """
    with path.open("rb") as f:
        moov = _child(f, 0, path.stat().st_size, b"moov", path)
        if moov is None:
            raise LeRobotFormatError(f"{path}: no moov box, not an mp4 the reader can walk")
        for stbl in _video_stbls(f, moov, path):
            stsd = _child(f, *stbl, b"stsd", path)
            if stsd is None:
                break
            f.seek(stsd[0] + 8)  # version/flags, entry_count
            size, kind = struct.unpack(">I4s", f.read(8))
            if size < 8 + 28:
                raise LeRobotFormatError(f"{path}: stsd entry {kind!r} too short for a video")
            f.read(24)  # reserved, data_reference_index, pre_defined, reserved, pre_defined
            width, height = struct.unpack(">HH", f.read(4))
            return CODECS.get(kind, kind.decode("latin-1")), width, height
    raise LeRobotFormatError(f"{path}: no video track with an stsd box")


def _video_stbls(f: Any, moov: tuple[int, int], path: Path) -> Iterator[tuple[int, int]]:
    """stbl boxes of the tracks whose handler is `vide`, as `mp4_frame_count` walks them."""
    for kind, start, end in _boxes(f, *moov, path):
        mdia = _child(f, start, end, b"mdia", path) if kind == b"trak" else None
        hdlr = None if mdia is None else _child(f, *mdia, b"hdlr", path)
        if mdia is None or hdlr is None:
            continue
        f.seek(hdlr[0] + 8)  # version/flags, pre_defined
        if f.read(4) != b"vide":
            continue
        stbl = _descend(f, mdia, (b"minf", b"stbl"), path)
        if stbl is not None:
            yield stbl


def _task_check(root: Path, info: dict[str, Any], rows: list[dict[str, Any]]) -> ChecklistFinding:
    path = root / "meta" / "tasks.jsonl"
    lines = path.read_text().splitlines() if path.is_file() else []
    tasks = {int(r["task_index"]): str(r.get("task", "")) for r in map(json.loads, lines)
             if r}
    missing: list[int] = []
    for row in rows:
        index = int(row["episode_index"])
        listed = row.get("tasks") or []
        sentences = [t if isinstance(t, str) else tasks.get(int(t), "") for t in listed]
        parquet = root / _data_path(info, index)
        used: list[int] = []
        if "task_index" in pq.read_schema(parquet).names:
            column = pq.read_table(parquet, columns=["task_index"]).column("task_index")
            used = sorted({int(v) for v in column.to_numpy().reshape(-1)})
        if (not sentences or not all(s.strip() for s in sentences)
                or not all(tasks.get(i, "").strip() for i in used)):
            missing.append(index)
    return _finding(5, "D6", "tasks", len(missing), 0,
                    f"{len(missing)} of {len(rows)} episodes without a task sentence"
                    + (f" (first {missing[0]})" if missing else ""))


def _stats_checks(
    root: Path, layout: ActionLayout, episodes: list[EpisodeFrames]
) -> list[ChecklistFinding]:
    path = root / STATS_FILE
    if not path.is_file():
        return [_finding(6, "D4", "stats.file", 1, 0, f"no {STATS_FILE}")]
    shipped: dict[str, Any] = json.loads(path.read_text())
    arrays = {
        "states": np.concatenate([f.states for f in episodes]) if episodes else None,
        "action": np.concatenate([f.action for f in episodes]) if episodes else None,
    }
    missing: list[str] = []
    bad = 0
    worst, at = 0.0, "every statistic equal"
    for feature in STAT_FEATURES:
        block = shipped.get(feature)
        values = arrays[feature]
        width = values.shape[1] if values is not None else None
        recomputed = (
            {} if values is None
            else {kind: stats_block(values.astype(dtype)) for kind, dtype in PRECISIONS.items()}
        )
        for stat in STATS:
            numbers = block.get(stat) if isinstance(block, dict) else None
            if not isinstance(numbers, list) or (width is not None and len(numbers) != width):
                missing.append(f"{feature}.{stat}")
                continue
            theirs = np.asarray([float(x) for x in numbers], dtype=np.float64)
            bad += int((~np.isfinite(theirs)).sum())
            gaps = {}
            for kind, mine in recomputed.items():
                gap = np.abs(theirs - np.asarray(mine[stat], dtype=np.float64))
                gap[~np.isfinite(gap)] = np.inf
                gaps[kind] = gap
            if not gaps:
                continue
            kind = min(gaps, key=lambda k: float(gaps[k].max()))
            if float(gaps[kind].max()) > worst:
                worst = float(gaps[kind].max())
                at = f"{feature}.{stat}[{int(gaps[kind].argmax())}] (nearest the {kind} recompute)"
    findings = [
        _finding(6, "D4", "stats.file", len(missing), 0,
                 f"{STATS_FILE}: " + (f"missing or wrong width: {', '.join(missing)}"
                                      if missing else "states and action blocks present")),
        _finding(6, "D4", "stats.finite", bad, 0, f"{bad} NaN or Inf numbers in {STATS_FILE}"),
    ]
    value = worst if math.isfinite(worst) else 1e300  # QACheck holds finite numbers only
    findings.append(_finding(6, "D4", "stats.release", value, STATS_TOLERANCE,
                             f"largest |shipped - recomputed| {worst:g} at {at}"))
    findings.append(_constant_check(shipped.get("action"), layout.dimensions))
    return findings


def constant_dims(block: Any) -> list[int]:
    """Action dims Psi0's normalizer passes through raw: max - min under its ill mask.

    Psi0 cda3fdf `ActionStateTransform` (bounds): |max - min| < 1e-4 (|max| + |min| + 1e-8).
    The `std` of the stats is no test: SIMPLE's float32 `stats_block` gives std 3.6e-4
    for psi-data's dim 31, which is 0.74 in every frame.
    """
    low = block.get("min") if isinstance(block, dict) else None
    high = block.get("max") if isinstance(block, dict) else None
    if not (isinstance(low, list) and isinstance(high, list) and len(low) == len(high)):
        return []
    return [i for i, (a, b) in enumerate(zip(low, high, strict=True))
            if abs(float(b) - float(a)) < 1e-4 * (abs(float(b)) + abs(float(a)) + 1e-8)]


def _constant_check(block: Any, dims: Sequence[ActionDimension]) -> ChecklistFinding:
    constant = constant_dims(block)
    if constant and max(constant) >= len(dims):
        return _finding(6, "D4", "stats.constant", 0, 0, "action stats wider than the layout")
    errors = [i for i in constant if not _constant_allowed(dims[i])]
    masked = [i for i in constant if dims[i].masked]
    return _finding(6, "D4", "stats.constant", len(errors), 0,
                    f"constant action dims {constant} (masked {masked}); errors {errors}")


# D4 makes a zero-variance dim an error unless it is masked or the layout declares it
# constant. ActionDimension has no field to declare that (g1.yaml says dim 31 is
# constant in a comment only), so until it has, an unmasked constant dim is listed, not
# failed: Psi0 passes it through raw. Asked of the PO 4/11/2026 (DA-02 PR).
UNDECLARED_CONSTANT_IS_ERROR = False


def _constant_allowed(dim: ActionDimension) -> bool:
    """Whether a constant action dim is no stats error (design 6.4 point 6, D4)."""
    return dim.masked or not UNDECLARED_CONSTANT_IS_ERROR


def _data_path(info: dict[str, Any], index: int) -> str:
    chunk = index // int(info["chunks_size"])
    return str(info["data_path"]).format(episode_chunk=chunk, episode_index=index)


def _video_path(info: dict[str, Any], index: int, camera: str) -> str:
    chunk = index // int(info["chunks_size"])
    return str(info["video_path"]).format(
        episode_chunk=chunk, episode_index=index, video_key=camera
    )

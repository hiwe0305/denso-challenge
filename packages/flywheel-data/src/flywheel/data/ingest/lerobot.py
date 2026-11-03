"""Read and write LeRobot v2.1 datasets in the layout Psi0 and SIMPLE write (DA-03 AC 1).

The three robot sources before the 17/11 demo - psi-data of the two-table task,
tray S1 (DA-33) and tray S2 (DA-35) - all leave SIMPLE's
`postprocess_psi0_sonic.py` in the same shape:

    meta/info.json         codebase_version "v2.1", fps, features, path templates
    meta/episodes.jsonl    one row per episode: episode_index, tasks, length, ...
    meta/tasks.jsonl       task_index -> task sentence
    data/chunk-XXX/episode_XXXXXX.parquet   states (32), action (36), timestamp, ...
    videos/chunk-XXX/<camera>/episode_XXXXXX.mp4

Only `pyarrow` and `json` read them here; the lane never imports `lerobot`
(03 section 7.3). A parquet that lacks a column the lane needs, or holds a
vector of the wrong width, raises `LeRobotFormatError` naming the file and the
column. The interface types are float32 for states and action, float64 for
timestamp and int64 for frame_index (Psi0 trains on float32). A file whose
values do not survive that cast exactly - a float64 action of 0.1 - raises
too, naming the column, how many values change and by how much; the lane never
rounds data without saying so. Anything that is a data quality question rather
than a format one - a meta `length` that disagrees with the rows, a timestamp
that goes backwards, an empty episode - reads without error and is left to QA
(task 3).

Video frame counts come from the mp4 container, never from decoding (DA-02
point 4 decodes in the adapter): the sample count of the video track's `stsz`
box, which is the number of frames the encoder wrote. psi-data's meta holds no
per-video count. A camera whose file is missing counts 0; a file that is not an
mp4 the reader can walk raises. `write_episode` never touches videos, so a frame
drop injected by DA-27 leaves the video longer than the rows, as it should.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from numpy.typing import NDArray

CODEBASE_VERSION = "v2.1"
STATE_DIM = 32
ACTION_DIM = 36
# Columns write_episode builds from EpisodeFrames; any other non-video feature is
# carried over from the parquet already at the target path.
# Append-only record, next to the dataset's meta, of every value the writer changed
# that the frames did not ask it to (03: lineage is append-only).
LINEAGE = "flywheel_lineage.jsonl"
INDEX_RULE = "LeRobot v2.1: index = dataset_from_index + row"
OWNED = ("states", "action", "timestamp", "frame_index", "episode_index", "index",
         "next.done", "task_index")


class LeRobotFormatError(ValueError):
    """A LeRobot file that does not have the layout the lane reads."""


@dataclass(frozen=True)
class EpisodeFrames:
    episode_index: int
    task: str
    timestamp: NDArray[np.float64]  # (T,)
    frame_index: NDArray[np.int64]  # (T,)
    states: NDArray[np.float32]  # (T, 32)
    action: NDArray[np.float32]  # (T, 36)
    video_frames: dict[str, int]  # camera -> frame count from the mp4 (stsz), 0 if missing


def read_info(root: Path) -> dict[str, Any]:
    """`meta/info.json` of the dataset at root, after checking it is LeRobot v2.1."""
    path = root / "meta" / "info.json"
    if not path.is_file():
        raise FileNotFoundError(f"{path}: no LeRobot info.json")
    info: dict[str, Any] = json.loads(path.read_text())
    version = info.get("codebase_version")
    if version != CODEBASE_VERSION:
        raise LeRobotFormatError(
            f"{path}: codebase_version {version!r}, expected {CODEBASE_VERSION!r}"
        )
    return info


def iter_episodes(root: Path) -> Iterator[EpisodeFrames]:
    """Every episode of `meta/episodes.jsonl`, in episode_index order."""
    info = read_info(root)
    tasks = _read_tasks(root)
    cameras = _cameras(info)
    for row in _read_episode_rows(root):
        index = int(row["episode_index"])
        path = root / _episode_path(info, "data_path", index)
        if not path.is_file():
            raise FileNotFoundError(f"{path}: episode {index} is in meta/episodes.jsonl")
        table = pq.read_table(path)
        _check_episode_index(table, path, index)
        yield EpisodeFrames(
            episode_index=index,
            task=_task_of(table, row, tasks, path),
            timestamp=_scalar(table, path, "timestamp", np.float64),
            frame_index=_scalar(table, path, "frame_index", np.int64),
            states=_vector(table, path, "states", STATE_DIM),
            action=_vector(table, path, "action", ACTION_DIM),
            video_frames=_video_frames(root, info, cameras, row),
        )


def write_episode(root: Path, frames: EpisodeFrames) -> None:
    """Write one episode into the dataset at root, in the layout `iter_episodes` reads.

    The dataset's `meta/info.json` must exist already: fps, features and path
    templates are the dataset's, not the episode's. The parquet at the target
    path is replaced; its columns that EpisodeFrames does not hold (the
    `observation.*` joints of Psi0's export) are carried over row by row,
    matched on frame_index, so a copy with dropped frames stays loadable. The
    episode's row in `meta/episodes.jsonl` keeps its other keys (instruction,
    environment_config) and `meta/tasks.jsonl` keeps its rows as they are.
    Totals in info.json are recounted. Videos are not written: `video_frames`
    of the frames is not stored, the count is read from the mp4 there.

    A replaced parquet keeps its column order, types and schema metadata. A new
    one takes the types Psi0's postprocess actually writes - float64 lists for
    states and action, float64 timestamp - whatever info.json declares; the
    float32 states and action of psi-data and tray S1 are exact in float64, so
    reading back gives the same values.

    The global `index` column starts after the episodes with a smaller index as
    the meta lists them now, so write a dataset in ascending episode order;
    changing the length of an earlier episode leaves later ones stale until they
    are written again. Writing renumbers `index` to that rule (proposal Q7,
    pending the PO): psi-data starts episode i at 2 x dataset_from_index in 95
    of 99 episodes. The renumbering is never silent: when any kept row's index
    changes, a row goes to `meta/flywheel_lineage.jsonl` with the old and new
    first index and the number of rows changed, and `check_index` reports the
    source's own mismatches at ingest.
    """
    info = read_info(root)
    path = root / _episode_path(info, "data_path", frames.episode_index)
    length = _check_frames(frames, path)
    rows = {int(r["episode_index"]): r for r in _read_episode_rows(root, missing_ok=True)}
    task_rows = _read_task_rows(root)
    tasks = {int(r["task_index"]): str(r["task"]) for r in task_rows}
    task_index = next((i for i, t in tasks.items() if t == frames.task), None)
    if task_index is None:
        task_index = max(tasks, default=-1) + 1
        tasks[task_index] = frames.task
        # The shape of psi-data's rows: category empty, description = task.
        task_rows.append(
            {"task_index": task_index, "task": frames.task, "category": "",
             "description": frames.task}
        )
    offset = sum(int(r["length"]) for i, r in rows.items() if i < frames.episode_index)

    old = pq.read_table(path) if path.is_file() else None
    owned: dict[str, pa.Array] = {
        "states": _list_array(frames.states),
        "action": _list_array(frames.action),
        "timestamp": pa.array(frames.timestamp, pa.float64()),
        "frame_index": pa.array(frames.frame_index, pa.int64()),
        "episode_index": pa.array(np.full(length, frames.episode_index), pa.int64()),
        "index": pa.array(np.arange(offset, offset + length), pa.int64()),
        "next.done": pa.array(np.arange(length) == length - 1, pa.bool_()),
        "task_index": pa.array(np.full(length, task_index), pa.int64()),
    }
    features = info.get("features", {})
    declared = [n for n, f in features.items() if f.get("dtype") != "video" and n not in owned]
    undeclared = [] if old is None else [n for n in old.column_names if n not in features]
    columns: dict[str, pa.Array] = {}
    for name in declared + [n for n in undeclared if n not in owned]:
        if old is None or name not in old.column_names:
            raise LeRobotFormatError(
                f"{path}: column {name!r} is declared in info.json but neither the episode"
                " nor the parquet already there holds it"
            )
        columns[name] = old.column(name).take(_rows_by_frame(old, frames.frame_index, path))
    order = old.column_names if old is not None else list(features)
    names = [n for n in order if n in owned or n in columns]
    names += [n for n in [*OWNED, *columns] if n not in names]
    table = pa.table({n: owned.get(n, columns.get(n)) for n in names})
    if old is not None:
        table = _cast_like(table, old)
    renumbered = _renumbering(old, owned["index"], frames, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    if renumbered is not None:
        with (root / "meta" / LINEAGE).open("a") as f:
            f.write(json.dumps(renumbered) + "\n")

    row = dict(rows.get(frames.episode_index, {}))
    string_tasks = any(isinstance(t, str) for t in row.get("tasks", []))
    row.update(
        episode_index=frames.episode_index,
        tasks=[frames.task if string_tasks else task_index],
        length=length,
        dataset_from_index=offset,
        dataset_to_index=offset + length - 1,
        instruction={"task_index": task_index, "task": frames.task},
    )
    rows[frames.episode_index] = row
    meta = root / "meta"
    ordered = [rows[i] for i in sorted(rows)]
    (meta / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ordered))
    task_rows.sort(key=lambda r: int(r["task_index"]))
    (meta / "tasks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in task_rows))
    chunks = {i // int(info["chunks_size"]) for i in rows}
    info.update(
        total_episodes=len(rows),
        total_frames=sum(int(r["length"]) for r in ordered),
        total_tasks=len(tasks),
        total_videos=len(rows) * len(_cameras(info)),
        total_chunks=len(chunks),
    )
    (meta / "info.json").write_text(json.dumps(info, indent=4))


@dataclass(frozen=True)
class IndexFinding:
    """An episode whose parquet `index` is not LeRobot v2.1's numbering."""

    episode_index: int
    rows: int
    rows_off: int  # rows whose index is not dataset_from_index + row
    expected_first: int  # dataset_from_index of the meta (else lengths before it)
    found_first: int | None  # None: no index column, or no rows


def check_index(root: Path) -> list[IndexFinding]:
    """Episodes of the dataset at root whose `index` column breaks INDEX_RULE."""
    info = read_info(root)
    findings = []
    offset = 0
    for row in _read_episode_rows(root):
        episode = int(row["episode_index"])
        path = root / _episode_path(info, "data_path", episode)
        if not path.is_file():
            raise FileNotFoundError(f"{path}: episode {episode} is in meta/episodes.jsonl")
        rows = pq.ParquetFile(path).metadata.num_rows
        start = int(row.get("dataset_from_index", offset))
        offset += int(row.get("length", rows))
        if "index" not in pq.read_schema(path).names:
            findings.append(IndexFinding(episode, rows, rows, start, None))
            continue
        found = _scalar(pq.read_table(path, columns=["index"]), path, "index", np.int64)
        off = int((found != np.arange(start, start + rows)).sum())
        if off:
            first = int(found[0]) if len(found) else None
            findings.append(IndexFinding(episode, rows, off, start, first))
    return findings


def read_episode_rows(root: Path) -> list[dict[str, Any]]:
    """Rows of `meta/episodes.jsonl` as written, in episode_index order."""
    read_info(root)
    return _read_episode_rows(root)


def _episode_path(info: dict[str, Any], template: str, index: int, camera: str = "") -> str:
    chunk = index // int(info["chunks_size"])
    path: str = info[template].format(episode_chunk=chunk, episode_index=index, video_key=camera)
    return path


def _cameras(info: dict[str, Any]) -> list[str]:
    return [k for k, v in info.get("features", {}).items() if v.get("dtype") == "video"]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _read_episode_rows(root: Path, missing_ok: bool = False) -> list[dict[str, Any]]:
    path = root / "meta" / "episodes.jsonl"
    if not path.is_file():
        if missing_ok:
            return []
        raise FileNotFoundError(f"{path}: no LeRobot episodes.jsonl")
    return sorted(_read_jsonl(path), key=lambda r: int(r["episode_index"]))


def _read_task_rows(root: Path) -> list[dict[str, Any]]:
    path = root / "meta" / "tasks.jsonl"
    return _read_jsonl(path) if path.is_file() else []


def _read_tasks(root: Path) -> dict[int, str]:
    return {int(r["task_index"]): str(r["task"]) for r in _read_task_rows(root)}


def _column(table: pa.Table, path: Path, name: str) -> pa.Array:
    if name not in table.column_names:
        raise LeRobotFormatError(f"{path}: column {name!r} missing")
    column = table.column(name).combine_chunks()
    if column.null_count:
        raise LeRobotFormatError(f"{path}: column {name!r} has {column.null_count} null rows")
    return column


def _vector(table: pa.Table, path: Path, name: str, width: int) -> NDArray[np.float32]:
    column = _column(table, path, name)
    kind = column.type
    if not (pa.types.is_list(kind) or pa.types.is_large_list(kind)
            or pa.types.is_fixed_size_list(kind)):
        raise LeRobotFormatError(f"{path}: column {name!r} is {kind}, expected a list of {width}")
    widths = set(pc.list_value_length(column).to_pylist())
    if widths - {width}:
        raise LeRobotFormatError(
            f"{path}: column {name!r} has width {sorted(widths)}, expected {width}"
        )
    values = _exact(column.flatten().to_numpy(zero_copy_only=False), np.float32, path, name)
    return values.reshape(-1, width)


def _scalar(table: pa.Table, path: Path, name: str, dtype: type[Any]) -> NDArray[Any]:
    column = _column(table, path, name)
    if pa.types.is_list(column.type) or pa.types.is_fixed_size_list(column.type):
        if set(pc.list_value_length(column).to_pylist()) - {1}:
            raise LeRobotFormatError(f"{path}: column {name!r} is not one value per row")
        column = column.flatten()
    return _exact(column.to_numpy(zero_copy_only=False), dtype, path, name)


def _exact(values: NDArray[Any], dtype: type[Any], path: Path, name: str) -> NDArray[Any]:
    """values as dtype, or LeRobotFormatError if the cast changes any of them."""
    cast = np.asarray(values, dtype=dtype)
    if cast.dtype == values.dtype:
        return cast
    source = np.asarray(values, dtype=np.float64)
    back = cast.astype(np.float64)
    changed = ~((back == source) | (np.isnan(back) & np.isnan(source)))
    if changed.any():
        loss = float(np.max(np.abs(back[changed] - source[changed])))
        raise LeRobotFormatError(
            f"{path}: column {name!r} is {values.dtype}; {int(changed.sum())} of {values.size}"
            f" values change when read as {np.dtype(dtype).name} (largest change {loss:g})"
        )
    return cast


def _check_episode_index(table: pa.Table, path: Path, index: int) -> None:
    if "episode_index" not in table.column_names:
        return
    found = set(_scalar(table, path, "episode_index", np.int64).tolist())
    if found - {index}:
        raise LeRobotFormatError(
            f"{path}: column 'episode_index' holds {sorted(found)}, meta says {index}"
        )


def _task_of(table: pa.Table, row: dict[str, Any], tasks: dict[int, str], path: Path) -> str:
    if "task_index" in table.column_names and table.num_rows:
        index = int(_scalar(table, path, "task_index", np.int64)[0])
        if index in tasks:
            return tasks[index]
    listed = row.get("tasks") or []
    if listed:
        first = listed[0]
        if isinstance(first, str):
            return first
        if int(first) in tasks:
            return tasks[int(first)]
    instruction = row.get("instruction")
    if isinstance(instruction, dict) and "task" in instruction:
        return str(instruction["task"])
    raise LeRobotFormatError(f"{path}: no task for episode {row['episode_index']} in meta")


def _video_frames(
    root: Path, info: dict[str, Any], cameras: list[str], row: dict[str, Any]
) -> dict[str, int]:
    index = int(row["episode_index"])
    counts = {}
    for camera in cameras:
        video = root / _episode_path(info, "video_path", index, camera)
        counts[camera] = mp4_frame_count(video) if video.is_file() else 0
    return counts


def mp4_frame_count(path: Path) -> int:
    """Frames of the video track of an mp4, from its `stsz` (or `stz2`) box; no decoding.

    Walks moov/trak/mdia: the track whose `hdlr` is `vide`, then minf/stbl. A
    fragmented mp4 (moov/mvex) keeps its samples in moof boxes and is refused.
    """
    with path.open("rb") as f:
        moov = _child(f, 0, path.stat().st_size, b"moov", path)
        if moov is None:
            raise LeRobotFormatError(f"{path}: no moov box, not an mp4 the reader can walk")
        if _child(f, *moov, b"mvex", path) is not None:
            raise LeRobotFormatError(f"{path}: fragmented mp4, frame count not in stsz")
        for kind, start, end in _boxes(f, *moov, path):
            mdia = _child(f, start, end, b"mdia", path) if kind == b"trak" else None
            hdlr = None if mdia is None else _child(f, *mdia, b"hdlr", path)
            if mdia is None or hdlr is None:
                continue
            f.seek(hdlr[0] + 8)  # version/flags, pre_defined
            if f.read(4) != b"vide":
                continue
            stbl = _descend(f, mdia, (b"minf", b"stbl"), path)
            sizes = stbl and (_child(f, *stbl, b"stsz", path) or _child(f, *stbl, b"stz2", path))
            if not sizes:
                raise LeRobotFormatError(f"{path}: video track has no stsz box")
            f.seek(sizes[0] + 8)  # version/flags, sample_size (stsz) or field_size (stz2)
            count: int = struct.unpack(">I", f.read(4))[0]
            return count
    raise LeRobotFormatError(f"{path}: no video track")


def _boxes(f: IO[bytes], start: int, end: int, path: Path) -> Iterator[tuple[bytes, int, int]]:
    """(type, payload start, box end) of the boxes between start and end."""
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        size, kind = struct.unpack(">I4s", f.read(8))
        header = 8
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header or pos + size > end:
            raise LeRobotFormatError(f"{path}: broken mp4 box {kind!r} at byte {pos}")
        yield kind, pos + header, pos + size
        pos += size


def _child(
    f: IO[bytes], start: int, end: int, kind: bytes, path: Path
) -> tuple[int, int] | None:
    for found, payload, box_end in _boxes(f, start, end, path):
        if found == kind:
            return payload, box_end
    return None


def _descend(
    f: IO[bytes], box: tuple[int, int], kinds: tuple[bytes, ...], path: Path
) -> tuple[int, int] | None:
    current: tuple[int, int] | None = box
    for kind in kinds:
        if current is None:
            return None
        current = _child(f, *current, kind, path)
    return current


def _check_frames(frames: EpisodeFrames, path: Path) -> int:
    length = len(frames.timestamp)
    expected = {
        "timestamp": (length,),
        "frame_index": (length,),
        "states": (length, STATE_DIM),
        "action": (length, ACTION_DIM),
    }
    for name, shape in expected.items():
        found = getattr(frames, name).shape
        if found != shape:
            raise LeRobotFormatError(
                f"{path}: column {name!r} of episode {frames.episode_index} has shape"
                f" {found}, expected {shape}"
            )
    return length


def _list_array(values: NDArray[np.float32]) -> pa.Array:
    rows, width = values.shape
    offsets = pa.array(np.arange(rows + 1) * width, pa.int32())
    flat = pa.array(values.reshape(-1).astype(np.float64), pa.float64())
    return pa.ListArray.from_arrays(offsets, flat)


def _rows_by_frame(old: pa.Table, frame_index: NDArray[np.int64], path: Path) -> pa.Array:
    positions: dict[int, int] = {}
    for position, value in enumerate(_scalar(old, path, "frame_index", np.int64).tolist()):
        positions.setdefault(value, position)
    missing = sorted(set(frame_index.tolist()) - positions.keys())
    if missing:
        raise LeRobotFormatError(
            f"{path}: column 'frame_index' has no rows {missing[:5]} to carry other columns from"
        )
    return pa.array([positions[f] for f in frame_index.tolist()], pa.int64())


def _renumbering(
    old: pa.Table | None, index: pa.Array, frames: EpisodeFrames, path: Path
) -> dict[str, Any] | None:
    """The lineage row for the index values this write changes, or None if it changes none."""
    if old is None or "index" not in old.column_names or not len(index):
        return None
    before = _scalar(old, path, "index", np.int64)[
        _rows_by_frame(old, frames.frame_index, path).to_numpy()
    ]
    after = index.to_numpy()
    changed = int((before != after).sum())
    if not changed:
        return None
    return {
        "change": "index_renumbered",
        "episode_index": frames.episode_index,
        "file": path.name,
        "rule": INDEX_RULE,
        "rows_changed": changed,
        "rows": len(after),
        "old_first": int(before[0]),
        "new_first": int(after[0]),
        "decision": "Q7 proposal, pending PO",
    }


def _cast_like(table: pa.Table, old: pa.Table) -> pa.Table:
    """Keep the column types and schema metadata (HF features) of the file replaced."""
    fields = [
        old.schema.field(f.name) if f.name in old.column_names else f for f in table.schema
    ]
    return table.cast(pa.schema(fields, metadata=old.schema.metadata))

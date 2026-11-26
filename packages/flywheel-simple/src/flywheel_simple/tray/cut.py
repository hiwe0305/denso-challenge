"""Cut the place segment out of a full tray release into a derived release (DA-46 task 3, AC 3).

Each kept episode of the parent release (`tray_s1_<hash12>`, DA-33's export) keeps its
frames from ARRIVE_B (else LOWER, when the planner skipped ARRIVE_B) minus a lead of
`lead_s`, to its end. Phase entry times come from the batch's `gen_log.jsonl` rows
(`phases`, written since DA-46): frame k of an episode is recorded at planner time
k / fps, so a phase entered at t starts at frame round(t * fps).

The derived release keeps the parent's Psi0 LeRobot v2.1 layout, so the train path
(`flywheel_psi0.tray.demo_sets`, `scripts/he/demo_subset.py`, `cplus_cut`) reads it
as it reads the parent:

- parquet: rows [start, length) of the parent's, `frame_index`, `timestamp`,
  `episode_index`, `index` and `next.done` renumbered, the other columns as they were,
  the parent's schema;
- video: the parent's decoded, the first `start` frames dropped, the rest encoded as
  the recorder does (h264, rate fps, the parent's size and pix_fmt);
- stats: the four files of `flywheel.data.inject.stats`, recomputed on the cut data
  with the same recipe, every column accumulated in float64 (that lane is not imported:
  this runs in the SIMPLE venv);
- meta: info.json totals, episodes.jsonl rows, `flywheel_export.json` episodes under
  their new index plus `derived_from`, and `meta/flywheel_cut.json` with the parent's
  hash and each episode's source frame range;
- `release_manifest.json`, then the directory is named `tray_s1place_<hash12>`.

pyarrow and av are imported when used, so the module imports in the workspace.
"""

from __future__ import annotations

import importlib
import json
import math
import shutil
from collections.abc import Callable, Collection, Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.generate import LOG_NAME, read_log
from flywheel_simple.tray.release import MANIFEST, verify_manifest, write_manifest

FPS = 50
FROM_PHASES = ("ARRIVE_B", "LOWER")
SCHEMA = "tray-place-cut/1"
PREFIX = "tray_s1place_"
CUT_META = "flywheel_cut.json"
EXPORT_META = "flywheel_export.json"
COPIED_META = ("tasks.jsonl", "modality.json", "lang_map.json", "action_layout.json")
# The numeric features `flywheel.data.inject.stats` recomputes, in its order.
DATASET_COLUMNS = (
    "states",
    "action",
    "timestamp",
    "frame_index",
    "episode_index",
    "index",
    "task_index",
    "next.done",
)
EPISODE_COLUMNS = ("action", "timestamp")
STATE_DIM = 32
ACTION_DIM = 36

TrimVideo = Callable[[Path, Path, int, int, int], None]


def _mod(name: str) -> Any:
    return importlib.import_module(name)


def phase_frame(phases: Sequence[Sequence[Any]], fps: int = FPS) -> tuple[str, int]:
    """(phase, frame) where the place segment begins: entry of ARRIVE_B, else of LOWER."""
    entered = {str(p[0]): float(p[1]) for p in reversed(phases)}  # first entry wins
    for name in FROM_PHASES:
        if name in entered:
            return name, round(entered[name] * fps)
    raise ValueError(f"phases {[p[0] for p in phases]} hold none of {list(FROM_PHASES)}")


def cut_start(phases: Sequence[Sequence[Any]], lead_s: float, fps: int = FPS) -> int:
    """First kept frame: ARRIVE_B's (else LOWER's) minus round(lead_s * fps), at least 0."""
    if lead_s < 0:
        raise ValueError(f"lead_s {lead_s} < 0")
    return max(0, phase_frame(phases, fps)[1] - round(lead_s * fps))


def read_phase_rows(batch: Path, seeds: Collection[int]) -> dict[int, dict[str, Any]]:
    """The recorded gen_log row of each seed, from every shard of `batch`.

    A seed without a recorded row, recorded twice, or whose row has no `phases`
    (a batch generated before DA-46) is refused.
    """
    seeds = {int(s) for s in seeds}
    rows: dict[int, dict[str, Any]] = {}
    for log in sorted(Path(batch).glob(f"shard-*/{LOG_NAME}")):
        for row in read_log(log):
            seed = int(row["seed"])
            if seed not in seeds or not row.get("recorded"):
                continue
            if seed in rows:
                raise ValueError(f"{batch}: seed {seed} is recorded twice")
            rows[seed] = row
    missing = sorted(set(seeds) - rows.keys())
    if missing:
        raise ValueError(f"{batch}: no recorded {LOG_NAME} row for seeds {missing[:5]}")
    old = sorted(s for s, r in rows.items() if not r.get("phases"))
    if old:
        raise ValueError(
            f"{batch}: rows of seeds {old[:5]} have no phases; the batch predates DA-46"
        )
    return rows


def cut_table(table: Any, start: int, episode_index: int, first_index: int, fps: int) -> Any:
    """Rows [start, end) of one episode's parquet table, renumbered; the parent's schema."""
    pa = _mod("pyarrow")
    n = table.num_rows - start
    frame_index = np.arange(n, dtype=np.int64)
    done = np.zeros(n, dtype=bool)
    done[-1] = True
    renumbered: dict[str, NDArray[Any]] = {
        "frame_index": frame_index,
        "timestamp": frame_index * 1.0 / fps,
        "episode_index": np.full(n, episode_index, dtype=np.int64),
        "index": np.arange(first_index, first_index + n, dtype=np.int64),
        "next.done": done,
    }
    columns = [
        pa.array(renumbered[field.name], type=field.type)
        if field.name in renumbered
        else table.column(field.name).slice(start)
        for field in table.schema
    ]
    return pa.Table.from_arrays(columns, schema=table.schema)


def _floats(table: Any, name: str, width: int) -> NDArray[np.float32]:
    """A list column as (rows, width) float32, as the DA-03 reader reads it (exact)."""
    column = table.column(name).combine_chunks()
    values = np.asarray(column.flatten().to_numpy(zero_copy_only=False))
    cast = values.astype(np.float32)
    if not np.array_equal(cast.astype(values.dtype), values, equal_nan=True):
        raise ValueError(f"column {name!r} is not exact in float32")
    if cast.size != table.num_rows * width:
        raise ValueError(f"column {name!r} is not {width} wide")
    return cast.reshape(-1, width)


def _scalars(table: Any, name: str, dtype: type[Any]) -> NDArray[Any]:
    return np.asarray(table.column(name).to_numpy(), dtype=dtype)


# `flywheel.data.inject.stats.stats_block_f64`: SIMPLE postprocess_psi0_sonic.py's recipe,
# accumulated in float64. A deliberate departure from SIMPLE @ 6d10628, which accumulates
# a float32 input in float32, so its stats drift with the frame count: a column of 0.74
# in 300000 frames gets mean 0.7381 and std 0.0019. `_floats` gives states and action as
# float32. Integer and flag columns give the values SIMPLE's recipe gives.
def stats_block(arr: NDArray[Any]) -> dict[str, list[float]]:
    arr = np.asarray(arr, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    return {
        "mean": arr.mean(axis=0).astype(np.float32).tolist(),
        "std": arr.std(axis=0).astype(np.float32).tolist(),
        "min": arr.min(axis=0).astype(np.float32).tolist(),
        "max": arr.max(axis=0).astype(np.float32).tolist(),
        "q01": np.quantile(arr, 0.01, axis=0).astype(np.float32).tolist(),
        "q99": np.quantile(arr, 0.99, axis=0).astype(np.float32).tolist(),
    }


def episode_columns(table: Any) -> dict[str, NDArray[Any]]:
    """The numeric features of one cut table as `flywheel.data.inject.stats` reads them."""
    return {
        "states": _floats(table, "states", STATE_DIM),
        "action": _floats(table, "action", ACTION_DIM),
        "timestamp": _scalars(table, "timestamp", np.float64),
        "frame_index": _scalars(table, "frame_index", np.int64),
        "episode_index": _scalars(table, "episode_index", np.int64),
        "index": _scalars(table, "index", np.int64),
        "task_index": _scalars(table, "task_index", np.int64),
        "next.done": _scalars(table, "next.done", bool).astype(np.float32),
    }


def _ordered(keys: Sequence[str], computed: dict[str, Any], what: str) -> dict[str, Any]:
    """computed in the parent's key order, new keys last; a parent key not recomputed fails."""
    stale = [k for k in keys if k not in computed]
    if stale:
        raise ValueError(f"parent {what} holds {stale}, which the cut cannot recompute")
    return {k: computed[k] for k in [*keys, *[k for k in computed if k not in keys]]}


def write_stats(
    meta: Path, parent_meta: Path, episodes: Sequence[tuple[int, dict[str, NDArray[Any]]]]
) -> None:
    """The four stats files of `flywheel.data.inject.stats.write_stats`, from the cut data."""
    parent_rows = [
        json.loads(line)
        for line in (parent_meta / "episodes_stats.jsonl").read_text().splitlines()
        if line.strip()
    ]
    row_keys = list(parent_rows[0]["stats"]) if parent_rows else list(EPISODE_COLUMNS)
    rows = []
    for index, cols in sorted(episodes, key=lambda e: e[0]):
        n = len(cols["timestamp"])
        computed = {k: {**stats_block(cols[k]), "count": [n]} for k in EPISODE_COLUMNS}
        stats = _ordered(row_keys, computed, "episode stats")
        rows.append({"episode_index": index, "stats": stats})
    (meta / "episodes_stats.jsonl").write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows)
    )
    dataset = {
        name: stats_block(np.concatenate([cols[name] for _, cols in episodes], axis=0))
        for name in DATASET_COLUMNS
    }
    parent_stats = json.loads((parent_meta / "stats.json").read_text())
    merged = _ordered(list(parent_stats), dataset, "stats.json")
    for name in ("stats.json", "stats_psi0.json"):
        (meta / name).write_text(json.dumps(merged, indent=4))
    (meta / "relative_stats.json").write_text("{}")


def trim_video(src: Path, dst: Path, start: int, n: int, fps: int = FPS) -> None:
    """Write src's frames from `start` to dst, re-encoded as the recorder encodes.

    h264 at rate fps, the source's width, height and pix_fmt. Fails, leaving no
    dst, unless exactly n frames were written.
    """
    av = _mod("av")
    picture_none = _mod("av.video.frame").PictureType.NONE
    dst.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with av.open(str(src)) as source, av.open(str(dst), mode="w") as out:
            video = source.streams.video[0]
            stream = out.add_stream("h264", rate=fps)
            stream.width = video.codec_context.width
            stream.height = video.codec_context.height
            stream.pix_fmt = video.codec_context.pix_fmt
            for seen, frame in enumerate(source.decode(video)):
                if seen < start:
                    continue
                frame.pts = written  # the source's timestamps would carry its time base
                frame.time_base = Fraction(1, fps)
                frame.pict_type = picture_none  # no keyframe forced where the source had one
                for packet in stream.encode(frame):
                    out.mux(packet)
                written += 1
            for packet in stream.encode(None):
                out.mux(packet)
        if written != n:
            raise ValueError(f"{src}: {written} frames from frame {start}, expected {n}")
    except BaseException:
        dst.unlink(missing_ok=True)
        raise


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _episode_path(info: Mapping[str, Any], template: str, index: int, camera: str = "") -> str:
    chunk = index // int(info["chunks_size"])
    path: str = info[template].format(episode_chunk=chunk, episode_index=index, video_key=camera)
    return path


def _cameras(info: Mapping[str, Any]) -> list[str]:
    return [k for k, v in info["features"].items() if v.get("dtype") == "video"]


def _kept(
    parent: Path, seeds: Collection[int] | None
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    """The parent export's episodes to keep (ascending index) and the parent's meta rows."""
    exported = json.loads((parent / "meta" / EXPORT_META).read_text())["episodes"]
    by_seed = {int(e["seed"]): e for e in exported}
    if len(by_seed) != len(exported):
        raise ValueError(f"{parent}/meta/{EXPORT_META} lists a seed twice")
    wanted = None if seeds is None else {int(s) for s in seeds}
    if wanted is not None:
        unknown = sorted(wanted - by_seed.keys())
        if unknown:
            raise ValueError(f"seeds {unknown[:5]} are not in {parent.name}")
    kept = sorted(
        (e for e in exported if wanted is None or int(e["seed"]) in wanted),
        key=lambda e: int(e["episode_index"]),
    )
    if not kept:
        raise ValueError("no episode selected")
    rows = {int(r["episode_index"]): r for r in _read_jsonl(parent / "meta" / "episodes.jsonl")}
    return kept, rows


def cut_release(
    parent: Path,
    batch: Path,
    releases: Path,
    lead_s: float = 1.0,
    seeds: Collection[int] | None = None,
    selection: dict[str, Any] | None = None,
    trim: TrimVideo = trim_video,
) -> Path:
    """Write the place cut of `parent` as `<releases>/tray_s1place_<hash12>`; return it.

    `seeds` selects episodes of the parent (all when None); `selection` records where
    they came from in `meta/flywheel_cut.json`.
    """
    parent = Path(parent)
    if not verify_manifest(parent):
        raise ValueError(f"{parent}: files do not match {MANIFEST}")
    info = json.loads((parent / "meta" / "info.json").read_text())
    fps = int(info["fps"])
    kept, parent_rows = _kept(parent, seeds)
    phase_rows = read_phase_rows(batch, {int(e["seed"]) for e in kept})

    plan = []
    for new, exported in enumerate(kept):
        old, seed = int(exported["episode_index"]), int(exported["seed"])
        length = int(parent_rows[old]["length"])
        row = phase_rows[seed]
        if length != int(row["steps"]):
            raise ValueError(f"seed {seed}: {length} frames in the release, {row['steps']} steps")
        from_phase, frame = phase_frame(row["phases"], fps)
        start = cut_start(row["phases"], lead_s, fps)
        if start >= length:
            raise ValueError(f"seed {seed}: cut starts at frame {start} of {length}")
        plan.append((new, old, seed, length, start, from_phase, frame, row))

    staging = Path(releases) / f".staging-cut-{parent.name}"
    if staging.exists():
        raise FileExistsError(f"{staging} exists; remove it after checking what left it")
    try:
        (staging / "meta").mkdir(parents=True)
        release_hash = _write_cut(
            parent, info, plan, parent_rows, staging, batch, lead_s, selection, trim
        )
        final = Path(releases) / f"{PREFIX}{release_hash[:12]}"
        if final.exists():
            raise FileExistsError(f"{final} exists")
        staging.rename(final)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return final


def _write_cut(
    parent: Path,
    info: dict[str, Any],
    plan: list[tuple[int, int, int, int, int, str, int, dict[str, Any]]],
    parent_rows: dict[int, dict[str, Any]],
    out: Path,
    batch: Path,
    lead_s: float,
    selection: dict[str, Any] | None,
    trim: TrimVideo,
) -> str:
    pq = _mod("pyarrow.parquet")
    fps = int(info["fps"])
    meta = out / "meta"
    stats_input = []
    rows, cut_episodes = [], []
    offset = 0
    for new, old, seed, length, start, from_phase, frame, gen_row in plan:
        src = parent / _episode_path(info, "data_path", old)
        table = pq.read_table(src)
        if table.num_rows != length:
            raise ValueError(f"{src}: {table.num_rows} rows, episodes.jsonl says {length}")
        cut = cut_table(table, start, new, offset, fps)
        n = cut.num_rows
        dst = out / _episode_path(info, "data_path", new)
        dst.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(cut, dst)
        for camera in _cameras(info):
            trim(
                parent / _episode_path(info, "video_path", old, camera),
                out / _episode_path(info, "video_path", new, camera),
                start,
                n,
                fps,
            )
        stats_input.append((new, episode_columns(cut)))
        rows.append(
            {
                **parent_rows[old],
                "episode_index": new,
                "length": n,
                "dataset_from_index": offset,
                "dataset_to_index": offset + n - 1,
            }
        )
        cut_episodes.append(
            {
                "episode_index": new,
                "seed": seed,
                "parent_episode_index": old,
                "parent_length": length,
                "source_from_frame": start,
                "source_to_frame": length,
                "length": n,
                "phase_frame": frame,
                "from_phase": from_phase,
                "carry_offset": gen_row.get("carry_offset"),
                "carry_yaw": gen_row.get("carry_yaw"),
                "phases": gen_row["phases"],
            }
        )
        offset += n

    write_stats(meta, parent / "meta", stats_input)
    _write_meta(parent, info, rows, [(p[0], p[1]) for p in plan], offset, meta)
    parent_manifest = json.loads((parent / MANIFEST).read_text())
    marker = {
        "schema": SCHEMA,
        "parent": {"release_id": parent.name, "release_hash": parent_manifest["release_hash"]},
        "source_batch": Path(batch).name,
        "from_phases": list(FROM_PHASES),
        "lead_s": lead_s,
        "fps": fps,
        "selection": selection,
        "frames": {"parent": sum(p[3] for p in plan), "cut": offset},
        "episodes": cut_episodes,
    }
    (meta / CUT_META).write_text(json.dumps(marker, indent=2) + "\n")
    return write_manifest(out)


def _write_meta(
    parent: Path,
    info: dict[str, Any],
    rows: list[dict[str, Any]],
    renumber: list[tuple[int, int]],
    frames: int,
    meta: Path,
) -> None:
    n = len(rows)
    new_info = {
        **info,
        "total_episodes": n,
        "total_frames": frames,
        "total_videos": n * len(_cameras(info)),
        "total_chunks": math.ceil(n / int(info["chunks_size"])),
    }
    if "splits" in info:
        new_info["splits"] = {"train": f"0:{n}"}
    (meta / "info.json").write_text(json.dumps(new_info, indent=4))
    (meta / "episodes.jsonl").write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows)
    )
    for name in COPIED_META:
        if (parent / "meta" / name).is_file():
            shutil.copyfile(parent / "meta" / name, meta / name)
    export = json.loads((parent / "meta" / EXPORT_META).read_text())
    by_index = {int(e["episode_index"]): e for e in export["episodes"]}
    export["episodes"] = [{**by_index[old], "episode_index": new} for new, old in renumber]
    export["derived_from"] = parent.name
    (meta / EXPORT_META).write_text(json.dumps(export, indent=2) + "\n")

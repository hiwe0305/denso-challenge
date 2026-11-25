"""Recompute a copy's stats files from its own data, as SIMPLE's export writes them.

Copied from SIMPLE `scripts/postprocess_psi0_sonic.py` @ 6d10628 (MIT; sha256
eb9fad60...aeb681): `stats_block` and the lists it runs over. A benchmark copy whose
stats were copied from the source would give every changed episode away to anyone who
recomputes them, so both copies get stats of their own data.

    meta/episodes_stats.jsonl   per episode: action, timestamp (+ count), compact JSON
    meta/stats.json             over the dataset: states, action, timestamp, frame_index,
                                episode_index, index, task_index, next.done
    meta/stats_psi0.json        the same content
    meta/relative_stats.json    {}

Every column is accumulated in float64 (`stats_block_f64`), a deliberate departure from
SIMPLE @ 6d10628: SIMPLE's `stats_block` accumulates a float32 input in float32, so its
action stats drift with the frame count (a column of 0.74 in 300000 frames gets mean
0.7381 and std 0.0019), and Psi0 may normalise with them. `stats_block` itself stays
SIMPLE's recipe, accumulating in the precision it is given: the export checklist runs
it at both precisions to recognise stats SIMPLE wrote.

`index` is the one the parquet holds, found through the DA-03 reader's `check_index` (in
a copy, the writer's dataset_from_index + row). psi-data e78fb93's own stats.json
follows from its parquet in float64 for `states` and in float32 for `action`, as SIMPLE
computes them (tests/unit/inject/test_source_stats.py).
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.data.ingest.lerobot import check_index, iter_episodes, read_episode_rows
from numpy.typing import NDArray

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


def stats_block(arr: NDArray[Any]) -> dict[str, list[float]]:
    """SIMPLE's `stats_block`, verbatim: accumulates in the input's precision.

    The export checklist uses it to recompute SIMPLE's stats; the files this module
    writes use `stats_block_f64`.
    """
    arr = np.asarray(arr)
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


def stats_block_f64(arr: NDArray[Any]) -> dict[str, list[float]]:
    """`stats_block` accumulated in float64, results as float32: what the stats files hold.

    Departs from SIMPLE @ 6d10628 on purpose, which accumulates float32 inputs in float32.
    Integer and flag columns give the values SIMPLE's recipe gives.
    """
    return stats_block(np.asarray(arr, dtype=np.float64))


def compute_stats(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Per-episode rows and dataset stats of the numeric features, from the data at root."""
    meta = root / "meta"
    tasks = {
        json.loads(line)["task"]: int(json.loads(line)["task_index"])
        for line in (meta / "tasks.jsonl").read_text().splitlines()
        if line.strip()
    }
    # `index` as the parquet holds it: the meta's dataset_from_index, or where the DA-03
    # reader finds an episode off LeRobot's rule (psi-data, Q7), the first index it holds.
    starts = {
        int(r["episode_index"]): int(r["dataset_from_index"]) for r in read_episode_rows(root)
    }
    for finding in check_index(root):
        if finding.found_first is not None:
            starts[finding.episode_index] = finding.found_first
    columns: dict[str, list[NDArray[Any]]] = {name: [] for name in DATASET_COLUMNS}
    rows: list[dict[str, Any]] = []
    for frames in iter_episodes(root):
        n = len(frames.timestamp)
        rows.append(
            {
                "episode_index": frames.episode_index,
                "stats": {
                    "action": {**stats_block_f64(frames.action), "count": [n]},
                    "timestamp": {**stats_block_f64(frames.timestamp), "count": [n]},
                },
            }
        )
        done = np.zeros(n, dtype=bool)
        done[-1] = True
        start = starts[frames.episode_index]
        for name, values in (
            ("states", frames.states),
            ("action", frames.action),
            ("timestamp", frames.timestamp),
            ("frame_index", frames.frame_index),
            ("episode_index", np.full(n, frames.episode_index, dtype=np.int64)),
            ("index", np.arange(start, start + n, dtype=np.int64)),
            ("task_index", np.full(n, tasks[frames.task], dtype=np.int64)),
            ("next.done", done.astype(np.float32)),
        ):
            columns[name].append(values)
    rows.sort(key=lambda r: int(r["episode_index"]))
    dataset = {name: stats_block_f64(np.concatenate(v, axis=0)) for name, v in columns.items()}
    return rows, dataset


def write_stats(
    root: Path, source: Path | None = None, owners: dict[int, int] | None = None
) -> None:
    """Write the four stats files of the LeRobot dataset at root from its data.

    Features the lane cannot recompute (image stats need decoded video) are carried from
    `source`'s files: per episode from the episode whose video the copy now holds,
    `owners[index]` for a duplicate, else the same index. Each file keeps the source's
    feature order; recomputed features take their place in it.
    """
    meta = root / "meta"
    rows, dataset = compute_stats(root)
    shipped_rows: dict[int, dict[str, Any]] = {}
    shipped: dict[str, Any] = {}
    if source is not None and (source / "meta" / "episodes_stats.jsonl").is_file():
        for line in (source / "meta" / "episodes_stats.jsonl").read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                shipped_rows[int(row["episode_index"])] = row["stats"]
    if source is not None and (source / "meta" / "stats.json").is_file():
        shipped = json.loads((source / "meta" / "stats.json").read_text())
    for row in rows:
        index = int(row["episode_index"])
        carried = shipped_rows.get((owners or {}).get(index, index), {})
        row["stats"] = _merge(carried, row["stats"])
    (meta / "episodes_stats.jsonl").write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows)
    )
    merged = _merge(shipped, dataset)
    for name in ("stats.json", "stats_psi0.json"):
        (meta / name).write_text(json.dumps(merged, indent=4))
    (meta / "relative_stats.json").write_text("{}")


def _merge(shipped: dict[str, Any], computed: dict[str, Any]) -> dict[str, Any]:
    """Shipped features in their order, recomputed ones replacing theirs, new ones last."""
    merged = {name: computed.get(name, value) for name, value in shipped.items()}
    merged.update({name: value for name, value in computed.items() if name not in merged})
    return merged

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

`index` is the writer's (dataset_from_index + row, LeRobot v2.1), read from the meta
rows. psi-data e78fb93's own stats.json does not follow from its parquet for `states`
(mean differs by up to 3.6e-4; likely taken before the export's downsampling), so the
source's files are not a reference for the copies.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.data.ingest.lerobot import iter_episodes, read_episode_rows
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


def write_stats(root: Path) -> None:
    """Write the four stats files of the LeRobot dataset at root from its data."""
    meta = root / "meta"
    tasks = {
        json.loads(line)["task"]: int(json.loads(line)["task_index"])
        for line in (meta / "tasks.jsonl").read_text().splitlines()
        if line.strip()
    }
    starts = {
        int(r["episode_index"]): int(r["dataset_from_index"]) for r in read_episode_rows(root)
    }
    columns: dict[str, list[NDArray[Any]]] = {name: [] for name in DATASET_COLUMNS}
    rows = []
    for frames in iter_episodes(root):
        n = len(frames.timestamp)
        rows.append(
            {
                "episode_index": frames.episode_index,
                "stats": {
                    "action": {**stats_block(frames.action), "count": [n]},
                    "timestamp": {**stats_block(frames.timestamp), "count": [n]},
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
    rows.sort(key=lambda r: int(r["episode_index"]))  # type: ignore[call-overload]
    (meta / "episodes_stats.jsonl").write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows)
    )
    dataset = {name: stats_block(np.concatenate(v, axis=0)) for name, v in columns.items()}
    for name in ("stats.json", "stats_psi0.json"):
        (meta / name).write_text(json.dumps(dataset, indent=4))
    (meta / "relative_stats.json").write_text("{}")

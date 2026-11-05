"""How closely replayed episodes reproduce their parents, frame by frame (DA-35 task 9).

For every saved episode of an S2 run (generate_s2.py) loads the replay and its
parent and compares them over their common frames: whether the wrist targets,
sticks, base and tray trajectories are bit-identical, the largest base and tray
position differences, and the frame counts. Writes `<run>/replay_compare.json`.

    PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \\
        scripts/g0/tray/s2/compare_replay.py --run fwdata/simple/tray/s2/replay-1104 \\
        --parents fwdata/simple/tray/virtual/parents-1103b
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from flywheel_simple.tray.s2.parents import ParentDemo, load_parent, parent_dataset


def compare(replay: ParentDemo, parent: ParentDemo) -> dict[str, Any]:
    n = min(replay.frames, parent.frames)
    fields = ("eef", "navigate", "base_pose", "tray_pose")
    identical = {f: bool(np.array_equal(getattr(replay, f)[:n], getattr(parent, f)[:n])) for f in fields}
    base = np.linalg.norm(replay.base_pose[:n, :2] - parent.base_pose[:n, :2], axis=1)
    tray = np.linalg.norm(replay.tray_pose[:n, :3] - parent.tray_pose[:n, :3], axis=1)
    return {
        "frames": replay.frames,
        "parent_frames": parent.frames,
        "identical": identical,
        "max_base_xy_m": round(float(base.max()), 4),
        "max_tray_m": round(float(tray.max()), 4),
        "final_tray_m": round(float(tray[-1]), 4),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--parents", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = []
    for shard in sorted(args.run.glob("shard-*")):
        attempts = [json.loads(x) for x in (shard / "attempts.jsonl").read_text().splitlines() if x]
        for a in attempts:
            if a["episode_index"] is None:
                continue
            pid = a["parent_episode"]
            _, p_shard, p_index = pid.split("/")
            parent = load_parent(parent_dataset(args.parents, p_shard), int(p_index), pid)
            replay = load_parent(parent_dataset(args.run, shard.name), a["episode_index"], "replay")
            rows.append({"parent_episode": pid, **compare(replay, parent)})
    exact = sum(all(r["identical"].values()) for r in rows)
    report = {
        "episodes": len(rows),
        "bit_identical": exact,
        "same_length": sum(r["frames"] == r["parent_frames"] for r in rows),
        "max_base_xy_m": max((r["max_base_xy_m"] for r in rows), default=None),
        "max_final_tray_m": max((r["final_tray_m"] for r in rows), default=None),
        "rows": rows,
    }
    (args.run / "replay_compare.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

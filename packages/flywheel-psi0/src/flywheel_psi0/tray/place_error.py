"""Final tray pose against the target zone, per rollout of an eval batch (tray.md 16).

A side metric, not a reading rule: how far the tray ended from the target zone on table B, in
the terms of the scorer's `in_target` check (`flywheel_simple.tray.predicates`):

    distance   |tray_xy - target_xy| of the tray's final position, m
    yaw error  min(|yaw - target_yaw|, |yaw - target_yaw - pi|), wrapped, deg (the tray is
               symmetric under a half turn)

The target pose is rebuilt from (level, seed) with `sample_episode`, as the env builds the scene.
Rollouts are the ones `eval_results` reads: per condition, the earliest finished attempt.

    python -m flywheel_psi0.tray.place_error <plan> --set <eval set> --out <eval_batch dir>
        [--json <file>]

`flywheel_simple` is imported when the command runs, as `eval_driver` does.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from flywheel_psi0.tray.eval_batch import chunk_plan, phases_for
from flywheel_psi0.tray.eval_results import Rollout, collect


def yaw_of(quat: Sequence[float]) -> float:
    """Yaw of a (w, x, y, z) quaternion, as the scorer takes it: atan2(R[1,0], R[0,0])."""
    w, x, y, z = np.asarray(quat, dtype=np.float64) / np.linalg.norm(quat)
    return math.atan2(2 * (x * y + w * z), 1 - 2 * (y * y + z * z))


def wrapped(a: float, b: float) -> float:
    """|a - b| wrapped to [0, pi]."""
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def pose_error(
    tray_pos: Sequence[float], tray_quat: Sequence[float], target: tuple[float, float, float]
) -> tuple[float, float]:
    """(distance m, yaw error deg) of the final tray pose to a target (x, y, yaw)."""
    tx, ty, tyaw = target
    distance = math.hypot(float(tray_pos[0]) - tx, float(tray_pos[1]) - ty)
    yaw = yaw_of(tray_quat)
    error = min(wrapped(yaw, tyaw), wrapped(yaw, tyaw + math.pi))
    return distance, math.degrees(error)


def rows_for(
    rollouts: Sequence[Rollout], target_of: Any, pos_tol: float, yaw_tol_deg: float
) -> list[dict[str, Any]]:
    """One row per rollout: level, seed, label, reached steps, distance, yaw error, in tolerance."""
    out = []
    for r in rollouts:
        distance, yaw = pose_error(
            r.row["tray_pos"], r.row["tray_quat"], target_of(r.level, r.seed)
        )
        steps = r.row.get("scorer_steps") or []
        out.append(
            {
                "level": r.level,
                "seed": r.seed,
                "success": bool(r.row.get("success")),
                "failure": r.row.get("failure"),
                "reach_b": bool(len(steps) > 4 and all(steps[:5])),
                "distance_m": round(distance, 4),
                "yaw_error_deg": round(yaw, 2),
                "in_tolerance": distance <= pos_tol and yaw <= yaw_tol_deg,
            }
        )
    return out


def summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Median and 10-90 % range of distance and yaw error, and how many are in tolerance."""
    if not rows:
        return {"n": 0}
    d = np.array([r["distance_m"] for r in rows])
    y = np.array([r["yaw_error_deg"] for r in rows])
    return {
        "n": len(rows),
        "distance_m": [round(float(v), 4) for v in np.percentile(d, [10, 50, 90])],
        "yaw_error_deg": [round(float(v), 2) for v in np.percentile(y, [10, 50, 90])],
        "in_tolerance": sum(bool(r["in_tolerance"]) for r in rows),
    }


def groups(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Summaries by level, for rollouts that reached table B, and by failure label."""
    out: dict[str, dict[str, Any]] = {}
    for level in sorted({r["level"] for r in rows}):
        out[f"level {level}"] = summary([r for r in rows if r["level"] == level])
    out["levels 1-2, reach_b"] = summary([r for r in rows if r["level"] in (1, 2) and r["reach_b"]])

    def label_of(r: dict[str, Any]) -> str:
        return "success" if r["success"] else str(r["failure"])

    for label in sorted({label_of(r) for r in rows}):
        sel = [r for r in rows if r["level"] in (1, 2) and label_of(r) == label]
        if sel:
            out[f"levels 1-2, {label}"] = summary(sel)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    from flywheel_simple.tray.config import TrayConfig
    from flywheel_simple.tray.randomize import sample_episode

    from flywheel_psi0.tray.runplan import TrayRunPlan

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--set", type=Path, required=True, help="eval set of eval_set.py")
    parser.add_argument("--out", type=Path, required=True, help="eval_batch directory")
    parser.add_argument("--chunk", type=int, default=10)
    parser.add_argument("--json", type=Path, help="write the rows and the summaries here")
    args = parser.parse_args(argv)
    TrayRunPlan.load(args.plan)  # same plan check as eval_results
    rows = [json.loads(line) for line in (args.set / "conditions.jsonl").read_text().splitlines()]
    chosen, _, missing = collect(args.out, chunk_plan(rows, args.chunk, phases_for(rows)))
    cfg = TrayConfig.load()

    def target_of(level: int, seed: int) -> tuple[float, float, float]:
        t = sample_episode(cfg, level, seed).target_pose
        return float(t.x), float(t.y), float(t.yaw)

    result_rows = rows_for(chosen, target_of, cfg.target_pos_tol, cfg.target_yaw_tol_deg)
    result: dict[str, Any] = {
        "tolerance": {"distance_m": cfg.target_pos_tol, "yaw_error_deg": cfg.target_yaw_tol_deg},
        "missing": missing,
        "groups": groups(result_rows),
        "rows": result_rows,
    }
    if args.json is not None:
        args.json.write_text(json.dumps(result, indent=1) + "\n")
    print(
        "| Nhóm | n | Khoảng cách p10 / p50 / p90 (cm) | Sai số góc p10 / p50 / p90 (°) "
        "| Trong dung sai |"
    )
    print("|---|---|---|---|---|")
    for name, s in result["groups"].items():
        if s["n"]:
            d = " / ".join(f"{100 * v:.1f}" for v in s["distance_m"])
            y = " / ".join(f"{v:.1f}" for v in s["yaw_error_deg"])
            print(f"| {name} | {s['n']} | {d} | {y} | {s['in_tolerance']} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())

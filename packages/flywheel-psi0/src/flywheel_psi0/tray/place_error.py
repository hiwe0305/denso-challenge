"""Final tray pose against the target zone, per rollout of an eval batch (tray.md 16).

A side metric, not a reading rule: how far the tray ended from the target zone on table B, in
the terms of the scorer's `in_target` check (`flywheel_simple.tray.predicates`):

    distance   |tray_xy - target_xy| of the tray's final position, m
    yaw error  min(|yaw - target_yaw|, |yaw - target_yaw - pi|), wrapped, deg (the tray is
               symmetric under a half turn)

The target pose is rebuilt from (level, seed) as the env builds the scene, by the scene of the
rollout's `task_uid` (`target_for`, DA-47): `sample_jig_episode` on the jig scene
(JIG_TASK_UID), `sample_episode` otherwise (the `+zone1` scene; rows without `task_uid` were
written before DA-47 and are zone1). A batch mixing the two scenes is refused (`scene_of`).
Rollouts are the ones `eval_results` reads: per condition and repeat, the earliest finished
attempt; `--repeats N` reads the `.r<k>` repeats of `eval_batch --repeats`.

    python -m flywheel_psi0.tray.place_error <plan> --set <eval set> --out <eval_batch dir>
        [--json <file>] [--curve] [--repeats N]

`--curve` adds the relaxed success of rule (c) of the 60k pair (tray.md 19.2): per position
tolerance of RELAXED_M, the rollouts that succeeded or failed as L-PLACE-POSE within that
distance and the scorer's yaw tolerance. Other failures are never relaxed. A side figure,
"relaxed" ("nới") wherever it is reported, never the primary metric.

`flywheel_simple` is imported when the command runs, as `eval_driver` does.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from flywheel_psi0.tray.eval_batch import chunk_plan, phases_for, with_repeats
from flywheel_psi0.tray.eval_results import (
    UNRECORDED,
    Rollout,
    collect,
    mismatch_warning,
    plan_mismatch,
    repeats_note,
    scorer_version,
)

RELAXED_M = (0.05, 0.075, 0.10, 0.15, 0.20)  # tray.md 19.2 (c): 5 cm is the scorer's own
# flywheel_simple.tray.jig_task.JIG_TASK_UID; jig_task imports SIMPLE, not in this venv.
JIG_TASK_UID = "g1_wholebody_tray_transfer_jig_teleop"
Target = tuple[float, float, float]  # x, y, yaw of the target zone
TargetOf = Callable[[int, int], Target]


def scene_of(rollouts: Sequence[Rollout]) -> str | None:
    """The one `task_uid` of the rollouts' rows (None: zone1); refuses a batch of two scenes."""
    uids = {r.row.get("task_uid") for r in rollouts}
    scenes = {JIG_TASK_UID if u == JIG_TASK_UID else None for u in uids}
    if len(scenes) > 1:
        shown = sorted(uids, key=lambda u: (u is None, u or ""))
        raise ValueError(f"rollouts mix scenes, task_uid {shown} (None: zone1, before DA-47)")
    return scenes.pop() if scenes else None


def target_for(task_uid: str | None) -> TargetOf:
    """(level, seed) -> target (x, y, yaw) on the scene of `task_uid`, as the env samples it."""
    from flywheel_simple.tray.config import TrayConfig
    from flywheel_simple.tray.randomize import sample_episode

    cfg = TrayConfig.load()
    if task_uid == JIG_TASK_UID:
        from flywheel_simple.tray.jig import JigConfig, sample_jig_episode

        jig = JigConfig.load()

        def jig_target(level: int, seed: int) -> Target:
            t = sample_jig_episode(cfg, jig, level, seed).target_pose
            return float(t.x), float(t.y), float(t.yaw)

        return jig_target

    def zone1_target(level: int, seed: int) -> Target:
        t = sample_episode(cfg, level, seed).target_pose
        return float(t.x), float(t.y), float(t.yaw)

    return zone1_target


def yaw_of(quat: Sequence[float]) -> float:
    """Yaw of a (w, x, y, z) quaternion, as the scorer takes it: atan2(R[1,0], R[0,0])."""
    w, x, y, z = np.asarray(quat, dtype=np.float64) / np.linalg.norm(quat)
    return math.atan2(2 * (x * y + w * z), 1 - 2 * (y * y + z * z))


def wrapped(a: float, b: float) -> float:
    """|a - b| wrapped to [0, pi]."""
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def pose_error(
    tray_pos: Sequence[float], tray_quat: Sequence[float], target: Target
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
                "repeat": r.repeat,
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


def tolerance_curve(
    rows: Sequence[dict[str, Any]], yaw_tol_deg: float, tolerances_m: Sequence[float] = RELAXED_M
) -> list[dict[str, Any]]:
    """Relaxed successes per position tolerance; only L-PLACE-POSE is relaxed, yaw is not."""

    def relaxed(r: dict[str, Any], tol: float) -> bool:
        return bool(r["success"]) or (
            r["failure"] == "L-PLACE-POSE"
            and r["distance_m"] <= tol
            and r["yaw_error_deg"] <= yaw_tol_deg
        )

    return [
        {
            "distance_m": tol,
            "yaw_error_deg": yaw_tol_deg,
            "n": len(rows),
            "relaxed_successes": sum(relaxed(r, tol) for r in rows),
        }
        for tol in tolerances_m
    ]


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

    from flywheel_psi0.tray.runplan import TrayRunPlan

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--set", type=Path, required=True, help="eval set of eval_set.py")
    parser.add_argument("--out", type=Path, required=True, help="eval_batch directory")
    parser.add_argument("--chunk", type=int, default=10)
    parser.add_argument("--json", type=Path, help="write the rows and the summaries here")
    parser.add_argument(
        "--curve", action="store_true", help="relaxed success per tolerance (tray.md 19.2 c)"
    )
    parser.add_argument(
        "--repeats", type=int, default=1, help="rollouts per condition, as run (DA-42)"
    )
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    plan = TrayRunPlan.load(args.plan)  # same plan check as eval_results
    rows = [json.loads(line) for line in (args.set / "conditions.jsonl").read_text().splitlines()]
    chunks = chunk_plan(rows, args.chunk, phases_for(rows))
    chosen, _, missing = collect(args.out, with_repeats(chunks, args.repeats))
    cfg = TrayConfig.load()
    scene = scene_of(chosen)  # refuses a directory of two scenes
    result_rows = rows_for(chosen, target_for(scene), cfg.target_pos_tol, cfg.target_yaw_tol_deg)
    version = scorer_version(chosen)  # refuses a directory of two scorer versions
    note = repeats_note(args.out, chunks, args.repeats)
    result: dict[str, Any] = {
        "scorer_version": version,
        "scorer_version_note": UNRECORDED if version is None else None,
        "task_uid": scene,
        "repeats": args.repeats,
        "repeats_note": note,
        "tolerance": {"distance_m": cfg.target_pos_tol, "yaw_error_deg": cfg.target_yaw_tol_deg},
        "missing": missing,
        "groups": groups(result_rows),
        "rows": result_rows,
    }
    if args.curve:
        headline = [r for r in result_rows if r["level"] in (1, 2)]
        result["relaxed_curve"] = {
            "label": "relaxed (nới): a side figure, not the primary metric",
            "levels 1-2": tolerance_curve(headline, cfg.target_yaw_tol_deg),
            **{
                f"level {lv}": tolerance_curve(
                    [r for r in result_rows if r["level"] == lv], cfg.target_yaw_tol_deg
                )
                for lv in sorted({r["level"] for r in result_rows})
            },
        }
    mismatch = plan_mismatch(plan, args.plan, rows)
    if mismatch is not None:
        result["plan_mismatch"] = mismatch
    if args.json is not None:
        args.json.write_text(json.dumps(result, indent=1) + "\n")
    if mismatch is not None:
        warning = mismatch_warning(mismatch)
        print(warning)
        print(warning, file=sys.stderr)
    print(f"Bộ chấm khay: phiên bản {version}" if version is not None else UNRECORDED)
    if note is not None:
        print(note)
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
    if args.curve:
        print("\nThành công nới (không phải chỉ số chính), góc giữ 10°:")
        print("| Nhóm | n | " + " | ".join(f"{100 * t:g} cm" for t in RELAXED_M) + " |")
        print("|---|---|" + "---|" * len(RELAXED_M))
        for name, curve in result["relaxed_curve"].items():
            if name != "label" and curve and curve[0]["n"]:
                cells = " | ".join(str(c["relaxed_successes"]) for c in curve)
                print(f"| {name} | {curve[0]['n']} | {cells} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())

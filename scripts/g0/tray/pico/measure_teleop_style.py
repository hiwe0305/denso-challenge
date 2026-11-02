"""Measure the motion style of the authors' human PICO teleop (psi-data) for DA-35 task 3.

Reads Psi0-format LeRobot episodes (state 32, action 36) of SIMPLE teleop tasks,
computes wrist and elbow positions in the torso frame by forward kinematics of
the commanded arm joints (decoupled_wbc's G1 model, waist at zero), and prints
per-dataset ranges (p10, p50, p90) of the metrics in flywheel_simple.tray.pico.style.

Action layout (meta/modality.json): hands 0-14, arms 14-28 (left then right, 7
each), torso rpy 28-31, height 31, torso vx, vy, vyaw 32-35, target yaw 35.

Run in the SIMPLE venv:

    PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/pico/measure_teleop_style.py fwdata/psi-data/simple/<task> ... \
        --out fwdata/psi-data/style.json
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
from decoupled_wbc.control.robot_model.instantiation.g1 import instantiate_g1_robot_model

from flywheel_simple.tray.pico.style import (
    band_fraction,
    jerk_rms,
    movement_segments,
    pauses,
    percentiles,
    segment_shape,
    speeds,
)

ARMS = slice(14, 28)
RPY = slice(28, 31)
NAV = slice(32, 35)
STILL_HAND = 0.05  # m/s; human PICO hands rarely drop below 0.02
STILL_NAV = 0.05
WALKING = 0.1  # m/s of the vx command
FRAMES = {
    side: (f"{side}_wrist_yaw_link", f"{side}_elbow_link") for side in ("left", "right")
}


def fk_paths(model: Any, arms: np.ndarray) -> dict[str, np.ndarray]:
    """(T, 3) wrist and elbow paths per side, torso frame, from (T, 14) arm joint targets."""
    names = model.joint_names
    idx = [names.index(j) for g in ("left_arm", "right_arm")
           for j in model.supplemental_info.joint_groups[g]["joints"]]  # fmt: skip
    out: dict[str, list[np.ndarray]] = {f: [] for pair in FRAMES.values() for f in pair}
    q = np.zeros(len(names))
    for row in arms:
        q[idx] = row
        model.cache_forward_kinematics(q, auto_clip=False)
        for f in out:
            out[f].append(np.array(model.frame_placement(f).np[:3, 3]))
    model.reset_forward_kinematics()
    return {f: np.asarray(v) for f, v in out.items()}


def wrist_rpy(model: Any, arms_row: np.ndarray, frame: str) -> np.ndarray:
    names = model.joint_names
    idx = [names.index(j) for g in ("left_arm", "right_arm")
           for j in model.supplemental_info.joint_groups[g]["joints"]]  # fmt: skip
    q = np.zeros(len(names))
    q[idx] = arms_row
    model.cache_forward_kinematics(q, auto_clip=False)
    r = np.array(model.frame_placement(frame).np[:3, :3])
    model.reset_forward_kinematics()
    roll = math.atan2(r[2, 1], r[2, 2])
    pitch = math.asin(-max(-1.0, min(1.0, r[2, 0])))
    yaw = math.atan2(r[1, 0], r[0, 0])
    return np.degrees([roll, pitch, yaw])


def episode_metrics(model: Any, action: np.ndarray, dt: float) -> dict[str, Any]:
    paths = fk_paths(model, action[:, ARMS])
    rpy = np.degrees(action[:, RPY])
    nav = action[:, NAV]
    wrists = {s: paths[FRAMES[s][0]] for s in FRAMES}
    elbows = {s: paths[FRAMES[s][1]] for s in FRAMES}
    v = {s: speeds(wrists[s], dt) for s in FRAMES}

    segments = []
    for s in FRAMES:
        for seg in movement_segments(v[s], dt):
            segments.append(segment_shape(wrists[s], v[s], seg, dt))
    still = (
        (v["left"] < STILL_HAND)
        & (v["right"] < STILL_HAND)
        & (np.abs(nav) < STILL_NAV).all(axis=1)
    )
    vx = nav[:, 0]
    walking = np.abs(vx) > WALKING
    mid = len(action) // 2
    return {
        "duration_s": len(action) * dt,
        "torso_pitch_min_deg": float(np.percentile(rpy[:, 1], 5)),
        "torso_pitch_max_deg": float(np.percentile(rpy[:, 1], 95)),
        "torso_roll_range_deg": float(np.ptp(np.percentile(rpy[:, 0], [5, 95]))),
        "torso_yaw_range_deg": float(np.ptp(np.percentile(rpy[:, 2], [5, 95]))),
        "segments": segments,
        "segments_per_min": len(segments) / (len(action) * dt / 60),
        "pauses_s": pauses(still, dt),
        "jerk_rms": float(np.mean([jerk_rms(wrists[s], dt) for s in FRAMES])),
        "tremor_frac_4_12hz": float(
            np.mean([band_fraction(np.gradient(wrists[s], dt, axis=0), dt, 4, 12) for s in FRAMES])
        ),
        "elbow_abs_y_m": float(np.mean([np.median(np.abs(elbows[s][:, 1])) for s in FRAMES])),
        "wrist_abs_y_m": float(np.mean([np.median(np.abs(wrists[s][:, 1])) for s in FRAMES])),
        "hands_apart_m": float(np.median(np.linalg.norm(wrists["left"] - wrists["right"], axis=1))),
        "wrist_z_p10_m": float(np.mean([np.percentile(wrists[s][:, 2], 10) for s in FRAMES])),
        "wrist_z_p90_m": float(np.mean([np.percentile(wrists[s][:, 2], 90) for s in FRAMES])),
        "wrist_x_p90_m": float(np.mean([np.percentile(wrists[s][:, 0], 90) for s in FRAMES])),
        "left_wrist_rpy_mid_deg": wrist_rpy(model, action[mid, ARMS], FRAMES["left"][0]).tolist(),
        "walk_frac": float(walking.mean()),
        "vx_max": float(np.abs(vx).max()),
        "vx_walking_mean": float(np.abs(vx[walking]).mean()) if walking.any() else float("nan"),
        "vx_accel_p95": float(np.percentile(np.abs(np.gradient(vx, dt)), 95)),
        "vyaw_max": float(np.abs(nav[:, 2]).max()),
    }


def summarise(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    scalar = [k for k, v in episodes[0].items() if isinstance(v, float)]
    out: dict[str, Any] = {k: percentiles([e[k] for e in episodes]) for k in scalar}
    segs = [s for e in episodes for s in e["segments"]]
    for k in ("peak_speed", "duration", "length", "curvature", "peak_time_frac"):
        out[f"segment_{k}"] = percentiles([s[k] for s in segs])
    out["pause_s"] = percentiles([p for e in episodes for p in e["pauses_s"]])
    out["pauses_per_episode"] = percentiles([float(len(e["pauses_s"])) for e in episodes])
    rpy = np.array([e["left_wrist_rpy_mid_deg"] for e in episodes])
    out["left_wrist_rpy_mid_deg_p50"] = np.median(rpy, axis=0).round(1).tolist()
    return out


def measure(root: Path, model: Any, limit: int | None) -> dict[str, Any]:
    info = json.loads((root / "meta" / "info.json").read_text())
    dt = 1.0 / info["fps"]
    files = sorted((root / "data").glob("*/episode_*.parquet"))[:limit]
    episodes = []
    for f in files:
        action = np.stack(pq.read_table(f, columns=["action"]).column("action").to_numpy(
            zero_copy_only=False)).astype(np.float64)  # fmt: skip
        if action.shape[1] != 36:
            raise ValueError(f"{f}: action has {action.shape[1]} dims, expected 36")
        episodes.append(episode_metrics(model, action, dt))
    return {"dataset": root.name, "episodes": len(episodes), "fps": info["fps"],
            "summary": summarise(episodes)}  # fmt: skip


def table(results: list[dict[str, Any]]) -> str:
    keys = [k for k, v in results[0]["summary"].items() if isinstance(v, dict)]
    head = "| Chỉ số | " + " | ".join(r["dataset"] for r in results) + " |"
    lines = [head, "|---|" + "---|" * len(results)]
    for k in keys:
        cells = []
        for r in results:
            p = r["summary"][k]
            cells.append(f"{p['p10']:.3g} / {p['p50']:.3g} / {p['p90']:.3g}" if p["n"] else "–")
        lines.append(f"| `{k}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("datasets", nargs="+", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--limit", type=int, help="episodes per dataset")
    args = parser.parse_args()
    model = instantiate_g1_robot_model(waist_location="lower_and_upper_body")
    results = [measure(root, model, args.limit) for root in args.datasets]
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, indent=1))
    print(table(results))
    for r in results:
        print(r["dataset"], "left wrist rpy mid (deg)", r["summary"]["left_wrist_rpy_mid_deg_p50"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Measure the motion style of teleop datasets (DA-35 tasks 3 and 12, AC 8).

Reads LeRobot episodes of SIMPLE teleop tasks in two layouts, computes wrist and
elbow positions in the torso frame by forward kinematics of the commanded arm
joints (decoupled_wbc's G1 model, waist at zero), and prints per-dataset ranges
(p10, p50, p90) of the metrics in flywheel_simple.tray.pico.style, plus how far
the wrist paths of different episodes lie apart (`wrist_dispersion_m`: each
episode's path resampled to 100 points of normalised time, the per-point
standard deviation over episodes, averaged over points and both hands).

- Psi0 (action 36: psi-data, DA-33's S1 release): arms 14-28 (left then right, 7
  each), torso rpy 28-31, walking command (vx, vy, vyaw) 32-35;
- SIMPLE recorder (action 43: virtual teleop, S2): the arm and waist joints of
  `action` by name, the walking command from `teleop.navigate_command`.

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


ARM_JOINTS = [
    f"{side}_{j}_joint"
    for side in ("left", "right")
    for j in ("shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow",
              "wrist_roll", "wrist_pitch", "wrist_yaw")
]  # fmt: skip
WAIST_RPY = ("waist_roll_joint", "waist_pitch_joint", "waist_yaw_joint")


def column(table: Any, name: str) -> np.ndarray:
    return np.stack(table.column(name).to_numpy(zero_copy_only=False)).astype(np.float64)


def psi0_layout(f: Path, names: list[str]) -> np.ndarray:
    """(T, 36) Psi0 action of an episode in either layout (only the columns used here)."""
    if len(names) == 36:
        return column(pq.read_table(f, columns=["action"]), "action")
    table = pq.read_table(f, columns=["action", "teleop.navigate_command"])
    action, nav = column(table, "action"), column(table, "teleop.navigate_command")
    out = np.zeros((len(action), 36))
    out[:, ARMS] = action[:, [names.index(j) for j in ARM_JOINTS]]
    out[:, RPY] = action[:, [names.index(j) for j in WAIST_RPY]]
    out[:, NAV] = nav[:, :3]
    return out


def dispersion(model: Any, actions: list[np.ndarray], points: int = 100) -> float:
    """Mean per-point standard deviation of the wrist paths over episodes (m)."""
    paths = []
    for action in actions:
        fk = fk_paths(model, action[:, ARMS])
        grid = np.linspace(0, len(action) - 1, points)
        both = [
            np.stack([np.interp(grid, np.arange(len(action)), fk[f][:, k]) for k in range(3)], 1)
            for f in (FRAMES["left"][0], FRAMES["right"][0])
        ]
        paths.append(np.stack(both))  # (2, points, 3)
    if len(paths) < 2:
        return float("nan")
    stack = np.stack(paths)  # (episodes, 2, points, 3)
    return float(np.linalg.norm(stack.std(axis=0), axis=-1).mean())


def episode_files(root: Path, limit: int | None, seed: int) -> list[Path]:
    """All episodes of a LeRobot dataset (or of every shard under a batch), `limit` at random."""
    files = sorted(root.glob("**/data/*/episode_*.parquet"))
    if limit is not None and len(files) > limit:
        pick = np.random.default_rng(seed).choice(len(files), size=limit, replace=False)
        files = [files[i] for i in sorted(pick)]
    return files


def measure(root: Path, model: Any, limit: int | None, seed: int = 0) -> dict[str, Any]:
    files = episode_files(root, limit, seed)
    if not files:
        raise ValueError(f"{root}: no episodes")
    meta = files[0].parents[2] / "meta" / "info.json"
    info = json.loads(meta.read_text())
    dt = 1.0 / info["fps"]
    names = info["features"]["action"]["names"]
    actions = [psi0_layout(f, names) for f in files]
    episodes = [episode_metrics(model, a, dt) for a in actions]
    summary = summarise(episodes)
    summary["wrist_dispersion_m"] = dispersion(model, actions)
    return {"dataset": root.name, "episodes": len(episodes), "fps": info["fps"],
            "summary": summary}  # fmt: skip


def table(results: list[dict[str, Any]]) -> str:
    keys = [k for k, v in results[0]["summary"].items() if isinstance(v, dict)]
    keys.append("wrist_dispersion_m")
    head = "| Chỉ số | " + " | ".join(r["dataset"] for r in results) + " |"
    lines = [head, "|---|" + "---|" * len(results)]
    for k in keys:
        cells = []
        for r in results:
            p = r["summary"][k]
            if not isinstance(p, dict):
                cells.append(f"{p:.3g}")
                continue
            cells.append(f"{p['p10']:.3g} / {p['p50']:.3g} / {p['p90']:.3g}" if p["n"] else "–")
        lines.append(f"| `{k}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("datasets", nargs="+", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--limit", type=int, help="episodes per dataset, drawn at random")
    parser.add_argument("--seed", type=int, default=0, help="for --limit")
    args = parser.parse_args()
    model = instantiate_g1_robot_model(waist_location="lower_and_upper_body")
    results = [measure(root, model, args.limit, args.seed) for root in args.datasets]
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, indent=1))
    print(table(results))
    for r in results:
        print(r["dataset"], "left wrist rpy mid (deg)", r["summary"]["left_wrist_rpy_mid_deg_p50"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

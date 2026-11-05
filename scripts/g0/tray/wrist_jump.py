"""Where and why the tray S1 arm actions jump (DA-33, DA-03 QA flag `action_jump.arm`).

Reads a tray release and its raw batch (the release's meta/flywheel_export.json names
the shard and raw episode of each episode) and, per episode:

- every step whose arm action moves more than the QA threshold, grouped into windows
  and labelled by the planner segment it falls in (from the recorded commands: the
  base stands while APPROACH_A raises the hands, then walks on);
- in each window: the commanded wrist target's angular speed (`action.eef`, what the
  planner sent), the IK's joint speed, the IK error (forward kinematics of the
  commanded joints against the target) and the tracking error of the measured joints;
- whether a wrist roll sits on its joint limit and how close wrist pitch comes to
  90 degrees (the G1 wrist is roll-pitch-yaw; at pitch +-90 roll and yaw align).

Runs in the SIMPLE venv (decoupled_wbc's G1 model for forward kinematics):

    fwdata/simple/.venv/bin/python scripts/g0/tray/wrist_jump.py \
        --release fwdata/releases/tray_s1_0d84cc87b1e5 --out fwdata/analysis/wrist_jump

Writes summary.json (per window kind) and episodes.jsonl (per episode and window), and
prints the steps 195-220 table of the first five episodes.
"""

from __future__ import annotations

import argparse
import importlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
from numpy.typing import NDArray

ARM_THRESHOLD = 0.0869346  # configs/data/qa.yaml action_jump.thresholds.arm (PR #86)
FPS = 50
# The raw `action` puts the left hand between the arms (body 0-21, left hand 22-28,
# right arm 29-35, right hand); `observation.state` has the 29 body joints first.
ACTION_BODY = list(range(22)) + list(range(29, 36))
# Arm joints in body order (decoupled_wbc's body_actuated_joints).
ARM = {
    "left": {"shoulder_pitch": 15, "shoulder_roll": 16, "shoulder_yaw": 17, "elbow": 18,
             "wrist_roll": 19, "wrist_pitch": 20, "wrist_yaw": 21},
    "right": {"shoulder_pitch": 22, "shoulder_roll": 23, "shoulder_yaw": 24, "elbow": 25,
              "wrist_roll": 26, "wrist_pitch": 27, "wrist_yaw": 28},
}
ARM_COLS = [c for side in ARM.values() for c in side.values()]
TABLE_STEPS = range(195, 221)


def _col(table: Any, key: str) -> NDArray[np.float64]:
    return np.asarray(table.column(key).to_pylist(), dtype=np.float64)


def _rot(q_wxyz: NDArray[np.float64]) -> NDArray[np.float64]:
    w, x, y, z = q_wxyz / np.linalg.norm(q_wxyz)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def _angle(a: NDArray[np.float64], b: NDArray[np.float64]) -> float:
    """Angle (rad) of the rotation between two rotation matrices."""
    c = (float(np.trace(a.T @ b)) - 1.0) / 2.0
    return float(np.arccos(np.clip(c, -1.0, 1.0)))


class Kinematics:
    """Wrist poses (pelvis frame) of body joint vectors, with decoupled_wbc's G1 model."""

    def __init__(self) -> None:
        g1 = importlib.import_module("decoupled_wbc.control.robot_model.instantiation.g1")
        self.model = g1.instantiate_g1_robot_model(
            waist_location="lower_body", high_elbow_pose=False
        )
        frames = self.model.supplemental_info.hand_frame_names
        self.frames = (frames["left"], frames["right"])

    def wrists(
        self, body: NDArray[np.float64]
    ) -> list[tuple[NDArray[np.float64], NDArray[np.float64]]]:
        q = self.model.get_configuration_from_actuated_joints(
            body_actuated_joint_values=body,
            left_hand_actuated_joint_values=np.zeros(7),
            right_hand_actuated_joint_values=np.zeros(7),
        )
        self.model.cache_forward_kinematics(q)
        out: list[tuple[NDArray[np.float64], NDArray[np.float64]]] = []
        for f in self.frames:
            p = self.model.frame_placement(f)
            out.append((np.asarray(p.translation, float), np.asarray(p.rotation, float)))
        return out


def segments(nav: NDArray[np.float64], steps: NDArray[np.float64]) -> list[tuple[str, int, int]]:
    """Planner segments from the recorded commands, as (name, first step, end step).

    Checked against the planner's own phase log (wrist_jump_sim.py, seeds 1000 and 1022):
    approach_raise: APPROACH_A raises the hands to the ready pose with the base standing
    (the robot starts inside `raise_at`), until a few steps after it walks;
    approach_walk: walk to table A; reach_grasp: REACH and GRASP (the base stands again)
    until the scorer's lift flag; lift_carry: LIFT to CARRY, until its reach_b flag;
    place_release: ARRIVE_B, LOWER, RELEASE and RETREAT.
    """
    n = len(nav)
    moving = np.abs(nav[:, :3]).max(axis=1) > 0
    walk0 = int(np.argmax(moving))
    raised = min(n, walk0 + 5)
    still = np.where(~moving[raised:])[0]
    reach = raised + int(still[0]) if len(still) else n

    def flag(name_index: int) -> int:
        hit = np.where(steps[:, name_index] > 0)[0]
        return int(hit[0]) if len(hit) else n

    lift, arrive = flag(2), flag(4)
    return [("approach_raise", 0, raised), ("approach_walk", raised, reach),
            ("reach_grasp", reach, lift), ("lift_carry", lift, arrive),
            ("place_release", arrive, n)]


def segment_of(segs: list[tuple[str, int, int]], step: int) -> str:
    for name, a, b in segs:
        if a <= step < b:
            return name
    return segs[-1][0]


def analyse(raw_root: Path, raw_episode: int, kin: Kinematics) -> dict[str, Any]:
    path = raw_root / f"data/chunk-{raw_episode // 1000:03d}/episode_{raw_episode:06d}.parquet"
    t = pq.read_table(path)
    action = _col(t, "action")[:, ACTION_BODY]
    state = _col(t, "observation.state")[:, :29]
    eef, nav, steps = _col(t, "action.eef"), _col(t, "teleop.navigate_command"), _col(
        t, "observation.tray_steps")
    n = len(action)
    segs = segments(nav, steps)
    jumps = np.abs(np.diff(action[:, ARM_COLS], axis=0))  # step k: action[k+1] - action[k]
    over = np.where(jumps.max(axis=1) > ARM_THRESHOLD)[0]
    # Target and achieved wrist rotation, both hands.
    tgt = [[_rot(eef[k, 3:7]), _rot(eef[k, 10:14])] for k in range(n)]
    tgt_pos = [[eef[k, 0:3], eef[k, 7:10]] for k in range(n)]
    cmd = [kin.wrists(action[k]) for k in range(n)]
    meas = [kin.wrists(state[k]) for k in range(n)]
    tgt_speed = np.zeros((n, 2))
    for k in range(1, n):
        for h in range(2):
            tgt_speed[k, h] = _angle(tgt[k - 1][h], tgt[k][h]) * FPS
    ik_rot = np.array([[_angle(cmd[k][h][1], tgt[k][h]) for h in range(2)] for k in range(n)])
    ik_pos = np.array([[np.linalg.norm(cmd[k][h][0] - tgt_pos[k][h]) for h in range(2)]
                       for k in range(n)])
    trk_rot = np.array([[_angle(meas[k][h][1], tgt[k][h]) for h in range(2)] for k in range(n)])
    by_seg: dict[str, list[int]] = defaultdict(list)
    for k in over:
        by_seg[segment_of(segs, int(k))].append(int(k))
    windows = {}
    for name, ks in by_seg.items():
        a, b = min(ks), max(ks) + 2
        lo, hi = max(0, a - 10), min(n, b + 10)
        jw = jumps[a:b - 1]
        worst = int(np.argmax(jw.max(axis=0)))
        windows[name] = {
            "steps": [a, b - 1],
            "n_over": len(ks),
            "max_jump": float(jw.max()),
            "max_jump_joint": f"{['left', 'right'][worst // 7]}_"
                              f"{list(ARM['left'])[worst % 7]}",
            "joint_speed_max": float(jw.max()) * FPS,
            "target_ang_speed_max": float(tgt_speed[lo:hi].max()),
            "ik_rot_err_max_deg": float(np.degrees(ik_rot[lo:hi].max())),
            "ik_pos_err_max_mm": float(1000 * ik_pos[lo:hi].max()),
            "track_rot_err_max_deg": float(np.degrees(trk_rot[lo:hi].max())),
            "wrist_roll_cmd_abs_max": float(np.abs(action[lo:hi][:, [19, 26]]).max()),
            "wrist_pitch_cmd_abs_max": float(np.abs(action[lo:hi][:, [20, 27]]).max()),
            "track_rot_err_after_deg": float(np.degrees(trk_rot[min(n - 1, b + 10)].max())),
            "wrist_yaw_meas_speed_max": float(
                np.abs(np.diff(state[lo:hi][:, [21, 28]], axis=0)).max() * FPS),
        }
    static = (tgt_speed.max(axis=1) < 0.01) & (np.arange(n) > 40)
    baseline = {"ik_rot_err_static_deg": float(np.degrees(np.median(ik_rot[static]))),
                "track_rot_err_static_deg": float(np.degrees(np.median(trk_rot[static])))}
    return {"segments": segs, "windows": windows, "baseline": baseline, "length": n,
            "action": action, "state": state, "tgt_speed": tgt_speed, "ik_rot": ik_rot,
            "trk_rot": trk_rot}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-episodes", type=int, default=None)
    args = parser.parse_args()
    meta = json.loads((args.release / "meta/flywheel_export.json").read_text())
    batch = Path(meta["source_batch"])
    kin = Kinematics()
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    tables: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for entry in meta["episodes"][: args.max_episodes]:
        res = analyse(batch / entry["shard"] / "raw", entry["raw_episode"], kin)
        rows.append({"episode_index": entry["episode_index"], "seed": entry["seed"],
                     "length": res["length"], "segments": res["segments"],
                     "windows": res["windows"], "baseline": res["baseline"]})
        if len(tables) < 5:
            tables.append((entry, res))
    with (args.out / "episodes.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    summary: dict[str, Any] = {"release": str(args.release), "threshold": ARM_THRESHOLD,
                               "episodes": len(rows), "windows": {}}
    for key in rows[0]["baseline"]:
        vals = np.array([r["baseline"][key] for r in rows])
        summary[key] = {"median": float(np.median(vals)), "max": float(vals.max())}
    kinds = sorted({k for r in rows for k in r["windows"]})
    for kind in kinds:
        ws = [r["windows"][kind] for r in rows if kind in r["windows"]]
        block: dict[str, Any] = {"episodes": len(ws)}
        for key in ws[0]:
            if key == "max_jump_joint":
                joints: dict[str, int] = defaultdict(int)
                for w in ws:
                    joints[w[key]] += 1
                block[key] = dict(sorted(joints.items(), key=lambda kv: -kv[1]))
            elif key == "steps":
                block["first_step"] = [min(w[key][0] for w in ws), max(w[key][0] for w in ws)]
                block["last_step"] = [min(w[key][1] for w in ws), max(w[key][1] for w in ws)]
            else:
                vals = np.array([w[key] for w in ws])
                block[key] = {"min": float(vals.min()), "median": float(np.median(vals)),
                              "max": float(vals.max())}
        summary["windows"][kind] = block
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    for entry, res in tables:
        a, s = res["action"], res["state"]
        print(f"\nepisode {entry['episode_index']} (seed {entry['seed']}), segments "
              f"{[(n, x, y) for n, x, y in res['segments']]}")
        print("step | L roll pitch yaw cmd | L yaw meas | R roll pitch yaw cmd | R yaw meas"
              " | tgt w L,R rad/s | IK err deg L,R | track err deg L,R")
        for k in TABLE_STEPS:
            if k >= len(a):
                break
            print(f"{k} | {a[k, 19]:+.3f} {a[k, 20]:+.3f} {a[k, 21]:+.3f} | {s[k, 21]:+.3f} | "
                  f"{a[k, 26]:+.3f} {a[k, 27]:+.3f} {a[k, 28]:+.3f} | {s[k, 28]:+.3f} | "
                  f"{res['tgt_speed'][k, 0]:.2f} {res['tgt_speed'][k, 1]:.2f} | "
                  f"{np.degrees(res['ik_rot'][k, 0]):.1f} {np.degrees(res['ik_rot'][k, 1]):.1f} | "
                  f"{np.degrees(res['trk_rot'][k, 0]):.1f} {np.degrees(res['trk_rot'][k, 1]):.1f}")


if __name__ == "__main__":
    main()

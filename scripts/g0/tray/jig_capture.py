"""Capture envelope of the DA-41 locating jig: which off-target drops it centres.

Plain MuJoCo, no robot. For each offset radius, direction and yaw error the tray (parts
in) is released `--drop` above the guide tops on the jig scene of one episode and left
to settle for 3 s; a drop counts as centred when the tray ends within `--centred` of
the target, within 3 degrees of its yaw and under 2 degrees of tilt. Prints one row per
(radius, yaw) and writes every drop to `--out` as JSON.

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/jig_capture.py --out fwdata/simple/tray/jig/capture.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path
from typing import Any

import mujoco
from flywheel_simple.tray import TrayConfig, mjcf
from flywheel_simple.tray.geometry import Pose2D, scene_geometry
from flywheel_simple.tray.jig import JigConfig, jig_scene_spec, sample_jig_episode

SETTLE_S = 3.0


def drop(cfg: TrayConfig, jig: JigConfig, level: int, seed: int, offset: Pose2D,
         height: float) -> dict[str, Any]:
    """Release the tray at the target moved by `offset` (target frame), `height` above it."""
    s = sample_jig_episode(cfg, jig, level, seed)
    spec = jig_scene_spec(cfg, jig, tray_pose=s.tray_pose, visuals={}, table_gap=s.table_gap,
                          target_pose=s.target_pose)
    model = spec.compile()
    data = mujoco.MjData(model)
    t = s.target_pose
    c, sn = math.cos(t.yaw), math.sin(t.yaw)
    pose = Pose2D(t.x + c * offset.x - sn * offset.y, t.y + sn * offset.x + c * offset.y,
                  t.yaw + offset.yaw)
    z = cfg.table_height + height
    quat = [math.cos(pose.yaw / 2), 0.0, 0.0, math.sin(pose.yaw / 2)]
    adr = model.jnt_qposadr[model.joint("tray_joint").id]
    data.qpos[adr : adr + 7] = [pose.x, pose.y, z, *quat]
    cy, sy = math.cos(pose.yaw), math.sin(pose.yaw)
    part_z = z + cfg.tray_floor + mjcf.SPAWN_GAP + cfg.part_height / 2
    for i, (x, y) in enumerate(scene_geometry(cfg).compartment_centers):
        adr = model.jnt_qposadr[model.joint(f"part_{i}_joint").id]
        data.qpos[adr : adr + 7] = [pose.x + cy * x - sy * y, pose.y + sy * x + cy * y, part_z,
                                    *quat]
    mujoco.mj_forward(model, data)
    for _ in range(round(SETTLE_S / model.opt.timestep)):
        mujoco.mj_step(model, data)
    tray = data.body("tray")
    w, qx, qy, qz = tray.xquat
    yaw = math.atan2(2 * (w * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
    return {
        "err_m": math.hypot(tray.xpos[0] - t.x, tray.xpos[1] - t.y),
        "yaw_err_deg": abs(math.degrees(math.remainder(yaw - t.yaw, 2 * math.pi))),
        "tilt_deg": math.degrees(math.acos(min(1.0, float(data.xmat[tray.id][8])))),
        "height_m": float(tray.xpos[2] - cfg.table_height),
        "parts_on_tray": all(data.body(f"part_{i}").xpos[2] > cfg.table_height
                             for i in range(cfg.part_count)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--case", default="1:1279", help="level:seed of the scene")
    ap.add_argument("--radii", type=float, nargs="+", default=[0.01, 0.02, 0.03, 0.04, 0.05, 0.06])
    ap.add_argument("--yaws", type=float, nargs="+", default=[0.0, 4.0, 8.0], help="degrees")
    ap.add_argument("--directions", type=int, default=8)
    ap.add_argument("--drop", type=float, default=0.02, help="m above the guide tops")
    ap.add_argument("--centred", type=float, default=0.012, help="m from the target")
    args = ap.parse_args()
    cfg, jig = TrayConfig.load(), JigConfig.load()
    level, seed = (int(v) for v in args.case.split(":"))
    rows = []
    for r, dyaw in itertools.product(args.radii, args.yaws):
        ok = 0
        for k in range(args.directions):
            a = 2 * math.pi * k / args.directions
            res = drop(cfg, jig, level, seed,
                       Pose2D(r * math.cos(a), r * math.sin(a), math.radians(dyaw)),
                       jig.height + args.drop)
            res["centred"] = (res["err_m"] <= args.centred and res["yaw_err_deg"] <= 3.0
                              and res["tilt_deg"] <= 2.0)
            ok += res["centred"]
            rows.append({"radius_m": r, "direction_deg": math.degrees(a), "yaw_deg": dyaw, **res})
        worst = max(x["err_m"] for x in rows[-args.directions:])
        print(f"radius {r * 100:.0f} cm, yaw {dyaw:g} deg: centred {ok}/{args.directions}, "
              f"worst end error {worst * 100:.1f} cm", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"jig": jig.__dict__, "case": args.case, "drop_m": args.drop,
                                    "rows": rows}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

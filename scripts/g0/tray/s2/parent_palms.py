"""Where the parents' palms were, frame by frame, by forward kinematics (DA-35 task 10).

The recording keeps the wrist targets the operator sent (`action.eef`), not where
the palms went: SIMPLE's arm PD sags under gravity, and DA-33's planner took that
up with a correction from the measured palms. S2 needs the palms themselves to
correct its moved hands the same way (flywheel_simple.tray.s2.replay).

For every parent of `<parents>/s2_segments.jsonl`, sets the tray env's MuJoCo
model to the recorded joints (`observation.state`) and pelvis pose
(`observation.base_pose`), runs mj_kinematics and reads the palm points as
`flywheel_simple.tray.simple_task.tray_state` does (midway between the wrist and
the middle finger base). Writes `<parents>/s2_palms.npz`: one (T, 2, 3) array per
parent (left, right; world), keyed by `palms_key(parent_id)`.

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \\
        scripts/g0/tray/s2/parent_palms.py --parents fwdata/simple/tray/virtual/parents-1103b
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.s2.parents import PALMS_FILE, palms_key, parent_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--parents", type=Path, required=True)
    args = parser.parse_args(argv)

    import mujoco  # type: ignore[import-not-found]  # SIMPLE venv
    import pandas  # type: ignore[import-untyped]

    from flywheel_simple.tray.pico.session import make_teleop_env

    env = make_teleop_env(0, headless=True)
    env.reset(seed=0, options={"level": 0})
    model, data = env.unwrapped.mjModel, env.unwrapped.mjData
    rows = [json.loads(x) for x in (args.parents / "s2_segments.jsonl").read_text().splitlines()]
    out: dict[str, NDArray[np.float64]] = {}
    for row in rows:
        root = parent_dataset(args.parents, row["shard"])
        info = json.loads((root / "meta" / "info.json").read_text())
        names = info["features"]["observation.state"]["names"]
        adr = [int(model.jnt_qposadr[model.joint(n).id]) for n in names]
        chunk = row["episode_index"] // int(info["chunks_size"])
        df = pandas.read_parquet(
            root / info["data_path"].format(episode_chunk=chunk, episode_index=row["episode_index"])
        )
        joints = np.stack(df["observation.state"].to_numpy())
        bases = np.stack(df["observation.base_pose"].to_numpy())
        palms = np.zeros((len(df), 2, 3))
        for i in range(len(df)):
            data.qpos[:7] = bases[i]
            data.qpos[adr] = joints[i]
            mujoco.mj_kinematics(model, data)
            for k, side in enumerate(("left", "right")):
                wrist = data.body(f"{side}_wrist_yaw_link").xpos
                finger = data.body(f"{side}_hand_middle_0_link").xpos
                palms[i, k] = (wrist + finger) / 2
        out[palms_key(row["parent_id"])] = palms
    env.close()
    np.savez_compressed(args.parents / PALMS_FILE, **out)  # type: ignore[arg-type]
    print(json.dumps({"parents": len(out), "file": str(args.parents / PALMS_FILE)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

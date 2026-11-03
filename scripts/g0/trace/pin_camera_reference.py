"""Pin the G0 camera reference of one SIMPLE task (DA-38, B3 of the PO review 3/11/2026).

Runs SIMPLE's real `eval-decoupled-wbc` for one short episode with the trace hook
installed, reads every camera the policy sees from the compiled MuJoCo model
(`flywheel_simple.trace.hook.camera_values`), and writes them with their
`reference_sha256` as YAML in the shape of the r5 block of
`configs/eval/diagnosis/system.yaml` (cameras keyed by uid). The Psi0 server is
replaced by a hold-pose stub: camera values do not depend on the policy, so no
GPU server is needed.

Run with the SIMPLE venv of scripts/g0/setup_simple.sh, at the pinned SIMPLE commit:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
        fwdata/simple/.venv/bin/python scripts/g0/trace/pin_camera_reference.py \
        --env-id simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0 \
        --data-dir <psi-data simple-eval/<task>/dr-level-0> \
        --out docs/g0/camera-reference-two-table.yaml
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from flywheel_simple.trace.camera import reference_sha256
from flywheel_simple.trace.hook import EpisodeTrace, TraceRecorder, install

CHUNK = 16
HEADER = (
    "# Bản tham chiếu camera G0 của một task SIMPLE (DA-38 nhiệm vụ 3.2, review PO 3/11/2026 B3).\n"
    "# Sinh bởi scripts/g0/trace/pin_camera_reference.py; không sửa tay. Khóa reference_sha256\n"
    "# và cameras có dạng khối r5 của configs/eval/diagnosis/system.yaml.\n"
)


class _Keep:
    def __init__(self) -> None:
        self.episodes: list[EpisodeTrace] = []

    def write(self, episode: EpisodeTrace) -> None:
        self.episodes.append(episode)


def _hold_pose(
    client: Any, images: Any, instruction: Any, state_dict: Any, *args: Any, **kwargs: Any
) -> tuple[np.ndarray, None]:
    states = np.asarray(state_dict["states"], dtype=np.float64)[0]
    row = np.concatenate([states[:28], states[28:31], states[31:32], [0.0, 0.0, 0.0, 0.0]])
    return np.tile(row, (CHUNK, 1)), None


def _simple_commit() -> tuple[str, bool]:
    """HEAD of the SIMPLE checkout that is imported, and whether its Python sources differ."""
    import simple

    root = Path(simple.__file__).resolve().parents[2]
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True)
    changed = subprocess.check_output(
        ["git", "-C", str(root), "diff", "--name-only", "HEAD", "--", "*.py"], text=True
    )
    return head.strip(), bool(changed.strip())


def read_cameras(env_id: str, data_dir: str) -> EpisodeTrace:
    from flywheel_simple.tray.run import prepare
    from simple.baselines import client, psi0_decoupled_wbc
    from simple.cli import eval_decoupled_wbc
    from simple.evals.api import EvalConfig

    prepare()
    keep = _Keep()
    install(eval_decoupled_wbc, psi0_decoupled_wbc, TraceRecorder(keep, run_plan_id="g0-pin"))
    client.HttpActionClient.query_action = _hold_pose  # type: ignore[method-assign]
    with tempfile.TemporaryDirectory() as eval_dir:
        eval_decoupled_wbc.run_eval(
            EvalConfig(
                env_id=env_id,
                policy="psi0_decoupled_wbc",
                data_format="lerobot",
                data_dir=data_dir,
                sim_mode="mujoco",
                headless=True,
                save_video=False,
                eval_dir=eval_dir,
                max_episode_steps=2,
                num_episodes=1,
                num_workers=1,
            ),
            show_progress=False,
        )
    (episode,) = [e for e in keep.episodes if e.cameras]
    return episode


def reference_document(env_id: str, episode: EpisodeTrace) -> dict[str, Any]:
    commit, dirty = _simple_commit()
    if dirty:
        raise SystemExit(f"SIMPLE checkout has uncommitted .py changes at {commit}; pin refused")
    cameras = sorted(episode.cameras, key=lambda c: c.uid)
    return {
        "env_id": env_id,
        "simple_commit": commit,
        "pinned_on": date.today().isoformat(),
        "reference_sha256": reference_sha256(cameras),
        "cameras": {
            c.uid: {
                "mount": c.mount,
                "width": c.width,
                "height": c.height,
                "fx": c.fx,
                "fy": c.fy,
                "cx": c.cx,
                "cy": c.cy,
                "pose": list(c.pose),
            }
            for c in cameras
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--env-id", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    document = reference_document(args.env_id, read_cameras(args.env_id, args.data_dir))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(HEADER + yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    print(document["reference_sha256"])


if __name__ == "__main__":
    main()

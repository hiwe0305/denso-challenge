"""Trace hook inside SIMPLE's real eval loop (DA-38 AC 1-5). Needs the SIMPLE env of S1-02.

Run in `fwdata/simple/.venv` with `MUJOCO_GL=egl`:

    FW_TRACE_DATA_TWO_TABLE=<psi-data simple-eval/<task>/dr-level-0> \
    FW_TRACE_DATA_TRAY=<a LeRobot tray dataset root> \
    pytest packages/flywheel-simple/tests/trace -m sim

The env, decoupled WBC and MuJoCo are real; only the Psi0 server is replaced by a
stub that returns a hold-pose chunk built from the state the agent sends, so no
GPU is needed. Each data variable left unset skips its task.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel_simple.trace.hook import EpisodeTrace, TraceRecorder, install
from flywheel_simple.trace.signals import STATE_SLICES

pytestmark = pytest.mark.sim

TWO_TABLE = "simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0"
TRAY = "simple/G1WholebodyTrayTransferTeleop-v0"
CHUNK = 16
STEPS = 40


def test_state_slices_copy_matches_simple() -> None:
    from simple.baselines import psi0_decoupled_wbc

    assert tuple(tuple(s) for s in psi0_decoupled_wbc.STATE_SLICES) == STATE_SLICES


def test_patched_names_exist_in_simple() -> None:
    from simple.baselines import psi0_decoupled_wbc as agent_module
    from simple.cli import eval_decoupled_wbc as eval_module
    from simple.utils import snake_to_pascal

    assert callable(eval_module.gym.make) and eval_module.gym.Wrapper is not None
    assert callable(eval_module._append_eval_stats_line)
    assert snake_to_pascal("psi0_decoupled_wbc") + "Agent" == "Psi0DecoupledWbcAgent"
    agent = agent_module.Psi0DecoupledWbcAgent
    assert callable(agent.get_action) and callable(agent.reset)


class ListSink:
    def __init__(self) -> None:
        self.episodes: list[EpisodeTrace] = []

    def write(self, episode: EpisodeTrace) -> None:
        self.episodes.append(episode)


def hold_pose_query(
    client: Any, images: Any, instruction: Any, state_dict: Any, *args: Any, **kwargs: Any
) -> tuple[np.ndarray, None]:
    """Stub of HttpActionClient.query_action: hold the sent pose, stand still."""
    # states (1, 32): upper 28 in Psi0 order, waist roll/pitch/yaw, base height command
    states = np.asarray(state_dict["states"], dtype=np.float64)[0]
    row = np.concatenate([states[:28], states[28:31], states[31:32], [0.0, 0.0, 0.0, 0.0]])
    return np.tile(row, (CHUNK, 1)), None


def run_traced_eval(env_id: str, data_dir: str, eval_dir: Path) -> EpisodeTrace:
    from flywheel_simple.tray.run import prepare
    from simple.baselines import client, psi0_decoupled_wbc
    from simple.cli import eval_decoupled_wbc
    from simple.evals.api import EvalConfig

    prepare()  # tray env id and SIMPLE's condition reader for tray datasets (PR #67)
    sink = ListSink()
    install(eval_decoupled_wbc, psi0_decoupled_wbc, TraceRecorder(sink, run_plan_id="sim-test"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client.HttpActionClient, "query_action", hold_pose_query)
        eval_decoupled_wbc.run_eval(
            EvalConfig(
                env_id=env_id,
                policy="psi0_decoupled_wbc",
                data_format="lerobot",
                data_dir=data_dir,
                sim_mode="mujoco",
                headless=True,
                save_video=False,
                eval_dir=str(eval_dir),
                max_episode_steps=STEPS,
                num_episodes=1,
                num_workers=1,
            ),
            show_progress=False,
        )
    (episode,) = [e for e in sink.episodes if e.cycles]
    return episode


@pytest.mark.parametrize(
    ("env_id", "var"), [(TWO_TABLE, "FW_TRACE_DATA_TWO_TABLE"), (TRAY, "FW_TRACE_DATA_TRAY")]
)
def test_trace_of_a_real_eval_episode(env_id: str, var: str, tmp_path: Path) -> None:
    data_dir = os.environ.get(var)
    if not data_dir:
        pytest.skip(f"{var} not set")
    ep = run_traced_eval(env_id, data_dir, tmp_path)

    # AC 1, 4: one cycle per policy step, closed by SIMPLE's own stats line
    assert ep.episode_id == "episode_0"
    stats = (tmp_path / "eval_stats.txt").read_text()
    assert f"episode_0: {ep.sim_success}" in stats
    assert len(ep.cycles) == STEPS
    # AC 2: sim clock at 50 Hz; a frame reaches the policy once per chunk
    t = np.array([c.t_state for c in ep.cycles])
    assert np.diff(t) == pytest.approx(np.full(STEPS - 1, 0.02), abs=1e-9)
    sent = [c.step for c in ep.cycles if c.t_image is not None]
    assert sent == list(range(0, STEPS, CHUNK))
    assert all(ep.cycles[s].t_image == ep.cycles[s].t_state for s in sent)
    # AC 6 (values come from the sim): the measured state moves, the base stands
    meas = np.array([c.meas_upper + c.meas_lower for c in ep.cycles])
    assert np.ptp(meas, axis=0).max() > 1e-4
    assert 0.5 < ep.cycles[-1].meas_lower[3] < 0.9
    assert ep.cycles[0].cmd_upper == pytest.approx(ep.cycles[0].meas_upper, abs=1e-5)
    # AC 3: cameras as rendered
    cams = {c.uid: c for c in ep.cameras}
    left = cams["head_stereo_left"]
    assert (left.width, left.height) == (640, 360)
    fy_cfg = 640 / (2 * np.tan(np.radians(110) / 2))  # CameraCfg: fov 110 deg on 640 px
    assert left.fy == pytest.approx(fy_cfg, rel=1e-6)
    assert np.linalg.norm(left.pose[3:]) == pytest.approx(1.0, abs=1e-6)


def test_upper_names_are_the_joints_state_slices_picks_from_g1_sonic() -> None:
    from flywheel_simple.trace.signals import UPPER_NAMES, WAIST_RPY
    from simple.robots.g1_sonic import WHOLE_BODY_JOINTS

    joints = list(WHOLE_BODY_JOINTS)
    picked = [joints[i] for _, start, end in STATE_SLICES for i in range(start, end)]
    assert tuple(picked) == UPPER_NAMES
    assert [joints[i] for i in WAIST_RPY] == ["waist_roll_joint", "waist_pitch_joint",
                                             "waist_yaw_joint"]  # fmt: skip


def test_entry_module_writes_one_trace_directory_per_episode(tmp_path: Path) -> None:
    import json

    from flywheel_simple.trace.run import install_from_env
    from simple.baselines import client
    from simple.cli import eval_decoupled_wbc
    from simple.evals.api import EvalConfig

    data_dir = os.environ.get("FW_TRACE_DATA_TWO_TABLE")
    if not data_dir:
        pytest.skip("FW_TRACE_DATA_TWO_TABLE not set")
    job_dir = tmp_path / "job"
    pinned = "fc7f9c90ebbf8c4662fd70e58de5aed668c0fbc5ccfbbd951dce705729cdeea2"
    install_from_env({"FW_TRACE_JOB_DIR": str(job_dir), "FW_JOB_ID": "sim-test",
                      "FW_RUN_PLAN_ID": "g0-DA-38-20261104",
                      "FW_CAMERA_REFERENCE_SHA256": pinned})  # fmt: skip
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client.HttpActionClient, "query_action", hold_pose_query)
        eval_decoupled_wbc.run_eval(
            EvalConfig(env_id=TWO_TABLE, policy="psi0_decoupled_wbc", data_format="lerobot",
                       data_dir=data_dir, sim_mode="mujoco", headless=True, save_video=False,
                       eval_dir=str(tmp_path / "eval"), max_episode_steps=STEPS,
                       num_episodes=1, num_workers=1),  # fmt: skip
            show_progress=False,
        )
    (trace_dir,) = [d for d in job_dir.iterdir() if (d / "steps.jsonl").exists()]
    steps = [json.loads(line) for line in (trace_dir / "steps.jsonl").read_text().splitlines()]
    camera_lines = (trace_dir / "camera_params.jsonl").read_text().splitlines()
    cams = [json.loads(line) for line in camera_lines]
    result = json.loads((trace_dir / "rollout_result.json").read_text())
    assert len(steps) == STEPS and {s["trace_id"] for s in steps} == {trace_dir.name}
    assert {c["uid"] for c in cams} == {"head_stereo_left", "head_stereo_right"}
    assert {c["reference_sha256"] for c in cams} == {pinned}
    assert result["trace_ref"]["uri"] == trace_dir.as_posix()
    assert result["infra_status"] == "ok"
    assert result["adapter_info"]["version"].startswith("simple@")

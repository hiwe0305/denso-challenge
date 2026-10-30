"""Stand and walk G1 under GR00T decoupled WBC, the controller of SIMPLE's *Teleop-v0 tasks.

Ported from scripts/g0/simple/run_two_table.py (S1-02). The upper body holds the
WBC default pose; the lower body runs the Balance/Walk RL policies and follows
`navigate_cmd = [vx, vy, yaw flag, target yaw]`. Facts S1-02 measured and this
module keeps: the WBC runs from the first step while the elastic band holds the
pelvis, the band stops lowering at -0.25 m (lowering further drags the robot into
a squat), and the WBC `SIMULATE_DT` must equal the env's `physics_dt`.

`simple`, `decoupled_wbc`, `gear_sonic` and `gymnasium` are imported inside
functions (through `_mod`) so this module imports in the workspace, where they
are absent.
"""

from __future__ import annotations

import importlib
import time
from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

CONTROL_DT = 1.0 / 50  # env step at render_hz 50
BAND_STOP_LENGTH = -0.25


def _mod(name: str) -> Any:
    """Import a SIMPLE-venv module lazily, typed as Any for the workspace type check."""
    return importlib.import_module(name)


def make_sonic_env(env_id: str, seed: int | None = None, **kwargs: Any) -> Any:
    """Build a SonicLocoManipEnv task in `sim_mode=mujoco`, headless, as teleop_decoupled_wbc."""
    gym = _mod("gymnasium")
    _mod("simple.envs")  # registers simple/* env ids
    sonic_config = _mod("gear_sonic.utils.mujoco_sim.configs").SimLoopConfig().load_wbc_yaml()
    sonic_config["ENV_NAME"] = "simple"
    options: dict[str, Any] = {
        "sim_mode": "mujoco",
        "headless": True,
        "render_hz": 50,
        "physics_dt": float(sonic_config["SIMULATE_DT"]),
        "webrtc": False,
        "sonic_config": sonic_config,
    }
    options.update(kwargs)
    env = gym.make(env_id, **options)
    env.reset(seed=seed)
    return env


class StandWalkController:
    """Decoupled WBC holding the default upper-body pose: PicoDecoupledAgent minus PICO."""

    def __init__(self, robot: Any) -> None:
        ControlLoopConfig = _mod(
            "decoupled_wbc.control.main.teleop.configs.configs"
        ).ControlLoopConfig
        get_wbc_policy = _mod("decoupled_wbc.control.policy.wbc_policy_factory").get_wbc_policy
        instantiate_g1_robot_model = _mod(
            "decoupled_wbc.control.robot_model.instantiation.g1"
        ).instantiate_g1_robot_model

        self.robot = robot
        cfg = robot.sonic_config
        enable_waist = cfg.get("enable_waist", False)
        high_elbow = cfg.get("high_elbow_pose", False)
        self._model = instantiate_g1_robot_model(
            waist_location="lower_and_upper_body" if enable_waist else "lower_body",
            high_elbow_pose=high_elbow,
        )
        if self._model.supplemental_info.body_actuated_joints != robot.joint_names[:29]:
            raise ValueError("decoupled WBC joint order differs from the SIMPLE robot")
        loop_cfg = ControlLoopConfig(enable_waist=enable_waist, high_elbow_pose=high_elbow)
        wbc_cfg = loop_cfg.load_wbc_yaml()
        if wbc_cfg["SIMULATE_DT"] != robot.sim_dt:
            raise ValueError(f"WBC SIMULATE_DT {wbc_cfg['SIMULATE_DT']} != {robot.sim_dt}")
        self._policy = get_wbc_policy(
            "g1", self._model, wbc_cfg, init_time=loop_cfg.upper_body_joint_speed
        )
        self._control_frequency = loop_cfg.control_frequency
        self._started = False

    def reset(self) -> None:
        """Fresh WBC pipeline with the RL lower body engaged, as teleop_decoupled_wbc does."""
        self._policy.reset(init_time=time.monotonic())
        self._policy.lower_body_policy.use_policy_action = True
        self._started = False

    def action(
        self,
        sim_obs: dict[str, Any],
        navigate_cmd: Sequence[float] = (0.0, 0.0, 0.0, 0.0),
        wrist_pose: NDArray[np.float64] | None = None,
    ) -> Any:
        """One `decoupled_wbc` ActionCmd; the first call ramps to the target over 2 s."""
        base_height = _mod("decoupled_wbc.control.main.constants").DEFAULT_BASE_HEIGHT
        ActionCmd = _mod("simple.core.action").ActionCmd

        if wrist_pose is not None:
            raise NotImplementedError("wrist targets go through TeleopRetargetingIK (DA-33)")
        t_now = time.monotonic()
        self._policy.set_observation(self._wbc_observation(sim_obs))
        self._policy.set_goal(
            {
                "target_upper_body_pose": self._model.get_initial_upper_body_pose(),
                "navigate_cmd": np.asarray(navigate_cmd, dtype=float),
                "base_height_command": np.atleast_1d(np.asarray(base_height)),
                "target_time": t_now + (1 / self._control_frequency if self._started else 2.0),
                "interpolation_garbage_collection_time": t_now - 2 / self._control_frequency,
                "timestamp": t_now,
            }
        )
        self._started = True
        q = self._policy.get_action(time=t_now)
        return ActionCmd(
            "decoupled_wbc",
            target_q=self._model.get_body_actuated_joints(q["q"]),
            target_waist=q["target_waist"],
            left_hand_q=self._model.get_hand_actuated_joints(q["q"], side="left"),
            right_hand_q=self._model.get_hand_actuated_joints(q["q"], side="right"),
        )

    def _wbc_observation(self, sim_obs: dict[str, Any]) -> dict[str, Any]:
        # As PicoDecoupledAgent._build_wbc_observation; importing that module pulls
        # in PICO video-streaming dependencies.
        z7 = np.zeros(7)

        # MJCF hand joint order -> natural
        def natural(q: NDArray[np.float64]) -> NDArray[np.float64]:
            return np.concatenate([q[:3], q[5:7], q[3:5]])

        def full(body_key: str, hand_key: str, default_body: NDArray[np.float64] | None) -> Any:
            return self._model.get_configuration_from_actuated_joints(
                body_actuated_joint_values=sim_obs.get(body_key, default_body),
                left_hand_actuated_joint_values=natural(sim_obs.get(f"left_hand_{hand_key}", z7)),
                right_hand_actuated_joint_values=natural(sim_obs.get(f"right_hand_{hand_key}", z7)),
            )

        imu_vel = sim_obs.get("secondary_imu_vel")
        return {
            "q": full("body_q", "q", None),
            "dq": full("body_dq", "dq", None),
            "ddq": full("body_ddq", "ddq", np.zeros(29)),
            "tau_est": full("body_tau_est", "tau_est", np.zeros(29)),
            "floating_base_pose": sim_obs["floating_base_pose"],
            "floating_base_vel": sim_obs["floating_base_vel"],
            "floating_base_acc": sim_obs.get("floating_base_acc", np.zeros(6)),
            "torso_quat": sim_obs.get("secondary_imu_quat", np.array([1, 0, 0, 0])),
            "torso_ang_vel": imu_vel[3:6] if imu_vel is not None else np.zeros(3),
            "wrist_pose": sim_obs.get("wrist_pose", np.zeros(14)),
        }


def release_band(
    env: Any,
    controller: StandWalkController,
    drop_rate: float = 0.15,
    stop_length: float = BAND_STOP_LENGTH,
    still_speed: float = 0.05,
    max_steps: int = 400,
) -> int:
    """Lower the elastic band under WBC control and switch it off once the pelvis is still.

    Returns the env step at which the band was released.
    """
    ActionCmd = _mod("simple.core.action").ActionCmd

    sim = env.unwrapped
    robot = sim.task.robot
    band = robot.elastic_band
    if band is None or not band.enable:
        return 0
    hold = ActionCmd("elastic_band", dropping=False, drop_rate=0.0)

    def hold_band() -> None:
        # Refresh the band force after every physics substep while it is on.
        if band.enable:
            robot.apply_action(hold)

    sim.substep_callback = hold_band
    for step in range(max_steps):
        band.length = max(band.length - drop_rate * CONTROL_DT, stop_length)
        if band.length <= stop_length and abs(float(sim.mjData.qvel[2])) < still_speed:
            band.enable = False
            sim.mjData.xfrc_applied[robot.band_attached_link] = 0.0
            sim.substep_callback = None
            return step
        env.step(controller.action(robot.prepare_obs()))
    raise RuntimeError(f"pelvis not still after {max_steps} steps; band kept on")

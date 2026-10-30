"""The tray task as a SIMPLE task and gymnasium env id, registered from this package.

Modelled on SIMPLE's g1_wholebody_locomotion_pick_between_tables_teleop: robot
g1_sonic under GR00T decoupled WBC, head stereo camera, physics_dt 0.005,
render_hz 50. SIMPLE is not forked: importing this module registers the task
in TaskRegistry, `register()` adds the env id to gymnasium.

The scene (both tables, the tray and its parts) is one MJCF written per reset
and attached through SIMPLE's articulated-object path, the only actor path in
`sim_mode=mujoco` that keeps our geoms, materials and textures as they are.

Policy observations stay as SIMPLE builds them (joint positions and camera
images). Tray, part and target poses go only to `info["privileged"]`
(design 3.6), added by TrayTransferEnv.

Only runs in the SIMPLE venv (S1-02).
"""

from __future__ import annotations

import math
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
from gymnasium import spaces  # type: ignore[import-not-found]
from simple.assets.articulate import ArticulatedObjectAsset  # type: ignore[import-not-found]
from simple.core.layout import Layout  # type: ignore[import-not-found]
from simple.core.task import Task  # type: ignore[import-not-found]
from simple.dr.manager import DRManager  # type: ignore[import-not-found]
from simple.envs.sonic_loco_manip import SonicLocoManipEnv  # type: ignore[import-not-found]
from simple.robots.registry import RobotRegistry  # type: ignore[import-not-found]
from simple.sensors import StereoCameraCfg  # type: ignore[import-not-found]
from simple.tasks.registry import TaskRegistry  # type: ignore[import-not-found]

from flywheel_simple.tray.config import TrayConfig
from flywheel_simple.tray.geometry import Pose2D
from flywheel_simple.tray.mjcf import write_scene_mjcf
from flywheel_simple.tray.randomize import SEED_RANGES, EpisodeSample, sample_episode, split_of
from flywheel_simple.wbc import make_sonic_env

TASK_UID = "g1_wholebody_tray_transfer_teleop"
ENV_ID = "simple/G1WholebodyTrayTransferTeleop-v0"
INSTRUCTION = (
    "Pick up the parts tray from table A with both hands, carry it to table B "
    "and place it in the target zone."
)
SCENE_ACTOR = "articulated"  # the key SIMPLE's MuJoCo engine expects for this actor path
SCENE_LIGHT_DIFFUSE = 0.4  # scaled by the level-2 light factor


def scene_dir() -> Path:
    """Where per-reset scene MJCF files go: $FLYWHEEL_TRAY_DIR or fwdata/simple/tray/scene."""
    if "FLYWHEEL_TRAY_DIR" in os.environ:
        return Path(os.environ["FLYWHEEL_TRAY_DIR"])
    return TrayConfig.default_path().parents[2] / "fwdata/simple/tray/scene"


def _yaw_quat(yaw: float) -> list[float]:
    return [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]


@TaskRegistry.register(TASK_UID)
class G1WholebodyTrayTransferTeleop(Task):  # type: ignore[misc]
    uid: str = TASK_UID
    label: str = "G1 TELEOP Tray Transfer"
    description: str = (
        "G1 carries a tray of six loose parts with both hands from table A to a target "
        "zone on table B."
    )
    metadata: dict[str, Any] = {
        "physics_dt": 0.005,
        "control_hz": 200,
        "render_hz": 50,
        "dr_level": 0,
        "version": 1.0,
        "need_gravity": True,
        "max_episode_steps": 4500,  # 90 s at render_hz 50 (design 4)
    }
    robot_cfg: dict[str, Any] = dict(uid="g1_sonic")
    sensor_cfgs: dict[str, Any] = dict(
        head_stereo=StereoCameraCfg(
            uid="Realsense_D435i",
            mount="eye_in_head",
            width=640,
            height=360,
            focal_length=1.93,
            fov=np.deg2rad(110),
            near=0.2,
            far=5,
            baseline=0.05,
            pose=dict(position=[0.0, 0.0, 0.0]),
        ),
    )
    dr_cfgs: dict[str, Any] = {}

    def __init__(
        self,
        robot_uid: str = "g1_sonic",
        split: str = "train",
        render_hz: int | None = None,
        dr_level: int = 0,
        tray_config: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.metadata = dict(type(self).metadata)
        self.cfg = TrayConfig.load(Path(tray_config) if tray_config else None)
        self._layout: Any = None
        self._robot = RobotRegistry.make(uid=robot_uid, **kwargs)
        super().__init__(
            dr=DRManager(level=dr_level),
            split=split,
            render_hz=render_hz,
            dr_level=dr_level,
            *args,
            **kwargs,
        )

    @property
    def layout(self) -> Any:
        assert self._layout is not None, "call reset() first"
        return self._layout

    @property
    def instruction(self) -> str:
        return INSTRUCTION

    @property
    def action_space(self) -> Any:
        return self.robot.controller.action_space

    @property
    def observation_space(self) -> Any:
        obs: dict[str, Any] = {
            "joint_qpos": spaces.Box(
                -np.pi, np.pi, shape=(self.robot.wholebody_dof,), dtype=np.float32
            ),
        }
        obs.update(dict(super().observation_space))
        return spaces.Dict(obs)

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> None:
        """Sample the episode for (level, seed), write its scene and lay out robot and camera.

        `options["level"]` overrides the env's dr_level. A seed outside the train,
        dev and holdout ranges is refused; no seed draws one from the train range.
        """
        level = int((options or {}).get("level", self.metadata.get("dr_level", 0)))
        if seed is None:
            seed = int(np.random.default_rng().integers(SEED_RANGES["train"].stop))
        split_of(seed)
        self.sample: EpisodeSample = sample_episode(self.cfg, level, seed)
        self.target_pose: Pose2D = self.sample.target_pose
        scene = write_scene_mjcf(
            replace(self.cfg, part_mass=self.sample.part_mass),
            scene_dir() / f"scene_{os.getpid()}.xml",
            tray_pose=self.sample.tray_pose,
            table_gap=self.sample.table_gap,
            light_diffuse=SCENE_LIGHT_DIFFUSE * self.sample.light_scale,
        )
        spawn = self.sample.robot_spawn
        layout = Layout()
        layout.add_robot(self.robot)
        layout.robot.pose.position = [spawn.x, spawn.y, 0.0]
        layout.robot.pose.quaternion = _yaw_quat(spawn.yaw)
        layout.add_articulated_object(
            SCENE_ACTOR,
            ArticulatedObjectAsset(
                uid="tray_scene",
                label="tray_scene",
                name="tray scene",
                usd_path=None,
                mjcf_path=str(scene),
            ),
        )
        for cam_id, cam_cfg in self.sensor_cfgs.items():
            if cam_cfg.quaternion is None:
                cam_cfg.pose["quaternion"] = self.robot.head_camera_orientation
            layout.add_camera(cam_id, cam_cfg)
        self._layout = layout
        self.robot.reset(spawn_pose=layout.robot.pose)

    def privileged_state(self, mujoco_env: Any) -> dict[str, Any]:
        """Tray, part and target poses: for the scorer, planner and logs, never the policy."""
        data = mujoco_env.mjData
        return {
            "tray_pos": np.asarray(data.body("tray").xpos).copy(),
            "tray_quat": np.asarray(data.body("tray").xquat).copy(),
            "part_pos": np.array([data.body(f"part_{i}").xpos for i in range(6)]),
            "target_pose": np.array([self.target_pose.x, self.target_pose.y, self.target_pose.yaw]),
        }

    def check_success(self, info: dict[str, Any], *args: Any, **kwargs: Any) -> bool:
        return False

    def compute_reward(self, info: dict[str, Any], *args: Any, **kwargs: Any) -> float:
        # Reward is not designed for this task (design 2); kept for SIMPLE's interface.
        return 0.0


class TrayTransferEnv(SonicLocoManipEnv):  # type: ignore[misc]
    """SonicLocoManipEnv that adds the task's privileged state to `info`."""

    def _get_info(self) -> dict[str, Any]:
        info: dict[str, Any] = super()._get_info()
        info["privileged"] = self.task.privileged_state(self.mujoco)
        return info


def register() -> None:
    """Add ENV_ID to gymnasium's registry; safe to call more than once."""
    import gymnasium as gym

    if ENV_ID not in gym.registry:
        gym.register(
            id=ENV_ID,
            entry_point=f"{__name__}:TrayTransferEnv",
            kwargs={"task": TASK_UID},
        )


def make_env(seed: int | None = 0, level: int = 0, **kwargs: Any) -> Any:
    register()
    return make_sonic_env(ENV_ID, seed=seed, dr_level=level, **kwargs)

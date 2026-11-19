"""The tray task on the jig scene (DA-41): fixed target on table B, locating jig around it.

A second SIMPLE task and env id beside DA-32's, so the scene of the frozen DA-34 run
plans (`simple_task`, `+zone1`) stays exactly as pinned. The task is DA-32's with one
change in `reset`: once the parent has sampled the episode and written its scene, the
target moves to the jig pose (`jig.with_jig_target`) and the scene file is written
again with the jig on table B. The layout already points at that file, so SIMPLE loads
the jig scene. Planner, step tracker and privileged state all read `task.sample` /
`task.target_pose`, which now hold the jig target.

Only runs in the SIMPLE venv (S1-02).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from simple.robots.registry import RobotRegistry  # type: ignore[import-not-found]
from simple.tasks.registry import TaskRegistry  # type: ignore[import-not-found]

from flywheel_simple.tray.jig import JigConfig, with_jig_target, write_jig_scene_mjcf
from flywheel_simple.tray.predicates import StepTracker
from flywheel_simple.tray.simple_task import (
    SCENE_LIGHT_DIFFUSE,
    G1WholebodyTrayTransferTeleop,
)
from flywheel_simple.wbc import make_sonic_env

JIG_TASK_UID = "g1_wholebody_tray_transfer_jig_teleop"
JIG_ENV_ID = "simple/G1WholebodyTrayTransferJigTeleop-v0"


@TaskRegistry.register(JIG_TASK_UID)
class G1WholebodyTrayTransferJigTeleop(G1WholebodyTrayTransferTeleop):
    uid: str = JIG_TASK_UID
    label: str = "G1 TELEOP Tray Transfer (jig)"
    description: str = (
        "G1 carries a tray of six loose parts with both hands from table A into a fixed "
        "locating jig on table B."
    )

    def __init__(self, *args: Any, jig_config: str | None = None, **kwargs: Any) -> None:
        self.jig = JigConfig.load(Path(jig_config) if jig_config else None)
        super().__init__(*args, **kwargs)
        problems = self.jig.check(self.cfg)
        if problems:
            raise ValueError("jig does not fit the tray: " + "; ".join(problems))

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> None:
        super().reset(seed=seed, options=options)
        assert self.scene_path is not None
        self.sample = with_jig_target(self.cfg, self.jig, self.sample)
        self.target_pose = self.sample.target_pose
        write_jig_scene_mjcf(
            replace(self.cfg, part_mass=self.sample.part_mass),
            self.jig,
            self.scene_path,
            tray_pose=self.sample.tray_pose,
            table_gap=self.sample.table_gap,
            light_diffuse=SCENE_LIGHT_DIFFUSE * self.sample.light_scale,
            target_pose=self.target_pose,
        )
        self.tracker = StepTracker(self.cfg, self.sample)

    def state_dict(self) -> dict[str, Any]:
        state = super().state_dict()
        state["tray"]["jig"] = dict(self.jig.__dict__)
        return state


def register() -> None:
    """Add JIG_ENV_ID to gymnasium's registry; safe to call more than once."""
    import gymnasium as gym  # type: ignore[import-not-found]

    if JIG_ENV_ID not in gym.registry:
        gym.register(
            id=JIG_ENV_ID,
            entry_point="flywheel_simple.tray.simple_task:TrayTransferEnv",
            kwargs={"task": JIG_TASK_UID},
        )


def make_env(seed: int | None = 0, level: int = 0, **kwargs: Any) -> Any:
    """A tray env on the jig scene; as `simple_task.make_env` (one live env per process)."""
    register()
    TaskRegistry._instances.pop(JIG_TASK_UID, None)
    RobotRegistry._instances.pop(G1WholebodyTrayTransferJigTeleop.robot_cfg["uid"], None)
    return make_sonic_env(JIG_ENV_ID, seed=seed, dr_level=level, **kwargs)

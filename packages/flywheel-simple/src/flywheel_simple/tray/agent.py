"""The tray planner driving G1 in SIMPLE: one episode from reset to DONE or ABORT (DA-33).

TrayAgent turns each step's scene state into a PlannerCommand and that into a
decoupled-WBC ActionCmd: wrists and hands through StandWalkController, base
through NavIntegrator (`limit_yaw` = the command's heading). run_episode resets
the env, lowers the elastic band, waits for the pelvis to stand still (it
slides ~9 cm in the 0.6 s after release, docs/g0/tray/upper-body.md), then runs
the planner until DONE plus the success window, ABORT, or the 90 s limit.

Only runs in the SIMPLE venv.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from flywheel_simple.tray.geometry import Pose2D
from flywheel_simple.tray.planner import Phase, PlannerCommand, PlannerConfig, TrayPlanner
from flywheel_simple.tray.simple_task import tray_state
from flywheel_simple.wbc import NavIntegrator, StandWalkController, release_band
from flywheel_simple.wbc.drive import pelvis_pose

CONTROL_DT = 1.0 / 50
STILL_SPEED = 0.05  # m/s, pelvis
STILL_HOLD_S = 0.5
MAX_SETTLE_S = 5.0
EPISODE_LIMIT_S = 90.0
SUCCESS_WINDOW_S = 3.0  # after DONE: release_stand needs t_stable of a still tray

OnStep = Callable[[dict[str, Any], dict[str, Any], Any], None]


@dataclass(frozen=True)
class EpisodeResult:
    success: bool
    failure: str | None
    abort_reason: str | None
    phases: list[tuple[str, float]] = field(default_factory=list)  # (phase, sim time entered)
    steps: int = 0
    sim_s: float = 0.0
    wall_s: float = 0.0


class TrayAgent:
    """PlannerCommand -> ActionCmd for one env; `reset` after each env reset."""

    def __init__(self, env: Any, planner_cfg: PlannerConfig) -> None:
        self.env = env
        self.planner_cfg = planner_cfg
        self.ctrl = StandWalkController(env.unwrapped.task.robot)
        self.nav = NavIntegrator(dt=CONTROL_DT)
        self.planner: TrayPlanner | None = None
        self.last_command: PlannerCommand | None = None

    def reset(self) -> None:
        """New planner for the task's current episode sample; fresh WBC pipeline."""
        task = self.env.unwrapped.task
        self.planner = TrayPlanner(self.planner_cfg, task.cfg, task.sample)
        self.ctrl.reset()
        self.last_command = None

    def start(self) -> None:
        """Begin planning from the robot's heading and wrists now (after the band is released)."""
        assert self.planner is not None, "call reset() first"
        self.nav.reset(yaw=pelvis_pose(self.env)[1])
        robot = self.env.unwrapped.task.robot
        self.planner.start(*self.ctrl.ik.current_wrists(robot.prepare_obs()))

    def stand(self) -> Any:
        """Default upper body, no walking: for band release and settling."""
        return self.ctrl.action(self.env.unwrapped.task.robot.prepare_obs())

    def act(self, obs: dict[str, Any], info: dict[str, Any]) -> Any:
        sim = self.env.unwrapped
        assert self.planner is not None, "call reset() first"
        state = tray_state(sim.mjModel, sim.mjData)
        xy, yaw = pelvis_pose(self.env)
        cmd = self.planner.step(state, Pose2D(float(xy[0]), float(xy[1]), yaw), info["tray_report"])
        self.last_command = cmd
        navigate = self.nav.command(*cmd.nav, limit_yaw=cmd.heading)
        return self.ctrl.action(
            sim.task.robot.prepare_obs(),
            navigate_cmd=navigate,
            wrist_pose=(cmd.left_wrist, cmd.right_wrist),
            hand_closure=cmd.hand_closure,
        )


def settle(env: Any, agent: TrayAgent) -> int:
    """Stand until the pelvis is slower than STILL_SPEED for STILL_HOLD_S; returns steps."""
    still = 0.0
    prev = pelvis_pose(env)[0]
    for k in range(round(MAX_SETTLE_S / CONTROL_DT)):
        env.step(agent.stand())
        xy = pelvis_pose(env)[0]
        speed = math.hypot(*(xy - prev)) / CONTROL_DT
        prev = xy
        still = still + CONTROL_DT if speed < STILL_SPEED else 0.0
        if still >= STILL_HOLD_S:
            return k + 1
    raise RuntimeError(f"pelvis not still within {MAX_SETTLE_S} s of band release")


def run_episode(
    env: Any,
    agent: TrayAgent,
    seed: int,
    level: int,
    on_step: OnStep | None = None,
) -> EpisodeResult:
    """Reset to (seed, level), release the band, settle, then run the planner."""
    wall0 = time.perf_counter()
    obs, info = env.reset(seed=seed, options={"level": level})
    agent.reset()
    release_band(env, agent.ctrl)
    settle(env, agent)
    agent.start()
    sim = env.unwrapped
    t0 = float(sim.mjData.time)
    obs, _, _, _, info = env.step(agent.stand())

    phases: list[tuple[str, float]] = []
    steps, done_since = 0, None
    report = info["tray_report"]
    while float(sim.mjData.time) - t0 < EPISODE_LIMIT_S:
        action = agent.act(obs, info)
        cmd = agent.last_command
        assert cmd is not None
        if not phases or phases[-1][0] != cmd.phase.name:
            phases.append((cmd.phase.name, round(float(sim.mjData.time) - t0, 2)))
        obs, _, terminated, _, info = env.step(action)
        steps += 1
        if on_step is not None:
            on_step(obs, info, action)
        report = info["tray_report"]
        if cmd.phase is Phase.ABORT or terminated:
            break
        if cmd.phase is Phase.DONE:
            done_since = done_since if done_since is not None else float(sim.mjData.time)
            if float(sim.mjData.time) - done_since >= SUCCESS_WINDOW_S:
                break
    cmd = agent.last_command
    return EpisodeResult(
        success=bool(report.success),
        failure=report.failure,
        abort_reason=cmd.abort_reason if cmd is not None else None,
        phases=phases,
        steps=steps,
        sim_s=round(float(sim.mjData.time) - t0, 2),
        wall_s=round(time.perf_counter() - wall0, 1),
    )

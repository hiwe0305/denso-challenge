"""The tray planner driving G1 in SIMPLE: one episode from reset to DONE or ABORT (DA-33).

TrayAgent turns each step's scene state into a PlannerCommand and that into a
decoupled-WBC ActionCmd: wrists and hands through StandWalkController, base
through NavIntegrator (`limit_yaw` = the command's heading). run_episode resets
the env and starts an episode as SIMPLE's eval-decoupled-wbc and
replay-decoupled-wbc do (D-24): no elastic band, the WBC holds its standing pose
until `robot.stabilized` (at most STABILIZE_MAX_STEPS steps). Recorded episodes
then begin from the state a replay or a policy evaluation begins from. The
planner runs until DONE plus the success window, ABORT, or the 90 s limit.

Only runs in the SIMPLE venv.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from flywheel_simple.tray.geometry import Pose2D
from flywheel_simple.tray.planner import Phase, PlannerCommand, PlannerConfig, TrayPlanner
from flywheel_simple.tray.simple_task import tray_state
from flywheel_simple.wbc import NavIntegrator, StandWalkController
from flywheel_simple.wbc.drive import pelvis_pose

CONTROL_DT = 1.0 / 50
STABILIZE_MAX_STEPS = 300  # eval_decoupled_wbc's cap
EPISODE_LIMIT_S = 90.0
SUCCESS_WINDOW_S = 3.0  # after DONE: release_stand needs t_stable of a still tray

OnStep = Callable[[dict[str, Any], dict[str, Any], Any], None]
# (observation, info, StandWalkController.last_record): the step's input and its action
OnFrame = Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], None]


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
        self.ctrl = StandWalkController(
            env.unwrapped.task.robot, max_joint_step=planner_cfg.arm_step_max
        )
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


def stabilize(env: Any, agent: TrayAgent) -> tuple[dict[str, Any], dict[str, Any], int]:
    """Stand until `robot.stabilized`, as eval/replay-decoupled-wbc's loop; (obs, info, steps).

    `robot.stabilized` counts its calls (it needs 100 before it checks the base
    velocity), so it is read once per step, as SIMPLE does.
    """
    robot = env.unwrapped.task.robot
    obs: dict[str, Any] = {}
    info: dict[str, Any] = {}
    steps = 0
    while not robot.stabilized and steps < STABILIZE_MAX_STEPS:
        obs, _, _, _, info = env.step(agent.stand())
        steps += 1
    return obs, info, steps


def run_episode(
    env: Any,
    agent: TrayAgent,
    seed: int,
    level: int,
    on_step: OnStep | None = None,
    on_frame: OnFrame | None = None,
    limit_s: float = EPISODE_LIMIT_S,
) -> EpisodeResult:
    """Reset to (seed, level), stand until stabilized (D-24), then run the planner.

    `on_frame` sees every planner step before it is applied (the recorder's input),
    so frames start on the step after stabilization, where a replay starts its
    first recorded frame (Review Focus 4); `on_step` sees the result. `limit_s`
    caps the planner's sim time.
    """
    wall0 = time.perf_counter()
    env.reset(seed=seed, options={"level": level})
    agent.reset()
    obs, info, _ = stabilize(env, agent)
    agent.start()
    sim = env.unwrapped
    t0 = float(sim.mjData.time)

    phases: list[tuple[str, float]] = []
    steps, done_since = 0, None
    report = info["tray_report"]
    while float(sim.mjData.time) - t0 < limit_s:
        action = agent.act(obs, info)
        cmd = agent.last_command
        assert cmd is not None
        if not phases or phases[-1][0] != cmd.phase.name:
            phases.append((cmd.phase.name, round(float(sim.mjData.time) - t0, 2)))
        if on_frame is not None:
            on_frame(obs, info, agent.ctrl.last_record)
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

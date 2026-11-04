"""Record PICO teleop demos of the tray task with SIMPLE's recorder (DA-35 AC 1, 2).

The loop follows `simple.cli.teleop_decoupled_wbc.main` step for step (same
agent calls, same frame builder, same LeRobot exporter, real-time 50 Hz for a
person at the headset) and adds what the tray task needs:

- reset to an explicit (level, seed) list instead of a random seed;
- tray pose, part positions and the seven step flags in every frame;
- a `flywheel` block in each saved episode's environment_config;
- one line per attempt in `attempts.jsonl` and one per session in
  `sessions.jsonl`, also for attempts that are not saved;
- scripted streamers run on a SimClock: one tick per step, no pacing, so an
  episode is the same on every run and faster than real time;
- only successful attempts are saved, unless `keep_failed`; an attempt ends at
  success, the first StepTracker failure label, time out or operator reset;
- videos go through DA-33's JoinedVideoWriter (`tray/recorder.py`), not
  decoupled_wbc's VideoWriter, whose `stop()` raced its encoder thread and crashed
  or hung S2 workers under load.

Run in the SIMPLE venv (PyAV and, for PICO, xrobotoolkit_sdk installed):

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m flywheel_simple.tray.pico.session --conditions 0:0-4,1:1-5 --operator op-01
"""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from flywheel_simple.tray import recorder
from flywheel_simple.tray.pico.conditions import Condition, ConditionQueue, parse_conditions
from flywheel_simple.tray.pico.recording import (
    TRAY_FEATURES,
    AttemptLog,
    Outcome,
    episode_outcome,
    flywheel_block,
    tray_frame,
)

MAX_EPISODE_STEPS = 4500  # 90 s at 50 Hz, the task's limit (design 28/10 section 4)
CONTROL_DT = 1.0 / 50
FPS = 50
DEFAULT_SAVE_DIR = Path("fwdata/simple/tray/pico")


def _mod(name: str) -> Any:
    """Import a SIMPLE-venv module lazily, typed as Any for the workspace type check."""
    return importlib.import_module(name)


@dataclass(frozen=True)
class SessionSummary:
    session: str
    operator: str
    source_detail: str
    started_at: str
    wall_min: float
    attempts: int
    successes: int
    saved: int


def make_teleop_env(
    level: int = 0, headless: bool = True, max_episode_steps: int = MAX_EPISODE_STEPS
) -> Any:
    """The tray env built as teleop_decoupled_wbc builds its env."""
    from flywheel_simple.tray.simple_task import ENV_ID, register

    register()
    cli = _mod("simple.cli.teleop_decoupled_wbc")
    sonic_config = cli._load_sonic_config()
    return _mod("gymnasium").make(
        ENV_ID,
        sim_mode="mujoco",
        render_hz=FPS,
        physics_dt=sonic_config["SIMULATE_DT"],
        headless=headless,
        max_episode_steps=max_episode_steps,
        sonic_config=sonic_config,
        target=None,
        dr_level=level,
        success_criteria=3,
    )


def simple_commit() -> str:
    root = Path(_mod("simple").__file__).resolve().parents[2]
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip()


def init_exporter(save_root: Path, env: Any, agent: Any, ego_view_shape: Any) -> Any:
    """SIMPLE's `_init_exporter` plus TRAY_FEATURES and JoinedVideoWriter; resumes a dataset."""
    utils = _mod("decoupled_wbc.data.utils")
    rec = _mod("simple.cli._decoupled_wbc_recording")
    robot_model = agent._dwbc_robot_model
    features = utils.get_dataset_features(robot_model)
    rec.set_ego_view_feature_shape(features, ego_view_shape)
    rec.validate_existing_ego_view_feature_shape(str(save_root), ego_view_shape)
    features["observation.state"]["names"] = env.unwrapped.task.robot.joint_names
    features.update(TRAY_FEATURES)
    return recorder._exporter_class().create(
        save_root=str(save_root),
        fps=FPS,
        features=features,
        modality_config=utils.get_modality_config(robot_model),
        task=env.unwrapped.task.instruction,
    )


def write_environment_config(
    exporter: Any, task: Any, episode_index: int, flywheel: dict[str, Any]
) -> None:
    """SIMPLE's `_save_episode_env_config` with the flywheel block added."""
    encoder = _mod("simple.utils").NumpyArrayEncoder
    meta_file = Path(exporter.root) / "meta" / "episodes.jsonl"
    lines = [json.loads(line) for line in meta_file.read_text().splitlines()]
    config = {**task.state_dict(), "flywheel": flywheel}
    lines[episode_index]["environment_config"] = json.dumps(config, cls=encoder)
    meta_file.write_text("".join(json.dumps(entry) + "\n" for entry in lines))


def on_episode_reset(robot: Any, agent: Any) -> None:
    """As the CLI in record mode: no elastic band drop, WBC reset, lower-body policy on."""
    if robot.elastic_band is not None:
        robot.elastic_band.enable = False
    agent._dropping = False
    agent.reset_policy()
    agent._wbc_policy.lower_body_policy.use_policy_action = True


def ready_to_record(robot: Any, agent: Any) -> bool:
    """The CLI's start condition: landed, stable, teleop activated by the operator."""
    landed = not agent._dropping and (robot.elastic_band is None or not robot.elastic_band.enable)
    return bool(
        landed
        and agent._teleop_policy.is_active
        and robot.stabilized
        and agent._cached_target_q is not None
    )


@dataclass
class AttemptResult:
    outcome: Outcome
    frames: int
    failure: str | None
    steps_reached: int


def run_attempt(env: Any, agent: Any, exporter: Any, obs: Any, info: Any, realtime: bool) -> Any:
    """Step until the attempt ends; frames go into the exporter's open episode.

    An agent with a `clock` (SimClock) is ticked once per env step and never
    paced; otherwise `realtime` holds 50 Hz wall time, as the CLI does.
    """
    cli = _mod("simple.cli.teleop_decoupled_wbc")
    sonic_env = env.unwrapped
    task, robot = sonic_env.task, sonic_env.task.robot
    clock = getattr(agent, "clock", None)
    pace = realtime and clock is None
    recording, frames, report = False, 0, None
    while True:
        step_start = time.monotonic()
        action = agent.get_action(obs, instruction=task.instruction, privileged_info=info)
        step_obs, step_info, step_action = obs.copy(), info.copy(), action.copy()
        obs, _, terminated, truncated, info = env.step(action)
        if clock is not None:
            clock.tick()
        reset_requested = agent.reset_requested  # clears on read
        sonic_env.update_viewer()
        sonic_env.update_reward()
        agent.update_render_caches(obs)

        recording = recording or ready_to_record(robot, agent)
        if recording:
            frame = cli._build_frame(
                agent,
                [],
                observation=step_obs,
                privileged_info=step_info,
                action=step_action,
                target_waist=step_action["target_waist"],
            )
            frame.update(tray_frame(step_info["privileged"], step_info.get("tray_report")))
            exporter.add_frame(frame)
            frames += 1

        report = info.get("tray_report")
        outcome = episode_outcome(terminated, truncated, report, reset_requested)
        if outcome is not None:
            return AttemptResult(
                outcome=outcome,
                frames=frames,
                failure=None if report is None else report.failure,
                steps_reached=0 if report is None else sum(report.steps),
            )
        if pace:
            time.sleep(max(0.0, CONTROL_DT - (time.monotonic() - step_start)))


def run_session(
    env: Any,
    agent: Any,
    queue: ConditionQueue,
    *,
    save_dir: Path,
    operator: str,
    session: str,
    source_detail: str,
    keep_failed: bool = False,
    realtime: bool = True,
    make_exporter: Callable[[Path, Any, Any, Any], Any] = init_exporter,
) -> SessionSummary:
    """Record attempts over `queue` until it is empty or the operator interrupts.

    `make_exporter(root, env, agent, ego_view_shape)` defaults to SIMPLE's LeRobot
    exporter; tests pass an in-memory one with the same methods.
    """
    task, robot = env.unwrapped.task, env.unwrapped.task.robot
    attempts_log = AttemptLog(save_dir / "attempts.jsonl")
    commit = simple_commit()
    started_at, t0 = datetime.now().isoformat(timespec="seconds"), time.monotonic()
    exporter: Any = None
    attempts = successes = saved = 0
    try:
        while (condition := queue.current) is not None:
            begin = getattr(getattr(agent, "_pico_streamer", None), "begin_attempt", None)
            if callable(begin):  # before the reset below hands the streamer its new episode
                begin(condition, queue.attempt)
            obs, info = env.reset(seed=condition.seed, options={"level": condition.level})
            if getattr(agent, "clock", None) is not None:
                agent.clock.reset()  # before the pipeline reset reads the time
            on_episode_reset(robot, agent)
            if exporter is None:
                root = save_dir / env.unwrapped.spec.id
                exporter = make_exporter(root, env, agent, obs["head_stereo_left"].shape)
            attempt_start = time.monotonic()
            try:
                result = run_attempt(env, agent, exporter, obs, info, realtime)
            except KeyboardInterrupt:
                result = AttemptResult("interrupted", exporter.episode_buffer["size"], None, 0)
            success = result.outcome == "success"
            episode_index = _finish_episode(
                exporter, task, result, keep_failed or success, condition,
                operator=operator, session=session, source_detail=source_detail, commit=commit,
                meta=streamer_meta(agent),
            )  # fmt: skip
            attempts += 1
            successes += success
            saved += episode_index is not None
            attempts_log.append(
                {
                    "session": session,
                    "operator": operator,
                    "source_detail": source_detail,
                    "level": condition.level,
                    "seed": condition.seed,
                    "condition_attempt": queue.attempt,
                    "outcome": result.outcome,
                    "failure": result.failure,
                    "steps_reached": result.steps_reached,
                    "recorded_frames": result.frames,
                    "sim_s": round(result.frames * CONTROL_DT, 2),
                    "wall_s": round(time.monotonic() - attempt_start, 2),
                    "episode_index": episode_index,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    **streamer_notes(agent),
                }
            )
            if result.outcome == "interrupted":
                break
            queue.record(success)
    finally:
        if exporter is not None:
            exporter.stop_video_writers()
    summary = SessionSummary(
        session=session,
        operator=operator,
        source_detail=source_detail,
        started_at=started_at,
        wall_min=round((time.monotonic() - t0) / 60, 2),
        attempts=attempts,
        successes=successes,
        saved=saved,
    )
    AttemptLog(save_dir / "sessions.jsonl").append(asdict(summary))
    return summary


def streamer_notes(agent: Any) -> dict[str, Any]:
    """What a scripted streamer adds to the attempt log (the virtual operator's phases)."""
    notes = getattr(getattr(agent, "_pico_streamer", None), "attempt_notes", None)
    return dict(notes()) if callable(notes) else {}


def streamer_meta(agent: Any) -> dict[str, Any]:
    """`source_kind` and extra flywheel meta of a scripted streamer's episode (else teleop)."""
    meta = getattr(getattr(agent, "_pico_streamer", None), "episode_meta", None)
    return dict(meta()) if callable(meta) else {}


def _finish_episode(
    exporter: Any,
    task: Any,
    result: AttemptResult,
    keep: bool,
    condition: Condition,
    *,
    operator: str,
    session: str,
    source_detail: str,
    commit: str,
    meta: dict[str, Any] | None = None,
) -> int | None:
    """Save the open episode with its meta, or drop it; the saved index or None."""
    if result.frames == 0 or not keep:
        exporter.skip_and_start_new_episode()
        return None
    episode_index = int(exporter.episode_buffer["episode_index"])
    exporter.save_episode()
    block = flywheel_block(
        condition=condition,
        operator=operator,
        session=session,
        source_detail=source_detail,
        outcome=result.outcome,
        simple_commit=commit,
        source_kind=(meta or {}).get("source_kind", "teleop"),
        extra={k: v for k, v in (meta or {}).items() if k != "source_kind"},
    )
    write_environment_config(exporter, task, episode_index, block)
    return episode_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--conditions", required=True, help="e.g. 0:0-4,1:1-5 (train seeds)")
    parser.add_argument("--operator", required=True, help="pseudonym, e.g. op-01")
    parser.add_argument("--session", default=datetime.now().strftime("s-%Y%m%d-%H%M%S"))
    parser.add_argument("--save-dir", type=Path, default=DEFAULT_SAVE_DIR)
    parser.add_argument("--streamer", choices=["pico", "scripted", "virtual"], default="pico")
    parser.add_argument("--max-attempts", type=int, default=3, help="per condition")
    parser.add_argument("--max-episode-steps", type=int, default=MAX_EPISODE_STEPS)
    parser.add_argument("--keep-failed", action="store_true", help="also save failed attempts")
    parser.add_argument(
        "--style-base", type=int, default=0, help="virtual: base of the per-attempt style seeds"
    )
    parser.add_argument("--no-style", action="store_true", help="virtual: plain planner targets")
    parser.add_argument(
        "--operator-config", type=Path, default=None, help="virtual: tray_virtual_teleop.yaml"
    )
    parser.add_argument("--no-headless", action="store_true", help="open the MuJoCo viewer")
    args = parser.parse_args(argv)

    conditions = parse_conditions(args.conditions)
    env = make_teleop_env(conditions[0].level, not args.no_headless, args.max_episode_steps)
    robot = env.unwrapped.task.robot
    if args.streamer == "pico":
        agent = _mod("simple.agents.pico_decoupled_agent").PicoDecoupledAgent(robot)
    else:
        from flywheel_simple.tray.pico import agent as pico_agent
        from flywheel_simple.tray.pico.clock import SimClock
        from flywheel_simple.tray.pico.operator import OperatorConfig

        operator_cfg = OperatorConfig.load(args.operator_config)
        streamer: Any = pico_agent.ScriptedStreamer()
        if args.streamer == "virtual":
            from flywheel_simple.tray.pico.operator import VirtualOperator
            from flywheel_simple.tray.planner import PlannerConfig

            operator = VirtualOperator(operator_cfg)
            streamer = pico_agent.VirtualPicoStreamer(
                env,
                operator,
                PlannerConfig.load(),
                style_base=None if args.no_style else args.style_base,
            )
        agent = pico_agent.StreamerDecoupledAgent(
            robot, streamer, clock=SimClock(), max_joint_step=operator_cfg.arm_step_max
        )
    agent.num_episodes = len(conditions)
    try:
        summary = run_session(
            env,
            agent,
            ConditionQueue(conditions, max_attempts=args.max_attempts),
            save_dir=args.save_dir,
            operator=args.operator,
            session=args.session,
            source_detail="virtual_teleop"
            if args.streamer == "virtual"
            else f"teleop_{args.streamer}",
            keep_failed=args.keep_failed,
        )
    finally:
        env.close()
        agent.close()
    print(json.dumps(asdict(summary)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

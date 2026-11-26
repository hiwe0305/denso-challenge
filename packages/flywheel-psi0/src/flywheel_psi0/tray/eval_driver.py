"""`eval-decoupled-wbc` on the tray task for a RunPlan eval, in SIMPLE's venv (DA-34 task 3).

Runs `flywheel_simple.tray.run eval-decoupled-wbc` (sim clock, seeded reset, the tray
condition reader) with two runtime patches, so no pinned file of the plan changes:

* each `FLYWHEEL_TRAY_OUTCOMES` row also gets the scorer's seven step flags
  (`scorer_steps`, in `predicates.STEP_NAMES` order) and the sim time at the end of the
  episode (`sim_time_s`): `TrayTransferEnv.outcome` keeps only the failure label;
* and (DA-42) the scorer's version and failure signals (`StepTracker.outcome_fields`:
  `scorer_version`, `failure_t`, `at_failure`, `step_latch_t`, palm-handle minima),
  plus `scorer_v1`: steps, success, failure and failure time of scorer version 1 run
  on the same states by a shadow tracker, so the two versions compare on one rollout
  (rollouts do not repeat on EGL). Rows are only added to; old keys keep their meaning;
* (DA-47) the task's `uid` (`task_uid`): `simple_task.TASK_UID` on scene zone1,
  `jig_task.JIG_TASK_UID` on scene jig2; a row without it is zone1. The jig env id is
  registered too (`jig_task.register`); its task subclasses the zone1 task without
  overriding `compute_reward`, and runs in the same `TrayTransferEnv`, so both patches
  apply to it. Its `reset` replaces `task.tracker` after the parent's, before any step;
  the shadow is built at the first `compute_reward`, from the tracker of the jig target;
* with `FW_TRACE_JOB_DIR` set, DA-38's trace hook (`flywheel_simple.trace.run`) records
  every control cycle (command, measured state, base yaw) under that directory, the
  input of `fw eval diag-system` and of Agent QA/QC.

Runtime dependency: `flywheel_simple` and SIMPLE are imported inside `main()` only, in
SIMPLE's venv with `packages/*/src` on PYTHONPATH; the module itself needs neither, so
the CPU tests drive `install` with stand-ins. One worker only: a spawned worker imports
this module as `__mp_main__` without running `main()` and would miss every patch, and
one Psi0 server at cda3fdf keeps one RTC state for all its clients.

    DEBUG=1 MUJOCO_GL=egl FLYWHEEL_TRAY_OUTCOMES=outcomes.jsonl \
        fwdata/simple/.venv/bin/python -m flywheel_psi0.tray.eval_driver \
        simple/G1WholebodyTrayTransferTeleop-v0 psi0_decoupled_wbc --data-format lerobot \
        --data-dir <set>/dr-level-1 --sim-mode mujoco --headless --port 22186 ...
"""

from __future__ import annotations

import functools
import os
import sys
from collections.abc import Callable, Sequence
from typing import Any

PATCHED = "flywheel_eval_driver"
SHADOW_VERSION = 1  # the scorer version run beside the task's own (DA-42)


def with_scorer_steps(outcome: Callable[[Any], dict[str, Any]]) -> Callable[[Any], dict[str, Any]]:
    """TrayTransferEnv.outcome that adds the step flags and the sim time to the row."""

    @functools.wraps(outcome)
    def wrapped(self: Any) -> dict[str, Any]:
        row = outcome(self)
        report = self.task.report
        row["scorer_steps"] = None if report is None else [bool(s) for s in report.steps]
        row["sim_time_s"] = float(self.mujoco.mjData.time)
        row["task_uid"] = self.task.uid
        tracker = getattr(self.task, "tracker", None)
        if tracker is not None:
            row.update(tracker.outcome_fields())
            row["scorer_v1"] = shadow_result(self.task)
        return row

    setattr(wrapped, PATCHED, True)
    return wrapped


def shadow_tracker(task: Any) -> Any | None:
    """The version 1 tracker beside `task.tracker`, new for each new task tracker.

    The task builds one tracker per reset; the shadow follows it. None when the task's
    tracker is version 1 itself.
    """
    tracker = task.tracker
    if tracker.version == SHADOW_VERSION:
        return None
    shadow = getattr(task, "_fw_shadow", None)
    if shadow is None or shadow[0] is not tracker:
        shadow = (tracker, type(tracker)(tracker.cfg, tracker.sample, version=SHADOW_VERSION))
        task._fw_shadow = shadow
        task._fw_shadow_report = None
    return shadow[1]


def with_shadow_scorer(compute_reward: Callable[..., float]) -> Callable[..., float]:
    """Task.compute_reward that also feeds the cycle's TrayState to the shadow tracker."""

    @functools.wraps(compute_reward)
    def wrapped(self: Any, *args: Any, **kwargs: Any) -> float:
        reward = compute_reward(self, *args, **kwargs)
        shadow = shadow_tracker(self)
        state = self.tracker.last_state
        if shadow is not None and state is not None:
            self._fw_shadow_report = shadow.update(state)
        return reward

    setattr(wrapped, PATCHED, True)
    return wrapped


def shadow_result(task: Any) -> dict[str, Any] | None:
    """Version 1's verdict on the episode, or None (task tracker is version 1, no step)."""
    report = getattr(task, "_fw_shadow_report", None)
    shadow = getattr(task, "_fw_shadow", None)
    if report is None or shadow is None or shadow[0] is not task.tracker:
        return None
    fields = shadow[1].outcome_fields()
    return {
        "scorer_version": SHADOW_VERSION,
        "steps": [bool(s) for s in report.steps],
        "success": bool(report.success),
        "failure": report.failure,
        "failure_t": fields["failure_t"],
        "at_failure": fields["at_failure"],
        "step_latch_t": fields["step_latch_t"],
    }


def install(simple_task: Any) -> None:
    """Patch `TrayTransferEnv.outcome` and the task's `compute_reward` once each."""
    env = simple_task.TrayTransferEnv
    if not getattr(env.outcome, PATCHED, False):
        env.outcome = with_scorer_steps(env.outcome)
    task = simple_task.G1WholebodyTrayTransferTeleop
    if not getattr(task.compute_reward, PATCHED, False):
        task.compute_reward = with_shadow_scorer(task.compute_reward)


def eval_args(argv: Sequence[str]) -> list[str]:
    """The arguments of `eval-decoupled-wbc`; refuses more than one worker."""
    args = list(argv)
    for i, arg in enumerate(args):
        value = arg.split("=", 1)[1] if arg.startswith("--num-workers=") else None
        if arg == "--num-workers" and i + 1 < len(args):
            value = args[i + 1]
        if value is not None and value != "1":
            raise ValueError("eval_driver runs one worker: spawned workers miss its patches")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = eval_args(sys.argv[1:] if argv is None else argv)
    from flywheel_simple.tray import jig_task, run, simple_task  # SIMPLE's venv only

    install(simple_task)
    # run.main registers the zone1 env id (run.prepare); one worker builds its env in this
    # process (eval_args), so registering the jig env id here is enough.
    jig_task.register()
    if os.environ.get("FW_TRACE_JOB_DIR"):
        from flywheel_simple.trace.run import install_from_env

        install_from_env(os.environ)
    return run.main(["eval-decoupled-wbc", *args])


if __name__ == "__main__":
    sys.exit(main())

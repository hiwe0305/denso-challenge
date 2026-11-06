"""`eval-decoupled-wbc` on the tray task for a RunPlan eval, in SIMPLE's venv (DA-34 task 3).

Runs `flywheel_simple.tray.run eval-decoupled-wbc` (sim clock, seeded reset, the tray
condition reader) with two runtime patches, so no pinned file of the plan changes:

* each `FLYWHEEL_TRAY_OUTCOMES` row also gets the scorer's seven step flags
  (`scorer_steps`, in `predicates.STEP_NAMES` order) and the sim time at the end of the
  episode (`sim_time_s`): `TrayTransferEnv.outcome` keeps only the failure label;
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


def with_scorer_steps(outcome: Callable[[Any], dict[str, Any]]) -> Callable[[Any], dict[str, Any]]:
    """TrayTransferEnv.outcome that adds the step flags and the sim time to the row."""

    @functools.wraps(outcome)
    def wrapped(self: Any) -> dict[str, Any]:
        row = outcome(self)
        report = self.task.report
        row["scorer_steps"] = None if report is None else [bool(s) for s in report.steps]
        row["sim_time_s"] = float(self.mujoco.mjData.time)
        return row

    setattr(wrapped, PATCHED, True)
    return wrapped


def install(simple_task: Any) -> None:
    """Patch `simple_task.TrayTransferEnv.outcome` once."""
    env = simple_task.TrayTransferEnv
    if not getattr(env.outcome, PATCHED, False):
        env.outcome = with_scorer_steps(env.outcome)


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
    from flywheel_simple.tray import run, simple_task  # SIMPLE's venv only

    install(simple_task)
    if os.environ.get("FW_TRACE_JOB_DIR"):
        from flywheel_simple.trace.run import install_from_env

        install_from_env(os.environ)
    return run.main(["eval-decoupled-wbc", *args])


if __name__ == "__main__":
    sys.exit(main())

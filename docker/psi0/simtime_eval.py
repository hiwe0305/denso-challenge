"""SIMPLE's eval-decoupled-wbc on sim time or wall time, for any SonicLocoManipEnv task.

Run in the SIMPLE image instead of the `eval-decoupled-wbc` entry point:

    python simtime_eval.py --clock sim|wall <eval-decoupled-wbc args...>

The eval loop, `psi0_decoupled_wbc` and the sonic WBC agent read `time.monotonic()` and sleep to
keep real time, and the WBC interpolates its targets on that clock, so a loaded machine changes
outcomes (docs/he/tray.md 8.1). `flywheel_simple.tray.run` (#90) fixes this for the tray task only:
its sim clock reads the live tray env and falls back to the wall clock for any other task. Here
`--clock sim` swaps the `time` module of those three SIMPLE modules for one whose `monotonic()` is
the MuJoCo time of the env being evaluated and whose `sleep()` returns at once; `--clock wall`
changes nothing, so both runs share this code path. Single process only (num_workers 1).
"""

from __future__ import annotations

import importlib
import sys
import time
from typing import Any

SIM_TIME_MODULES = (
    "simple.cli.eval_decoupled_wbc",
    "simple.baselines.psi0_decoupled_wbc",
    "simple.agents.sonic_decoupled_wbc_agent",
)
_envs: list[Any] = []  # the SonicLocoManipEnv built by the eval, recorded at construction


class SimTime:
    """Stand-in for `time`: monotonic() is the env's MuJoCo time, sleep() does not wait."""

    def monotonic(self) -> float:
        if not _envs:
            return time.monotonic()  # before the env exists, as in flywheel_simple.tray.run
        data = getattr(_envs[-1].mujoco, "mjData", None)  # set on the first reset; the agent
        return float(data.time) if data is not None else 0.0  # reads the clock before it

    def sleep(self, seconds: float) -> None:
        del seconds

    def __getattr__(self, name: str) -> Any:
        return getattr(time, name)


def record_envs(env_cls: Any) -> None:
    init = env_cls.__init__

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        init(self, *args, **kwargs)
        _envs.append(self)

    env_cls.__init__ = __init__


def main(argv: list[str]) -> None:
    if len(argv) < 2 or argv[0] != "--clock" or argv[1] not in ("sim", "wall"):
        raise SystemExit("usage: simtime_eval.py --clock sim|wall <eval-decoupled-wbc args...>")
    clock, rest = argv[1], argv[2:]
    if clock == "sim":
        env_mod = importlib.import_module("simple.envs.sonic_loco_manip")
        record_envs(env_mod.SonicLocoManipEnv)
        for name in SIM_TIME_MODULES:
            setattr(importlib.import_module(name), "time", SimTime())  # noqa: B010
    sys.argv = ["eval-decoupled-wbc", *rest]
    importlib.import_module("simple.cli.eval_decoupled_wbc").typer_main()


if __name__ == "__main__":
    main(sys.argv[1:])

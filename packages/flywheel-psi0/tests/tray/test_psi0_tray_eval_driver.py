"""The eval driver's runtime patches, with stand-ins for SIMPLE's tray env (DA-34 task 3)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from flywheel_psi0.tray.eval_driver import eval_args, install


def fake_simple_task() -> Any:
    class TrayTransferEnv:
        def __init__(self, steps: tuple[bool, ...] | None, time: float) -> None:
            report = None if steps is None else SimpleNamespace(steps=steps)
            self.task = SimpleNamespace(report=report)
            self.mujoco = SimpleNamespace(mjData=SimpleNamespace(time=time))

        def outcome(self) -> dict[str, Any]:
            return {"seed": 1000100, "failure": "L-TIMEOUT"}

    return SimpleNamespace(TrayTransferEnv=TrayTransferEnv)


def test_outcome_rows_get_the_step_flags_and_the_sim_time() -> None:
    simple_task = fake_simple_task()
    install(simple_task)
    env = simple_task.TrayTransferEnv((True, True, False, False, False, False, False), 93.285)
    assert env.outcome() == {
        "seed": 1000100,
        "failure": "L-TIMEOUT",
        "scorer_steps": [True, True, False, False, False, False, False],
        "sim_time_s": 93.285,
    }
    assert simple_task.TrayTransferEnv(None, 0.0).outcome()["scorer_steps"] is None


def test_install_patches_once() -> None:
    simple_task = fake_simple_task()
    install(simple_task)
    patched = simple_task.TrayTransferEnv.outcome
    install(simple_task)
    assert simple_task.TrayTransferEnv.outcome is patched


@pytest.mark.parametrize(
    "argv", [["--num-workers", "2"], ["--num-workers=4"], ["x", "--num-workers", "0"]]
)
def test_more_than_one_worker_is_refused(argv: list[str]) -> None:
    with pytest.raises(ValueError, match="one worker"):
        eval_args(argv)


def test_other_arguments_pass_unchanged() -> None:
    argv = ["simple/G1WholebodyTrayTransferTeleop-v0", "psi0_decoupled_wbc", "--num-workers", "1"]
    assert eval_args(argv) == argv

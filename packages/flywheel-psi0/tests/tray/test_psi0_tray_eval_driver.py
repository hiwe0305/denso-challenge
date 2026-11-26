"""The eval driver's runtime patches, with stand-ins for SIMPLE's tray env (DA-34 task 3)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from flywheel_psi0.tray.eval_driver import eval_args, install


class FakeTracker:
    """StepTracker's surface the driver uses: version, update, last_state, outcome_fields.

    A state is a number; version 2 fails on states >= 2, version 1 on states >= 1.
    """

    def __init__(self, cfg: Any, sample: Any, version: int = 2) -> None:
        self.cfg, self.sample, self.version = cfg, sample, version
        self.last_state: float | None = None
        self.failure_t: float | None = None

    def update(self, state: float) -> Any:
        self.last_state = state
        failed = state >= (2 if self.version == 2 else 1)
        if failed and self.failure_t is None:
            self.failure_t = state
        failure = "L-TRAY-TILT" if failed else None
        return SimpleNamespace(steps=(True,) * 3 + (False,) * 4, success=False, failure=failure)

    def outcome_fields(self) -> dict[str, Any]:
        return {
            "scorer_version": self.version,
            "failure_t": self.failure_t,
            "at_failure": None,
            "step_latch_t": [0.0] * 7,
            "palm_handle_min_m": {"left": 0.1, "right": 0.1, "both": 0.1},
        }


TASK_UID = "g1_wholebody_tray_transfer_teleop"
JIG_TASK_UID = "g1_wholebody_tray_transfer_jig_teleop"


def fake_simple_task() -> Any:
    class Task:
        uid = TASK_UID

        def __init__(self, version: int = 2) -> None:
            self.tracker = FakeTracker("cfg", "sample", version)
            self.report: Any = None

        def compute_reward(self, state: float) -> float:
            self.report = self.tracker.update(state)
            return 0.5

        def reset(self) -> None:
            self.tracker = FakeTracker("cfg", "sample", self.tracker.version)

    class TrayTransferEnv:
        def __init__(self, steps: tuple[bool, ...] | None, time: float) -> None:
            report = None if steps is None else SimpleNamespace(steps=steps)
            self.task = SimpleNamespace(report=report, uid=TASK_UID)
            self.mujoco = SimpleNamespace(mjData=SimpleNamespace(time=time))

        def outcome(self) -> dict[str, Any]:
            return {"seed": 1000100, "failure": "L-TIMEOUT"}

    return SimpleNamespace(TrayTransferEnv=TrayTransferEnv, G1WholebodyTrayTransferTeleop=Task)


def env_with(simple_task: Any, task: Any) -> Any:
    env = simple_task.TrayTransferEnv(None, 12.5)
    env.task = task
    return env


def test_outcome_rows_get_the_step_flags_and_the_sim_time() -> None:
    simple_task = fake_simple_task()
    install(simple_task)
    env = simple_task.TrayTransferEnv((True, True, False, False, False, False, False), 93.285)
    assert env.outcome() == {
        "seed": 1000100,
        "failure": "L-TIMEOUT",
        "scorer_steps": [True, True, False, False, False, False, False],
        "sim_time_s": 93.285,
        "task_uid": TASK_UID,
    }
    assert simple_task.TrayTransferEnv(None, 0.0).outcome()["scorer_steps"] is None


def test_rows_get_the_scorer_version_signals_and_version_1_beside_it() -> None:
    simple_task = fake_simple_task()
    install(simple_task)
    task = simple_task.G1WholebodyTrayTransferTeleop()
    for state in (0.0, 1.0, 1.5):
        assert task.compute_reward(state) == 0.5  # the reward is the task's own
    row = env_with(simple_task, task).outcome()
    assert row["scorer_version"] == 2 and row["failure_t"] is None
    assert row["palm_handle_min_m"] == {"left": 0.1, "right": 0.1, "both": 0.1}
    assert row["failure"] == "L-TIMEOUT"  # keys of the env's own row are left as they were
    v1 = row["scorer_v1"]
    assert v1["scorer_version"] == 1 and v1["failure"] == "L-TRAY-TILT"
    assert v1["failure_t"] == 1.0 and v1["success"] is False
    assert v1["steps"] == [True] * 3 + [False] * 4


def test_shadow_follows_the_tracker_of_each_reset() -> None:
    simple_task = fake_simple_task()
    install(simple_task)
    task = simple_task.G1WholebodyTrayTransferTeleop()
    task.compute_reward(1.0)
    task.reset()
    assert env_with(simple_task, task).outcome()["scorer_v1"] is None  # no step yet
    task.compute_reward(0.0)
    assert env_with(simple_task, task).outcome()["scorer_v1"]["failure"] is None


def test_the_jig_task_gets_the_patches_and_its_shadow_scores_the_jig_target() -> None:
    # jig_task.G1WholebodyTrayTransferJigTeleop: no compute_reward of its own; its reset
    # runs the parent's (tracker of the zone1 sample), then replaces sample and tracker.
    simple_task = fake_simple_task()
    install(simple_task)
    parent = simple_task.G1WholebodyTrayTransferTeleop

    class JigTask(parent):  # type: ignore[misc, valid-type]
        uid = JIG_TASK_UID

        def reset(self) -> None:
            super().reset()
            self.sample = "jig sample"
            self.tracker = FakeTracker("cfg", self.sample, self.tracker.version)

    assert "compute_reward" not in vars(JigTask)
    task = JigTask()
    task.compute_reward(0.0)
    task.reset()
    jig_tracker = task.tracker
    task.compute_reward(1.0)
    assert task.tracker is jig_tracker  # the step did not swap trackers
    assert task._fw_shadow[0] is task.tracker and task._fw_shadow[1].sample == "jig sample"
    row = env_with(simple_task, task).outcome()
    assert row["task_uid"] == JIG_TASK_UID
    assert row["scorer_v1"]["failure"] == "L-TRAY-TILT" and row["scorer_v1"]["failure_t"] == 1.0


def test_no_shadow_when_the_task_scores_with_version_1() -> None:
    simple_task = fake_simple_task()
    install(simple_task)
    task = simple_task.G1WholebodyTrayTransferTeleop(version=1)
    task.compute_reward(1.0)
    row = env_with(simple_task, task).outcome()
    assert row["scorer_version"] == 1 and row["scorer_v1"] is None


def test_install_patches_once() -> None:
    simple_task = fake_simple_task()
    install(simple_task)
    patched = simple_task.TrayTransferEnv.outcome
    reward = simple_task.G1WholebodyTrayTransferTeleop.compute_reward
    install(simple_task)
    assert simple_task.TrayTransferEnv.outcome is patched
    assert simple_task.G1WholebodyTrayTransferTeleop.compute_reward is reward


@pytest.mark.parametrize(
    "argv", [["--num-workers", "2"], ["--num-workers=4"], ["x", "--num-workers", "0"]]
)
def test_more_than_one_worker_is_refused(argv: list[str]) -> None:
    with pytest.raises(ValueError, match="one worker"):
        eval_args(argv)


def test_other_arguments_pass_unchanged() -> None:
    argv = ["simple/G1WholebodyTrayTransferTeleop-v0", "psi0_decoupled_wbc", "--num-workers", "1"]
    assert eval_args(argv) == argv

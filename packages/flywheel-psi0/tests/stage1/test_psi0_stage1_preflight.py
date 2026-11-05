"""The pre-flight's micro-step loop against a scheduler that steps as DeepSpeed's, on CPU.

DeepSpeed and accelerate are not in the dev environment, so the scheduler is a fake
with the two properties that matter (DeepSpeed 0.17.1, accelerate 1.7.0): it steps
only at the accumulation boundary (`DeepSpeedSchedulerWrapper.step` is a no-op, the
engine steps it), and `WarmupCosineLR` has `_last_lr` only when built at iteration -1.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

import pytest
from flywheel_psi0.stage1.preflight import micro_steps

ACCUMULATION = 2


class Engine:
    """accelerate's DeepSpeed path: backward also runs the engine's step."""

    def __init__(self, scheduler: DeepSpeedLikeScheduler) -> None:
        self.scheduler, self.micro = scheduler, 0

    @contextlib.contextmanager
    def autocast(self) -> Iterator[None]:
        yield

    def backward(self, loss: Any) -> None:
        self.micro += 1
        if self.micro % ACCUMULATION == 0:
            self.scheduler.boundary_step()


class DeepSpeedLikeScheduler:
    def __init__(self, last_batch_iteration: int, lrs: list[float]) -> None:
        self.iteration, self.lrs = last_batch_iteration, lrs
        if last_batch_iteration == -1:
            # get_lr() before the start is [0.0], zipped onto the first group only
            self._last_lr = [0.0, *lrs[1:]]

    def boundary_step(self) -> None:
        self.iteration += 1
        self._last_lr = list(self.lrs)

    def step(self) -> None:
        pass  # DeepSpeedSchedulerWrapper

    def get_last_lr(self) -> list[float]:
        assert getattr(self, "_last_lr", None) is not None, "need to call step() first"
        return self._last_lr


class Loss:
    def float(self) -> Loss:
        return self

    def pow(self, exponent: int) -> Loss:
        return self

    def mean(self) -> Loss:
        return self


class Optimizer:
    def step(self) -> None:
        pass

    def zero_grad(self) -> None:
        pass


def run(last_batch_iteration: int) -> list[float]:
    scheduler = DeepSpeedLikeScheduler(last_batch_iteration, [1e-4, 1e-5])
    return micro_steps(
        Engine(scheduler), lambda x: Loss(), Optimizer(), scheduler, lambda: None, 2 * ACCUMULATION
    )


def test_a_scheduler_started_at_minus_one_logs_every_micro_step() -> None:
    assert run(-1) == [0.0, 1e-4, 1e-4, 1e-4]


def test_a_scheduler_started_at_zero_fails_at_the_first_micro_step() -> None:
    with pytest.raises(AssertionError, match="need to call step"):
        run(0)

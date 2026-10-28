"""CPU-only fake adapters for exercising the Flywheel core."""

from flywheel.testkit.fakes.adapters import FakeGenerator, FakePolicy, FakeTeleop, FakeTrainer
from flywheel.testkit.fakes.sim import FakeSim2D
from flywheel.testkit.fakes.task import ToyPickPlace

__all__ = [
    "FakeGenerator",
    "FakePolicy",
    "FakeSim2D",
    "FakeTeleop",
    "FakeTrainer",
    "ToyPickPlace",
]

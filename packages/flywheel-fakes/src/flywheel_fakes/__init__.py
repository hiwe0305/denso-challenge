"""CPU-only fake adapters for exercising the Flywheel core."""

from flywheel_fakes.adapters import FakeGenerator, FakePolicy, FakeTeleop, FakeTrainer
from flywheel_fakes.sim import FakeSim2D
from flywheel_fakes.task import ToyPickPlace

__all__ = [
    "FakeGenerator",
    "FakePolicy",
    "FakeSim2D",
    "FakeTeleop",
    "FakeTrainer",
    "ToyPickPlace",
]

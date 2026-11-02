"""A control clock that follows simulated time instead of the wall clock.

SIMPLE's PICO agent times the WBC's upper-body interpolation with
`time.monotonic()` and the teleop CLI sleeps to hold 50 Hz real time. Right for
a person at the headset; for scripted input (virtual teleop, S2 replay) it makes
runs depend on how fast the machine steps. With this clock the session ticks
one control period per env step and never sleeps, so an episode is the same on
every run and runs faster than real time (same idea as DA-33's D-17).

The clock goes back to `start` at every episode reset: the agent resets the WBC
pipeline with the clock's time then, so each episode sees identical times.
"""

from __future__ import annotations

import time
from typing import Any

CONTROL_DT = 1.0 / 50


class SimClock:
    """Time = start + ticks * dt, computed from the tick count (no float drift)."""

    def __init__(self, dt: float = CONTROL_DT, start: float = 1000.0) -> None:
        self.dt = dt
        self.start = start
        self._ticks = 0

    def monotonic(self) -> float:
        return self.start + self._ticks * self.dt

    def tick(self) -> None:
        self._ticks += 1

    def reset(self) -> None:
        self._ticks = 0

    def sleep(self, seconds: float) -> None:
        pass  # simulated time does not wait


class ClockedTime:
    """Stands in for the `time` module: `monotonic` and `sleep` from the clock, rest real."""

    def __init__(self, clock: SimClock) -> None:
        self.clock = clock

    def monotonic(self) -> float:
        return self.clock.monotonic()

    def sleep(self, seconds: float) -> None:
        self.clock.sleep(seconds)

    def __getattr__(self, name: str) -> Any:
        return getattr(time, name)

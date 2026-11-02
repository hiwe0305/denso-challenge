"""Simulated control clock for the teleop pipeline (DA-35 task 4)."""

from __future__ import annotations

import time

import pytest
from flywheel_simple.tray.pico.clock import ClockedTime, SimClock


def test_clock_ticks_by_the_control_period_and_resets_to_its_start() -> None:
    clock = SimClock(dt=0.02, start=100.0)
    assert clock.monotonic() == 100.0
    for _ in range(50):
        clock.tick()
    assert clock.monotonic() == pytest.approx(101.0)
    clock.reset()
    assert clock.monotonic() == 100.0


def test_ticks_are_exact_multiples() -> None:
    # Same tick count, same time, bit for bit: no accumulated float drift.
    a, b = SimClock(), SimClock()
    for _ in range(4500):
        a.tick()
    for _ in range(4500):
        b.tick()
    assert a.monotonic() == b.monotonic() == pytest.approx(SimClock().start + 90.0)


def test_sleep_does_not_wait() -> None:
    clock = SimClock()
    t0 = time.perf_counter()
    clock.sleep(5.0)
    assert time.perf_counter() - t0 < 0.1


def test_clocked_time_reads_the_clock_and_forwards_the_rest() -> None:
    clock = SimClock(start=7.0)
    proxy = ClockedTime(clock)
    assert proxy.monotonic() == 7.0
    clock.tick()
    assert proxy.monotonic() == pytest.approx(7.02)
    assert proxy.perf_counter is time.perf_counter  # anything else is the real module
    t0 = time.perf_counter()
    proxy.sleep(5.0)
    assert time.perf_counter() - t0 < 0.1

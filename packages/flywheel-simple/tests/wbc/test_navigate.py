"""navigate_cmd integrator (DA-33 AC 1): pure, runs in the workspace."""

from __future__ import annotations

import math

import pytest
from flywheel_simple.wbc.navigate import NavIntegrator


def test_target_yaw_integrates_and_wraps() -> None:
    nav = NavIntegrator()
    nav.reset(yaw=3.0)
    for _ in range(25):
        cmd = nav.command(0.0, 0.0, 1.0)
    assert cmd[3] == pytest.approx(3.0 + 0.5 - 2 * math.pi, abs=1e-9)


def test_command_is_clipped() -> None:
    assert list(NavIntegrator().command(0.9, -0.9, 2.0)[:3]) == [0.5, -0.5, 1.0]


def test_limit_yaw_stops_the_target_but_keeps_the_turn_flag() -> None:
    nav = NavIntegrator()
    for _ in range(400):
        cmd = nav.command(0.0, 0.0, 0.5, limit_yaw=math.pi)
    assert cmd[3] == pytest.approx(math.pi, abs=1e-9)
    assert cmd[2] == 0.5


def test_limit_yaw_takes_the_short_way_across_the_wrap() -> None:
    nav = NavIntegrator()
    nav.reset(yaw=3.0)
    for _ in range(100):
        cmd = nav.command(0.0, 0.0, 1.0, limit_yaw=-3.0)
    assert cmd[3] == pytest.approx(-3.0, abs=1e-9)


def test_reset_sets_the_target() -> None:
    nav = NavIntegrator()
    nav.command(0.0, 0.0, 1.0)
    nav.reset(yaw=-1.0)
    assert nav.command(0.2, 0.0, 0.0)[3] == pytest.approx(-1.0)

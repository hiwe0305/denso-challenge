"""Replay QA verdicts from a replay outcome and the recorded final tray pose; no simulator."""

from __future__ import annotations

import math

import pytest
from flywheel_simple.tray.replay_qa import TRAY_TOL_M, verdict, yaw_gap_deg

RECORDED = [-1.2, 0.05, 0.85, 1.0, 0.0, 0.0, 0.0]  # pos xyz, quat wxyz (yaw 0)


def _outcome(dx: float = 0.0, yaw: float = 0.0, success: bool = True) -> dict:  # type: ignore[type-arg]
    return {
        "success": success,
        "tray_pos": [RECORDED[0] + dx, RECORDED[1], RECORDED[2]],
        "tray_quat": [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)],
    }


def test_matching_replay_passes() -> None:
    v = verdict(3, 101, RECORDED, _outcome(dx=0.005))
    assert v.passed and v.reason == "pass" and v.tray_error_m == pytest.approx(0.005)


def test_half_turn_counts_as_the_same_pose() -> None:
    assert yaw_gap_deg(math.pi, 0.0) == pytest.approx(0.0, abs=1e-9)
    assert verdict(0, 1, RECORDED, _outcome(yaw=math.pi)).passed


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        (None, "not_replayed"),
        (_outcome(success=False), "not_success"),
        (_outcome(dx=TRAY_TOL_M + 0.005), "tray_moved"),
        (_outcome(yaw=math.radians(10)), "tray_moved"),
    ],
)
def test_failures_name_their_reason(outcome: dict | None, reason: str) -> None:  # type: ignore[type-arg]
    v = verdict(0, 1, RECORDED, outcome)
    assert not v.passed and v.reason == reason

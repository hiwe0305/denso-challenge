"""CPU tests of the final tray pose against the target zone (tray.md 16)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest
from flywheel_psi0.tray import place_error as pe
from flywheel_psi0.tray.eval_results import Rollout
from flywheel_simple.tray.config import TrayConfig
from flywheel_simple.tray.predicates import quat_to_mat, yaw_error
from flywheel_simple.tray.randomize import sample_episode


def quat_of_yaw(yaw: float) -> list[float]:
    return [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]


def test_yaw_matches_the_scorer() -> None:
    rng = np.random.default_rng(0)
    for _ in range(50):
        q = rng.normal(size=4)
        rot = quat_to_mat(q)
        assert pe.yaw_of(q.tolist()) == pytest.approx(math.atan2(rot[1, 0], rot[0, 0]), abs=1e-12)
        a, b = rng.uniform(-10, 10, size=2)
        assert pe.wrapped(a, b) == pytest.approx(yaw_error(a, b), abs=1e-12)


def test_pose_error_is_distance_and_half_turn_symmetric_yaw() -> None:
    target = (1.0, 2.0, math.radians(30))
    d, y = pe.pose_error([1.03, 2.04, 0.85], quat_of_yaw(math.radians(36)), target)
    assert d == pytest.approx(0.05) and y == pytest.approx(6.0)
    _, y = pe.pose_error([1.0, 2.0, 0.85], quat_of_yaw(math.radians(30 + 180 - 4)), target)
    assert y == pytest.approx(4.0)  # the tray is symmetric under a half turn


def _rollout(level: int, seed: int, pos: list[float], yaw: float, **row: object) -> Rollout:
    body = {"tray_pos": pos, "tray_quat": quat_of_yaw(yaw), **row}
    return Rollout(level, seed, 0, "l1-000", 0, body)


def test_rows_and_groups_use_the_scorer_tolerance() -> None:
    target = {(1, 7): (0.0, 0.0, 0.0), (2, 8): (1.0, 0.0, 0.5), (0, 9): (0.0, 0.0, 0.0)}
    rollouts = [
        _rollout(1, 7, [0.03, 0.0, 0.8], math.radians(5), success=True, scorer_steps=[True] * 7),
        _rollout(
            2,
            8,
            [1.10, 0.0, 0.8],
            0.5,
            failure="L-PLACE-POSE",
            scorer_steps=[True] * 5 + [False] * 2,
        ),
        _rollout(0, 9, [0.0, 0.0, 0.8], 0.0, failure="L-TIMEOUT", scorer_steps=[False] * 7),
    ]
    rows = pe.rows_for(rollouts, lambda lv, s: target[(lv, s)], 0.05, 10.0)
    assert [(r["in_tolerance"], r["reach_b"]) for r in rows] == [(True, True), (False, True),
                                                                 (True, False)]  # fmt: skip
    assert rows[1]["distance_m"] == pytest.approx(0.10)
    g = pe.groups(rows)
    assert g["levels 1-2, reach_b"]["n"] == 2 and g["levels 1-2, reach_b"]["in_tolerance"] == 1
    assert g["levels 1-2, L-PLACE-POSE"]["distance_m"][1] == pytest.approx(0.10)
    assert "levels 1-2, L-TIMEOUT" not in g  # level 0 is reported on its own
    assert g["levels 1-2, success"]["n"] == 1
    assert pe.summary([]) == {"n": 0}


def test_a_tray_left_on_the_target_is_in_tolerance() -> None:
    cfg = TrayConfig.load()
    t = sample_episode(cfg, 1, 1_000_003).target_pose
    _, y = pe.pose_error([t.x, t.y, 0.85], quat_of_yaw(t.yaw), (t.x, t.y, t.yaw))
    assert y == pytest.approx(0.0, abs=1e-9)


def test_relaxed_curve_relaxes_place_pose_only_and_never_yaw() -> None:
    # tray.md 19.2 (c): a side figure; only L-PLACE-POSE moves in, within distance and 10 deg
    rows: list[dict[str, Any]] = [
        {"success": True, "failure": None, "distance_m": 0.01, "yaw_error_deg": 2.0},
        {"success": False, "failure": "L-PLACE-POSE", "distance_m": 0.07, "yaw_error_deg": 5.0},
        {"success": False, "failure": "L-PLACE-POSE", "distance_m": 0.12, "yaw_error_deg": 9.0},
        {"success": False, "failure": "L-PLACE-POSE", "distance_m": 0.06, "yaw_error_deg": 25.0},
        {"success": False, "failure": "L-TRAY-TILT", "distance_m": 0.02, "yaw_error_deg": 1.0},
        {"success": False, "failure": "L-TIMEOUT", "distance_m": 0.03, "yaw_error_deg": 1.0},
    ]
    curve = pe.tolerance_curve(rows, 10.0)
    assert [c["distance_m"] for c in curve] == [0.05, 0.075, 0.10, 0.15, 0.20]
    assert [c["relaxed_successes"] for c in curve] == [1, 2, 2, 3, 3]
    assert {c["n"] for c in curve} == {6} and {c["yaw_error_deg"] for c in curve} == {10.0}

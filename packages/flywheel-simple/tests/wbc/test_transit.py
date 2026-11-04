"""Joint-space transit of the arms (D-29): the quintic, its step bound, the branch choice; pure."""

from __future__ import annotations

import numpy as np
import pytest
from flywheel_simple.wbc.transit import (
    PEAK_SPEED,
    JointPath,
    choose_branch,
    quintic,
    roll_margin,
    transit_steps,
)


def test_quintic_starts_and_ends_at_rest() -> None:
    h = 1e-4
    for tau in (0.0, 1.0):
        lo, hi = max(tau - h, 0.0), min(tau + h, 1.0)
        speed = (quintic(hi) - quintic(lo)) / (hi - lo)
        accel = (quintic(min(tau + 2 * h, 1.0)) - 2 * quintic(tau) + quintic(max(tau - 2 * h, 0.0)))
        assert abs(speed) < 1e-6
        assert abs(accel / (2 * h) ** 2) < 1e-2  # 60 tau (1 - tau)(1 - 2 tau) -> 0
    assert quintic(0.0) == 0.0 and quintic(1.0) == 1.0 and quintic(0.5) == pytest.approx(0.5)
    # Speed peaks at tau = 1/2 at PEAK_SPEED: the bound transit_steps uses.
    assert (quintic(0.5 + h) - quintic(0.5 - h)) / (2 * h) == pytest.approx(PEAK_SPEED, rel=1e-6)


def test_path_is_quintic_in_every_joint() -> None:
    start, goal = np.array([0.1, -0.4, 1.2]), np.array([0.6, -0.4, -1.3])
    path = JointPath.plan(start, goal, max_step=0.08)
    assert np.array_equal(path.at(0), start) and np.allclose(path.at(path.steps), goal)
    assert np.allclose(path.at(path.steps + 5), goal)  # holds the goal after the end
    for k in (1, path.steps // 3, path.steps - 1):
        assert np.allclose(path.at(k), start + quintic(k / path.steps) * (goal - start))
    moves = np.abs(np.diff([path.at(k) for k in range(path.steps + 1)], axis=0))
    assert moves[0].max() < 1e-3 and moves[-1].max() < 1e-3  # at rest at both ends
    assert np.all(moves[:, 1] == 0.0)  # a joint that does not move stays put


@pytest.mark.parametrize("seed", range(20))
def test_no_joint_moves_more_than_max_step_per_step(seed: int) -> None:
    rng = np.random.default_rng(seed)
    start, goal = rng.uniform(-2.5, 2.5, 14), rng.uniform(-2.5, 2.5, 14)
    max_step = float(rng.uniform(0.02, 0.1))
    path = JointPath.plan(start, goal, max_step)
    moves = np.abs(np.diff([path.at(k) for k in range(path.steps + 1)], axis=0))
    assert moves.max() <= max_step + 1e-12
    # and the path is no longer than the bound needs: one step fewer could exceed it
    span = float(np.max(np.abs(goal - start)))
    assert path.steps == transit_steps(start, goal, max_step) >= PEAK_SPEED * span / max_step


def test_min_steps_stretch_a_short_transit() -> None:
    start = np.zeros(3)
    assert JointPath.plan(start, start + 0.01, 0.08, min_steps=30).steps == 30
    assert transit_steps(start, start, 0.08) == 1
    with pytest.raises(ValueError, match="positive"):
        transit_steps(start, start, 0.0)


def test_the_branch_away_from_the_roll_limit_wins() -> None:
    # Seed 0 converged with wrist_roll on its limit (margin 0); seed 2 reaches the same pose
    # with 0.6 rad to spare, seed 3 has more margin but misses the pose by 2 cm.
    errors = [0.0004, 0.0009, 0.0011, 0.0210]
    margins = [0.0, 0.2, 0.6, 1.4]
    distances = [0.3, 0.9, 1.5, 2.0]
    assert choose_branch(errors, margins, distances, error_tol=0.005) == 2


def test_equal_margins_take_the_shortest_path() -> None:
    # The palm-up hold can put every solution on the limit: then go to the nearest one.
    errors = [0.001, 0.001, 0.002]
    margins = [0.0, 0.0005, 0.0]
    distances = [1.2, 0.4, 0.2]
    assert choose_branch(errors, margins, distances, error_tol=0.005) == 2
    with pytest.raises(ValueError, match="one error"):
        choose_branch([0.1], [0.0, 1.0], [0.0], 0.005)


def test_roll_margin_is_the_distance_to_the_nearer_limit() -> None:
    assert roll_margin(1.9, -1.97, 1.97) == pytest.approx(0.07)
    assert roll_margin(-1.0, -1.97, 1.97) == pytest.approx(0.97)

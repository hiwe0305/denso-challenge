"""Seven step predicates, success and failure labels (DA-32 AC 6). Pure logic, workspace CI."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import numpy as np
import pytest
from flywheel_simple.tray.predicates import yaw_error

DT = 0.02


def run(tracker: Any, states: Iterator[Any]) -> list[Any]:
    return [tracker.update(s) for s in states]


def test_yaw_error_wraps() -> None:
    assert yaw_error(np.pi - 0.05, -np.pi + 0.05) == pytest.approx(0.1)
    assert yaw_error(0.2, -0.1) == pytest.approx(0.3)


def test_success_needs_continuous_stability(
    make_tracker: Callable[[], Any], placed_state_sequence: Callable[..., Iterator[Any]]
) -> None:
    reports = run(make_tracker(), placed_state_sequence(bounce_at=0.5))
    assert not reports[int(1.2 / DT)].success  # the bounce at 0.5 s restarts the 1.0 s window
    assert reports[int(1.7 / DT)].success


def test_placed_still_and_released_succeeds_after_t_stable(
    make_tracker: Callable[[], Any], placed_state_sequence: Callable[..., Iterator[Any]]
) -> None:
    reports = run(make_tracker(), placed_state_sequence())
    assert not reports[int(0.9 / DT)].success
    assert reports[int(1.1 / DT)].success and reports[-1].failure is None


def test_part_drop_is_failure_and_final(
    make_tracker: Callable[[], Any], carry_sequence: Callable[..., Iterator[Any]]
) -> None:
    reports = run(make_tracker(), carry_sequence(drop_part_at=2.0))
    assert reports[int(1.9 / DT)].failure is None
    assert reports[int(2.1 / DT)].failure == "L-PART-DROP"
    assert reports[-1].failure == "L-PART-DROP" and not reports[-1].success


def test_place_outside_tolerance_labels_place_pose(
    make_tracker: Callable[[], Any], placed_state_sequence: Callable[..., Iterator[Any]]
) -> None:
    reports = run(make_tracker(), placed_state_sequence(offset_xy=(0.08, 0.0)))
    assert reports[-1].failure == "L-PLACE-POSE" and not reports[-1].success


def test_one_hand_lost_while_carrying(
    make_tracker: Callable[[], Any], carry_sequence: Callable[..., Iterator[Any]]
) -> None:
    reports = run(make_tracker(), carry_sequence(release_left_at=3.0))
    assert reports[int(3.1 / DT)].failure is None  # within the contact grace period
    assert reports[-1].failure == "L-ONE-HAND"


def test_tray_tilt_while_carrying(
    make_tracker: Callable[[], Any], carry_sequence: Callable[..., Iterator[Any]]
) -> None:
    from dataclasses import replace

    tilt = np.deg2rad(20)
    tilted = np.array([np.cos(tilt / 2), np.sin(tilt / 2), 0.0, 0.0])
    states = [replace(s, tray_quat=tilted) if s.t >= 1.0 else s for s in carry_sequence()]
    reports = run(make_tracker(), iter(states))
    assert reports[-1].failure == "L-TRAY-TILT"


def test_robot_fall_labels_balance(
    make_tracker: Callable[[], Any], idle_state: Callable[..., Any]
) -> None:
    from dataclasses import replace

    tracker = make_tracker()
    tracker.update(idle_state(t=0.0))
    assert tracker.update(replace(idle_state(t=0.02), pelvis_height=0.3)).failure == "L-BALANCE"


def test_timeout(make_tracker: Callable[[], Any], idle_state: Callable[..., Any]) -> None:
    tracker = make_tracker()
    assert tracker.update(idle_state(t=0.0)).failure is None
    assert tracker.update(idle_state(t=90.01)).failure == "L-TIMEOUT"


def test_full_episode_reaches_all_seven_steps_in_order(
    make_tracker: Callable[[], Any], full_episode: Callable[[], Iterator[Any]]
) -> None:
    reports = run(make_tracker(), full_episode())
    first = [next(i for i, r in enumerate(reports) if r.steps[k]) for k in range(7)]
    assert first == sorted(first)
    assert reports[-1].steps == (True,) * 7
    assert reports[-1].success and reports[-1].failure is None


def test_steps_stay_reached(
    make_tracker: Callable[[], Any], full_episode: Callable[[], Iterator[Any]]
) -> None:
    reports = run(make_tracker(), full_episode())
    for k in range(7):
        flags = [r.steps[k] for r in reports]
        first = flags.index(True)
        assert all(flags[first:])


def test_reset_clears_progress(
    make_tracker: Callable[[], Any],
    full_episode: Callable[[], Iterator[Any]],
    idle_state: Callable[..., Any],
) -> None:
    tracker = make_tracker()
    run(tracker, full_episode())
    tracker.reset()
    report = tracker.update(idle_state(t=0.0))
    assert report.steps == (False,) * 7 and not report.success and report.failure is None

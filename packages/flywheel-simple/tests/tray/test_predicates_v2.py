"""Failure signals and scorer version 2 of the tray predicates (DA-42). Pure logic, workspace CI."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest

DT = 0.02


def run(tracker: Any, states: Iterator[Any]) -> list[Any]:
    return [tracker.update(s) for s in states]


# --- 2.1 failure signals ------------------------------------------------------------


def test_failure_time_and_state_at_failure(
    make_tracker: Callable[[], Any], carry_sequence: Callable[..., Iterator[Any]]
) -> None:
    tracker = make_tracker()
    reports = run(tracker, carry_sequence(drop_part_at=2.0))
    fields = tracker.outcome_fields()
    assert reports[-1].failure == "L-PART-DROP"
    assert fields["failure_t"] == pytest.approx(2.0)
    at = fields["at_failure"]
    assert at["tray_on_table"] == "none"
    assert at["hand_contacts"] == {"left": True, "right": True}
    assert at["tilt_deg"] == pytest.approx(0.0)
    assert len(at["tray_pos"]) == 3 and len(at["tray_quat"]) == 4


def test_no_failure_leaves_failure_fields_empty(
    make_tracker: Callable[[], Any], full_episode: Callable[[], Iterator[Any]]
) -> None:
    tracker = make_tracker()
    assert run(tracker, full_episode())[-1].success
    fields = tracker.outcome_fields()
    assert fields["failure_t"] is None and fields["at_failure"] is None


def test_step_latch_times_follow_the_steps(
    make_tracker: Callable[[], Any], full_episode: Callable[[], Iterator[Any]]
) -> None:
    tracker = make_tracker()
    reports = run(tracker, full_episode())
    times = tracker.outcome_fields()["step_latch_t"]
    states = list(full_episode())
    first = [next(i for i, r in enumerate(reports) if r.steps[k]) for k in range(7)]
    assert times == [states[i].t for i in first]
    assert times == sorted(times)


def test_unreached_steps_have_no_latch_time(
    make_tracker: Callable[[], Any], idle_state: Callable[..., Any]
) -> None:
    tracker = make_tracker()
    tracker.update(idle_state(t=0.0))
    assert tracker.outcome_fields()["step_latch_t"] == [None] * 7


def test_palm_handle_minimum_per_hand_and_same_cycle(
    make_tracker: Callable[[], Any], full_episode: Callable[[], Iterator[Any]]
) -> None:
    tracker = make_tracker()
    run(tracker, full_episode())  # palms sit on the handle centres while gripping
    palms = tracker.outcome_fields()["palm_handle_min_m"]
    assert palms == {
        "left": pytest.approx(0.0),
        "right": pytest.approx(0.0),
        "both": pytest.approx(0.0),
    }


def test_same_cycle_minimum_is_not_the_per_hand_minimum(
    make_tracker: Callable[[], Any], idle_state: Callable[..., Any]
) -> None:
    """Each palm reaches its handle, but never both in one cycle: `both` stays large."""
    from dataclasses import replace

    tracker = make_tracker()
    s = idle_state(t=0.0)
    tracker.update(s)
    far_left, far_right = s.left_palm, s.right_palm
    handles = _handles_of(tracker, s)
    tracker.update(replace(s, t=0.02, left_palm=handles[0], right_palm=far_right))
    tracker.update(replace(s, t=0.04, left_palm=far_left, right_palm=handles[1]))
    palms = tracker.outcome_fields()["palm_handle_min_m"]
    assert palms["left"] == pytest.approx(0.0) and palms["right"] == pytest.approx(0.0)
    assert palms["both"] > 0.3


def test_signals_are_json_and_reset_clears_them(
    make_tracker: Callable[[], Any],
    carry_sequence: Callable[..., Iterator[Any]],
    idle_state: Callable[..., Any],
) -> None:
    tracker = make_tracker()
    run(tracker, carry_sequence(drop_part_at=1.0))
    json.dumps(tracker.outcome_fields())
    assert tracker.last_state is not None
    tracker.reset()
    assert tracker.last_state is None
    tracker.update(idle_state(t=0.0))
    fields = tracker.outcome_fields()
    assert fields["failure_t"] is None and fields["step_latch_t"] == [None] * 7


def _handles_of(tracker: Any, s: Any) -> Any:
    from flywheel_simple.tray.predicates import quat_to_mat

    return tracker._handle_centres(s, quat_to_mat(s.tray_quat))

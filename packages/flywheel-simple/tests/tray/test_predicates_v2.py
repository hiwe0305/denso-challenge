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


# --- 3.1 scorer version and approach_a ----------------------------------------------


def make_versioned(version: int) -> Any:
    from flywheel_simple.tray import TrayConfig
    from flywheel_simple.tray.predicates import StepTracker
    from flywheel_simple.tray.randomize import sample_episode

    cfg = TrayConfig.load()
    return StepTracker(cfg, sample_episode(cfg, 0, 0), version=version)


def shift_palms(states: Iterator[Any], along: float, out: float) -> Iterator[Any]:
    """Palms of gripping hands moved `along` the handle bar and `out` above it.

    Bars run along the tray's x axis; the fixture's tray is unturned, so world x.
    """
    from dataclasses import replace

    for s in states:
        if any(s.hand_contacts):
            offset = [along, 0.0, out]
            s = replace(s, left_palm=s.left_palm + offset, right_palm=s.right_palm + offset)
        yield s


def test_default_scorer_is_version_2_and_unknown_versions_are_refused() -> None:
    from flywheel_simple.tray.predicates import SCORER_VERSION

    assert SCORER_VERSION == 2 and make_versioned(SCORER_VERSION).version == 2
    with pytest.raises(ValueError, match="scorer version 3"):
        make_versioned(3)


def test_grasp_at_the_bar_end_latches_approach_only_in_version_2(
    full_episode: Callable[[], Iterator[Any]],
) -> None:
    # Palm point 0.06 m along the bar (its end) and 0.09 m off it: 0.108 m from the
    # centre, over r_reach 0.10, but 0.09 m from the bar.
    v1, v2 = make_versioned(1), make_versioned(2)
    r1 = run(v1, shift_palms(full_episode(), along=0.06, out=0.09))
    r2 = run(v2, shift_palms(full_episode(), along=0.06, out=0.09))
    assert r1[-1].steps == (False,) * 7 and r1[-1].success  # success never needed the steps
    assert r2[-1].steps == (True,) * 7 and r2[-1].success
    bar = v2.outcome_fields()["palm_handle_bar_min_m"]["both"]
    centre = v2.outcome_fields()["palm_handle_min_m"]["both"]
    assert bar == pytest.approx(0.09) and centre == pytest.approx((0.06**2 + 0.09**2) ** 0.5)


def test_both_hands_on_handles_latch_approach_whatever_the_palm_distance(
    full_episode: Callable[[], Iterator[Any]],
) -> None:
    reports = run(make_versioned(2), shift_palms(full_episode(), along=0.0, out=0.25))
    assert reports[-1].steps == (True,) * 7
    assert (
        run(make_versioned(1), shift_palms(full_episode(), along=0.0, out=0.25))[-1].steps[0]
        is False
    )


def test_approach_still_needs_the_base_in_front_of_table_a(
    make_tracker: Callable[[], Any], idle_state: Callable[..., Any]
) -> None:
    from dataclasses import replace

    tracker = make_tracker()
    far = replace(idle_state(t=0.0), hand_contacts=(True, True))
    far = replace(far, base_xy=far.base_xy + [-2.0, 0.0])  # 2 m back from table A
    assert tracker.update(far).steps[0] is False


# --- 3.2 L-TRAY-TILT only while held ------------------------------------------------


def tilted(deg: float) -> Any:
    import numpy as np

    a = np.deg2rad(deg)
    return np.array([np.cos(a / 2), np.sin(a / 2), 0.0, 0.0])


def moved(s: Any, dz: float = 0.0, quat: Any = None) -> Any:
    """The state with its unturned tray raised by dz and turned to quat, parts riding along."""
    from dataclasses import replace

    import numpy as np
    from flywheel_simple.tray.predicates import quat_to_mat

    q = s.tray_quat if quat is None else quat
    pos = s.tray_pos + np.array([0.0, 0.0, dz])
    parts = pos + (s.part_pos - s.tray_pos) @ quat_to_mat(q).T
    return replace(s, tray_pos=pos, tray_quat=q, part_pos=parts)


def dropped_onto_b(states: Iterator[Any], tilt_deg: float = 25.0) -> Iterator[Any]:
    """The full episode with its set-down replaced by a release 0.1 m above the target:
    the tray falls three cycles tilted, off both tables and out of both hands, then lies
    flat in the target as before."""
    from dataclasses import replace

    released = False
    for s in states:
        if s.tray_on_table == "B" and any(s.hand_contacts):
            yield replace(moved(s, dz=0.1), tray_on_table="none")
            continue
        if s.tray_on_table == "B" and not released:
            released = True
            for k in range(3):
                falling = moved(s, dz=0.05, quat=tilted(tilt_deg))
                yield replace(falling, t=s.t - 0.06 + 0.02 * k, tray_on_table="none")
        yield s


def test_release_above_table_b_is_tilt_in_version_1_success_in_version_2(
    full_episode: Callable[[], Iterator[Any]],
) -> None:
    v1, v2 = make_versioned(1), make_versioned(2)
    r1 = run(v1, dropped_onto_b(full_episode()))
    r2 = run(v2, dropped_onto_b(full_episode()))
    assert r1[-1].failure == "L-TRAY-TILT" and not r1[-1].success
    at = v1.outcome_fields()["at_failure"]
    assert at["hand_contacts"] == {"left": False, "right": False}
    assert at["tray_on_table"] == "none" and at["tilt_deg"] == pytest.approx(25.0)
    assert r2[-1].failure is None and r2[-1].success


def test_tilt_while_held_with_both_hands_is_still_a_failure(
    carry_sequence: Callable[..., Iterator[Any]],
) -> None:

    states = (moved(s, quat=tilted(20)) if s.t >= 1.0 else s for s in carry_sequence())
    tracker = make_versioned(2)
    assert run(tracker, states)[-1].failure == "L-TRAY-TILT"
    assert tracker.outcome_fields()["failure_t"] == pytest.approx(1.0)


def test_tilt_after_one_hand_lets_go_is_one_hand_in_version_2(
    carry_sequence: Callable[..., Iterator[Any]],
) -> None:

    def states() -> Iterator[Any]:
        for s in carry_sequence(release_left_at=2.0):
            yield moved(s, quat=tilted(30)) if s.t >= 2.0 else s

    assert run(make_versioned(1), states())[-1].failure == "L-TRAY-TILT"
    assert run(make_versioned(2), states())[-1].failure == "L-ONE-HAND"

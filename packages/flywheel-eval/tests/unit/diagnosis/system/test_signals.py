"""Step 1 of the ordered check: thiếu tín hiệu → CHƯA RÕ (DA-13 AC 1).

The control is a complete trace, which must cost no code its verdict. Every
other case takes one thing away and names the code that loses its verdict by
it, because a check that reported "something is missing" without saying which
evidence to collect is not the answer spec section 6.4 asks for.
"""

from __future__ import annotations

from flywheel.eval.config import SignalLimits
from flywheel.eval.diagnosis.system.signals import check_signals, unjudgeable_codes
from flywheel.eval.diagnosis.system.verdict import Diagnosis, combine

LIMITS = SignalLimits(max_gap_fraction=0.0, max_dropped_frames=0, min_steps=10)


def test_a_complete_trace_costs_no_code_its_verdict(clean_rows, inputs_from) -> None:
    assert unjudgeable_codes(inputs_from(clean_rows), LIMITS) == {}


def test_a_field_nobody_logged_costs_the_code_measured_on_it(row, inputs_from) -> None:
    rows = [row(step) for step in range(20)]
    for item in rows:
        del item["t_image"]

    reasons = unjudgeable_codes(inputs_from(rows), LIMITS)

    assert set(reasons) == {"R4"}
    assert "t_image" in reasons["R4"]


def test_a_missing_command_field_costs_r3_not_r4(row, inputs_from) -> None:
    rows = [row(step) for step in range(20)]
    for item in rows:
        del item["cmd_lower"]

    reasons = unjudgeable_codes(inputs_from(rows), LIMITS)

    assert set(reasons) == {"R3"}
    assert "cmd_lower" in reasons["R3"]


def test_a_gap_over_the_allowance_costs_the_code(row, inputs_from) -> None:
    rows = [row(step) for step in range(20)]
    rows[4]["t_image"] = "NaN"

    strict = unjudgeable_codes(inputs_from(rows), LIMITS)
    tolerant = unjudgeable_codes(
        inputs_from(rows),
        SignalLimits(max_gap_fraction=0.1, max_dropped_frames=0, min_steps=10),
    )

    assert set(strict) == {"R4"}
    assert "1/20" in strict["R4"]
    # One null cycle in twenty is under a 10% allowance, so the code keeps its
    # verdict; the allowance is what the calibration on real traces moves.
    assert tolerant == {}


def test_dropped_camera_frames_cost_the_sync_check(row, inputs_from) -> None:
    rows = [row(step) for step in range(20)]
    rows[3]["dropped_frames"] = 2

    reasons = unjudgeable_codes(inputs_from(rows), LIMITS)

    assert set(reasons) == {"R4"}
    assert "mất 2 khung" in reasons["R4"]


def test_a_trace_too_short_for_a_percentile_costs_every_code(row, inputs_from) -> None:
    rows = [row(step) for step in range(3)]

    reasons = unjudgeable_codes(inputs_from(rows), LIMITS)

    assert set(reasons) == {"R3", "R4"}
    assert "3 chu kỳ" in reasons["R3"]


def test_a_skipped_code_and_no_fault_is_unknown_not_clean(row, inputs_from) -> None:
    # The whole point of putting this check first: an episode nobody could
    # judge must not come out as an episode with no system fault (FR21).
    rows = [row(step) for step in range(20)]
    for item in rows:
        del item["t_image"]

    verdict = combine("ep_1", [check_signals(inputs_from(rows), LIMITS)], None)

    assert verdict.diagnosis is Diagnosis.UNKNOWN
    assert [skip.code for skip in verdict.skipped] == ["R4"]
    assert verdict.blocks_policy_analysis


def test_a_complete_trace_with_nothing_fired_is_clean(clean_rows, inputs_from) -> None:
    verdict = combine("ep_1", [check_signals(inputs_from(clean_rows), LIMITS)], None)

    assert verdict.diagnosis is Diagnosis.CLEAN
    assert not verdict.blocks_policy_analysis


def test_null_image_timestamps_cost_r4_nothing(row, inputs_from) -> None:
    # The writer's 25 Hz camera on a 50 Hz loop: every other `t_image` is null.
    rows = [row(step, t_image=None if step % 2 else 0.1 * step) for step in range(20)]

    assert unjudgeable_codes(inputs_from(rows), LIMITS) == {}


def test_a_trace_with_no_new_frame_at_all_costs_r4(row, inputs_from) -> None:
    rows = [row(step, t_image=None) for step in range(20)]

    reasons = unjudgeable_codes(inputs_from(rows), LIMITS)

    assert set(reasons) == {"R4"}
    assert "khung ảnh" in reasons["R4"]

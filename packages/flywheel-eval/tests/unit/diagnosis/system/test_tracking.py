"""R3: tracking error of the WBC, upper and lower body apart (DA-13 AC 1).

The control is the trace that tracks its commands exactly, and it must not
fire. Each fault moves one half of the body away from its command and checks
that the finding names that half, because a finding that did not would send the
engineer to the wrong part of the WBC configuration.
"""

from __future__ import annotations

from flywheel.contracts.trace import LOWER_BODY, UPPER_BODY
from flywheel.eval.config import R3Thresholds
from flywheel.eval.diagnosis.system.reader import read_trace_log
from flywheel.eval.diagnosis.system.tracking import check_r3
from flywheel.eval.diagnosis.system.verdict import Diagnosis, combine

CFG = R3Thresholds(tau_track_upper=0.05, tau_track_lower=0.05, percentile=99.0)


def test_a_controller_that_tracks_does_not_fire(clean_rows, write_trace) -> None:
    result = check_r3(read_trace_log(write_trace(clean_rows)), CFG)

    assert result.findings == []


def test_the_upper_body_missing_its_command_fires_on_the_upper_body(row, write_trace) -> None:
    rows = [row(step, meas_upper=[0.5, 0.2, 0.3]) for step in range(20)]

    result = check_r3(read_trace_log(write_trace(rows)), CFG)

    assert [(finding.code, finding.part) for finding in result.findings] == [("R3", "upper")]
    assert result.findings[0].value > CFG.tau_track_upper
    assert result.findings[0].threshold == CFG.tau_track_upper


def test_the_lower_body_is_judged_against_its_own_threshold(row, write_trace) -> None:
    # The lower body is off by 0.2 and the upper body tracks. With one
    # threshold over both halves this would be a controller fault of unstated
    # origin; with two it says which half.
    rows = [row(step, meas_lower=[0.7, 0.0]) for step in range(20)]

    result = check_r3(read_trace_log(write_trace(rows)), CFG)

    assert [finding.part for finding in result.findings] == ["lower"]


def test_a_lower_threshold_wide_enough_lets_the_lower_body_pass(row, write_trace) -> None:
    rows = [row(step, meas_lower=[0.7, 0.0]) for step in range(20)]
    wide = R3Thresholds(tau_track_upper=0.05, tau_track_lower=0.5, percentile=99.0)

    assert check_r3(read_trace_log(write_trace(rows)), wide).findings == []


def test_both_halves_are_reported_when_both_are_off(row, write_trace) -> None:
    rows = [row(step, meas_upper=[0.5, 0.2, 0.3], meas_lower=[0.7, 0.0]) for step in range(20)]

    result = check_r3(read_trace_log(write_trace(rows)), CFG)

    assert sorted(finding.part or "" for finding in result.findings) == ["lower", "upper"]


def test_the_finding_names_the_worst_cycle(row, write_trace) -> None:
    rows = [row(step) for step in range(20)]
    rows[7] = row(7, meas_upper=[0.9, 0.2, 0.3])
    cfg = R3Thresholds(tau_track_upper=0.05, tau_track_lower=0.05, percentile=100.0)

    result = check_r3(read_trace_log(write_trace(rows)), cfg)

    assert result.findings[0].where == "dòng trace 7"


def test_a_half_nobody_measured_does_not_fire(row, write_trace) -> None:
    # The upper body has no measurement on any cycle - `TraceStep` writes it as
    # "NaN" - so there is no statistic to compare. `signals.py` is what reports
    # that; what must not happen here is a finding invented out of it, in
    # either direction.
    rows = [row(step, meas_upper=["NaN"] * len(UPPER_BODY)) for step in range(20)]

    result = check_r3(read_trace_log(write_trace(rows)), CFG)

    assert [finding.part for finding in result.findings] == []


def test_a_tracking_fault_is_a_controller_fault(row, write_trace) -> None:
    rows = [row(step, meas_upper=[0.5, 0.2, 0.3]) for step in range(20)]

    verdict = combine("ep_1", [check_r3(read_trace_log(write_trace(rows)), CFG)], None)

    assert verdict.diagnosis is Diagnosis.CONTROLLER


def test_a_robot_facing_its_target_heading_across_pi_does_not_fire(row, write_trace) -> None:
    # The end-to-end case of the PO check on hook #80: target yaw 3.13 rad,
    # measured -3.13 rad on every cycle, 0.023 rad apart.
    cmd = [0.5 if name == "base_height" else 0.0 for name in LOWER_BODY]
    meas = list(cmd)
    cmd[LOWER_BODY.index("yaw")], meas[LOWER_BODY.index("yaw")] = 3.13, -3.13
    rows = [row(step, cmd_lower=cmd, meas_lower=meas) for step in range(20)]

    assert check_r3(read_trace_log(write_trace(rows)), CFG).findings == []


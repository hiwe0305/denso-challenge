"""R1, R2, R4, R5 and R6, each on its own control and its own fault (DA-13 AC 1).

Two things every one of these has to get right. A clean input must not fire,
and an input nobody supplied must come back as a named skip rather than as a
check that found nothing - the difference between "no fault" and "no evidence"
is the whole of FR21.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.artifacts import RTCInferenceRecord
from flywheel.contracts.trace import CameraParams
from flywheel.eval.config import (
    CameraReference,
    R1Thresholds,
    R2Thresholds,
    R3Thresholds,
    R4Thresholds,
    R5Thresholds,
    R6Thresholds,
)
from flywheel.eval.diagnosis.system.reader import (
    CAMERA_NAME,
    read_camera_params,
    read_trace_log,
)
from flywheel.eval.diagnosis.system.runtime import check_r1, check_r2, check_r4, check_r5, check_r6
from flywheel.eval.diagnosis.system.tracking import check_r3
from flywheel.eval.diagnosis.system.verdict import Diagnosis, combine

R1 = R1Thresholds(tau_lat_s=0.1, percentile=99.0)
# d of the server with the team's serve flags (`system.yaml`, r2)
R2 = R2Thresholds(rtc_inference_delay_steps=6, max_underruns=0)
R4 = R4Thresholds(tau_sync_s=0.01)
R6 = R6Thresholds(ok_statuses=("ok",))

REFERENCE = CameraReference(
    mount="head_link",
    width=640,
    height=480,
    fx=400.0,
    fy=400.0,
    cx=320.0,
    cy=240.0,
    pose=(0.0, 0.0, 1.5, 1.0, 0.0, 0.0, 0.0),
)
R5 = R5Thresholds(
    reference_sha256="b" * 64,
    cameras={"head": REFERENCE},
    tolerance_intrinsics_px=0.5,
    tolerance_position_m=0.005,
    tolerance_quaternion=0.01,
)


def _records(rows: list[dict[str, Any]]) -> tuple[RTCInferenceRecord, ...]:
    return tuple(RTCInferenceRecord.model_validate(row) for row in rows)


def _cameras(tmp_path: Path, entry: dict[str, Any]) -> tuple[CameraParams, ...]:
    path = tmp_path / CAMERA_NAME
    path.write_text(json.dumps(entry), encoding="utf-8")
    return read_camera_params(path)


def test_r1_does_not_fire_on_a_run_that_answered_in_time(rtc_rows) -> None:
    assert check_r1(_records(rtc_rows), R1).findings == []


def test_r1_fires_on_the_percentile_and_names_the_worst_chunk(rtc_rows) -> None:
    rows = [dict(row) for row in rtc_rows]
    for row in rows:
        row["chunk_received_s"] = row["observation_sent_s"] + 0.4

    result = check_r1(_records(rows), R1)

    assert [finding.code for finding in result.findings] == ["R1"]
    assert result.findings[0].value == pytest.approx(0.4)
    assert result.findings[0].threshold == pytest.approx(0.1)
    assert result.findings[0].where is not None
    assert result.findings[0].where != "chunk 0"


def test_r1_and_r2_without_an_rtc_log_are_skips_not_passes() -> None:
    assert [skip.code for skip in check_r1((), R1).skipped] == ["R1"]
    assert [skip.code for skip in check_r2((), R2).skipped] == ["R2"]
    assert check_r1((), R1).findings == []


def test_r2_does_not_fire_on_inference_inside_the_delay_rtc_covers(rtc_rows) -> None:
    assert check_r2(_records(rtc_rows), R2).findings == []


def test_r2_does_not_fire_on_the_records_rtc_client_writes_for_a_healthy_run(rtc_rows) -> None:
    # Shaped exactly as `RTCClient` of DA-19 writes them under SIMPLE's
    # refill-when-empty (`refill_at=0`): every request goes out with the buffer
    # at 0, and 50 ms of inference at 50 Hz is ceil(0.05 * 50) = 3 steps, under
    # the d of 6 that the server's RTC covers on hardware. The buffer level says
    # nothing here; reading it as a stall fired R2 on every chunk.
    rows = [
        dict(
            row,
            observation_sent_s=0.2 * index,
            chunk_received_s=0.2 * index + 0.05,
            buffer_level=0,
            delay_steps=3,
        )
        for index, row in enumerate(rtc_rows)
    ]

    assert check_r2(_records(rows), R2).findings == []


def test_r2_fires_on_a_chunk_slower_than_rtc_covers(rtc_rows) -> None:
    rows = [dict(row, buffer_level=0, delay_steps=3) for row in rtc_rows]
    rows[5]["delay_steps"] = 9
    rows[7]["delay_steps"] = 12

    result = check_r2(_records(rows), R2)

    assert [finding.code for finding in result.findings] == ["R2"]
    finding = result.findings[0]
    assert finding.value == pytest.approx(2.0)
    assert finding.threshold == pytest.approx(0.0)
    assert finding.where == "chunk 7"
    assert "12" in (finding.detail or "") and "d = 6" in (finding.detail or "")


def test_r2_at_exactly_the_server_delay_is_covered(rtc_rows) -> None:
    rows = [dict(row, delay_steps=6) for row in rtc_rows]

    assert check_r2(_records(rows), R2).findings == []


def test_r2_fires_one_step_past_the_server_delay_under_max_delay(rtc_rows) -> None:
    # 7 is under the checkpoint's max_delay of 8 but past the d = 6 the server
    # actually runs with: the robot would stall on it, which the old limit missed.
    rows = [dict(row) for row in rtc_rows]
    rows[3]["delay_steps"] = 7

    assert [finding.code for finding in check_r2(_records(rows), R2).findings] == ["R2"]


def test_a_slow_first_chunk_alone_fires_nothing(rtc_rows) -> None:
    # Chunk 0 is asked for before any action ran, on a cold model: 2 s and 100
    # steps there is the start of the trace, not a stall or a slow loop.
    rows = [dict(row) for row in rtc_rows]
    rows[0]["chunk_received_s"] = rows[0]["observation_sent_s"] + 2.0
    rows[0]["delay_steps"] = 100
    records = _records(rows)

    for result in (check_r1(records, R1), check_r2(records, R2)):
        assert result.findings == [] and result.skipped == []


def test_an_rtc_log_with_only_chunk_0_is_a_skip_not_a_pass(rtc_rows) -> None:
    records = _records(rtc_rows[:1])

    assert [skip.code for skip in check_r1(records, R1).skipped] == ["R1"]
    assert [skip.code for skip in check_r2(records, R2).skipped] == ["R2"]
    assert check_r1(records, R1).findings == check_r2(records, R2).findings == []


def test_r2_tolerates_as_many_slow_chunks_as_the_config_allows(rtc_rows) -> None:
    rows = [dict(row) for row in rtc_rows]
    rows[5]["delay_steps"] = 9

    tolerant = R2Thresholds(rtc_inference_delay_steps=6, max_underruns=1)

    assert check_r2(_records(rows), tolerant).findings == []


def test_r4_does_not_fire_when_the_clocks_stay_together(clean_rows, write_trace) -> None:
    assert check_r4(read_trace_log(write_trace(clean_rows)), R4).findings == []


def test_r4_fires_on_the_largest_offset_not_an_average(row, write_trace) -> None:
    # Nineteen cycles are paired to 2 ms and one is 200 ms out. An average
    # would be 12 ms and under most thresholds; the policy still acted once on
    # a stale image, which is what spec section 6.4 asks about.
    rows = [row(step) for step in range(20)]
    rows[11]["t_image"] = rows[11]["t_state"] + 0.2

    result = check_r4(read_trace_log(write_trace(rows)), R4)

    assert [finding.code for finding in result.findings] == ["R4"]
    assert result.findings[0].value == pytest.approx(0.2)
    assert result.findings[0].where == "dòng trace 11"


def test_r4_is_a_sync_fault_and_r1_a_runtime_fault(row, write_trace, rtc_rows) -> None:
    rows = [row(step) for step in range(20)]
    rows[11]["t_image"] = rows[11]["t_state"] + 0.2
    slow = [dict(record) for record in rtc_rows]
    for record in slow:
        record["chunk_received_s"] = record["observation_sent_s"] + 0.4

    sync = combine("ep_1", [check_r4(read_trace_log(write_trace(rows)), R4)], None)
    runtime = combine("ep_1", [check_r1(_records(slow), R1)], None)

    assert sync.diagnosis is Diagnosis.SYNC
    assert runtime.diagnosis is Diagnosis.RUNTIME


def test_a_runtime_fault_outranks_a_sync_fault(row, write_trace, rtc_rows) -> None:
    # Spec section 6.4 checks latency before sync, so the label is the one the
    # engineer fixes first; the other measurement still travels in the record.
    rows = [row(step) for step in range(20)]
    rows[11]["t_image"] = rows[11]["t_state"] + 0.2
    slow = [dict(record) for record in rtc_rows]
    for record in slow:
        record["chunk_received_s"] = record["observation_sent_s"] + 0.4

    verdict = combine(
        "ep_1",
        [check_r4(read_trace_log(write_trace(rows)), R4), check_r1(_records(slow), R1)],
        None,
    )

    assert verdict.diagnosis is Diagnosis.RUNTIME
    assert [finding.code for finding in verdict.findings] == ["R1", "R4"]


def test_r5_does_not_fire_on_the_reference_calibration(tmp_path, camera_entry) -> None:
    assert check_r5(_cameras(tmp_path, camera_entry), R5).findings == []


def test_r5_fires_on_a_camera_calibrated_against_another_reference(tmp_path, camera_entry) -> None:
    entry = {**camera_entry, "reference_sha256": "c" * 64}

    result = check_r5(_cameras(tmp_path, entry), R5)

    assert [finding.code for finding in result.findings] == ["R5"]
    assert result.findings[0].threshold is None
    assert "bản tham chiếu" in (result.findings[0].detail or "")


def test_r5_still_compares_the_values_of_a_camera_on_another_reference(
    tmp_path, camera_entry
) -> None:
    # Decision Q3 of 3/11/2026: `reference_sha256` is the G0-pinned reference
    # the hook copies from the RunPlan. A different hash is one finding; the
    # values are then still compared within tolerance, so the tolerances are
    # never dead code behind the hash.
    entry = {**camera_entry, "reference_sha256": "c" * 64, "fx": 404.0}

    result = check_r5(_cameras(tmp_path, entry), R5)

    details = [finding.detail or "" for finding in result.findings]
    assert len(details) == 2
    assert "bản tham chiếu `cccccccccccc" in details[0]
    assert details[1] == "`fx` lệch khỏi bản tham chiếu"


def test_r5_fires_on_an_intrinsic_outside_its_tolerance(tmp_path, camera_entry) -> None:
    result = check_r5(_cameras(tmp_path, {**camera_entry, "fx": 404.0}), R5)

    assert [finding.detail for finding in result.findings] == ["`fx` lệch khỏi bản tham chiếu"]
    assert result.findings[0].value == pytest.approx(4.0)


def test_r5_tolerates_a_render_difference_inside_the_tolerance(tmp_path, camera_entry) -> None:
    assert check_r5(_cameras(tmp_path, {**camera_entry, "cx": 320.2}), R5).findings == []


def test_r5_fires_on_a_camera_that_moved(tmp_path, camera_entry) -> None:
    moved = {**camera_entry, "pose": [0.0, 0.03, 1.5, 1.0, 0.0, 0.0, 0.0]}

    result = check_r5(_cameras(tmp_path, moved), R5)

    assert [finding.detail for finding in result.findings] == [
        "`vị trí camera` lệch khỏi bản tham chiếu"
    ]


def test_r5_reads_q_and_minus_q_as_the_same_orientation(tmp_path, camera_entry) -> None:
    # A unit quaternion and its negation are one rotation; a writer may emit
    # either sign for the same camera.
    flipped = {**camera_entry, "pose": [0.0, 0.0, 1.5, -1.0, 0.0, 0.0, 0.0]}

    assert check_r5(_cameras(tmp_path, flipped), R5).findings == []


def test_r5_fires_on_a_camera_that_turned(tmp_path, camera_entry) -> None:
    turned = {**camera_entry, "pose": [0.0, 0.0, 1.5, 0.9988, 0.05, 0.0, 0.0]}

    result = check_r5(_cameras(tmp_path, turned), R5)

    assert "hướng camera" in (result.findings[0].detail or "")


def test_r5_is_a_calibration_fault(tmp_path, camera_entry) -> None:
    drifted = check_r5(_cameras(tmp_path, {**camera_entry, "fx": 404.0}), R5)
    verdict = combine("ep_1", [drifted], None)

    assert verdict.diagnosis is Diagnosis.CALIBRATION


def test_a_camera_not_in_the_reference_is_a_skip(tmp_path, camera_entry) -> None:
    result = check_r5(_cameras(tmp_path, {**camera_entry, "uid": "wrist"}), R5)

    assert result.findings == []
    assert [skip.code for skip in result.skipped] == ["R5"]
    assert "wrist" in result.skipped[0].reason


def test_r5_without_camera_params_is_a_skip() -> None:
    assert [skip.code for skip in check_r5((), R5).skipped] == ["R5"]


def test_r6_does_not_fire_on_a_healthy_status() -> None:
    assert check_r6("ok", R6).findings == []


def test_r6_fires_on_a_server_fault_and_says_it_is_not_the_policy() -> None:
    result = check_r6("rtc_timeout", R6)

    assert [finding.code for finding in result.findings] == ["R6"]
    assert "không phải lỗi policy" in (result.findings[0].detail or "")


def test_r6_alone_is_an_infra_fault() -> None:
    infra = combine("ep_1", [check_r6("sim_crash", R6)], "sim_crash")

    assert infra.diagnosis is Diagnosis.INFRA
    assert infra.infra_status == "sim_crash"
    assert infra.blocks_policy_analysis


def test_r6_outranks_every_other_code_and_the_rest_still_travel(row, write_trace) -> None:
    # Decision Q1 of 3/11/2026: when the simulator or the server failed, the
    # tracking error, latency and buffer are consequences of it, so the label
    # is `infra` and never `controller`; the other findings are still shown.
    off = read_trace_log(write_trace([row(step, meas_upper=[0.6, 0.2, 0.3]) for step in range(20)]))
    r3 = R3Thresholds(tau_track_upper=0.1, tau_track_lower=0.15, percentile=99.0)
    tracking = check_r3(off, r3)

    verdict = combine("ep_1", [tracking, check_r6("sim_crash", R6)], "sim_crash")

    assert verdict.diagnosis is Diagnosis.INFRA
    assert [finding.code for finding in verdict.findings] == ["R6", "R3"]


def test_an_episode_that_logged_no_infra_status_is_a_skip() -> None:
    assert [skip.code for skip in check_r6(None, R6).skipped] == ["R6"]


def test_r5_without_a_pinned_reference_is_a_skip(tmp_path: Path, camera_entry) -> None:
    # This is what `system.yaml` ships as until G0 fixes the reference. A skip
    # keeps the episode from being cleared; a placeholder hash would instead
    # make every episode a calibration fault.
    unpinned = R5Thresholds(
        reference_sha256=None,
        cameras={},
        tolerance_intrinsics_px=0.5,
        tolerance_position_m=0.005,
        tolerance_quaternion=0.01,
    )

    result = check_r5(_cameras(tmp_path, camera_entry), unpinned)

    assert result.findings == []
    assert [skip.code for skip in result.skipped] == ["R5"]
    assert "chưa ghim ở G0" in result.skipped[0].reason
    assert combine("ep_1", [result], "ok").diagnosis is Diagnosis.UNKNOWN


def test_r4_on_a_trace_with_no_frame_is_a_skip_not_a_pass(row, write_trace) -> None:
    trace = read_trace_log(write_trace([row(step, t_image=None) for step in range(20)]))

    result = check_r4(trace, R4)

    assert result.findings == []
    assert [skip.code for skip in result.skipped] == ["R4"]

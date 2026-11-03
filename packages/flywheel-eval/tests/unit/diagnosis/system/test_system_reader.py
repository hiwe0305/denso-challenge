"""The reader of the F-SYS checks: what it turns into arrays, and what it refuses.

The cases that matter are the ones where a wrong read would turn into a wrong
verdict: a gap read as a number clears a threshold, and a "no new frame" read
as a gap costs R4 on every trace the writer produces. Every step goes through
`flywheel.contracts.trace.TraceStep`, so a line the contract refuses is
refused here too, with its line number.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel.contracts.trace import LOWER_BODY, UPPER_BODY
from flywheel.eval.diagnosis.system.reader import (
    CAMERA_NAME,
    RTC_NAME,
    STEPS_NAME,
    ReaderError,
    load_episode,
    percentile,
    read_camera_params,
    read_rtc_log,
    read_trace_log,
)


def test_reads_the_episode_id_and_hashes_the_trace(clean_rows, write_trace) -> None:
    trace = read_trace_log(write_trace(clean_rows))

    assert trace.episode_id == "ep_1"
    assert trace.num_steps == 20
    assert len(trace.trace_sha256) == 64
    assert trace.gap_counts == {}


def test_a_step_without_an_episode_id_is_refused(row, write_trace) -> None:
    rows = [row(step) for step in range(3)]
    del rows[2]["episode_id"]

    with pytest.raises(ReaderError, match="dòng 3 không phải TraceStep"):
        read_trace_log(write_trace(rows))


@pytest.mark.parametrize("text", ["NaN", "Infinity", "-Infinity"])
def test_a_value_the_contract_writes_as_not_finite_is_a_gap(row, write_trace, text) -> None:
    # Every comparison against a NaN is false, so a NaN tracking error left in
    # place would clear tau_track and come back as a controller that tracked.
    rows = [
        row(0),
        row(1, meas_upper=[text, 0.2, 0.3]),
        row(2, t_image=text),
        row(3, t_state=text),
    ]

    trace = read_trace_log(write_trace(rows))

    assert trace.gap_counts == {"meas_upper": 1, "t_image": 1, "t_state": 1}
    error = trace.tracking_error("upper")
    assert math.isnan(error[1])
    assert error[0] == pytest.approx(0.0)
    offset = trace.sync_offset()
    assert math.isnan(offset[2]) and math.isnan(offset[3])


def test_a_bare_json_nan_is_refused_not_read_as_a_number(row, write_trace) -> None:
    # `json.loads` accepts the token NaN, but `TraceStep` writes a non-finite
    # value only as a string; a bare one is a writer outside the contract.
    path = write_trace([row(0), row(1, meas_upper=[float("nan"), 0.2, 0.3])])

    with pytest.raises(ReaderError, match="dòng 2 không phải TraceStep"):
        read_trace_log(path)


def test_a_null_image_timestamp_is_no_new_frame_not_a_gap(row, write_trace) -> None:
    # `TraceStep` writes `t_image: null` on every cycle the camera did not
    # render (25 Hz camera, 50 Hz control); counting those as gaps would cost
    # R4 its verdict on every trace the writer produces.
    rows = [row(step, t_image=None if step % 2 else 0.1 * step) for step in range(4)]

    trace = read_trace_log(write_trace(rows))

    assert trace.gap_counts == {}
    assert trace.rows[1].t_image is None
    assert trace.frame_cycles == 2
    offset = trace.sync_offset()
    assert offset[0] == pytest.approx(0.0)
    assert math.isnan(offset[1])


def test_a_string_the_contract_does_not_allow_is_refused(row, write_trace) -> None:
    with pytest.raises(ReaderError, match="t_state"):
        read_trace_log(write_trace([row(0, t_state="late")]))


def test_an_image_timestamp_left_out_is_no_new_frame(row, write_trace) -> None:
    # `TraceStep.t_image` defaults to null, so leaving it out is the writer
    # saying no frame arrived, not a gap; R4 then has no cycle to measure.
    rows = [row(step) for step in range(4)]
    for item in rows:
        del item["t_image"]

    trace = read_trace_log(write_trace(rows))

    assert trace.gap_counts == {}
    assert trace.frame_cycles == 0
    assert trace.sync_offset().size == 0


@pytest.mark.parametrize("field", ["t_state", "cmd_upper", "meas_lower"])
def test_a_step_missing_a_signal_is_refused(row, write_trace, field) -> None:
    rows = [row(0), row(1)]
    del rows[1][field]

    with pytest.raises(ReaderError, match=f"(?s)dòng 2 không phải TraceStep.*{field}"):
        read_trace_log(write_trace(rows))


def test_tracking_error_is_the_norm_per_cycle_upper_and_lower_apart(row, write_trace) -> None:
    rows = [
        row(0, meas_upper=[0.1, 0.2, 0.3], meas_lower=[0.5, 0.0]),
        row(1, meas_upper=[0.4, 0.6, 0.3], meas_lower=[0.8, 0.4]),
    ]

    trace = read_trace_log(write_trace(rows))

    # upper: |(0.3, 0.4, 0.0)| = 0.5; lower: |(0.3, 0.4)| = 0.5
    assert trace.tracking_error("upper") == pytest.approx([0.0, 0.5])
    assert trace.tracking_error("lower") == pytest.approx([0.0, 0.5])


@pytest.mark.parametrize(
    ("field", "width"), [("meas_upper", len(UPPER_BODY) - 1), ("cmd_lower", len(LOWER_BODY) + 1)]
)
def test_a_vector_not_of_the_contracts_width_is_refused(row, write_trace, field, width) -> None:
    # 28 upper-body and 7 lower-body channels; a norm over any other count is
    # not the tracking error of this robot.
    rows = [row(0), row(1)]
    rows[1][field] = [0.0] * width

    with pytest.raises(ReaderError, match=f"(?s)dòng 2 không phải TraceStep.*{field}"):
        read_trace_log(write_trace(rows))


def test_steps_of_two_traces_in_one_file_are_refused(row, write_trace) -> None:
    rows = [row(0), row(1, trace_id="trace_9")]

    with pytest.raises(ReaderError, match="trace_9"):
        read_trace_log(write_trace(rows))


def test_sync_offset_is_the_absolute_difference_of_the_two_clocks(row, write_trace) -> None:
    rows = [row(0, t_state=1.0, t_image=1.05), row(1, t_state=2.0, t_image=1.9)]

    trace = read_trace_log(write_trace(rows))

    assert trace.sync_offset() == pytest.approx([0.05, 0.1])


def test_dropped_frames_are_summed_over_the_episode(row, write_trace) -> None:
    rows = [row(0), row(1, dropped_frames=2), row(2, dropped_frames=1)]

    trace = read_trace_log(write_trace(rows))

    assert trace.dropped_frames == 3


def test_a_line_that_is_not_json_says_which_line(tmp_path: Path) -> None:
    path = tmp_path / STEPS_NAME
    path.write_text('{"step": 0}\nnot json\n', encoding="utf-8")

    with pytest.raises(ReaderError, match="dòng 2 không phải JSON"):
        read_trace_log(path)


def test_the_rtc_log_is_read_through_the_contract(tmp_path: Path, rtc_rows) -> None:
    path = tmp_path / RTC_NAME
    path.write_text("".join(json.dumps(item) + "\n" for item in rtc_rows), encoding="utf-8")

    records = read_rtc_log(path)

    assert len(records) == 10
    assert records[0].buffer_level == 6


def test_an_rtc_line_the_contract_rejects_says_so(tmp_path: Path, rtc_rows) -> None:
    broken: dict[str, Any] = dict(rtc_rows[0])
    broken["chunk_received_s"] = broken["observation_sent_s"] - 1.0
    path = tmp_path / RTC_NAME
    path.write_text(json.dumps(broken) + "\n", encoding="utf-8")

    with pytest.raises(ReaderError, match="không phải RTCInferenceRecord"):
        read_rtc_log(path)


def test_camera_params_are_one_camera_per_line(tmp_path: Path, camera_entry) -> None:
    # Decision G1 on PR #48: `camera_params.jsonl`, one CameraParams per line.
    path = tmp_path / CAMERA_NAME
    lines = [camera_entry, {**camera_entry, "uid": "wrist"}]
    path.write_text("".join(json.dumps(item) + "\n" for item in lines), encoding="utf-8")

    views = read_camera_params(path)

    assert [view.uid for view in views] == ["head", "wrist"]
    assert {view.trace_id for view in views} == {"trace_1"}


def test_a_camera_line_without_a_trace_id_is_refused(tmp_path: Path, camera_entry) -> None:
    path = tmp_path / CAMERA_NAME
    entry = {key: camera_entry[key] for key in camera_entry if key != "trace_id"}
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    with pytest.raises(ReaderError, match="trace_id"):
        read_camera_params(path)


def test_a_camera_of_another_trace_is_refused(write_job, clean_rows, camera_entry) -> None:
    folder = write_job(clean_rows, camera=[camera_entry, {**camera_entry, "trace_id": "trace_9"}])

    with pytest.raises(ReaderError, match="trace_9"):
        load_episode(folder)


def test_a_camera_pose_that_is_not_seven_numbers_is_refused(tmp_path: Path, camera_entry) -> None:
    path = tmp_path / CAMERA_NAME
    path.write_text(json.dumps({**camera_entry, "pose": [0.0, 0.0, 1.5]}) + "\n", encoding="utf-8")

    with pytest.raises(ReaderError, match="(?s)không phải CameraParams.*7 elements"):
        read_camera_params(path)


def test_load_episode_reads_the_trace_directory_of_decision_g1(
    write_job, rollout_result, clean_rows, rtc_rows, camera_entry
) -> None:
    # Decision G1 on PR #48: <job>/<trace_id>/{steps.jsonl, camera_params.jsonl,
    # rollout_result.json}; the RTC log of DA-19 is one per job, in <job>/.
    folder = write_job(
        clean_rows, rtc=rtc_rows, camera=[camera_entry], result=rollout_result("ok")
    )

    inputs = load_episode(folder)

    assert inputs.trace.num_steps == 20
    assert inputs.has_rtc_log and inputs.has_camera_params
    assert len(inputs.rtc) == len(rtc_rows)
    assert inputs.infra_status == "ok"


def test_the_trace_file_itself_finds_the_same_files(
    write_job, rollout_result, clean_rows, rtc_rows
) -> None:
    folder = write_job(clean_rows, rtc=rtc_rows, result=rollout_result("ok"))

    inputs = load_episode(folder / STEPS_NAME)

    assert len(inputs.rtc) == len(rtc_rows)
    assert inputs.infra_status == "ok"


def test_an_rtc_log_beside_the_trace_is_not_the_job_log(write_job, clean_rows, rtc_rows) -> None:
    # The job log is the one DA-19 writes; a file in the episode dir is not
    # read, and its absence from the job dir costs R1 and R2 by name.
    folder = write_job(clean_rows)
    (folder / RTC_NAME).write_text(
        "".join(json.dumps(item) + "\n" for item in rtc_rows), encoding="utf-8"
    )

    assert not load_episode(folder).has_rtc_log


def test_infra_status_is_read_from_the_rollout_result(
    write_job, rollout_result, clean_rows
) -> None:
    folder = write_job(clean_rows, result=rollout_result("simulator_error"))

    assert load_episode(folder).infra_status == "simulator_error"


def test_a_rollout_file_that_is_not_a_rollout_result_is_refused(write_job, clean_rows) -> None:
    folder = write_job(clean_rows, result={"infra_status": "sim_crash"})

    with pytest.raises(ReaderError, match="RolloutResult"):
        load_episode(folder)


def test_a_rollout_result_of_another_trace_is_refused(
    write_job, rollout_result, clean_rows
) -> None:
    # Files of two episodes in one directory would pair this trace with
    # another episode's infra status.
    folder = write_job(clean_rows, result=rollout_result("ok", trace_id="trace_9"))

    with pytest.raises(ReaderError, match="trace_9"):
        load_episode(folder)


def test_a_job_wide_rtc_log_is_filtered_to_the_trace(write_job, clean_rows, rtc_rows) -> None:
    # `RTCClient` of DA-19 writes one `rtc.jsonl` per job for every trace in
    # it; the latency of another episode is not this episode's latency.
    other = [{**record, "trace_id": "trace_2", "chunk_received_s": 9.0} for record in rtc_rows]
    folder = write_job(clean_rows, rtc=[*rtc_rows, *other])

    inputs = load_episode(folder)

    assert inputs.trace.trace_id == "trace_1"
    assert len(inputs.rtc) == len(rtc_rows)
    assert {record.trace_id for record in inputs.rtc} == {"trace_1"}


def test_an_rtc_log_with_no_chunk_of_the_trace_costs_r1_and_r2(
    write_job, clean_rows, rtc_rows
) -> None:
    other = [{**record, "trace_id": "trace_2"} for record in rtc_rows]
    folder = write_job(clean_rows, rtc=other)

    inputs = load_episode(folder)

    assert inputs.has_rtc_log
    assert inputs.rtc == ()


def test_a_step_without_a_trace_id_is_refused(write_job, clean_rows, rtc_rows) -> None:
    # Without it the job-wide RTC log has no way to say which chunks are this
    # episode's; `TraceStep` requires it, so the guess is never made.
    unnamed = [{key: item[key] for key in item if key != "trace_id"} for item in clean_rows]
    folder = write_job(unnamed, rtc=rtc_rows)

    with pytest.raises(ReaderError, match="trace_id"):
        load_episode(folder)


def test_an_episode_without_the_optional_files_still_loads(write_job, clean_rows) -> None:
    inputs = load_episode(write_job(clean_rows))

    assert inputs.rtc == () and inputs.cameras == ()
    assert not inputs.has_rtc_log and not inputs.has_camera_params
    assert inputs.infra_status is None


def test_an_episode_without_a_trace_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ReaderError, match=f"không tìm thấy {STEPS_NAME}"):
        load_episode(tmp_path)


def test_a_percentile_of_nothing_finite_is_nan_not_zero() -> None:
    # nan reads as "not measured" downstream; zero would read as a value under
    # every threshold, which is the silent pass FR21 forbids.
    assert math.isnan(percentile(np.array([np.nan, np.nan]), 99))
    assert percentile(np.array([1.0, np.nan, 3.0]), 50) == pytest.approx(2.0)


def test_a_vector_logged_as_null_is_refused(row, write_trace) -> None:
    # `TraceStep` has no null vector: a cycle with no measurement writes its
    # channels as "NaN", which is a gap (above). A null is a writer outside
    # the contract, and reading it as a gap would hide that.
    with pytest.raises(ReaderError, match="(?s)dòng 2 không phải TraceStep.*cmd_upper"):
        read_trace_log(write_trace([row(0), row(1, cmd_upper=None)]))


def test_an_empty_steps_file_is_a_trace_of_no_cycle_named_by_its_directory(
    write_job, rollout_result
) -> None:
    # A rollout cut off before its first cycle: the steps say nothing, but the
    # RolloutResult beside them still says why, and R6 must still read it.
    folder = write_job([], result=rollout_result("simulator_error"))

    inputs = load_episode(folder)

    assert inputs.trace.num_steps == 0
    assert (inputs.trace.trace_id, inputs.trace.episode_id) == ("trace_1", "trace_1")
    assert inputs.infra_status == "simulator_error"

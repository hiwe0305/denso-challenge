"""The reader of the F-SYS checks: what it turns into arrays, and what it refuses.

The cases that matter are the ones where a wrong read would turn into a wrong
verdict: a gap read as a number clears a threshold, and a field nobody logged
read as present makes the missing-signal check miss it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel.eval.diagnosis.system.reader import (
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
    assert trace.absent_fields == ()
    assert trace.gap_counts == {}


def test_a_trace_naming_no_episode_falls_back_to_the_file_name(row, write_trace) -> None:
    rows = [row(step) for step in range(3)]
    for item in rows:
        del item["episode_id"]

    trace = read_trace_log(write_trace(rows, name="ep_fallback.jsonl"))

    assert trace.episode_id == "ep_fallback"


def test_a_value_that_is_not_finite_is_a_gap_not_a_number(row, write_trace) -> None:
    # Every comparison against a NaN is false, so a NaN tracking error left in
    # place would clear tau_track and come back as a controller that tracked.
    rows = [row(0), row(1, meas_upper=[float("nan"), 0.2, 0.3]), row(2, t_image="NaN")]
    path = write_trace(rows)
    path.write_text(
        "".join(json.dumps(item).replace("NaN", "NaN") + "\n" for item in rows),
        encoding="utf-8",
    )

    trace = read_trace_log(path)

    assert trace.gap_counts == {"meas_upper": 1, "t_image": 1}
    error = trace.tracking_error("upper")
    assert math.isnan(error[1])
    assert error[0] == pytest.approx(0.0)


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


def test_a_field_no_row_carries_is_absent_not_a_gap(row, write_trace) -> None:
    rows = [row(step) for step in range(4)]
    for item in rows:
        del item["t_image"]

    trace = read_trace_log(write_trace(rows))

    assert trace.absent_fields == ("t_image",)
    assert "t_image" not in trace.gap_counts
    assert trace.sync_offset().size == 0


def test_tracking_error_is_the_norm_per_cycle_upper_and_lower_apart(row, write_trace) -> None:
    rows = [
        row(0, meas_upper=[0.1, 0.2, 0.3], meas_lower=[0.5, 0.0]),
        row(1, meas_upper=[0.4, 0.6, 0.3], meas_lower=[0.8, 0.4]),
    ]

    trace = read_trace_log(write_trace(rows))

    # upper: |(0.3, 0.4, 0.0)| = 0.5; lower: |(0.3, 0.4)| = 0.5
    assert trace.tracking_error("upper") == pytest.approx([0.0, 0.5])
    assert trace.tracking_error("lower") == pytest.approx([0.0, 0.5])


def test_a_command_and_a_measurement_of_different_width_is_refused(row, write_trace) -> None:
    rows = [row(0, meas_upper=[0.1, 0.2])]

    trace = read_trace_log(write_trace(rows))

    with pytest.raises(ReaderError, match="khác số kênh"):
        trace.tracking_error("upper")


def test_a_trace_changing_its_channel_count_is_refused(row, write_trace) -> None:
    rows = [row(0), row(1, cmd_upper=[0.1, 0.2], meas_upper=[0.1, 0.2])]

    trace = read_trace_log(write_trace(rows))

    with pytest.raises(ReaderError, match="đổi số kênh"):
        trace.tracking_error("upper")


def test_sync_offset_is_the_absolute_difference_of_the_two_clocks(row, write_trace) -> None:
    rows = [row(0, t_state=1.0, t_image=1.05), row(1, t_state=2.0, t_image=1.9)]

    trace = read_trace_log(write_trace(rows))

    assert trace.sync_offset() == pytest.approx([0.05, 0.1])


def test_dropped_frames_are_summed_over_the_episode(row, write_trace) -> None:
    rows = [row(0), row(1, dropped_frames=2), row(2, dropped_frames=1)]

    trace = read_trace_log(write_trace(rows))

    assert trace.dropped_frames == 3


def test_a_line_that_is_not_json_says_which_line(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text('{"step": 0}\nnot json\n', encoding="utf-8")

    with pytest.raises(ReaderError, match="dòng 2 không phải JSON"):
        read_trace_log(path)


def test_a_signal_that_is_not_a_number_is_refused(row, write_trace) -> None:
    with pytest.raises(ReaderError, match="`t_state` phải là số"):
        read_trace_log(write_trace([row(0, t_state=True)]))


def test_the_rtc_log_is_read_through_the_contract(tmp_path: Path, rtc_rows) -> None:
    path = tmp_path / "rtc.jsonl"
    path.write_text("".join(json.dumps(item) + "\n" for item in rtc_rows), encoding="utf-8")

    records = read_rtc_log(path)

    assert len(records) == 10
    assert records[0].buffer_level == 6


def test_an_rtc_line_the_contract_rejects_says_so(tmp_path: Path, rtc_rows) -> None:
    broken: dict[str, Any] = dict(rtc_rows[0])
    broken["chunk_received_s"] = broken["observation_sent_s"] - 1.0
    path = tmp_path / "rtc.jsonl"
    path.write_text(json.dumps(broken) + "\n", encoding="utf-8")

    with pytest.raises(ReaderError, match="không phải RTCInferenceRecord"):
        read_rtc_log(path)


def test_camera_params_read_as_one_object_or_a_list(tmp_path: Path, camera_entry) -> None:
    single = tmp_path / "one.json"
    single.write_text(json.dumps(camera_entry), encoding="utf-8")
    many = tmp_path / "many.json"
    many.write_text(json.dumps([camera_entry, {**camera_entry, "uid": "wrist"}]), encoding="utf-8")

    assert [view.uid for view in read_camera_params(single)] == ["head"]
    assert [view.uid for view in read_camera_params(many)] == ["head", "wrist"]


def test_a_camera_pose_that_is_not_seven_numbers_is_refused(tmp_path: Path, camera_entry) -> None:
    path = tmp_path / "camera_params.json"
    path.write_text(json.dumps({**camera_entry, "pose": [0.0, 0.0, 1.5]}), encoding="utf-8")

    with pytest.raises(ReaderError, match="7 số hữu hạn"):
        read_camera_params(path)


def test_load_episode_finds_the_files_beside_the_trace(
    tmp_path: Path, clean_rows, rtc_rows, camera_entry
) -> None:
    (tmp_path / "trace.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in clean_rows), encoding="utf-8"
    )
    (tmp_path / "rtc.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in rtc_rows), encoding="utf-8"
    )
    (tmp_path / "camera_params.json").write_text(json.dumps(camera_entry), encoding="utf-8")
    (tmp_path / "episode.json").write_text(json.dumps({"infra_status": "ok"}), encoding="utf-8")

    inputs = load_episode(tmp_path)

    assert inputs.trace.num_steps == 20
    assert inputs.has_rtc_log and inputs.has_camera_params
    assert inputs.infra_status == "ok"


def test_an_episode_without_the_optional_files_still_loads(tmp_path: Path, clean_rows) -> None:
    (tmp_path / "trace.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in clean_rows), encoding="utf-8"
    )

    inputs = load_episode(tmp_path)

    assert inputs.rtc == () and inputs.cameras == ()
    assert not inputs.has_rtc_log and not inputs.has_camera_params
    assert inputs.infra_status is None


def test_an_episode_without_a_trace_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ReaderError, match="không tìm thấy trace.jsonl"):
        load_episode(tmp_path)


def test_a_percentile_of_nothing_finite_is_nan_not_zero() -> None:
    # nan reads as "not measured" downstream; zero would read as a value under
    # every threshold, which is the silent pass FR21 forbids.
    assert math.isnan(percentile(np.array([np.nan, np.nan]), 99))
    assert percentile(np.array([1.0, np.nan, 3.0]), 50) == pytest.approx(2.0)

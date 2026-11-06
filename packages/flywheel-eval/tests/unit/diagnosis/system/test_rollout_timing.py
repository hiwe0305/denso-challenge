"""R1 and R2 on a synchronous rollout are recorded, not counted (DA-13 AC 7).

Decision (a) of the PO, 5/11/2026: SIMPLE waits for the server before it steps
the sim, so latency cannot make a sim episode fail. R1 and R2 are still
measured and travel with the verdict, but only an asynchronous rollout (DA-23)
counts them. A rollout whose mode nobody wrote down counts them too, and says
so: an unknown mode is never taken for a synchronous one (FR21).
"""

from __future__ import annotations

from typing import Any

import pytest
from flywheel.contracts.artifacts import RTCInferenceRecord
from flywheel.contracts.diagnosis import SystemDiagnosis
from flywheel.eval.config import R1Thresholds, R2Thresholds, R3Thresholds
from flywheel.eval.diagnosis.system.artifact import build_system_record
from flywheel.eval.diagnosis.system.reader import SystemInputs, load_episode, read_trace_log
from flywheel.eval.diagnosis.system.runtime import check_r1, check_r2
from flywheel.eval.diagnosis.system.tracking import check_r3
from flywheel.eval.diagnosis.system.verdict import CheckResult, Diagnosis, combine

R1 = R1Thresholds(tau_lat_s=0.1, percentile=99.0)
R2 = R2Thresholds(rtc_inference_delay_steps=6, max_underruns=0)
R3 = R3Thresholds(tau_track_upper=0.1, tau_track_lower=0.15, percentile=99.0)


def _slow(rtc_rows: list[dict[str, Any]]) -> list[CheckResult]:
    """R1 and R2 both firing: 0.4 s on every chunk is 20 steps at 50 Hz, over d = 6."""
    rows = [
        dict(row, chunk_received_s=row["observation_sent_s"] + 0.4, delay_steps=20)
        for row in rtc_rows
    ]
    records = tuple(RTCInferenceRecord.model_validate(row) for row in rows)
    return [check_r1(records, R1), check_r2(records, R2)]


def _no_log() -> list[CheckResult]:
    return [check_r1((), R1), check_r2((), R2)]


def test_sync_rollout_records_r1_and_r2_without_blocking(rtc_rows) -> None:
    verdict = combine("ep_1", _slow(rtc_rows), "ok", "sync")

    assert verdict.diagnosis is Diagnosis.CLEAN
    assert not verdict.blocks_policy_analysis
    assert verdict.findings == [] and verdict.skipped == []
    assert [finding.code for finding in verdict.recorded] == ["R1", "R2"]
    for finding in verdict.recorded:
        assert "rollout đồng bộ" in (finding.detail or "")
        assert "không quy lỗi" in (finding.detail or "")


def test_sync_rollout_keeps_the_label_of_the_faults_that_count(row, write_trace, rtc_rows) -> None:
    rows = [row(step, meas_upper=[0.5, 0.2, 0.3]) for step in range(20)]
    tracking = check_r3(read_trace_log(write_trace(rows)), R3)

    verdict = combine("ep_1", [tracking, *_slow(rtc_rows)], "ok", "sync")

    # R3 is the label on its own merit; R1 and R2 were set aside, not outranked
    assert verdict.diagnosis is Diagnosis.CONTROLLER
    assert {finding.code for finding in verdict.findings} == {"R3"}
    assert [finding.code for finding in verdict.recorded] == ["R1", "R2"]


def test_sync_rollout_without_an_rtc_log_is_recorded_not_unknown() -> None:
    verdict = combine("ep_1", _no_log(), "ok", "sync")

    assert verdict.diagnosis is Diagnosis.CLEAN
    assert verdict.skipped == []
    assert [skip.code for skip in verdict.recorded_skipped] == ["R1", "R2"]
    assert all("không quy lỗi" in skip.reason for skip in verdict.recorded_skipped)


def test_async_rollout_counts_r1_and_r2_as_before(rtc_rows) -> None:
    verdict = combine("ep_1", _slow(rtc_rows), "ok", "async")

    assert verdict.diagnosis is Diagnosis.RUNTIME
    assert verdict.blocks_policy_analysis
    assert [finding.code for finding in verdict.findings] == ["R1", "R2"]
    assert verdict.recorded == [] and verdict.recorded_skipped == []
    assert all("không rõ" not in (finding.detail or "") for finding in verdict.findings)


def test_unknown_mode_counts_r1_and_r2_and_says_the_mode_was_unknown(rtc_rows) -> None:
    verdict = combine("ep_1", _slow(rtc_rows), "ok", None)

    assert verdict.diagnosis is Diagnosis.RUNTIME
    assert verdict.recorded == []
    for finding in verdict.findings:
        assert "không rõ rollout đồng bộ hay bất đồng bộ" in (finding.detail or "")


def test_unknown_mode_without_an_rtc_log_stays_unknown() -> None:
    verdict = combine("ep_1", _no_log(), "ok", None)

    assert verdict.diagnosis is Diagnosis.UNKNOWN
    assert [skip.code for skip in verdict.skipped] == ["R1", "R2"]


@pytest.mark.parametrize("timing", ["sync", "async"])
def test_the_rollout_result_states_its_mode_in_its_own_words(
    write_job, rollout_result, clean_rows, timing
) -> None:
    # The SimpleSim hook writes "sync" for SIMPLE's eval loop (PR #148).
    folder = write_job(clean_rows, result=dict(rollout_result(), timing=timing))

    assert load_episode(folder).timing == timing


def test_a_timing_verdict_without_timing_reads_as_async(
    write_job, rollout_result, clean_rows
) -> None:
    # `runner.json` written before PR #146 carries a verdict and no `timing`;
    # only an asynchronous rollout ever has a verdict.
    for verdict in ("ok", "starved", "not_checked"):
        folder = write_job(clean_rows, result=dict(rollout_result(), timing_verdict=verdict))

        assert load_episode(folder).timing == "async"


def test_a_rollout_result_that_does_not_say_is_unknown_not_sync(
    write_job, rollout_result, clean_rows
) -> None:
    # What the hook wrote before PR #148: no `timing`, no verdict.
    with_result = write_job(clean_rows, result=rollout_result())
    without_result = write_job(clean_rows)

    assert load_episode(with_result).timing is None
    assert load_episode(without_result).timing is None


def test_the_record_keeps_r1_and_r2_of_a_sync_rollout_apart_from_the_label(
    write_trace, clean_rows, rtc_rows
) -> None:
    inputs = SystemInputs(trace=read_trace_log(write_trace(clean_rows)))
    synced = combine("ep_1", _slow(rtc_rows), "ok", "sync")

    record = build_system_record(synced, "c" * 64, inputs)

    assert record.diagnosis == "clean"
    assert record.timing == "sync"
    assert record.findings == [] and record.skipped == []
    assert [finding.code for finding in record.recorded] == ["R1", "R2"]
    assert all("không quy lỗi" in (finding.detail or "") for finding in record.recorded)
    # The shared contract takes it whole: `clean` beside recorded R1 and R2.
    shared = SystemDiagnosis.model_validate_json(record.model_dump_json())
    assert shared.model_dump(mode="json") == record.model_dump(mode="json")


def test_the_record_of_a_sync_rollout_without_an_rtc_log_keeps_the_skips(
    write_trace, clean_rows
) -> None:
    inputs = SystemInputs(trace=read_trace_log(write_trace(clean_rows)))

    record = build_system_record(combine("ep_1", _no_log(), "ok", "sync"), "c" * 64, inputs)

    assert record.diagnosis == "clean"
    assert [skip.code for skip in record.recorded_skipped] == ["R1", "R2"]
    SystemDiagnosis.model_validate_json(record.model_dump_json())


def test_a_slow_sync_episode_read_off_disk_is_not_a_runtime_fault(
    write_job, rollout_result, clean_rows, rtc_rows
) -> None:
    # The demo's part 6 on a real SIMPLE episode: /act at ~0.4 s, 20 steps of
    # delay against d = 6, and the hook's "sync". Decision (a) now holds on disk.
    slow = [
        dict(row, chunk_received_s=row["observation_sent_s"] + 0.4, delay_steps=20)
        for row in rtc_rows
    ]
    folder = write_job(clean_rows, rtc=slow, result=dict(rollout_result(), timing="sync"))
    inputs = load_episode(folder)

    results = [check_r1(inputs.rtc, R1), check_r2(inputs.rtc, R2)]
    record = build_system_record(
        combine("ep_1", results, inputs.infra_status, inputs.timing), "c" * 64, inputs
    )

    assert record.diagnosis == "clean"
    assert [finding.code for finding in record.recorded] == ["R1", "R2"]


def test_the_record_of_an_unknown_mode_keeps_r1_and_r2_and_why(
    write_trace, clean_rows, rtc_rows
) -> None:
    inputs = SystemInputs(trace=read_trace_log(write_trace(clean_rows)))

    record = build_system_record(combine("ep_1", _slow(rtc_rows), "ok", None), "c" * 64, inputs)

    assert record.diagnosis == "runtime"
    assert [finding.code for finding in record.findings] == ["R1", "R2"]
    assert all("không rõ" in (finding.detail or "") for finding in record.findings)

"""τ calibrated from successful episodes and the G0 run (DA-37 tasks 3, 4, 6.2; AC 4, 6).

Every trace is built here as DA-38's hook lays one out (`<trace_id>/steps.jsonl`
beside `rollout_result.json`), so the calibration reads it through DA-13's own
loader, the way it will read a real one.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel.contracts.trace import LOWER_BODY, UPPER_BODY
from flywheel.eval.api import calibrate_tau as _calibrate_tau
from flywheel.eval.api import store_tau
from flywheel.eval.cli import app
from flywheel.eval.config import load_system_thresholds
from flywheel.eval.diagnosis.system.reader import ReaderError, load_episode, read_rtc_log
from flywheel.eval.diagnosis.system.runtime import check_r1, check_r4
from flywheel.eval.diagnosis.system.tracking import check_r3
from flywheel.eval.scorer.tau import (
    CALIBRATION_PERCENTILE,
    FEW_SAMPLES,
    TAU_RECORDS,
    TauError,
    TauReport,
)
from flywheel.store.blobs import get_blob
from flywheel.store.paths import StorePaths
from typer.testing import CliRunner

UPPER = [0.0] * len(UPPER_BODY)
LOWER = [0.0] * len(LOWER_BODY)
ROOT = Path(__file__).resolve().parents[5]
SYSTEM_YAML = ROOT / "configs" / "eval" / "diagnosis" / "system.yaml"
THRESHOLDS, _ = load_system_thresholds(SYSTEM_YAML)


def calibrate_tau(teleop: list[Path], g0: list[Path] | None = None, **options: Any) -> TauReport:
    """`calibrate_tau` on the repo's `system.yaml`, wherever pytest runs from."""
    return _calibrate_tau(teleop, g0, config_path=SYSTEM_YAML, **options)


def p99(values: list[float]) -> float:
    return float(np.percentile(values, 99.0))


def step(
    trace_id: str,
    index: int,
    upper_error: float,
    lower_error: Any = 0.0,
    sync: Any = 0.0,
    run_plan: str = "rp_1",
) -> dict[str, Any]:
    """One cycle whose first upper and first lower channel miss by the given amounts,
    with the frame `sync` seconds after the state (None: no new frame)."""
    return {
        "trace_id": trace_id,
        "episode_id": f"episode_{index}",
        "run_plan_id": run_plan,
        "step": index,
        "t_state": 0.02 * index,
        "t_image": None if sync is None else 0.02 * index + sync,
        "cmd_upper": [upper_error, *UPPER[1:]],
        "meas_upper": list(UPPER),
        "cmd_lower": [lower_error, *LOWER[1:]],
        "meas_lower": list(LOWER),
        "dropped_frames": 0,
    }


def write_trace(
    root: Path,
    trace_id: str,
    upper: list[float],
    lower: list[Any] | None = None,
    *,
    sim: bool | None = True,
    infra: str = "ok",
    result: bool = True,
    sync: list[Any] | None = None,
    run_plan: str = "rp_1",
    adapter: str = "simple",
) -> Path:
    """`<root>/<trace_id>/steps.jsonl`, and `rollout_result.json` unless `result` is False."""
    lower = lower if lower is not None else [0.0] * len(upper)
    sync = sync if sync is not None else [0.0] * len(upper)
    folder = root / trace_id
    folder.mkdir(parents=True)
    rows = [
        step(trace_id, i, u, lo, s, run_plan)
        for i, (u, lo, s) in enumerate(zip(upper, lower, sync, strict=True))
    ]
    data = "".join(json.dumps(row) + "\n" for row in rows).encode("utf-8")
    (folder / "steps.jsonl").write_bytes(data)
    if result:
        payload = {
            "job_id": trace_id.split("-")[0],
            "trace_ref": {
                "trace_id": trace_id,
                "uri": f"{trace_id}/",
                "sha256": hashlib.sha256(data).hexdigest(),
            },
            "sim_success": sim,
            "infra_status": infra,
            "usage": {"wall_seconds": 1.0, "gpu_seconds": 0.0},
            "camera_params_hash": None,
            "adapter_info": {
                "name": adapter,
                "version": "0.1.0",
                "image_digest": None,
                "nondeterminism": [],
            },
            "timing": "sync",
        }
        (folder / "rollout_result.json").write_text(json.dumps(payload), encoding="utf-8")
    return folder


def test_tau_track_is_the_99th_percentile_of_each_episodes_own_statistic(
    tmp_path: Path,
) -> None:
    # R3 judges an episode by the p99 of its cycles, so each good episode is
    # reduced to that number first and tau is the p99 of those numbers.
    first = [0.001 * i for i in range(60)]
    second = [0.002 * i for i in range(90)]
    write_trace(tmp_path, "j1-a", first, [0.01] * 60)
    write_trace(tmp_path, "j1-b", second, [0.03] * 90)

    report = calibrate_tau([tmp_path])

    upper, lower = report.value("tau_track_upper"), report.value("tau_track_lower")
    assert upper.value == pytest.approx(p99([p99(first), p99(second)]))
    assert upper.value != pytest.approx(p99(first + second))
    assert (upper.samples, upper.cycles, upper.skipped_cycles) == (2, 150, 0)
    assert upper.percentile == CALIBRATION_PERCENTILE == 99.0
    assert upper.episode_percentile == THRESHOLDS.r3.percentile
    assert (upper.exceeded, upper.few_samples) == (1, True)
    assert lower.value == pytest.approx(p99([0.01, 0.03]))
    assert [episode.trace_id for episode in report.episodes] == ["j1-a", "j1-b"]
    assert {episode.success for episode in report.episodes} == {"sim_success"}
    assert report.episodes[0].run_plan_ids == ["rp_1"]
    assert report.episodes[0].adapter == "simple@0.1.0"


def test_the_checks_fire_on_at_most_one_calibration_episode(tmp_path: Path) -> None:
    # Review of #169, point 1: with cycles pooled, R3 fired on 8/20 and 11/20
    # of the very episodes tau came from. Run the checks themselves on them.
    rng = np.random.default_rng(7)
    folders = []
    latencies: dict[str, list[float]] = {}
    for index in range(20):
        cycles = 300
        folders.append(
            write_trace(
                tmp_path / "teleop",
                f"j1-{index:02d}",
                [float(x) for x in np.abs(rng.normal(0.0, 0.05, cycles))],
                [float(x) for x in np.abs(rng.normal(0.0, 0.08, cycles))],
                sync=[float(x) for x in rng.exponential(0.003, cycles)],
            )
        )
        latencies[f"g0-{index:02d}"] = [float(x) for x in 0.05 + rng.exponential(0.01, 40)]
    log = write_rtc(tmp_path / "g0", latencies)

    report = calibrate_tau([tmp_path / "teleop"], [log])

    def tau(key: str) -> float:
        value = report.value(key).value
        assert value is not None
        return value

    r3 = dataclasses.replace(
        THRESHOLDS.r3,
        tau_track_upper=tau("tau_track_upper"),
        tau_track_lower=tau("tau_track_lower"),
    )
    r4 = dataclasses.replace(THRESHOLDS.r4, tau_sync_s=tau("tau_sync_s"))
    r1 = dataclasses.replace(THRESHOLDS.r1, tau_lat_s=tau("tau_lat_s"))
    fired = {"upper": 0, "lower": 0, "sync": 0, "lat": 0}
    for folder in folders:
        trace = load_episode(folder).trace
        for finding in check_r3(trace, r3).findings:
            fired[str(finding.part)] += 1
        fired["sync"] += len(check_r4(trace, r4).findings)
    records = read_rtc_log(log)
    for trace_id in latencies:
        chunks = tuple(r for r in records if r.trace_id == trace_id)
        fired["lat"] += len(check_r1(chunks, r1).findings)

    assert fired == {
        "upper": report.value("tau_track_upper").exceeded,
        "lower": report.value("tau_track_lower").exceeded,
        "sync": report.value("tau_sync_s").exceeded,
        "lat": report.value("tau_lat_s").exceeded,
    }
    assert all(count <= 1 for count in fired.values()), fired
    assert report.value("tau_sync_s").episode_percentile == 100.0


def test_a_value_under_a_hundred_episodes_is_flagged(tmp_path: Path) -> None:
    # Under 100 episodes the 99th percentile is nearly the largest one (AC 4);
    # the cycles of one episode are not independent samples of it.
    write_trace(tmp_path, "j1-a", [0.01] * (FEW_SAMPLES + 50))

    value = calibrate_tau([tmp_path]).value("tau_track_upper")

    assert (value.samples, value.cycles) == (1, FEW_SAMPLES + 50)
    assert value.few_samples is True


def test_failed_and_infra_episodes_are_left_out_with_the_reason(tmp_path: Path) -> None:
    write_trace(tmp_path, "j1-ok", [0.01] * 20)
    write_trace(tmp_path, "j1-fail", [5.0] * 20, sim=False)
    write_trace(tmp_path, "j1-infra", [5.0] * 20, sim=None, infra="timeout")

    report = calibrate_tau([tmp_path])

    assert report.value("tau_track_upper").value == pytest.approx(0.01)
    assert {(item.trace_id, item.reason) for item in report.left_out} == {
        ("j1-fail", "SIMPLE báo trượt"),
        ("j1-infra", "lỗi hạ tầng `timeout`"),
    }


def test_a_demo_without_a_sim_flag_counts_only_when_declared(tmp_path: Path) -> None:
    write_trace(tmp_path, "demo-1", [0.02] * 20, result=False)

    with pytest.raises(TauError, match="--demos"):
        calibrate_tau([tmp_path])
    report = calibrate_tau([tmp_path], declared_demos=True)

    assert report.value("tau_track_upper").value == pytest.approx(0.02)
    assert report.episodes[0].success == "declared_demo"


def test_a_cycle_with_a_gap_is_skipped_not_read_as_zero(tmp_path: Path) -> None:
    # Raw psi-data logs `meas_lower` as "NaN"; a zero there would pull τ down.
    lower: list[Any] = [0.2] * 10 + ["NaN"] * 10
    write_trace(tmp_path, "j1-a", [0.01] * 20, lower)

    report = calibrate_tau([tmp_path])

    tau_lower = report.value("tau_track_lower")
    assert tau_lower.value == pytest.approx(0.2)
    assert (tau_lower.samples, tau_lower.cycles, tau_lower.skipped_cycles) == (1, 10, 10)


def test_a_half_never_measured_has_no_value_rather_than_zero(tmp_path: Path) -> None:
    write_trace(tmp_path, "j1-a", [0.01] * 20, ["NaN"] * 20)

    tau_lower = calibrate_tau([tmp_path]).value("tau_track_lower")

    assert tau_lower.value is None
    assert (tau_lower.samples, tau_lower.cycles, tau_lower.exceeded) == (0, 0, 0)


def test_a_trace_found_through_two_paths_is_read_once(tmp_path: Path) -> None:
    folder = write_trace(tmp_path, "j1-a", [0.01] * 20)

    report = calibrate_tau([tmp_path, folder])

    assert len(report.episodes) == 1
    assert report.left_out == []
    assert report.value("tau_track_upper").cycles == 20


def test_a_trace_the_contract_refuses_stops_the_run(tmp_path: Path) -> None:
    folder = write_trace(tmp_path, "j1-a", [0.01] * 20)
    (folder / "steps.jsonl").write_text('{"trace_id": "j1-a"}\n', encoding="utf-8")

    with pytest.raises(ReaderError):
        calibrate_tau([tmp_path])


def test_a_directory_with_no_trace_is_refused(tmp_path: Path) -> None:
    with pytest.raises(TauError, match="steps.jsonl"):
        calibrate_tau([tmp_path])


def test_the_report_is_stored_as_a_blob_and_listed(tmp_path: Path) -> None:
    write_trace(tmp_path / "eval", "j1-a", [0.01] * 20)
    report = calibrate_tau([tmp_path / "eval"])
    store = tmp_path / "store"

    digest, index = store_tau(report, store)
    store_tau(report, store)

    assert digest == report.sha256
    assert TauReport.model_validate_json(get_blob(digest, StorePaths(store))) == report
    lines = [json.loads(row) for row in index.read_text(encoding="utf-8").splitlines()]
    assert index == store / TAU_RECORDS
    assert len(lines) == 2 and lines[0] == lines[1]
    assert lines[0]["values"]["tau_track_upper"]["samples"] == 1


def test_the_command_prints_each_value_beside_the_one_in_use(tmp_path: Path) -> None:
    write_trace(tmp_path / "eval", "j1-a", [0.01] * 20)

    result = CliRunner().invoke(
        app,
        [
            "tau",
            "--teleop",
            str(tmp_path / "eval"),
            "--config",
            str(SYSTEM_YAML),
            "--store",
            str(tmp_path / "store"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (
        "tau_track_upper: 0.01 rad; phân vị 99 qua 1 episode, mỗi episode lấy phân vị 99 "
        "của 20 chu kỳ (bỏ 0 chu kỳ thiếu tín hiệu); đang dùng 0.1"
    ) in result.output
    assert "0/1 episode hiệu chỉnh vượt ngưỡng này" in result.output
    assert "ít mẫu (dưới 100 episode)" in result.output
    assert "simple@0.1.0" in result.output
    assert "không phải rollout của policy" in result.output
    assert "report_sha256: " in result.output
    assert (tmp_path / "store" / TAU_RECORDS).is_file()


def test_the_command_exits_two_and_stores_nothing_without_a_success(tmp_path: Path) -> None:
    write_trace(tmp_path / "eval", "j1-a", [0.01] * 20, sim=False)

    result = CliRunner().invoke(
        app,
        [
            "tau",
            "--teleop",
            str(tmp_path / "eval"),
            "--config",
            str(SYSTEM_YAML),
            "--store",
            str(tmp_path / "store"),
        ],
    )

    assert result.exit_code == 2
    assert "không hiệu chỉnh được" in result.output
    assert not (tmp_path / "store" / TAU_RECORDS).exists()


# ---------------------------------------------------------------------------
# task 4: tau_sync from the same episodes, tau_lat from the G0 baseline run
# ---------------------------------------------------------------------------


def write_rtc(folder: Path, latencies: dict[str, list[float]], job: str = "g0") -> Path:
    """`<folder>/rtc.jsonl`: per trace, chunk i took `latencies[trace][i]` seconds."""
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for trace_id, values in latencies.items():
        for index, latency in enumerate(values):
            sent = 1.0 + 0.5 * index
            rows.append(
                {
                    "job_id": job,
                    "trace_id": trace_id,
                    "chunk_index": index,
                    "observation_sent_s": sent,
                    "chunk_received_s": sent + latency,
                    "delay_steps": 1,
                    "buffer_level": 0,
                    "boundary_jump": 0.0,
                }
            )
    path = folder / "rtc.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_tau_sync_pools_the_offsets_of_cycles_with_a_frame(tmp_path: Path) -> None:
    # A cycle with no new frame (`t_image: null`) has no offset to count.
    sync: list[Any] = [0.004] * 10 + [None] * 5 + [0.001] * 5
    write_trace(tmp_path, "j1-a", [0.01] * 20, sync=sync)

    tau_sync = calibrate_tau([tmp_path]).value("tau_sync_s")

    assert tau_sync.value == pytest.approx(0.004)
    assert (tau_sync.samples, tau_sync.cycles, tau_sync.skipped_cycles) == (1, 15, 5)
    assert (tau_sync.unit, tau_sync.episode_percentile) == ("s", 100.0)


def test_tau_lat_leaves_chunk_0_out_and_counts_the_traces(tmp_path: Path) -> None:
    # Chunk 0 is the cold start; R1 leaves it out, so the threshold does too.
    log = write_rtc(tmp_path / "g0", {"g0-t1": [2.0, 0.05, 0.06], "g0-t2": [2.0, 0.07]})

    report = calibrate_tau([], [log])

    (tau_lat,) = report.values
    assert tau_lat.key == "tau_lat_s"
    assert tau_lat.value == pytest.approx(p99([p99([0.05, 0.06]), 0.07]))
    assert (tau_lat.samples, tau_lat.cycles, tau_lat.few_samples) == (2, 3, True)
    assert tau_lat.episode_percentile == THRESHOLDS.r1.percentile
    assert report.episodes == []
    (used,) = report.rtc_logs
    assert (used.job_ids, used.chunks) == (["g0"], 5)
    assert used.unchecked_traces == ["g0-t1", "g0-t2"]
    assert used.sha256 == hashlib.sha256(log.read_bytes()).hexdigest()


def test_both_sources_give_all_four_values_apart(tmp_path: Path) -> None:
    write_trace(tmp_path / "teleop", "j1-a", [0.01] * 20)
    write_rtc(tmp_path / "g0", {"g0-t1": [1.0, 0.08]})

    report = calibrate_tau([tmp_path / "teleop"], [tmp_path / "g0"])

    assert [item.key for item in report.values] == [
        "tau_track_upper",
        "tau_track_lower",
        "tau_sync_s",
        "tau_lat_s",
    ]
    assert report.value("tau_lat_s").value == pytest.approx(0.08)


def test_no_input_at_all_is_refused() -> None:
    with pytest.raises(TauError, match="không có đầu vào"):
        calibrate_tau([], [])


def test_a_g0_directory_with_no_rtc_log_is_refused(tmp_path: Path) -> None:
    with pytest.raises(TauError, match="rtc.jsonl"):
        calibrate_tau([], [tmp_path])


def test_the_command_reads_g0_alone_and_warns_on_a_sim_sync_of_zero(tmp_path: Path) -> None:
    write_trace(tmp_path / "eval", "j1-a", [0.01] * 20)
    write_rtc(tmp_path / "g0", {"g0-t1": [1.0, 0.08]})

    both = CliRunner().invoke(
        app,
        [
            "tau",
            "--teleop",
            str(tmp_path / "eval"),
            "--g0",
            str(tmp_path / "g0"),
            "--config",
            str(SYSTEM_YAML),
        ],
    )
    g0_only = CliRunner().invoke(
        app, ["tau", "--g0", str(tmp_path / "g0"), "--config", str(SYSTEM_YAML)]
    )

    assert both.exit_code == 0, both.output
    assert "tau_sync_s: 0 s" in both.output
    assert "rollout SIMPLE đồng bộ theo cách dựng" in both.output
    assert (
        "tau_lat_s: 0.08 s; phân vị 99 qua 1 trace G0, mỗi trace G0 lấy phân vị 99 của 1 chunk"
    ) in both.output
    assert "bỏ 0 chu kỳ không có khung ảnh mới hoặc thiếu tín hiệu" in both.output
    assert "log RTC của G0: 1 file, 2 chunk" in both.output
    assert g0_only.exit_code == 0, g0_only.output
    assert "tau_track_upper" not in g0_only.output


# ---------------------------------------------------------------------------
# task 6.2: calibrating again gives the same tau, byte for byte (AC 6)
# ---------------------------------------------------------------------------

EPISODES: dict[str, tuple[list[float], list[Any]]] = {
    "j1-a": ([0.001 * i for i in range(40)], [0.003] * 20 + [None] * 20),
    "j1-b": ([0.002 * i for i in range(70)], [0.001] * 70),
    "j1-c": ([0.05] * 30, [0.002] * 30),
}
LATENCIES = {"g0-t1": [1.5, 0.05, 0.07, 0.06], "g0-t2": [1.4, 0.08, 0.04]}


def build(root: Path, order: list[str]) -> tuple[Path, Path]:
    """The same episodes and G0 log under `root`, the traces written in `order`."""
    for trace_id in order:
        upper, sync = EPISODES[trace_id]
        write_trace(root / "teleop", trace_id, upper, sync=sync)
    write_rtc(root / "g0", LATENCIES)
    return root / "teleop", root / "g0"


def test_the_same_episodes_give_the_same_report_in_two_places(tmp_path: Path) -> None:
    # A tau that moved between two runs over the same data would make the
    # threshold a property of the run rather than of the data.
    teleop_one, g0_one = build(tmp_path / "one", ["j1-a", "j1-b", "j1-c"])
    teleop_two, g0_two = build(tmp_path / "two", ["j1-c", "j1-a", "j1-b"])

    first = calibrate_tau([teleop_one], [g0_one])
    second = calibrate_tau([teleop_two], [g0_two])

    assert first.canonical() == second.canonical()
    assert first.sha256 == second.sha256


def test_running_twice_gives_the_same_blob_and_appends_a_line(tmp_path: Path) -> None:
    teleop, g0 = build(tmp_path / "data", ["j1-a", "j1-b", "j1-c"])
    store = tmp_path / "store"

    first, index = store_tau(calibrate_tau([teleop], [g0]), store)
    second, _ = store_tau(calibrate_tau([teleop], [g0]), store)

    assert first == second
    assert len(index.read_text(encoding="utf-8").splitlines()) == 2


def test_another_episode_changes_the_report(tmp_path: Path) -> None:
    teleop, _ = build(tmp_path / "data", ["j1-a", "j1-b", "j1-c"])
    base = calibrate_tau([teleop])
    write_trace(teleop, "j1-d", [0.5] * 20)

    grown = calibrate_tau([teleop])

    assert grown.sha256 != base.sha256
    assert grown.value("tau_track_upper").value != base.value("tau_track_upper").value


# ---------------------------------------------------------------------------
# review of #169: duplicates, mixed sets, crashed G0 traces, benchmark copies
# ---------------------------------------------------------------------------


def test_a_copy_of_a_trace_with_the_same_bytes_counts_once_and_is_listed(
    tmp_path: Path,
) -> None:
    write_trace(tmp_path / "job", "j1-a", [0.01] * 20)
    write_trace(tmp_path / "copy", "j1-a", [0.01] * 20)

    report = calibrate_tau([tmp_path / "job", tmp_path / "copy"])

    assert len(report.episodes) == 1
    assert report.value("tau_track_upper").cycles == 20
    (copy,) = report.left_out
    assert copy.trace_id == "j1-a" and "giống hệt" in copy.reason


def test_a_set_mixing_runs_is_refused_unless_declared(tmp_path: Path) -> None:
    write_trace(tmp_path, "j1-a", [0.01] * 20, run_plan="rp_1")
    write_trace(tmp_path, "j2-a", [0.02] * 20, run_plan="rp_2")

    with pytest.raises(TauError, match="--mixed-runs"):
        calibrate_tau([tmp_path])
    report = calibrate_tau([tmp_path], mixed_runs=True)

    assert report.mixed_runs is True
    assert [episode.run_plan_ids for episode in report.episodes] == [["rp_1"], ["rp_2"]]


def test_a_set_mixing_adapters_or_success_sources_is_refused(tmp_path: Path) -> None:
    write_trace(tmp_path / "a", "j1-a", [0.01] * 20, adapter="simple")
    write_trace(tmp_path / "a", "j1-b", [0.01] * 20, adapter="psi0-serve-simple-rtc")
    write_trace(tmp_path / "b", "j1-c", [0.01] * 20)
    write_trace(tmp_path / "b", "demo-1", [0.01] * 20, result=False)

    with pytest.raises(TauError, match="adapter"):
        calibrate_tau([tmp_path / "a"])
    with pytest.raises(TauError, match="--demos"):
        calibrate_tau([tmp_path / "b"], declared_demos=True)


def test_a_rollout_simple_could_not_judge_is_not_a_demo(tmp_path: Path) -> None:
    write_trace(tmp_path, "j1-a", [0.01] * 20, sim=None)

    with pytest.raises(TauError, match="không kết luận"):
        calibrate_tau([tmp_path], declared_demos=True)


def test_a_g0_trace_that_crashed_is_left_out_of_tau_lat(tmp_path: Path) -> None:
    # Review of #169, point 4: one crashed 5 s trace made tau_lat 5 s.
    job = tmp_path / "g0"
    write_rtc(job, {"g0-ok": [1.0, 0.05, 0.06], "g0-crash": [1.0, 5.0]})
    write_trace(job, "g0-ok", [0.01] * 20)
    write_trace(job, "g0-crash", [0.01] * 20, sim=None, infra="simulator_error")

    report = calibrate_tau([], [job])

    tau_lat = report.value("tau_lat_s")
    assert tau_lat.value == pytest.approx(p99([0.05, 0.06]))
    assert tau_lat.samples == 1
    assert [(item.trace_id, item.reason) for item in report.left_out] == [
        ("g0-crash", "log RTC của G0: lỗi hạ tầng `simulator_error`")
    ]
    assert report.rtc_logs[0].unchecked_traces == []


def test_the_same_rtc_log_found_twice_is_read_once(tmp_path: Path) -> None:
    write_rtc(tmp_path / "one", {"g0-t1": [1.0, 0.05, 0.07]})
    write_rtc(tmp_path / "two", {"g0-t1": [1.0, 0.05, 0.07]})
    write_rtc(tmp_path / "other", {"g0-t1": [1.0, 0.05, 0.09]})

    report = calibrate_tau([], [tmp_path / "one", tmp_path / "two"])

    assert len(report.rtc_logs) == 1
    assert report.value("tau_lat_s").cycles == 2
    with pytest.raises(TauError, match="hai bản khác nhau"):
        calibrate_tau([], [tmp_path / "one", tmp_path / "other"])


@pytest.mark.parametrize("source", ["teleop", "g0"])
def test_nothing_under_a_benchmark_copy_is_read(tmp_path: Path, source: str) -> None:
    copy = tmp_path / "copies" / "bench_01"
    (copy / "meta").mkdir(parents=True)
    (copy / "meta" / "benchmark_copy.json").write_text("{}", encoding="utf-8")
    write_trace(tmp_path / "eval", "j1-a", [0.01] * 20)
    write_trace(copy / "traces", "j9-a", [0.01] * 20)
    write_rtc(tmp_path / "g0", {"g0-t1": [1.0, 0.05]})
    write_rtc(copy / "rtc" / "job", {"g0-t9": [1.0, 0.5]})

    with pytest.raises(TauError, match="bản sao benchmark"):
        if source == "teleop":
            calibrate_tau([tmp_path])
        else:
            calibrate_tau([], [tmp_path])


def test_a_set_with_nothing_measured_exits_two_and_stores_nothing(tmp_path: Path) -> None:
    write_trace(tmp_path / "eval", "j1-a", ["NaN"] * 20, ["NaN"] * 20, sync=[None] * 20)

    with pytest.raises(TauError, match="không giá trị nào"):
        calibrate_tau([tmp_path / "eval"])
    result = CliRunner().invoke(
        app,
        [
            "tau",
            "--teleop",
            str(tmp_path / "eval"),
            "--config",
            str(SYSTEM_YAML),
            "--store",
            str(tmp_path / "store"),
        ],
    )

    assert result.exit_code == 2
    assert not (tmp_path / "store").exists()

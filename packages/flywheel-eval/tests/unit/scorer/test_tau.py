"""τ_track calibrated from successful episodes (DA-37 task 3, AC 4).

Every trace is built here as DA-38's hook lays one out (`<trace_id>/steps.jsonl`
beside `rollout_result.json`), so the calibration reads it through DA-13's own
loader, the way it will read a real one.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel.contracts.trace import LOWER_BODY, UPPER_BODY
from flywheel.eval.api import calibrate_tau, store_tau
from flywheel.eval.cli import app
from flywheel.eval.diagnosis.system.reader import ReaderError
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


def step(
    trace_id: str, index: int, upper_error: float, lower_error: Any = 0.0, sync: Any = 0.0
) -> dict[str, Any]:
    """One cycle whose first upper and first lower channel miss by the given amounts,
    with the frame `sync` seconds after the state (None: no new frame)."""
    return {
        "trace_id": trace_id,
        "episode_id": f"episode_{index}",
        "run_plan_id": "rp_1",
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
) -> Path:
    """`<root>/<trace_id>/steps.jsonl`, and `rollout_result.json` unless `result` is False."""
    lower = lower if lower is not None else [0.0] * len(upper)
    sync = sync if sync is not None else [0.0] * len(upper)
    folder = root / trace_id
    folder.mkdir(parents=True)
    rows = [
        step(trace_id, i, u, lo, s)
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
                "name": "simple",
                "version": "0.1.0",
                "image_digest": None,
                "nondeterminism": [],
            },
            "timing": "sync",
        }
        (folder / "rollout_result.json").write_text(json.dumps(payload), encoding="utf-8")
    return folder


def test_tau_track_is_the_99th_percentile_of_every_cycle_pooled(tmp_path: Path) -> None:
    first = [0.001 * i for i in range(60)]
    second = [0.002 * i for i in range(90)]
    write_trace(tmp_path, "j1-a", first, [0.01] * 60)
    write_trace(tmp_path, "j1-b", second, [0.03] * 90)

    report = calibrate_tau([tmp_path])

    upper, lower = report.value("tau_track_upper"), report.value("tau_track_lower")
    assert upper.value == pytest.approx(float(np.percentile(first + second, 99.0)))
    assert (upper.samples, upper.episodes, upper.skipped_cycles) == (150, 2, 0)
    assert upper.percentile == CALIBRATION_PERCENTILE == 99.0
    assert upper.few_samples is False
    assert lower.value == pytest.approx(0.03)
    assert [episode.trace_id for episode in report.episodes] == ["j1-a", "j1-b"]
    assert {episode.success for episode in report.episodes} == {"sim_success"}


def test_a_value_under_a_hundred_samples_is_flagged(tmp_path: Path) -> None:
    # Under 100 samples the 99th percentile is nearly the largest one (AC 4).
    write_trace(tmp_path, "j1-a", [0.01] * (FEW_SAMPLES - 1))

    report = calibrate_tau([tmp_path])

    assert report.value("tau_track_upper").samples == FEW_SAMPLES - 1
    assert report.value("tau_track_upper").few_samples is True


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
    assert (tau_lower.samples, tau_lower.skipped_cycles) == (10, 10)


def test_a_half_never_measured_has_no_value_rather_than_zero(tmp_path: Path) -> None:
    write_trace(tmp_path, "j1-a", [0.01] * 20, ["NaN"] * 20)

    tau_lower = calibrate_tau([tmp_path]).value("tau_track_lower")

    assert tau_lower.value is None
    assert (tau_lower.samples, tau_lower.episodes) == (0, 0)


def test_a_trace_found_through_two_paths_is_read_once(tmp_path: Path) -> None:
    folder = write_trace(tmp_path, "j1-a", [0.01] * 20)

    report = calibrate_tau([tmp_path, folder])

    assert len(report.episodes) == 1
    assert report.value("tau_track_upper").samples == 20


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
    assert lines[0]["values"]["tau_track_upper"]["samples"] == 20


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
    assert "tau_track_upper: 0.01 rad; phân vị 99 trên 20 mẫu từ 1 episode" in result.output
    assert "đang dùng 0.1" in result.output
    assert "ít mẫu (dưới 100)" in result.output
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
    assert (tau_sync.samples, tau_sync.skipped_cycles, tau_sync.unit) == (15, 5, "s")


def test_tau_lat_leaves_chunk_0_out_and_counts_the_traces(tmp_path: Path) -> None:
    # Chunk 0 is the cold start; R1 leaves it out, so the threshold does too.
    log = write_rtc(tmp_path / "g0", {"g0-t1": [2.0, 0.05, 0.06], "g0-t2": [2.0, 0.07]})

    report = calibrate_tau([], [log])

    (tau_lat,) = report.values
    assert tau_lat.key == "tau_lat_s"
    assert tau_lat.value == pytest.approx(float(np.percentile([0.05, 0.06, 0.07], 99.0)))
    assert (tau_lat.samples, tau_lat.episodes, tau_lat.few_samples) == (3, 2, True)
    assert report.episodes == []
    (used,) = report.rtc_logs
    assert (used.job_ids, used.chunks) == (["g0"], 5)
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
    assert "tau_lat_s: 0.08 s; phân vị 99 trên 1 mẫu từ 1 episode" in both.output
    assert "log RTC của G0: 1 file, 2 chunk" in both.output
    assert g0_only.exit_code == 0, g0_only.output
    assert "tau_track_upper" not in g0_only.output

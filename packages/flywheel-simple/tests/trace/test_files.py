"""Files the trace hook writes per episode, read back through the contracts (DA-38 AC 1, 3, 4).

`TraceStep` and `CameraParams` come with Contract change #31 (PR #48); until it
merges those two checks are skipped and the files are checked by field name only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel_simple.trace.camera import CameraValues, reference_sha256
from flywheel_simple.trace.files import EpisodeDirSink
from flywheel_simple.trace.hook import CycleRecord, EpisodeTrace

# SIMPLE's venv, where the `sim` tests run, has no flywheel package
RolloutResult = pytest.importorskip("flywheel.contracts.v0").RolloutResult

PINNED = "fc7f9c90ebbf8c4662fd70e58de5aed668c0fbc5ccfbbd951dce705729cdeea2"


def camera(uid: str = "head_stereo_left", fx: float = 224.0) -> CameraValues:
    return CameraValues(uid, "eye_in_head", 640, 360, fx, fx, 320.0, 180.0,
                        (0.05, 0.02, 0.43, 0.66, 0.26, -0.26, -0.66))  # fmt: skip


def episode(success: bool | None = True) -> EpisodeTrace:
    def cycle(step: int, t_image: float | None, meas: float) -> CycleRecord:
        return CycleRecord(step, 0.02 * step, t_image, [0.1] * 28, [meas] * 28,
                           [0.0] * 7, [0.0, 0.0, 0.0, 0.74, 0.0, 0.0, 0.0])  # fmt: skip

    return EpisodeTrace(
        trace_id="job-1-0123456789ab",
        episode_id="episode_3" if success is not None else "unfinished-0",
        run_plan_id="g0-DA-38-test",
        cameras=[camera(), camera("head_stereo_right")],
        cycles=[cycle(0, 0.0, 0.1), cycle(1, None, float("nan"))],
        sim_success=success,
        wall_seconds=1.5,
    )


def write(tmp_path: Path, ep: EpisodeTrace, reference: str | None = PINNED) -> Path:
    EpisodeDirSink(
        tmp_path, job_id="job-1", camera_reference_sha256=reference, adapter_version="b75c678"
    ).write(ep)
    return tmp_path / ep.episode_id


def test_one_directory_per_episode_with_trace_cameras_and_result(tmp_path: Path) -> None:
    d = write(tmp_path, episode())
    assert sorted(p.name for p in d.iterdir()) == [
        "camera_params.json",
        "episode.json",
        "trace.jsonl",
    ]
    rows = [json.loads(line) for line in (d / "trace.jsonl").read_text().splitlines()]
    assert [r["step"] for r in rows] == [0, 1]
    assert {r["trace_id"] for r in rows} == {"job-1-0123456789ab"}
    assert rows[1]["t_image"] is None  # no new frame on that cycle
    assert rows[1]["meas_upper"][0] == "NaN"  # the contract's name, not a bare NaN


def test_trace_lines_are_trace_steps(tmp_path: Path) -> None:
    trace = pytest.importorskip("flywheel.contracts.trace", reason="Contract change #31, PR #48")
    d = write(tmp_path, episode())
    for line in (d / "trace.jsonl").read_text().splitlines():
        trace.TraceStep.model_validate_json(line)


def test_camera_params_carry_the_pinned_reference_not_their_own_hash(tmp_path: Path) -> None:
    ep = episode()
    cams = json.loads((write(tmp_path, ep) / "camera_params.json").read_text())
    assert [c["uid"] for c in cams] == ["head_stereo_left", "head_stereo_right"]
    assert {c["reference_sha256"] for c in cams} == {PINNED}
    assert PINNED != reference_sha256(ep.cameras)  # Q3: not a hash of the episode's cameras


def test_camera_params_are_camera_params(tmp_path: Path) -> None:
    trace = pytest.importorskip("flywheel.contracts.trace", reason="Contract change #31, PR #48")
    for entry in json.loads((write(tmp_path, episode()) / "camera_params.json").read_text()):
        trace.CameraParams.model_validate(entry)


def test_episode_json_is_the_rollout_result_da13_reads_infra_status_from(tmp_path: Path) -> None:
    d = write(tmp_path, episode())
    result = RolloutResult.model_validate_json((d / "episode.json").read_text())
    assert (result.sim_success, result.infra_status) == (True, "ok")
    assert result.trace_ref is not None
    assert result.trace_ref.trace_id == "job-1-0123456789ab"
    assert result.trace_ref.uri == (d / "trace.jsonl").as_posix()
    assert result.camera_params_hash == PINNED


def test_an_episode_simple_never_reported_is_a_simulator_error(tmp_path: Path) -> None:
    d = write(tmp_path, episode(success=None))
    result = RolloutResult.model_validate_json((d / "episode.json").read_text())
    assert (result.sim_success, result.infra_status) == (None, "simulator_error")


def test_without_a_pinned_reference_no_camera_params_are_written(tmp_path: Path) -> None:
    d = write(tmp_path, episode(), reference=None)
    assert not (d / "camera_params.json").exists()  # R5 then says CHƯA RÕ
    result = RolloutResult.model_validate_json((d / "episode.json").read_text())
    assert result.camera_params_hash is None


def test_a_reference_that_is_not_a_sha256_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="sha256"):
        write(tmp_path, episode(), reference="fake-camera-v0")


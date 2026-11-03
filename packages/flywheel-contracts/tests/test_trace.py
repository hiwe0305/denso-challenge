"""Unit and contract tests for TraceStep and CameraParams (Issue #31)."""

import json
from pathlib import Path

import pytest
from flywheel.contracts.trace import CameraParams, TraceStep
from pydantic import ValidationError

FIXTURES_DIR = (
    Path(__file__).resolve().parents[2]
    / "flywheel-testkit"
    / "src"
    / "flywheel"
    / "testkit"
    / "fixtures"
)
SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"


def test_valid_trace_step_fixture() -> None:
    path = FIXTURES_DIR / "artifacts" / "TraceStep.json"
    step = TraceStep.model_validate_json(path.read_text(encoding="utf-8"))
    assert step.step == 0
    assert len(step.cmd_upper) == 28
    assert len(step.meas_upper) == 28
    assert len(step.cmd_lower) == 7
    assert len(step.meas_lower) == 7
    assert TraceStep.model_validate_json(step.model_dump_json()) == step


def test_valid_camera_params_fixture() -> None:
    path = FIXTURES_DIR / "artifacts" / "CameraParams.json"
    cam = CameraParams.model_validate_json(path.read_text(encoding="utf-8"))
    assert cam.width == 640
    assert cam.height == 480
    assert len(cam.pose) == 7
    assert CameraParams.model_validate_json(cam.model_dump_json()) == cam


def test_trace_step_dimension_mismatch() -> None:
    with pytest.raises(ValidationError) as exc1:
        TraceStep(
            trace_id="tr1",
            episode_id="ep1",
            run_plan_id="rp1",
            step=0,
            t_state=0.0,
            cmd_upper=[0.0] * 28,
            meas_upper=[0.0] * 27,  # mismatch
            cmd_lower=[0.0] * 7,
            meas_lower=[0.0] * 7,
        )
    assert "meas_upper length" in str(exc1.value)

    with pytest.raises(ValidationError) as exc2:
        TraceStep(
            trace_id="tr1",
            episode_id="ep1",
            run_plan_id="rp1",
            step=0,
            t_state=0.0,
            cmd_upper=[0.0] * 28,
            meas_upper=[0.0] * 28,
            cmd_lower=[0.0] * 7,
            meas_lower=[0.0] * 6,  # mismatch
        )
    assert "meas_lower length" in str(exc2.value)


def test_camera_params_pose_validation() -> None:
    # Invalid pose length (not 7)
    with pytest.raises(ValidationError) as exc1:
        CameraParams(
            episode_id="ep1",
            uid="cam1",
            mount="head",
            width=640,
            height=480,
            fx=500.0,
            fy=500.0,
            cx=320.0,
            cy=240.0,
            pose=[0.0] * 6,
            reference_sha256="0" * 64,
        )
    assert "pose must contain 7 elements" in str(exc1.value)

    # Unnormalized quaternion
    with pytest.raises(ValidationError) as exc2:
        CameraParams(
            episode_id="ep1",
            uid="cam1",
            mount="head",
            width=640,
            height=480,
            fx=500.0,
            fy=500.0,
            cx=320.0,
            cy=240.0,
            pose=[0.0, 0.0, 0.0, 2.0, 0.0, 0.0, 0.0],
            reference_sha256="0" * 64,
        )
    assert "quaternion [qw, qx, qy, qz] must be normalized" in str(exc2.value)


@pytest.mark.parametrize(
    "trace_name",
    ["clean.jsonl", "r4_sync_delay.jsonl", "r5_calibration_offset.jsonl", "missing_signals.jsonl"],
)
def test_trace_dataset_fixtures_loading(trace_name: str) -> None:
    path = FIXTURES_DIR / "trace" / trace_name
    assert path.is_file(), f"Missing trace fixture: {path}"
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 100, f"Expected 100 cycles, got {len(lines)}"
    for idx, line in enumerate(lines):
        step = TraceStep.model_validate_json(line)
        assert step.step == idx


def test_camera_dataset_fixtures_loading() -> None:
    for name in ["camera_clean.json", "camera_offset.json"]:
        path = FIXTURES_DIR / "trace" / name
        assert path.is_file(), f"Missing camera fixture: {path}"
        cam = CameraParams.model_validate_json(path.read_text(encoding="utf-8"))
        assert cam.width > 0
        assert cam.height > 0
        assert len(cam.pose) == 7


def test_schemas_match_committed_files() -> None:
    for model in (TraceStep, CameraParams):
        schema_path = SCHEMAS_DIR / f"{model.__name__}.json"
        assert schema_path.is_file(), f"Missing schema file: {schema_path}"
        committed = json.loads(schema_path.read_text(encoding="utf-8"))
        assert committed == model.model_json_schema()

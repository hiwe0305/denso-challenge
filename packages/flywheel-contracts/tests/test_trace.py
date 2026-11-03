"""Unit and contract tests for TraceStep and CameraParams (Issue #31)."""

import json
from pathlib import Path

import pytest
from flywheel.contracts.trace import LOWER_BODY, UPPER_BODY, CameraParams, TraceStep
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


def _step(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "trace_id": "tr1",
        "episode_id": "ep1",
        "run_plan_id": "rp1",
        "step": 0,
        "t_state": 0.0,
        "cmd_upper": [0.0] * 28,
        "meas_upper": [0.0] * 28,
        "cmd_lower": [0.0] * 7,
        "meas_lower": [0.0] * 7,
    }
    return row | overrides


def test_layout_names_have_28_upper_and_7_lower_dims() -> None:
    assert len(UPPER_BODY) == 28
    assert len(set(UPPER_BODY)) == 28
    assert len(LOWER_BODY) == 7
    # D-26: action[3:5] holds the left middle finger, action[5:7] the left index
    assert UPPER_BODY[3:7] == (
        "left_hand_middle_0_joint",
        "left_hand_middle_1_joint",
        "left_hand_index_0_joint",
        "left_hand_index_1_joint",
    )
    assert LOWER_BODY == (
        "waist_roll",
        "waist_pitch",
        "waist_yaw",
        "base_height",
        "vx",
        "vy",
        "yaw",
    )


@pytest.mark.parametrize("field", ["cmd_upper", "meas_upper"])
@pytest.mark.parametrize("size", [0, 7, 27, 29, 36])
def test_upper_body_must_have_28_dims(field: str, size: int) -> None:
    with pytest.raises(ValidationError) as exc:
        TraceStep.model_validate(_step(**{field: [0.0] * size}))
    assert field in str(exc.value)


@pytest.mark.parametrize("field", ["cmd_lower", "meas_lower"])
@pytest.mark.parametrize("size", [0, 6, 8])
def test_lower_body_must_have_7_dims(field: str, size: int) -> None:
    # 8 is the layout with turning_flag (action[34]) kept, which issue #31 drops
    with pytest.raises(ValidationError) as exc:
        TraceStep.model_validate(_step(**{field: [0.0] * size}))
    assert field in str(exc.value)


def test_schema_states_the_dimension_counts() -> None:
    props = TraceStep.model_json_schema()["properties"]
    for field, size in (("cmd_upper", 28), ("meas_upper", 28), ("cmd_lower", 7), ("meas_lower", 7)):
        assert (props[field]["minItems"], props[field]["maxItems"]) == (size, size)


@pytest.mark.parametrize("run_plan_id", ["rp_001", "g0-DA-38-20261103", "g0-S1-03-20261027"])
def test_run_plan_id_accepts_runplans_and_the_g0_convention(run_plan_id: str) -> None:
    assert TraceStep.model_validate(_step(run_plan_id=run_plan_id)).run_plan_id == run_plan_id


@pytest.mark.parametrize(
    "run_plan_id", ["g0-DA38-20261103", "g0-DA-38-2026-11-03", "g0-da-38-20261103", "g0-DA-38"]
)
def test_run_plan_id_refuses_a_malformed_g0_id(run_plan_id: str) -> None:
    with pytest.raises(ValidationError) as exc:
        TraceStep.model_validate(_step(run_plan_id=run_plan_id))
    assert "g0-<story>-<yyyymmdd>" in str(exc.value)


def test_missing_signals_counts_dropped_frames_per_cycle() -> None:
    path = FIXTURES_DIR / "trace" / "missing_signals.jsonl"
    steps = [TraceStep.model_validate_json(line) for line in path.read_text().splitlines()]
    # a frame is due on even cycles (25 Hz camera, 50 Hz loop); from cycle 30 each is lost
    assert {s.dropped_frames for s in steps} == {0, 1}
    for s in steps:
        lost = s.step % 2 == 0 and s.step >= 30
        assert s.dropped_frames == int(lost)
        if lost:
            assert s.t_image is None
    assert sum(s.dropped_frames for s in steps) == 35


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

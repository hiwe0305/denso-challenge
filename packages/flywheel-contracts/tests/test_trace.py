"""Unit and contract tests for TraceStep and CameraParams (Issue #31)."""

import hashlib
import json
import math
from pathlib import Path

import pytest
from flywheel.contracts.trace import (
    CAMERA_NAME,
    LOWER_BODY,
    STEPS_NAME,
    UPPER_BODY,
    CameraParams,
    TraceStep,
)
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
    assert cam.trace_id == "tr_clean"
    assert (cam.width, cam.height) == (640, 360)
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
    steps = _steps("tr_missing")
    # a frame is due on even cycles (25 Hz camera, 50 Hz loop); from cycle 30 each is lost
    assert {s.dropped_frames for s in steps} == {0, 1}
    for s in steps:
        lost = s.step % 2 == 0 and s.step >= 30
        assert s.dropped_frames == int(lost)
        if lost:
            assert s.t_image is None
    assert sum(s.dropped_frames for s in steps) == 35


def test_camera_params_needs_its_trace_id() -> None:
    row = json.loads((FIXTURES_DIR / "artifacts" / "CameraParams.json").read_text("utf-8"))
    del row["trace_id"]
    with pytest.raises(ValidationError) as exc:
        CameraParams.model_validate(row)
    assert "trace_id" in str(exc.value)


def test_camera_params_pose_validation() -> None:
    # Invalid pose length (not 7)
    with pytest.raises(ValidationError) as exc1:
        CameraParams(
            trace_id="tr1",
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
            trace_id="tr1",
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


TRACE_DIR = FIXTURES_DIR / "trace"
TRACES = ["tr_clean", "tr_sync_delay", "tr_calib_offset", "tr_missing"]
# Two-table G0 camera reference (DA-38 docs/g0/camera-reference-two-table.yaml at f94d5bc)
REFERENCE_SHA256 = "fc7f9c90ebbf8c4662fd70e58de5aed668c0fbc5ccfbbd951dce705729cdeea2"


def _steps(trace_id: str) -> list[TraceStep]:
    text = (TRACE_DIR / trace_id / STEPS_NAME).read_text(encoding="utf-8")
    return [TraceStep.model_validate_json(line) for line in text.splitlines()]


def _cameras(trace_id: str) -> list[CameraParams]:
    text = (TRACE_DIR / trace_id / CAMERA_NAME).read_text(encoding="utf-8")
    return [CameraParams.model_validate_json(line) for line in text.splitlines()]


def _pinned_hash(cameras: list[CameraParams]) -> str:
    # The pinning rule of DA-38 (flywheel_simple.trace.camera.reference_sha256): sorted by
    # uid, floats rounded to 1e-9, compact JSON with sorted keys.
    records = [
        {
            "uid": c.uid,
            "mount": c.mount,
            "width": c.width,
            "height": c.height,
            **{k: round(getattr(c, k), 9) for k in ("fx", "fy", "cx", "cy")},
            "pose": [round(v, 9) + 0.0 for v in c.pose],
        }
        for c in sorted(cameras, key=lambda c: c.uid)
    ]
    payload = json.dumps(records, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_every_trace_fixture_is_a_g1_directory() -> None:
    assert sorted(p.name for p in TRACE_DIR.iterdir() if p.is_dir()) == sorted(TRACES)
    for trace_id in TRACES:
        assert sorted(p.name for p in (TRACE_DIR / trace_id).iterdir()) == [
            CAMERA_NAME,
            STEPS_NAME,
        ]


@pytest.mark.parametrize("trace_id", TRACES)
def test_trace_steps_have_100_cycles_of_their_own_trace(trace_id: str) -> None:
    steps = _steps(trace_id)
    assert [s.step for s in steps] == list(range(100))
    assert {s.trace_id for s in steps} == {trace_id}
    assert len({s.episode_id for s in steps}) == 1


@pytest.mark.parametrize("trace_id", TRACES)
def test_trace_cameras_are_the_two_head_cameras_of_their_trace(trace_id: str) -> None:
    cameras = _cameras(trace_id)
    assert [c.uid for c in cameras] == ["head_stereo_left", "head_stereo_right"]
    assert {c.trace_id for c in cameras} == {trace_id}
    assert {c.episode_id for c in cameras} == {_steps(trace_id)[0].episode_id}
    assert {c.reference_sha256 for c in cameras} == {REFERENCE_SHA256}


@pytest.mark.parametrize("trace_id", ["tr_clean", "tr_sync_delay", "tr_missing"])
def test_clean_cameras_are_the_pinned_reference(trace_id: str) -> None:
    assert _pinned_hash(_cameras(trace_id)) == REFERENCE_SHA256


def test_calibration_offset_moves_only_the_left_camera() -> None:
    clean = {c.uid: c for c in _cameras("tr_clean")}
    offset = {c.uid: c for c in _cameras("tr_calib_offset")}
    assert _pinned_hash(list(offset.values())) != REFERENCE_SHA256
    assert offset["head_stereo_right"].model_dump(exclude={"trace_id", "episode_id"}) == clean[
        "head_stereo_right"
    ].model_dump(exclude={"trace_id", "episode_id"})
    left, ref = offset["head_stereo_left"], clean["head_stereo_left"]
    assert left.fx == pytest.approx(ref.fx * 1.1)
    # 15 degrees between the two orientations: |<q_ref, q>| = cos(7.5 deg)
    dot = abs(sum(a * b for a, b in zip(left.pose[3:], ref.pose[3:], strict=True)))
    assert dot == pytest.approx(math.cos(math.radians(7.5)))


def test_schemas_match_committed_files() -> None:
    for model in (TraceStep, CameraParams):
        schema_path = SCHEMAS_DIR / f"{model.__name__}.json"
        assert schema_path.is_file(), f"Missing schema file: {schema_path}"
        committed = json.loads(schema_path.read_text(encoding="utf-8"))
        assert committed == model.model_json_schema()

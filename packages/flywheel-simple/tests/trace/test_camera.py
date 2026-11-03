"""Camera intrinsics and pose as MuJoCo renders them (DA-38 AC 3). Pure logic, CPU."""

from __future__ import annotations

import math

import numpy as np
import pytest
from flywheel_simple.trace.camera import CameraValues, mujoco_intrinsics, reference_sha256


def test_fovy_camera_has_square_pixels_and_a_centred_principal_point() -> None:
    # SIMPLE sets fovy = 2 atan(H / (2 fy)); the head camera is 640x360 with fov 110 deg.
    fy_cfg = 640 / (2 * math.tan(math.radians(110) / 2))
    fovy = math.degrees(2 * math.atan(360 / (2 * fy_cfg)))
    fx, fy, cx, cy = mujoco_intrinsics(640, 360, fovy, sensorsize=(0.0, 0.0), intrinsic=None)
    assert fy == pytest.approx(fy_cfg)
    assert fx == pytest.approx(fy)
    assert (cx, cy) == pytest.approx((320.0, 180.0))


def test_sensor_camera_inverts_simples_focal_and_principal_pixels() -> None:
    # SIMPLE passes sensor_size=[W, H], focal_pixel=[fx, fy], principal_pixel=[cx - W/2, cy - H/2].
    fx, fy, cx, cy = mujoco_intrinsics(
        640, 480, 0.0, sensorsize=(640.0, 480.0), intrinsic=(600.0, 610.0, 5.0, -4.0)
    )
    assert (fx, fy, cx, cy) == pytest.approx((600.0, 610.0, 325.0, 236.0))


def test_sensor_camera_scales_when_render_size_differs_from_sensor() -> None:
    fx, fy, cx, cy = mujoco_intrinsics(
        320, 240, 0.0, sensorsize=(640.0, 480.0), intrinsic=(600.0, 600.0, 0.0, 0.0)
    )
    assert (fx, fy, cx, cy) == pytest.approx((300.0, 300.0, 160.0, 120.0))


def test_fovy_camera_needs_a_positive_fovy() -> None:
    with pytest.raises(ValueError, match="fovy"):
        mujoco_intrinsics(640, 360, 0.0, sensorsize=(0.0, 0.0), intrinsic=None)


def values(**overrides: object) -> CameraValues:
    base: dict[str, object] = dict(
        uid="head_stereo_left",
        mount="eye_in_head",
        width=640,
        height=360,
        fx=224.0,
        fy=224.0,
        cx=320.0,
        cy=180.0,
        pose=(0.0, 0.025, 0.0, 0.5, -0.5, 0.5, -0.5),
    )
    base.update(overrides)
    return CameraValues(**base)  # type: ignore[arg-type]


def test_reference_hash_is_stable_and_hex() -> None:
    digest = reference_sha256([values()])
    assert digest == reference_sha256([values()])
    assert len(digest) == 64 and int(digest, 16) >= 0


def test_reference_hash_ignores_camera_order_and_float_noise() -> None:
    a = values()
    b = values(uid="head_stereo_right", pose=(0.0, -0.025, 0.0, 0.5, -0.5, 0.5, -0.5))
    noisy = values(fx=224.0 + 1e-12)
    assert reference_sha256([a, b]) == reference_sha256([b, a])
    assert reference_sha256([noisy]) == reference_sha256([a])


def test_reference_hash_changes_when_a_calibration_value_changes() -> None:
    assert reference_sha256([values()]) != reference_sha256([values(fx=230.0)])
    pose = np.array(values().pose)
    pose[1] += 0.01
    assert reference_sha256([values()]) != reference_sha256([values(pose=tuple(pose))])

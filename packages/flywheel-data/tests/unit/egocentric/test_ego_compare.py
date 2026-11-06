"""DA-04 task 5: E-A against E-B on the same frames, with known deviations (AC 5)."""

from __future__ import annotations

import numpy as np
import pytest
from ego_data import FRAMES, K, synthetic_pose
from flywheel.data.ingest.egocentric.compare import (
    compare,
    eb_camera_points,
    project,
    rotation_angle_deg,
)
from flywheel.data.ingest.egocentric.estimate import Estimate
from flywheel.data.ingest.egocentric.estimate_job import TIPS, WRIST

SIZE = (1920, 1080)


def rotation_y(degrees: float) -> np.ndarray:
    a = np.radians(degrees)
    return np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])


def turning_pose(step_deg: float):  # type: ignore[no-untyped-def]
    pose = synthetic_pose()
    camera = pose.camera.astype(np.float64).copy()
    for t in range(FRAMES):
        camera[t, :3, :3] = rotation_y(step_deg * t)
    from dataclasses import replace

    return replace(pose, camera=camera.astype(np.float32))


def estimate_from(pose, pixel_offset: tuple[float, float], depth_offset: float,  # type: ignore[no-untyped-def]
                  camera: np.ndarray, moving: float = 0.0) -> Estimate:
    pixels, points, score = {}, {}, {}
    k = K.astype(np.float64)
    for side in ("left", "right"):
        joints = eb_camera_points(pose, side)
        full_points = np.zeros((FRAMES, 21, 3))
        full_points[:, [WRIST, *TIPS]] = joints + [0, 0, depth_offset]
        full_pixels = np.zeros((FRAMES, 21, 2))
        full_pixels[:, [WRIST, *TIPS]] = project(joints, k) + pixel_offset
        pixels[side], points[side], score[side] = full_pixels, full_points, np.ones(FRAMES)
    return Estimate(camera, pixels, points, score, np.full(FRAMES, moving), {})


def test_known_pixel_and_depth_offsets_come_back() -> None:
    pose = synthetic_pose()
    ea = estimate_from(pose, (3.0, 4.0), 0.02, pose.camera.astype(np.float64))
    deviation = compare(pose, ea, K.astype(np.float64), SIZE)
    right = deviation.hands["right"]
    assert right is not None and right.frames == FRAMES and right.detection == 1.0
    assert right.pixel_median == pytest.approx(5.0) and right.wrist_pixel_median == pytest.approx(5)
    assert right.depth_median_m == pytest.approx(0.02) and right.point_median_m == pytest.approx(
        0.02)
    assert deviation.rotation_median_deg == pytest.approx(0.0, abs=1e-6)


def test_a_known_rotation_error_per_step_comes_back() -> None:
    eb = turning_pose(1.0)
    ea_camera = turning_pose(1.5).camera.astype(np.float64)
    deviation = compare(eb, estimate_from(eb, (0, 0), 0, ea_camera), K.astype(np.float64), SIZE)
    assert deviation.rotation_median_deg == pytest.approx(0.5, abs=1e-3)
    assert deviation.eb_rotation_median_deg == pytest.approx(1.0, abs=1e-3)


def test_translation_direction_is_compared_on_moving_steps_only() -> None:
    eb = synthetic_pose()
    camera = eb.camera.astype(np.float64).copy()
    camera[:, 2, 3] = np.arange(FRAMES) * 0.01  # E-B walks forward
    from dataclasses import replace

    eb = replace(eb, camera=camera.astype(np.float32))
    ea_camera = camera.copy()
    ea_camera[:, 0, 3] = np.arange(FRAMES) * 0.01  # E-A thinks it also slides sideways
    deviation = compare(eb, estimate_from(eb, (0, 0), 0, ea_camera, moving=1.0),
                        K.astype(np.float64), SIZE)
    assert deviation.translation_direction_median_deg == pytest.approx(45.0, abs=0.01)
    still = compare(eb, estimate_from(eb, (0, 0), 0, ea_camera, moving=0.0),
                    K.astype(np.float64), SIZE)
    assert still.translation_steps == 0 and still.translation_direction_median_deg is None


def test_frames_where_ea_lost_the_hand_lower_detection() -> None:
    pose = synthetic_pose()
    ea = estimate_from(pose, (0, 0), 0, pose.camera.astype(np.float64))
    ea.score["left"][: FRAMES // 2] = 0
    deviation = compare(pose, ea, K.astype(np.float64), SIZE)
    assert deviation.hands["left"] is not None
    assert deviation.hands["left"].detection == pytest.approx(0.5)
    assert deviation.hands["left"].frames == FRAMES // 2


def test_different_lengths_are_refused() -> None:
    pose = synthetic_pose()
    ea = estimate_from(pose, (0, 0), 0, pose.camera.astype(np.float64))
    with pytest.raises(ValueError, match="frames"):
        compare(synthetic_pose(FRAMES - 1), ea, K.astype(np.float64), SIZE)


def test_rotation_angle() -> None:
    assert rotation_angle_deg(rotation_y(30.0)) == pytest.approx(30.0)

"""DA-04 task 5: E-A math, with answers known in advance (AC 4; D5).

MediaPipe is never imported here: the detector and the tracker are fakes of the
lane's Protocols; the VO tracker runs with OpenCV on a synthetic rotation.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from flywheel.data.ingest.egocentric.estimate import read_estimate, to_pose
from flywheel.data.ingest.egocentric.estimate_job import (
    TIPS,
    WRIST,
    HandDetection,
    SideTracker,
    VOTracker,
    chain,
    estimate_video,
    hand_mask,
    lift_hand,
    rotation_from_homography,
    wrist_frame,
)

K = np.array([[500.0, 0, 320], [0, 500.0, 240], [0, 0, 1]])


def hand_world() -> np.ndarray:
    rng = np.random.default_rng(1)
    points = rng.normal(0, 0.03, (21, 3))
    points[5], points[17], points[9], points[0] = (0.03, 0, 0), (-0.03, 0, 0), (0, -0.06, 0), (
        0, 0, 0)
    return points


def projected(points: np.ndarray, k: np.ndarray) -> np.ndarray:
    return np.stack([k[0, 0] * points[:, 0] / points[:, 2] + k[0, 2],
                     k[1, 1] * points[:, 1] / points[:, 2] + k[1, 2]], axis=1)


def rotation(axis: np.ndarray, degrees: float) -> np.ndarray:
    import cv2

    vector = np.asarray(axis, float) / np.linalg.norm(axis) * np.radians(degrees)
    return np.asarray(cv2.Rodrigues(vector)[0])


def test_lift_recovers_the_hand_translation() -> None:
    world = hand_world()
    t = np.array([0.08, -0.05, 0.45])
    lifted = lift_hand(projected(world + t, K), world, K)
    np.testing.assert_allclose(lifted, world + t, atol=1e-9)


def test_wrist_frame_is_a_rotation_at_the_wrist() -> None:
    points = hand_world() + [0.1, 0.0, 0.5]
    pose = wrist_frame(points)
    r = pose[:3, :3]
    np.testing.assert_allclose(r.T @ r, np.eye(3), atol=1e-12)
    assert np.linalg.det(r) == pytest.approx(1.0)
    np.testing.assert_allclose(pose[:3, 3], points[0])


def test_a_pure_rotation_comes_back_from_its_homography() -> None:
    r = rotation([0.2, 1.0, 0.1], 3.0)
    h = K @ r @ np.linalg.inv(K)
    np.testing.assert_allclose(rotation_from_homography(h * 2.5, K), r, atol=1e-9)


def test_chain_inverts_each_step() -> None:
    r, t = rotation([0, 1, 0], 5.0), np.array([0.0, 0.0, 0.01])
    camera = chain(np.eye(4), r, t)
    point_in_first = np.array([0.1, 0.2, 1.0, 1.0])
    np.testing.assert_allclose(np.linalg.inv(camera) @ point_in_first,
                               np.append(r @ point_in_first[:3] + t, 1.0), atol=1e-12)


def test_vo_finds_a_known_camera_rotation() -> None:
    import cv2

    rng = np.random.default_rng(3)
    texture = cv2.GaussianBlur(rng.integers(0, 255, (480, 640), dtype=np.uint8), (3, 3), 0)
    r = rotation([0.0, 1.0, 0.0], 2.0)
    warped = cv2.warpPerspective(texture, K @ r @ np.linalg.inv(K), (640, 480))
    tracker = VOTracker(K, features=1500, min_flow=1.0, step_m=0.005)
    tracker.step(texture, None)
    found, t, moving = tracker.step(warped, None)
    angle = np.degrees(np.arccos(np.clip((np.trace(found.T @ r) - 1) / 2, -1, 1)))
    assert not moving and np.allclose(t, 0) and angle < 0.3


def detection(side: str, x: float, score: float = 0.9) -> HandDetection:
    pixels = np.tile([x, 200.0], (21, 1))
    return HandDetection(side=side, pixels=pixels, world=hand_world(), score=score)


def test_sides_come_from_position_not_from_the_label() -> None:
    sides = SideTracker(width=640)
    both = sides.assign([detection("left", 500), detection("left", 100)])
    assert both["left"].pixels[WRIST, 0] == 100 and both["right"].pixels[WRIST, 0] == 500
    one = sides.assign([detection("left", 480)])  # near where the right hand was
    assert list(one) == ["right"]
    fresh = SideTracker(width=640).assign([detection("right", 100)])
    assert list(fresh) == ["left"]
    assert SideTracker(width=640).assign([]) == {}


def test_the_hand_mask_hides_the_hand_box() -> None:
    mask = hand_mask((480, 640), [detection("left", 100)])
    assert mask[200, 100] == 0 and mask[400, 600] == 255


class FakeHands:
    """Two hands at known camera-frame positions, labels deliberately wrong."""

    def __init__(self, k: np.ndarray, offsets: dict[str, np.ndarray]) -> None:
        self.k, self.offsets = k, offsets

    def detect(self, rgb: np.ndarray, timestamp_ms: int) -> list[HandDetection]:
        found = []
        for side, offset in self.offsets.items():
            points = hand_world() + offset
            found.append(HandDetection("right", projected(points, self.k), hand_world(), 0.8))
        return found


class FakeTracker:
    def step(self, gray: np.ndarray, mask: np.ndarray | None) -> tuple[np.ndarray, np.ndarray,
                                                                         bool]:
        return rotation([0, 1, 0], 1.0), np.zeros(3), False


def frames(n: int) -> Iterator[np.ndarray]:
    for _ in range(n):
        yield np.zeros((480, 640, 3), dtype=np.uint8)


def test_estimate_video_and_to_pose_with_fakes(tmp_path: Path) -> None:
    offsets = {"left": np.array([-0.15, 0.05, 0.5]), "right": np.array([0.15, 0.05, 0.5])}
    scale = 0.5
    result = estimate_video(frames(4), FakeHands(K * [[scale], [scale], [1]], offsets),
                            FakeTracker(), K, fps=30.0, scale=scale)
    assert result["camera"].shape == (4, 4, 4) and result["left_px"].shape == (4, 21, 2)
    np.testing.assert_allclose(result["left_cam"][0], hand_world() + offsets["left"], atol=1e-9)
    np.testing.assert_allclose(result["right_px"][0],
                               projected(hand_world() + offsets["right"], K), atol=1e-9)
    path = tmp_path / "ep.npz"
    np.savez(path, meta=np.array('{"model": "fake"}'), **result)
    estimate = read_estimate(path)
    pose = to_pose(estimate)
    np.testing.assert_allclose(pose.camera[0], np.eye(4), atol=1e-6)
    # the world is the first camera: frame 0 hands are where the camera saw them
    np.testing.assert_allclose(pose.right_tips[0], (hand_world() + offsets["right"])[list(TIPS)],
                               atol=1e-6)
    expected = (estimate.camera[3] @ np.append(hand_world()[0] + offsets["left"], 1))[:3]
    np.testing.assert_allclose(pose.left_wrist[3][:3, 3], expected, atol=1e-6)
    np.testing.assert_allclose(pose.confidence_left, 0.8)


def test_a_missing_hand_is_nan_with_zero_confidence(tmp_path: Path) -> None:
    result = estimate_video(frames(2), FakeHands(K, {"left": np.array([-0.1, 0, 0.5])}),
                            FakeTracker(), K, fps=30.0, scale=1.0)
    path = tmp_path / "ep.npz"
    np.savez(path, meta=np.array("{}"), **result)
    pose = to_pose(read_estimate(path))
    assert np.isnan(pose.right_wrist).all() and (pose.confidence_right == 0).all()

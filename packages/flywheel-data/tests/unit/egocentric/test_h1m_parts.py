"""Human-1M view, unit by unit: joints, cleaning, frames, quality (DA-04 11.3, 11/11/2026)."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest
from flywheel.data.export.human1m.frames import (
    EpisodeFrames,
    JointClean,
    clean_joints,
    from_egodex,
    from_estimates,
    project,
    scaled_intrinsic,
)
from flywheel.data.export.human1m.layout import FRAME_FEATURES, JOINTS, arkit_joints
from flywheel.data.export.human1m.quality import Requirements, bone_cv, measure
from flywheel.data.export.human1m.subtasks import Subtask

K = np.array([[100.0, 0, 64.0], [0, 100.0, 48.0], [0, 0, 1]])


def hand(frames: int, x: float = 0.0, z: float = 0.5) -> np.ndarray:  # type: ignore[type-arg]
    """(T, 21, 3): a rigid hand, joints spread around (x, 0, z) in the camera frame."""
    offsets = np.stack([np.linspace(-0.04, 0.04, 21), np.linspace(0, 0.08, 21),
                        np.zeros(21)], axis=1)
    return np.tile(offsets + [x, 0.0, z], (frames, 1, 1))


def test_arkit_joints_are_21_distinct_in_mediapipe_order() -> None:
    names = arkit_joints("left")
    assert len(names) == len(JOINTS) == 21 and len(set(names)) == 21
    assert names[0] == "leftHand"
    assert names[1:5] == ["leftThumbKnuckle", "leftThumbIntermediateBase",
                          "leftThumbIntermediateTip", "leftThumbTip"]
    assert names[5] == "leftIndexFingerKnuckle" and names[20] == "leftLittleFingerTip"
    assert not any("Metacarpal" in n or "Forearm" in n for n in names)


def test_feature_widths_follow_human1m() -> None:
    widths = {k: v["shape"][0] for k, v in FRAME_FEATURES.items()}
    assert widths["observation.state.hand_left_cam"] == 63
    assert widths["observation.state.hand_right_cam_rotation"] == 84
    assert widths["observation.state.camera_rotation"] == 4
    assert {"left_hand_mask", "right_hand_confidence", "scene_id", "collector_id",
            "subtask_index"} <= set(FRAME_FEATURES)


def test_clean_joints_rebuilds_a_spike_and_keeps_unseen_frames() -> None:
    points = hand(40)
    points[:, :, 0] += np.linspace(0, 0.1, 40)[:, None]  # a steady slide
    truth = points.copy()
    points[20] += 0.3  # one-frame spike
    points[30:33] = np.nan  # not seen
    cleaned, done = clean_joints(points, JointClean(savgol_window=5))
    assert done["interpolated_frames"] == 1
    assert np.isnan(cleaned[30:33]).all()
    assert np.abs(cleaned[20] - truth[20]).max() < 1e-6
    assert np.abs(cleaned[:30] - truth[:30]).max() < 1e-6  # a line stays a line


def test_project_and_mask_keep_hands_inside_the_image() -> None:
    frames = 4
    left, right = hand(frames, x=0.0), hand(frames, x=5.0)  # right is far off to the side
    left[3] = np.nan
    f = EpisodeFrames(hands={"left": left.astype(np.float32), "right": right.astype(np.float32)},
                      rotations={"left": None, "right": None}, camera_position=None,
                      camera_rotation=None,
                      confidence={"left": np.ones(frames, np.float32),
                                  "right": np.ones(frames, np.float32)},
                      intrinsic=K, image_size=(128, 96))
    assert f.mask("left").tolist() == [True, True, True, False]
    assert not f.mask("right").any()
    pixels, front = project(np.array([[0.0, 0.0, 1.0]]), K)
    assert front.all() and np.allclose(pixels, [[64.0, 48.0]])
    assert np.allclose(scaled_intrinsic(K, (128, 96), (64, 48))[:2], K[:2] / 2)


def write_arkit(path: Path, frames: int = 12) -> np.ndarray:  # type: ignore[type-arg]
    """An EgoDex-like HDF5 with all 21 joints a hand; the camera 1 m up the world y,
    looking along world +z. Returns the camera transform."""
    camera = np.tile(np.eye(4), (frames, 1, 1))
    camera[:, 1, 3] = 1.0
    with h5py.File(path, "w") as f:
        f["transforms/camera"] = camera.astype(np.float32)
        for side, x in (("left", -0.1), ("right", 0.1)):
            for j, name in enumerate(arkit_joints(side)):
                pose = np.tile(np.eye(4), (frames, 1, 1))
                pose[:, :3, 3] = [x + 0.003 * j, 1.0, 0.5]
                f[f"transforms/{name}"] = pose.astype(np.float32)
                f[f"confidences/{name}"] = np.full(frames, 0.8, np.float32)
        f["camera/intrinsic"] = K.astype(np.float32)
    return camera


def test_egodex_joints_move_into_the_camera_frame(tmp_path: Path) -> None:
    write_arkit(tmp_path / "0.hdf5")
    f = from_egodex(tmp_path / "0.hdf5", K, (128, 96))
    assert f.frames == 12
    assert np.allclose(f.hands["left"][0, 0], [-0.1, 0.0, 0.5], atol=1e-6)
    assert np.allclose(f.hands["right"][0, 20], [0.1 + 0.06, 0.0, 0.5], atol=1e-6)
    assert np.allclose(f.rotations["left"][0, 0], [0, 0, 0, 1])  # type: ignore[index]
    assert np.allclose(f.camera_position[0], [0, 1, 0])  # type: ignore[index]
    assert np.allclose(f.camera_rotation[0], [0, 0, 0, 1])  # type: ignore[index]
    assert np.allclose(f.confidence["right"], 0.8)
    assert f.mask("left").all()


def test_ea_estimates_are_cut_to_the_video_and_scored(tmp_path: Path) -> None:
    frames = 30
    left = hand(frames)
    left[10:12] = np.nan
    score = np.full(frames, 0.9)
    score[10:12] = 0.0
    np.savez(tmp_path / "ep_x.npz", meta="{}", camera=np.tile(np.eye(4), (frames, 1, 1)),
             left_cam=left, right_cam=np.full((frames, 21, 3), np.nan), left_score=score,
             right_score=np.zeros(frames), left_px=np.zeros((frames, 21, 2)),
             right_px=np.zeros((frames, 21, 2)), moving=np.zeros(frames))
    f = from_estimates(tmp_path / "ep_x.npz", 25, K, (128, 96), JointClean())
    assert f.frames == 25 and f.rotations["left"] is None and f.camera_position is None
    assert f.confidence["left"][10] == 0.0 and f.confidence["left"][0] == pytest.approx(0.9)
    assert (f.confidence["right"] == 0).all()
    assert f.provenance["estimated_frames"] == frames


def test_quality_reports_human1m_checks() -> None:
    frames = 40
    left = hand(frames).astype(np.float32)
    left[:4] = np.nan  # 90 % seen
    f = EpisodeFrames(hands={"left": left, "right": np.full((frames, 21, 3), np.nan, np.float32)},
                      rotations={"left": None, "right": None}, camera_position=None,
                      camera_rotation=None,
                      confidence={"left": np.ones(frames, np.float32),
                                  "right": np.zeros(frames, np.float32)},
                      intrinsic=K, image_size=(128, 96))
    q = measure(f, 30.0, 480, [Subtask(0, 20, "a", "s"), Subtask(20, 40, "b", "s")],
                Requirements())
    assert q["hands_visible"] == pytest.approx(0.9)
    assert q["checks"] == {"fps": True, "resolution": True, "hands_visible": False,
                           "subtask_seconds": False}  # 0.67 s subtasks
    assert q["left_bone_cv"] == pytest.approx(0.0, abs=1e-6)  # a rigid hand
    assert q["right_bone_cv"] is None
    assert bone_cv(left, np.zeros(frames, dtype=bool)) is None

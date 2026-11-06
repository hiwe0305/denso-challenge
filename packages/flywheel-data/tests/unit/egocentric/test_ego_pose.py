"""DA-04 task 4: E-B pose read straight from EgoDex tracking (AC 4)."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest
from ego_data import FRAMES, aperture_track, right_wrist_track, synthetic_pose, write_hdf5
from flywheel.data.ingest.egocentric.pose import (
    EgoPose,
    aperture,
    load_pose,
    read_egodex_pose,
    save_pose,
    wrist_speed,
)


def test_eb_reads_camera_wrists_tips_and_confidence(tmp_path: Path) -> None:
    path = tmp_path / "t" / "0.hdf5"
    write_hdf5(path)
    pose = read_egodex_pose(path)
    assert pose.frames == FRAMES
    np.testing.assert_allclose(pose.right_wrist[:, 0, 3], right_wrist_track(), atol=1e-6)
    np.testing.assert_allclose(aperture(pose, "right"), aperture_track(), atol=1e-6)
    np.testing.assert_allclose(pose.confidence_right, 0.9)
    assert pose.left_tips.shape == (FRAMES, 5, 3)


def test_a_file_without_confidences_gives_nan_not_zero(tmp_path: Path) -> None:
    path = tmp_path / "t" / "0.hdf5"
    write_hdf5(path, confidences=False)
    pose = read_egodex_pose(path)
    assert np.isnan(pose.confidence_left).all() and np.isnan(pose.confidence_right).all()


def test_pose_npz_round_trips_in_the_da18_layout(tmp_path: Path) -> None:
    pose = synthetic_pose()
    save_pose(pose, tmp_path / "pose.npz")
    with np.load(tmp_path / "pose.npz") as data:
        assert sorted(data.files) == sorted(f.name for f in fields(EgoPose))
        assert all(data[name].dtype == np.float32 for name in data.files)
    loaded = load_pose(tmp_path / "pose.npz")
    for f in fields(EgoPose):
        np.testing.assert_array_equal(getattr(loaded, f.name), getattr(pose, f.name))


def test_the_layout_is_checked() -> None:
    pose = synthetic_pose()
    with pytest.raises(ValueError, match="shape"):
        EgoPose(**{**{f.name: getattr(pose, f.name) for f in fields(EgoPose)},
                   "left_tips": pose.left_tips[:, :4]})
    with pytest.raises(ValueError, match="float32"):
        EgoPose(**{**{f.name: getattr(pose, f.name) for f in fields(EgoPose)},
                   "camera": pose.camera.astype(np.float64)})


def test_wrist_speed_is_metres_per_second() -> None:
    pose = synthetic_pose()
    speed = wrist_speed(pose, "right", 30.0)
    step = abs(right_wrist_track()[20] - right_wrist_track()[19])
    assert speed[20] == pytest.approx(step * 30.0, rel=1e-4)
    assert speed[GRASP_MIDDLE] == pytest.approx(0.0)


GRASP_MIDDLE = 45

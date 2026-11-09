"""DA-04 task 10: E-A pose cleaning before pose.npz (docs/he/stage1.md 2.8). CPU only.

Every step runs on synthetic tracks whose answer is known: a hand turning slowly,
then flipped, jumped or shaken on purpose.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from ego_data import FRAMES, make_videos
from flywheel.data.annotate.deid.blur import BlurParams, Box, Frame
from flywheel.data.ingest.egocentric import api
from flywheel.data.ingest.egocentric.clean import CleanParams
from flywheel.data.ingest.egocentric.config import EgoConfig, load_config
from flywheel.data.ingest.egocentric.episodes import (
    POSE,
    POSE_EA,
    bundle_dir,
    read_bundle,
    read_episodes,
)
from flywheel.data.ingest.egocentric.estimate import Estimate, to_pose
from flywheel.data.ingest.egocentric.estimate_job import TIPS, wrist_frame
from flywheel.data.ingest.egocentric.pose import load_pose
from flywheel.data.ingest.egocentric.source import register_egodex
from flywheel.data.ingest.egocentric.video_source import register_videos

ROOT = Path(__file__).resolve().parents[5]


def axis_angle(axis: np.ndarray, radians: float) -> np.ndarray:
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(radians) * k + (1 - np.cos(radians)) * k @ k


def hand_points() -> np.ndarray:
    """21 landmarks of a right hand, palm towards -z, fingers curled to +z (wrist frame)."""
    rng = np.random.default_rng(3)
    points = rng.normal(0, 0.01, (21, 3))
    points[0], points[5], points[17], points[9] = (0, 0, 0), (0.04, 0.08, 0), (-0.03, 0.07, 0), (
        0.005, 0.09, 0)
    for tip in TIPS[1:]:
        points[tip] = points[tip] * [1, 0, 0] + [0, 0.1, 0.03]  # curled: palm side, +z
    return points


def estimate(frames: int = FRAMES, seed: int = 0) -> Estimate:
    """A VO track that turns about y; both hands drift slowly in the camera frame."""
    rng = np.random.default_rng(seed)
    camera = np.repeat(np.eye(4)[None], frames, axis=0)
    for t in range(frames):
        camera[t, :3, :3] = axis_angle([0, 1, 0], 0.02 * t)
        camera[t, :3, 3] = [0.005 * t, 0, 0]
    points = {}
    for side, x in (("left", -0.15), ("right", 0.15)):
        track = np.empty((frames, 21, 3))
        for t in range(frames):
            turn = axis_angle([0, 0, 1], 0.01 * t)
            track[t] = hand_points() @ turn.T + [x + 0.001 * t, 0.05, 0.5]
        points[side] = track + rng.normal(0, 1e-4, track.shape)
    return Estimate(camera=camera, pixels={s: np.zeros((frames, 21, 2)) for s in points},
                    points=points, score={s: np.full(frames, 0.9) for s in points},
                    moving=np.ones(frames), meta={"step_m": 0.005})


def test_the_camera_frame_keeps_hands_where_the_camera_saw_them() -> None:
    est = estimate()
    pose = to_pose(est, "camera")
    np.testing.assert_allclose(pose.camera, np.repeat(np.eye(4)[None], FRAMES, 0))
    np.testing.assert_allclose(pose.left_wrist[7], wrist_frame(est.points["left"][7]), atol=1e-6)
    np.testing.assert_allclose(pose.right_tips[9], est.points["right"][9][list(TIPS)], atol=1e-6)
    world = to_pose(est)  # the old default: hands moved by the VO track
    np.testing.assert_allclose(world.left_wrist[7], est.camera[7] @ wrist_frame(
        est.points["left"][7]), atol=1e-5)
    with pytest.raises(ValueError, match="pose frame"):
        to_pose(est, "head")


def test_the_repo_config_cleans_in_the_camera_frame() -> None:
    params = CleanParams.from_config(load_config(ROOT / "configs/data/egocentric.yaml").pose_ea)
    assert params.frame == "camera"
    assert CleanParams.from_config({}) == CleanParams()  # no section: as before task 10
    with pytest.raises(ValueError, match="unknown keys"):
        CleanParams.from_config({"clean": {"window": 21, "typo": 1}})
    with pytest.raises(ValueError, match="frame"):
        CleanParams.from_config({"clean": {"frame": "head"}})


class NoFace:
    def detect(self, frame: Frame) -> list[Box]:
        return []


def save_estimate(path: Path, est: Estimate) -> None:
    arrays = {"camera": est.camera, "moving": est.moving, "meta": np.array(json.dumps(est.meta))}
    for side in ("left", "right"):
        arrays |= {f"{side}_px": est.pixels[side], f"{side}_cam": est.points[side],
                   f"{side}_score": est.score[side]}
    np.savez(path, **arrays)


def test_import_writes_the_team_video_in_the_camera_frame_and_says_so(
    tmp_path: Path, store: Path, cfg: EgoConfig
) -> None:
    pytest.importorskip("cv2")
    work = tmp_path / "work"
    api.ingest(register_videos(make_videos(tmp_path / "rec", frames=FRAMES), cfg), work, cfg,
               store)
    api.deid(work, NoFace(), BlurParams(0.6, 0.3, 960, 0.0, 2, 4),
             {"name": "fake", "revision": "0", "sha256": "0", "runtime": "test"})
    (episode,) = read_episodes(work)
    estimates = tmp_path / "ea"
    estimates.mkdir()
    save_estimate(estimates / f"{episode.episode_id}.npz", estimate())
    api.import_estimates(work, estimates, CleanParams(frame="camera"))
    folder = bundle_dir(work, episode.episode_id)
    pose = load_pose(folder / POSE)
    np.testing.assert_allclose(pose.camera, np.repeat(np.eye(4)[None], FRAMES, 0))
    assert (folder / POSE_EA).is_file()
    bundle = read_bundle(work, episode.episode_id)
    assert bundle.pose_frame == "camera"
    assert bundle.pose_cleaning is not None
    assert bundle.pose_cleaning["params"]["frame"] == "camera"


def test_eb_is_never_cleaned(tmp_path: Path, store: Path, cfg: EgoConfig) -> None:
    work = tmp_path / "work"
    api.ingest(register_egodex(store, cfg), work, cfg, store)
    api.write_eb_poses(work)
    episode = read_episodes(work)[0]
    folder = bundle_dir(work, episode.episode_id)
    before = (folder / POSE).read_bytes(), (folder / "bundle.json").read_bytes()
    estimates = tmp_path / "ea"
    estimates.mkdir()
    frames = load_pose(folder / POSE).frames
    save_estimate(estimates / f"{episode.episode_id}.npz", estimate(frames))
    api.import_estimates(work, estimates, CleanParams(frame="camera"))
    assert ((folder / POSE).read_bytes(), (folder / "bundle.json").read_bytes()) == before
    assert (folder / POSE_EA).is_file()

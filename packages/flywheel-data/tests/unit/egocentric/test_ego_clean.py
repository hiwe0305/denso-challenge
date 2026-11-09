"""DA-04 task 10: E-A pose cleaning before pose.npz (docs/he/stage1.md 2.8). CPU only.

Every step runs on synthetic tracks whose answer is known: a hand turning slowly,
then flipped, jumped or shaken on purpose.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from ego_data import FRAMES, make_videos
from flywheel.data.annotate.deid.blur import BlurParams, Box, Frame
from flywheel.data.ingest.egocentric import api
from flywheel.data.ingest.egocentric.clean import (
    FLIPS,
    CleanParams,
    angle,
    chirality,
    clean_pose,
    continuous_signs,
    interpolate,
    jump_frames,
    keep_continuous,
    one_sign,
    savgol,
    seen_runs,
    smooth,
    to_quaternion,
    to_rotation,
)
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


def hand_points(side: str = "right") -> np.ndarray:
    """21 landmarks of a hand in its wrist frame, fingers curled to +z for a right hand;
    a left hand is its mirror image (x negated)."""
    rng = np.random.default_rng(3)
    points = rng.normal(0, 0.01, (21, 3))
    points[0], points[5], points[17], points[9] = (0, 0, 0), (0.04, 0.08, 0), (-0.03, 0.07, 0), (
        0.005, 0.09, 0)
    for tip in TIPS[1:]:
        points[tip] = points[tip] * [1, 0, 0] + [0, 0.1, 0.03]  # curled: palm side, +z
    return points if side == "right" else points * [-1, 1, 1]


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
            track[t] = hand_points(side) @ turn.T + [x + 0.001 * t, 0.05, 0.5]
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


def test_the_test_hands_have_their_sides_chirality() -> None:
    pose = to_pose(estimate(), "camera")
    for side, sign in (("left", -1), ("right", 1)):
        votes = chirality(pose.wrist(side).astype(float), pose.tips(side).astype(float))
        assert (votes == sign).all(), side


def test_flipped_frames_are_turned_back_and_unseen_frames_stay_nan() -> None:
    truth = to_pose(estimate(), "camera").left_wrist.astype(float)[:, :3, :3]
    noisy = truth.copy()
    for t in (10, 11, 12, 70):
        noisy[t] = noisy[t] @ FLIPS[1]  # a mirrored hand: pi about y
    noisy[30] = noisy[30] @ FLIPS[0]
    noisy[40:45] = np.nan  # the hand was not seen
    noisy[45:48] = noisy[45:48] @ FLIPS[2]  # and came back flipped about z
    fixed, turned = keep_continuous(noisy, 30.0)
    assert turned == 8
    seen = np.isfinite(noisy.reshape(len(noisy), -1)).all(axis=1)
    assert np.isnan(fixed[~seen]).all()
    assert np.degrees(angle(fixed[seen], truth[seen])).max() < 0.1  # arccos of float32 input


def test_a_real_turn_is_not_taken_for_a_flip() -> None:
    """A wrist turning 20 degrees a frame is fast but not a flip; nothing is turned."""
    turning = np.stack([axis_angle([1, 0, 0], np.radians(20) * t) for t in range(20)])
    fixed, turned = keep_continuous(turning, 30.0)
    assert turned == 0 and np.allclose(fixed, turning)


def test_a_mirrored_track_gets_its_sides_sign() -> None:
    pose = to_pose(estimate(), "camera")
    right, tips = pose.right_wrist.astype(float), pose.right_tips.astype(float)
    mirrored = right.copy()
    mirrored[:, :3, :3] = right[:, :3, :3] @ FLIPS[1]  # the whole track the other way
    fixed, turned = one_sign(mirrored, tips, "right")
    assert turned and np.allclose(fixed, right)
    same, turned = one_sign(right, tips, "right")
    assert not turned and same is right
    # the left hand's chirality is the other one: a correct left track stays
    left = pose.left_wrist.astype(float)
    assert not one_sign(left, pose.left_tips.astype(float), "left")[1]


def test_clean_pose_reports_what_it_turned() -> None:
    pose = to_pose(estimate(), "camera")
    noisy = pose.right_wrist.copy()
    noisy[5, :3, :3] = noisy[5, :3, :3] @ FLIPS[1].astype(np.float32)
    out, report = clean_pose(replace(pose, right_wrist=noisy), CleanParams("camera", 30.0))
    assert report["right"] == {"seen_frames": FRAMES, "flipped_frames": 1, "track_turned": False}
    assert report["left"]["flipped_frames"] == 0
    np.testing.assert_allclose(out.right_wrist, pose.right_wrist, atol=1e-5)
    untouched, _ = clean_pose(replace(pose, right_wrist=noisy), CleanParams("camera"))
    assert np.array_equal(untouched.right_wrist, noisy)


def test_quaternions_round_trip_near_and_far_from_identity() -> None:
    rng = np.random.default_rng(5)
    rotations = [axis_angle(rng.normal(size=3), a) for a in rng.uniform(0, np.pi, 50)]
    rotations += [axis_angle([1, 0, 0], np.pi), axis_angle([0, 1, 1], np.pi - 1e-6), np.eye(3)]
    m = np.stack(rotations)
    np.testing.assert_allclose(to_rotation(to_quaternion(m)), m, atol=1e-9)


def test_seen_runs_are_half_open() -> None:
    seen = np.array([0, 1, 1, 0, 0, 1, 0, 1, 1, 1], dtype=bool)
    assert seen_runs(seen) == [(1, 3), (5, 6), (7, 10)]


def spiked() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pose = to_pose(estimate(), "camera")
    truth, tips = pose.left_wrist.astype(float), pose.left_tips.astype(float)
    noisy, noisy_tips = truth.copy(), tips.copy()
    noisy[50, :3, 3] += [0.2, 0, 0]  # the hand estimate jumps for one frame
    noisy_tips[50] += [0.2, 0, 0]
    noisy[50, :3, :3] = axis_angle([1, 0, 0], np.radians(60)) @ noisy[50, :3, :3]
    noisy[100:110] = np.nan  # not seen
    noisy_tips[100:110] = np.nan
    noisy[110, :3, 3] += [0.3, 0, 0]  # a run's first frame: no step to judge it by
    noisy[FRAMES - 1, :3, 3] += [0.3, 0, 0]  # a run's last frame: held from the one before
    return truth, noisy, noisy_tips


def test_a_jump_frame_is_interpolated_and_no_frame_is_dropped() -> None:
    truth, noisy, tips = spiked()
    bad = jump_frames(noisy, 5.0)
    # the jump in and the jump back out; the first frame after the gap has no step
    assert np.flatnonzero(bad).tolist() == [50, 51, 111, FRAMES - 1]
    wrist, fixed_tips, count = interpolate(noisy, tips, bad)
    assert count == 4 and wrist.shape == noisy.shape and fixed_tips.shape == tips.shape
    np.testing.assert_allclose(wrist[50, :3, 3], truth[50, :3, 3], atol=1e-3)  # 1 mm
    np.testing.assert_allclose(fixed_tips[50], tips[49] + (tips[52] - tips[49]) / 3)
    assert np.degrees(angle(wrist[50, :3, :3], truth[50, :3, :3])) < 0.5
    np.testing.assert_allclose(wrist[FRAMES - 1, :3, 3], noisy[FRAMES - 2, :3, 3])
    assert np.isnan(wrist[100:110]).all() and np.isnan(fixed_tips[100:110]).all()
    np.testing.assert_allclose(wrist[110], noisy[110])  # judged by nothing: kept as seen


def test_a_quiet_track_has_no_jumps() -> None:
    truth = to_pose(estimate(), "camera").right_wrist.astype(float)
    assert not jump_frames(truth, 5.0).any()


@pytest.mark.parametrize(("frames", "window"), [(50, 21), (30, 21), (21, 21), (12, 21), (40, 9)])
def test_savgol_matches_scipys_interp_mode(frames: int, window: int) -> None:
    signal = pytest.importorskip("scipy.signal")
    values = np.random.default_rng(frames).normal(size=(frames, 5, 3))
    used = min(window, frames if frames % 2 else frames - 1)
    expected = signal.savgol_filter(values, used, 2, axis=0, mode="interp")
    np.testing.assert_allclose(savgol(values, window, 2), expected, atol=1e-12)


def test_savgol_keeps_a_parabola_and_leaves_short_runs_alone() -> None:
    t = np.arange(40, dtype=float)
    parabola = np.stack([0.5 * t**2 - t, 3 - 0.1 * t], axis=1)
    np.testing.assert_allclose(savgol(parabola, 21, 2), parabola, atol=1e-8)
    short = np.random.default_rng(0).normal(size=(3, 2))
    assert np.array_equal(savgol(short, 21, 2), short)  # window 3 fits order 2 exactly


def test_quaternion_signs_follow_the_previous_one() -> None:
    q = to_quaternion(np.stack([axis_angle([0, 0, 1], 0.1 * t) for t in range(6)]))
    mixed = q * np.array([1, -1, 1, -1, -1, 1])[:, None]
    np.testing.assert_allclose(continuous_signs(mixed), q)


def test_smoothing_brings_a_shaking_hand_closer_and_keeps_unseen_frames() -> None:
    truth_pose = to_pose(estimate(), "camera")
    truth = truth_pose.right_wrist.astype(float)
    tips = truth_pose.right_tips.astype(float)
    rng = np.random.default_rng(9)
    noisy = truth.copy()
    noisy[:, :3, 3] += rng.normal(0, 0.01, (FRAMES, 3))  # 1 cm shake
    for t in range(FRAMES):
        noisy[t, :3, :3] = axis_angle(rng.normal(size=3), np.radians(5)) @ noisy[t, :3, :3]
    noisy[60:62] = np.nan  # a 2-frame gap splits the clip in two runs
    smoothed, _, runs = smooth(noisy, tips, 21, 2)
    assert runs == 2 and np.isnan(smoothed[60:62]).all()
    seen = np.isfinite(noisy[:, 0, 0])

    def error(w: np.ndarray) -> tuple[float, float]:
        return (float(np.linalg.norm(w[seen, :3, 3] - truth[seen, :3, 3], axis=1).mean()),
                float(np.degrees(angle(w[seen, :3, :3], truth[seen, :3, :3])).mean()))

    (before_m, before_deg), (after_m, after_deg) = error(noisy), error(smoothed)
    assert after_m < before_m / 2 and after_deg < before_deg / 2
    rotations = smoothed[seen, :3, :3]
    np.testing.assert_allclose(rotations @ np.swapaxes(rotations, 1, 2),
                               np.broadcast_to(np.eye(3), rotations.shape), atol=1e-9)


def test_the_repo_cleaning_end_to_end_on_a_noisy_clip() -> None:
    params = CleanParams.from_config(load_config(ROOT / "configs/data/egocentric.yaml").pose_ea)
    assert (params.flip_deg, params.jump_mad, params.savgol_window, params.savgol_order) == (
        30, 5.0, 21, 2)
    pose = to_pose(estimate(), "camera")
    noisy = pose.left_wrist.copy()
    noisy[20, :3, :3] = noisy[20, :3, :3] @ FLIPS[1].astype(np.float32)
    noisy[80, :3, 3] += 0.3
    out, report = clean_pose(replace(pose, left_wrist=noisy), params)
    assert report["left"] == {"seen_frames": FRAMES, "flipped_frames": 1, "track_turned": False,
                              "interpolated_frames": 2, "smoothed_runs": 1}
    assert np.linalg.norm(out.left_wrist[80, :3, 3] - pose.left_wrist[80, :3, 3]) < 0.005
    assert out.camera.shape == pose.camera.shape and out.frames == pose.frames


def test_a_bad_window_is_refused() -> None:
    with pytest.raises(ValueError, match="odd"):
        CleanParams(savgol_window=20)

"""K, W, P cut and anchors of a parent demo from its step flags (DA-35 task 8, AC 4)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from flywheel_simple.tray.s2.config import S2Config, segment_with
from flywheel_simple.tray.s2.parents import ParentDemo, hands_closed_from_action
from flywheel_simple.tray.s2.segments import Segmentation, SegmentError, segment, walking_runs

# Shaped like parents-1103b shard-00 episode 0: flags first at these frames, step 7 not
# shown (a frame holds the state before its step), walking runs as recorded.
STEP_FRAMES = (355, 360, 498, 951, 1066, 1592, None)
RUNS = ((119, 279), (300, 318), (576, 1155), (1162, 1207), (1243, 1275), (1413, 1456), (1641, 1675))
FRAMES = 1675


def demo(
    step_frames: tuple[int | None, ...] = STEP_FRAMES,
    runs: tuple[tuple[int, int], ...] = RUNS,
    frames: int = FRAMES,
) -> ParentDemo:
    steps = np.zeros((frames, 7), dtype=bool)
    for k, first in enumerate(step_frames):
        if first is not None:
            steps[first:, k] = True
    nav = np.zeros((frames, 4))
    for a, b in runs:
        nav[a:b, 0] = 0.3
    pose = np.tile([0.0, 0.0, 0.75, 1.0, 0.0, 0.0, 0.0], (frames, 1))
    # Both wrists reach 0.4 m forward over frames 200-360 (the grasp flag), then stay.
    eef = np.zeros((frames, 14))
    reach = 0.4 * np.clip((np.arange(frames) - 200) / 160, 0.0, 1.0)
    for k in (0, 7):
        eef[:, k] = reach
        eef[:, k + 3] = 1.0
    return ParentDemo(
        parent_id="test/shard-00/0",
        level=1,
        seed=100,
        eef=eef,
        navigate=nav,
        base_pose=pose,
        tray_pose=pose.copy(),
        steps=steps,
        hands_closed=np.zeros((frames, 2), dtype=bool),
    )


def test_cut_follows_the_flags() -> None:
    cut = segment(demo())
    assert cut.k_end == 498 + 25  # lift + 0.5 s
    assert cut.w_end == 1066  # reach_b
    assert cut.frames == FRAMES
    assert [cut.segment_of(f) for f in (0, 522, 523, 1065, 1066, FRAMES - 1)] == list("KKWWPP")


def test_walks_set_the_gates() -> None:
    cut = segment(demo())
    assert cut.walk_a_end == 279  # the corrective step 300-318 while reaching is too short
    assert cut.place_start == 1456  # standing at table B after the last step there


def test_hands_follow_the_tray_while_reaching_and_grasping() -> None:
    cut = segment(demo())
    assert cut.reach_start == 260  # wrists within 0.25 m of their grasp pose from here
    assert cut.grasp_end == 360 + 10  # grasp flag + 0.2 s
    expected = {0: "robot", 259: "robot", 260: "tray", 369: "tray", 370: "robot",
                522: "robot", 1455: "robot", 1456: "target", 1674: "target"}  # fmt: skip
    assert {f: cut.anchor_of(f) for f in expected} == expected


def test_hold_is_capped_at_reach_b() -> None:
    cut = segment(demo(step_frames=(355, 360, 498, 505, 510, 1592, None)))
    assert cut.k_end == cut.w_end == 510


def test_only_short_walks_before_step_one() -> None:
    cut = segment(demo(runs=((300, 318), (576, 1155))))
    assert cut.walk_a_end == 318


def test_missing_or_disordered_flags_are_refused() -> None:
    with pytest.raises(SegmentError, match="place"):
        segment(demo(step_frames=(355, 360, 498, 951, 1066, None, None)))
    with pytest.raises(SegmentError, match="out of order"):
        segment(demo(step_frames=(355, 360, 498, 1100, 1066, 1592, None)))
    with pytest.raises(SegmentError, match="reach_b"):
        segment(demo(step_frames=(355, 360, 498, 498, 498, 1592, None)))


def test_walking_runs_use_the_policy_switch() -> None:
    nav = np.zeros((10, 4))
    nav[2:4, 0] = 0.3
    nav[5, 2] = 0.12  # turn flag alone walks
    nav[7, 0] = 0.05  # below the switch: balance policy
    assert walking_runs(nav) == ((2, 4), (5, 6))


def test_segmentation_round_trips_through_json() -> None:
    cut = segment(demo())
    again = Segmentation.from_dict(json.loads(json.dumps(cut.as_dict())))
    assert again == cut


def test_hands_closed_from_dex3_targets() -> None:
    names = ["waist_yaw_joint", "left_hand_index_0_joint", "right_hand_index_0_joint"]
    action = np.array([[0.4, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 1.0, 1.5]])
    assert hands_closed_from_action(action, names).tolist() == [
        [False, False],
        [True, False],
        [True, True],
    ]


def test_config_loads() -> None:
    cfg = S2Config.load()
    assert cfg.hold_s == 0.5 and cfg.walk_min_s == 0.5
    assert segment_with(demo(), cfg) == segment(demo())


def test_parent_shapes_are_checked() -> None:
    good = demo(frames=10)
    with pytest.raises(ValueError, match="navigate"):
        ParentDemo(**{**good.__dict__, "navigate": np.zeros((9, 4))})

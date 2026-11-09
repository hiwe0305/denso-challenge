"""DA-04 task 6: egocentric QA, one contract QAReport per episode (AC 5)."""

from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path

import numpy as np
import pytest
from ego_data import FRAMES, K, synthetic_pose
from flywheel.contracts.artifacts import Episode
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.pose import EgoPose
from flywheel.data.ingest.egocentric.segments import EgoSegment
from flywheel.data.qa.egocentric import EgoQAInput, jitter_deg_s, run_ego_qa, valid_segments

ROOT = Path(__file__).resolve().parents[5]
EXAMPLE = ROOT / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/Episode.json"
SEGMENTS = (EgoSegment(0, 45, "pick", "pick up the cup", "rule"),
            EgoSegment(45, FRAMES, "place", "place the cup", "rule"))


def item(**changes: object) -> EgoQAInput:
    base = EgoQAInput(
        episode=Episode.model_validate_json(EXAMPLE.read_text()), pose=synthetic_pose(),
        segments=SEGMENTS, unresolved_share=0.0, video_frames=FRAMES,
        instruction="Pick up the cup and place it on the plate.", intrinsic=K.astype(np.float64),
        image_size=(1920, 1080), fps=30.0, gate_passed=True)
    return replace(base, **changes)  # type: ignore[arg-type]


def failed(cfg: EgoConfig, **changes: object) -> tuple[str, list[str]]:
    report = run_ego_qa(item(**changes), cfg)
    return report.decision, [c.name for c in report.checks if not c.passed]


def test_a_clean_episode_passes_every_check(cfg: EgoConfig) -> None:
    report = run_ego_qa(item(), cfg)
    assert report.decision == "pass" and report.reasons == []
    assert {c.name for c in report.checks} == set(cfg.qa)
    assert report.threshold_version == cfg.threshold_version
    assert report.report_id == run_ego_qa(item(), cfg).report_id


@pytest.mark.parametrize(("changes", "decision", "check"), [
    ({"gate_passed": False}, "reject", "deid_gate"),
    ({"instruction": " "}, "reject", "instruction"),
    ({"video_frames": FRAMES - 3}, "reject", "video_frames"),
    ({"segments": SEGMENTS[:1]}, "reject", "segment_count"),
    ({"unresolved_share": 0.5}, "flag", "segment_ambiguous"),
])
def test_each_check_fails_as_the_config_says(
    cfg: EgoConfig, changes: dict[str, object], decision: str, check: str
) -> None:
    assert failed(cfg, **changes) == (decision, [check])


def test_no_segment_fails_both_segment_checks(cfg: EgoConfig) -> None:
    assert failed(cfg, segments=()) == ("reject", ["segments", "segment_count"])


def test_a_short_episode_is_rejected(cfg: EgoConfig) -> None:
    pose = synthetic_pose()
    short = EgoPose(**{f.name: getattr(pose, f.name)[:10] for f in fields(EgoPose)})
    decision, names = failed(cfg, pose=short, video_frames=10, segments=(
        EgoSegment(0, 10, "pick", "pick", "rule"),))
    assert decision == "reject" and "min_frames" in names


def lose(pose: EgoPose, side: str, frames: slice) -> EgoPose:
    wrist, tips = pose.wrist(side).copy(), pose.tips(side).copy()
    wrist[frames], tips[frames] = np.nan, np.nan
    return replace(pose, **{f"{side}_wrist": wrist, f"{side}_tips": tips})


def test_nan_hand_frames_are_flagged_with_counts_per_hand(cfg: EgoConfig) -> None:
    """Review of PR 152: E-A loses hands (20/20 real files); QA says how many frames."""
    pose = lose(lose(synthetic_pose(), "left", slice(0, 30)), "right", slice(20, 25))
    report = run_ego_qa(item(pose=pose), cfg)
    assert report.decision == "flag"
    assert report.reasons == [
        f"hand_pose_nan (D1): NaN hand pose in 30 frames (left 30/{FRAMES}, right 5/{FRAMES})"]
    check = next(c for c in report.checks if c.name == "hand_pose_nan")
    assert check.value == 30 and not check.passed
    assert np.isnan(pose.left_wrist[0]).all()  # QA reads the pose, it does not mend it


def test_no_finite_hand_at_all_is_rejected(cfg: EgoConfig) -> None:
    pose = lose(lose(synthetic_pose(), "left", slice(0, 50)), "right", slice(50, FRAMES))
    assert failed(cfg, pose=pose)[0] == "flag"  # one hand at a time is still a hand
    gone = lose(lose(synthetic_pose(), "left", slice(None)), "right", slice(None))
    report = run_ego_qa(item(pose=gone), cfg)
    assert report.decision == "reject" and report.reasons[0] == (
        f"hand_pose_nan (D1): no frame has a finite hand pose"
        f" (NaN frames: left {FRAMES}/{FRAMES}, right {FRAMES}/{FRAMES})")


def test_confidence_not_recorded_is_a_flag_not_a_pass(cfg: EgoConfig) -> None:
    pose = synthetic_pose()
    nan = np.full(FRAMES, np.nan, dtype=np.float32)
    report = run_ego_qa(item(pose=replace(pose, confidence_left=nan, confidence_right=nan)), cfg)
    assert report.decision == "flag"
    assert report.reasons == ["pose_low_confidence: the source recorded no pose confidence"]


def test_low_confidence_and_hands_out_of_frame_flag(cfg: EgoConfig) -> None:
    pose = synthetic_pose()
    low = np.full(FRAMES, 0.1, dtype=np.float32)
    assert failed(cfg, pose=replace(pose, confidence_left=low, confidence_right=low)) == (
        "flag", ["pose_low_confidence"])
    behind = pose.camera.copy()
    behind[:, 2, 3] = 1.0  # camera moved past the hands: they are behind it
    assert failed(cfg, pose=replace(pose, camera=behind)) == ("flag", ["hand_out_of_frame"])


def test_a_shaking_camera_flags_jitter(cfg: EgoConfig) -> None:
    pose = synthetic_pose()
    camera = pose.camera.copy()
    rng = np.random.default_rng(0)
    for t in range(FRAMES):
        a = np.radians(rng.normal(0, 3))
        camera[t, :3, :3] = [[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]]
    assert jitter_deg_s(camera, 30.0) > cfg.qa["camera_jitter_deg_s"].threshold
    assert jitter_deg_s(pose.camera, 30.0) == pytest.approx(0.0, abs=1e-3)
    decision, names = failed(cfg, pose=replace(pose, camera=camera))
    assert decision == "flag" and "camera_jitter_deg_s" in names


def test_valid_segments_allow_a_gap_but_not_an_overlap() -> None:
    gap = (EgoSegment(0, 40, "pick", "a", "rule"), EgoSegment(50, 100, "place", "b", "human"))
    assert valid_segments(gap, 100)
    assert not valid_segments(gap, 99)
    assert not valid_segments((EgoSegment(0, 40, "pick", "a", "rule"),
                               EgoSegment(30, 100, "place", "b", "rule")), 100)
    assert not valid_segments((EgoSegment(5, 5, "pick", "a", "rule"),), 100)


WHOLE_TASK = "Pick up the cup and place it on the plate."  # item()'s instruction


def human(*segments: EgoSegment) -> tuple[EgoSegment, ...]:
    return tuple(replace(s, label_source="human") for s in segments)


def test_a_person_settles_what_the_rules_left_open(cfg: EgoConfig) -> None:
    """Task 9: once every segment is human-reviewed, the rules' open events do not count."""
    report = run_ego_qa(item(segments=human(*SEGMENTS), unresolved_share=0.5), cfg)
    assert report.decision == "pass"
    check = next(c for c in report.checks if c.name == "segment_ambiguous")
    assert check.value == 0.0 and check.passed
    # one segment a person did not see keeps the rules' share
    mixed = (SEGMENTS[0], *human(SEGMENTS[1]))
    assert failed(cfg, segments=mixed, unresolved_share=0.5) == ("flag", ["segment_ambiguous"])
    # no segment at all is not "every segment human"
    assert "segment_ambiguous" in failed(cfg, segments=(), unresolved_share=0.5)[1]


def test_one_human_segment_with_the_whole_task_sentence_is_a_sample(cfg: EgoConfig) -> None:
    """Task 9 (Hiếu 9/11/2026): a 2-3 s clip is one sample with the whole-task sentence;
    a person cut it to the frames to keep, so one segment is enough there."""
    whole = human(EgoSegment(20, 120, "pick", WHOLE_TASK, "rule"))
    report = run_ego_qa(item(segments=whole, unresolved_share=1.0), cfg)
    assert report.decision == "pass" and report.reasons == []
    count = next(c for c in report.checks if c.name == "segment_count")
    assert (count.value, count.threshold, count.passed) == (1.0, 1.0, True)


@pytest.mark.parametrize("segments", [
    # EgoDex: a person kept the pick and rejected the place; the place is still lost
    human(EgoSegment(0, 45, "pick", "pick up the cup", "rule")),
    # the whole-task sentence, but no person said so
    (EgoSegment(0, FRAMES, "pick", WHOLE_TASK, "rule"),),
    (EgoSegment(0, FRAMES, "pick", WHOLE_TASK, "model"),),
])
def test_other_single_segments_still_fail_segment_count(
    cfg: EgoConfig, segments: tuple[EgoSegment, ...]
) -> None:
    report = run_ego_qa(item(segments=segments), cfg)
    assert report.decision == "reject"
    count = next(c for c in report.checks if c.name == "segment_count")
    assert (count.value, count.threshold, count.passed) == (1.0, 2.0, False)

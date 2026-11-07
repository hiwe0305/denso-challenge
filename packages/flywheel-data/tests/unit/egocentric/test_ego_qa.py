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

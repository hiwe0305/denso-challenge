"""DA-04 task 3: a person reviews a sample; their decisions become `human` labels."""

from __future__ import annotations

from pathlib import Path

import pytest
from ego_data import FRAMES
from flywheel.data.ingest.egocentric import review
from flywheel.data.ingest.egocentric.episodes import (
    SEGMENTS,
    Bundle,
    bundle_dir,
    write_bundle,
)
from flywheel.data.ingest.egocentric.segments import (
    EgoSegment,
    read_segment_rows,
    write_segment_table,
)


def make_work(tmp_path: Path, episodes: int = 3) -> tuple[Path, list[str]]:
    work = tmp_path / "work"
    ids = []
    for i in range(episodes):
        eid = f"ep_{i:016x}"
        write_bundle(work, Bundle(
            episode_id=eid, hdf5=None, mp4="x.mp4", frames=FRAMES, fps=30.0, task="t",
            instruction="", pose_source="E-B", action_quality="retargeted", pose="pose.npz",
            video_frames=FRAMES, objects=("cup",), intrinsic=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
            image_size=(64, 36)))
        write_segment_table(bundle_dir(work, eid) / SEGMENTS, [
            EgoSegment(0, 45, "pick", "pick up the cup", "rule"),
            EgoSegment(45, FRAMES, "place", "place the cup", "model")], 30.0)
        ids.append(eid)
    return work, ids


def test_the_sample_is_fixed_by_the_seed(tmp_path: Path) -> None:
    work, ids = make_work(tmp_path)
    first = review.sample(work, ids, 0.5, seed=7)
    assert len(first) == 3 and first == review.sample(work, ids, 0.5, seed=7)
    assert all(r["decision"] is None for r in first)
    assert len(review.sample(work, ids, 0.01, seed=7)) == 1


def test_apply_writes_human_labels_and_drops_rejects(tmp_path: Path) -> None:
    work, ids = make_work(tmp_path)
    rows = [
        {"episode_id": ids[0], "segment": 0, "decision": "accept", "reviewer": "Hiếu"},
        {"episode_id": ids[0], "segment": 1, "decision": "fix", "reviewer": "Hiếu",
         "description": "place the cup on the plate", "frame_start": 45},
        {"episode_id": ids[1], "segment": 1, "decision": "reject", "reviewer": "Hiếu"},
        {"episode_id": ids[2], "segment": 0, "decision": None, "reviewer": None},
    ]
    sheet = tmp_path / "sheet.jsonl"
    review.write_sheet(sheet, rows)
    assert review.apply(work, review.read_sheet(sheet)) == {"accept": 1, "fix": 1, "reject": 1}
    first = read_segment_rows(bundle_dir(work, ids[0]) / SEGMENTS)
    assert [s.label_source for s in first] == ["human", "human"]
    assert first[1].description == "place the cup on the plate"
    assert [s.step_id for s in read_segment_rows(bundle_dir(work, ids[1]) / SEGMENTS)] == ["pick"]
    assert [s.label_source for s in read_segment_rows(bundle_dir(work, ids[2]) / SEGMENTS)] == [
        "rule", "model"]


def test_apply_refuses_overlaps_unknown_decisions_and_anonymous_reviews(tmp_path: Path) -> None:
    work, ids = make_work(tmp_path)
    with pytest.raises(ValueError, match="overlap"):
        review.apply(work, [{"episode_id": ids[0], "segment": 1, "decision": "fix",
                             "reviewer": "H", "frame_start": 30}])
    with pytest.raises(ValueError, match="decision"):
        review.apply(work, [{"episode_id": ids[0], "segment": 0, "decision": "maybe",
                             "reviewer": "H"}])
    with pytest.raises(ValueError, match="reviewer"):
        review.apply(work, [{"episode_id": ids[0], "segment": 0, "decision": "accept"}])

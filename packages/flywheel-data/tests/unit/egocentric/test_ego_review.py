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


def at(step: str, start: int, end: int) -> dict[str, object]:
    return {"step_id": step, "frame_start": start, "frame_end": end}


PICK, PLACE = at("pick", 0, 45), at("place", 45, FRAMES)


def test_the_sheet_names_segments_by_match_not_position(tmp_path: Path) -> None:
    work, ids = make_work(tmp_path)
    rows = review.sample(work, ids, 1.0, seed=7)
    assert all("segment" not in r for r in rows)
    assert [r["match"] for r in rows[:2]] == [PICK, PLACE]


def test_apply_writes_human_labels_and_drops_rejects(tmp_path: Path) -> None:
    work, ids = make_work(tmp_path)
    rows = [
        {"episode_id": ids[0], "match": PICK, "decision": "accept", "reviewer": "Hiếu"},
        {"episode_id": ids[0], "match": PLACE, "decision": "fix", "reviewer": "Hiếu",
         "description": "place the cup on the plate", "frame_start": 45},
        {"episode_id": ids[1], "match": PLACE, "decision": "reject", "reviewer": "Hiếu"},
        {"episode_id": ids[2], "match": PICK, "decision": None, "reviewer": None},
    ]
    sheet = tmp_path / "sheet.jsonl"
    review.write_sheet(sheet, rows)
    assert review.apply(work, review.read_sheet(sheet), ids) == {
        "accept": 1, "fix": 1, "reject": 1}
    first = read_segment_rows(bundle_dir(work, ids[0]) / SEGMENTS)
    assert [s.label_source for s in first] == ["human", "human"]
    assert first[1].description == "place the cup on the plate"
    assert [s.step_id for s in read_segment_rows(bundle_dir(work, ids[1]) / SEGMENTS)] == ["pick"]
    assert [s.label_source for s in read_segment_rows(bundle_dir(work, ids[2]) / SEGMENTS)] == [
        "rule", "model"]


def test_applying_the_sheet_again_after_a_reject_is_refused_not_misapplied(
    tmp_path: Path
) -> None:
    """Review of PR 152: by position, the second apply raised IndexError or hit another
    segment."""
    work, ids = make_work(tmp_path)
    rows = [{"episode_id": ids[0], "match": PICK, "decision": "reject", "reviewer": "H"},
            {"episode_id": ids[0], "match": PLACE, "decision": "accept", "reviewer": "H"}]
    review.apply(work, rows, ids)
    after = read_segment_rows(bundle_dir(work, ids[0]) / SEGMENTS)
    with pytest.raises(ValueError, match="no segment pick@0-45"):
        review.apply(work, rows, ids)
    assert read_segment_rows(bundle_dir(work, ids[0]) / SEGMENTS) == after


def test_three_segments_are_matched_by_their_frames(tmp_path: Path) -> None:
    work, ids = make_work(tmp_path)
    path = bundle_dir(work, ids[0]) / SEGMENTS
    write_segment_table(path, [EgoSegment(0, 20, "pick", "a", "rule"),
                               EgoSegment(20, 45, "place", "b", "rule"),
                               EgoSegment(45, FRAMES, "pick", "c", "rule")], 30.0)
    review.apply(work, [{"episode_id": ids[0], "match": at("pick", 45, FRAMES),
                         "decision": "fix", "description": "pick it again", "reviewer": "H"}],
                 ids)
    assert [s.description for s in read_segment_rows(path)] == ["a", "b", "pick it again"]


def test_a_bad_row_refuses_the_whole_sheet_before_writing(tmp_path: Path) -> None:
    work, ids = make_work(tmp_path)
    before = [read_segment_rows(bundle_dir(work, e) / SEGMENTS) for e in ids]
    good = {"episode_id": ids[0], "match": PICK, "decision": "accept", "reviewer": "H"}
    for bad, message in [
        ({"episode_id": "ep_unknown", "match": PICK, "decision": "accept", "reviewer": "H"},
         "not an episode"),
        ({"episode_id": ids[1], "match": at("pick", -1, 45), "decision": "accept",
          "reviewer": "H"}, "no segment"),
        ({"episode_id": ids[1], "match": PLACE, "decision": "fix", "reviewer": "H",
          "frame_start": 30}, "overlap"),
        ({**good}, "reviewed twice"),
        ({"episode_id": ids[1], "segment": 0, "decision": "accept", "reviewer": "H"}, "match"),
    ]:
        with pytest.raises(ValueError, match=message):
            review.apply(work, [good, bad], ids)
    assert [read_segment_rows(bundle_dir(work, e) / SEGMENTS) for e in ids] == before


def test_apply_refuses_unknown_decisions_and_anonymous_reviews(tmp_path: Path) -> None:
    work, ids = make_work(tmp_path)
    with pytest.raises(ValueError, match="decision"):
        review.apply(work, [{"episode_id": ids[0], "match": PICK, "decision": "maybe",
                             "reviewer": "H"}], ids)
    with pytest.raises(ValueError, match="reviewer"):
        review.apply(work, [{"episode_id": ids[0], "match": PICK, "decision": "accept"}], ids)

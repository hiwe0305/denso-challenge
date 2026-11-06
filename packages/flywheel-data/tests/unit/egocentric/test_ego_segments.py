"""DA-04 task 3: segments by rule, model suggestions when the rule is unsure (AC 3)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from ego_data import FRAMES, GRASP, RELEASE, synthetic_pose
from flywheel.contracts.segments import Segment
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.pose import EgoPose
from flywheel.data.ingest.egocentric.segments import (
    EgoSegment,
    Event,
    cut_episode,
    find_events,
    pick_place_steps,
    read_segment_rows,
    two_table_steps,
    write_segment_table,
)


class FakeSuggester:
    def __init__(self, answer: int | None) -> None:
        self.answer = answer
        self.calls: list[tuple[list[int], str]] = []

    def suggest(self, images: Sequence[bytes], frames: Sequence[int], event: str,
                instruction: str) -> int | None:
        self.calls.append((list(frames), event))
        assert len(images) == len(frames)
        return self.answer


class FakeLabeler:
    def describe(self, images: Sequence[bytes], step: str, instruction: str) -> str | None:
        return f"{step} the cup now"


def frames_of(indices: Sequence[int]) -> list[bytes]:
    return [b"jpeg" for _ in indices]


def test_the_rule_finds_the_grasp_and_release_it_was_given(cfg: EgoConfig) -> None:
    side, events, _ = find_events(synthetic_pose(), 30.0, cfg.segment)
    assert side == "right"
    assert [(e.kind, e.reasons) for e in events] == [("grasp", []), ("release", [])]
    assert abs(events[0].frame - sum(GRASP) // 2) <= 3
    assert abs(events[1].frame - sum(RELEASE) // 2) <= 3


def test_pick_place_cuts_tile_the_episode(cfg: EgoConfig) -> None:
    cut = cut_episode(synthetic_pose(), 30.0, "pick_place", cfg.segment,
                      instruction="Pick up the cup.", obj="cup")
    assert [s.step_id for s in cut.segments] == ["pick", "place"]
    assert cut.segments[0].frame_start == 0 and cut.segments[-1].frame_end == FRAMES
    assert cut.segments[0].frame_end == cut.segments[1].frame_start
    assert [s.description for s in cut.segments] == ["pick up the cup", "place the cup"]
    assert {s.label_source for s in cut.segments} == {"rule"} and cut.unresolved_share == 0


def test_a_tail_after_the_last_release_stays_in_its_place() -> None:
    events = [Event("grasp", 10, None), Event("release", 20, None), Event("grasp", 30, None),
              Event("release", 40, None)]
    assert pick_place_steps(events, 50) == [("pick", 0, 10), ("place", 10, 20),
                                            ("pick", 20, 30), ("place", 30, 50)]
    assert pick_place_steps([], 50) == [("pick", 0, 50)]


def test_a_still_hand_gives_no_event_and_counts_as_unresolved(cfg: EgoConfig) -> None:
    pose = synthetic_pose()
    still = replace(pose, right_wrist=np.repeat(pose.right_wrist[:1], FRAMES, axis=0))
    cut = cut_episode(still, 30.0, "pick_place", cfg.segment, instruction="", obj="cup")
    assert cut.events == [] and cut.unresolved_share == 1.0
    assert len(cut.segments) == 1


def low_confidence(pose: EgoPose) -> EgoPose:
    return replace(pose, confidence_right=np.full(FRAMES, 0.1, dtype=np.float32))


def test_an_ambiguous_event_goes_to_the_model_and_takes_its_frame(cfg: EgoConfig) -> None:
    suggester = FakeSuggester(answer=47)
    cut = cut_episode(low_confidence(synthetic_pose()), 30.0, "pick_place", cfg.segment,
                      instruction="Pick up the cup.", obj="cup", suggester=suggester,
                      frames_of=frames_of, model_names={"segment_suggester": "robobrain@x"})
    assert [e.reasons for e in cut.events] == [["low_confidence"], ["low_confidence"]]
    assert len(suggester.calls) == 2 and len(suggester.calls[0][0]) <= cfg.segment.model_frames
    assert cut.events[0].frame == 47 and cut.events[0].source == "model"
    assert cut.segments[0].frame_end == 47 and cut.segments[0].label_source == "model"
    assert cut.unresolved_share == 0 and cut.models == {"segment_suggester": "robobrain@x"}


def test_without_an_answer_the_rule_stays_and_is_counted(cfg: EgoConfig) -> None:
    cut = cut_episode(low_confidence(synthetic_pose()), 30.0, "pick_place", cfg.segment,
                      instruction="", obj="cup", suggester=FakeSuggester(None),
                      frames_of=frames_of)
    assert cut.unresolved_share == 1.0 and {s.label_source for s in cut.segments} == {"rule"}


def test_the_labeler_writes_each_sentence(cfg: EgoConfig) -> None:
    cut = cut_episode(synthetic_pose(), 30.0, "pick_place", cfg.segment, instruction="",
                      obj="cup", labeler=FakeLabeler(), frames_of=frames_of,
                      model_names={"labeler": "robobrain@x"})
    assert [s.description for s in cut.segments] == ["pick the cup now", "place the cup now"]
    assert {s.label_source for s in cut.segments} == {"model"}


def test_two_table_maps_events_and_the_walk_to_six_steps(cfg: EgoConfig) -> None:
    pose = synthetic_pose()
    camera = pose.camera.copy()
    camera[60:80, 2, 3] = np.linspace(0, 2.0, 20)  # the person walks between the tables
    camera[80:, 2, 3] = 2.0
    _, events, _ = find_events(pose, 30.0, cfg.segment)
    from flywheel.data.ingest.egocentric.segments import camera_speed

    steps, notes = two_table_steps(events, camera_speed(replace(pose, camera=camera), 30.0, 5),
                                   FRAMES, cfg.segment)
    assert [s[0] for s in steps] == ["approach", "grasp", "walk", "arrive", "place", "release"]
    assert steps[0][1] == 0 and steps[-1][2] == FRAMES and notes == []
    walk = dict((s[0], s[1:]) for s in steps)["walk"]
    assert 55 <= walk[0] <= 62 and 78 <= walk[1] <= 85


def test_segments_parquet_round_trips_and_is_the_contract_plus_frames(
    tmp_path: Path, cfg: EgoConfig
) -> None:
    cut = cut_episode(synthetic_pose(), 30.0, "pick_place", cfg.segment, instruction="",
                      obj="cup")
    path = tmp_path / "segments.parquet"
    write_segment_table(path, cut.segments, 30.0)
    assert read_segment_rows(path) == cut.segments
    table = pq.read_table(path)
    assert table.column_names == [*Segment.model_fields, "frame_start", "frame_end"]
    rows = table.to_pylist()
    assert rows[0]["t_end"] == pytest.approx(rows[0]["frame_end"] / 30.0)
    pq.write_table(pa.table({"t_start": [0.0]}), tmp_path / "bad.parquet")
    with pytest.raises(ValueError, match="schema"):
        read_segment_rows(tmp_path / "bad.parquet")


def test_the_same_pose_gives_the_same_segments(cfg: EgoConfig) -> None:
    first = cut_episode(synthetic_pose(), 30.0, "pick_place", cfg.segment, instruction="",
                        obj="cup").segments
    assert cut_episode(synthetic_pose(), 30.0, "pick_place", cfg.segment, instruction="",
                       obj="cup").segments == first
    assert all(isinstance(s, EgoSegment) for s in first)

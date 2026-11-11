"""Subtasks of the Human-1M view: tray phases from keyframe marks, EgoDex rule segments
tiled over the episode, the hand named (DA-04 11.2, 11/11/2026)."""

from __future__ import annotations

import pytest
from flywheel.data.export.human1m.subtasks import (
    Marks,
    Subtask,
    merge_short,
    rule_subtasks,
    tile,
    tray_subtasks,
    with_hand,
)

TEMPLATES = {k: k.upper() for k in ("grasp", "carry", "place", "grasp+carry", "carry+place",
                                    "grasp+carry+place")}


def test_short_phases_merge_into_their_neighbour() -> None:
    pieces = merge_short([(("grasp",), 0, 5), (("carry",), 5, 60), (("place",), 60, 80)], 9)
    assert pieces == [(("grasp", "carry"), 0, 60), (("place",), 60, 80)]
    assert merge_short([(("a",), 0, 3), (("b",), 3, 5)], 10) == [(("a", "b"), 0, 5)]


def test_tray_subtasks_tile_the_clip_with_the_merged_sentence() -> None:
    subs = tray_subtasks(90, 30.0, Marks(lift=12, place=60), TEMPLATES, 0.3, "kf", "TASK", "fb")
    assert [(s.start, s.end, s.text) for s in subs] == [
        (0, 12, "GRASP"), (12, 60, "CARRY"), (60, 90, "PLACE")]
    short = tray_subtasks(90, 30.0, Marks(lift=4, place=60), TEMPLATES, 0.3, "kf", "TASK", "fb")
    assert [(s.start, s.end, s.text) for s in short] == [(0, 60, "GRASP+CARRY"),
                                                         (60, 90, "PLACE")]
    none = tray_subtasks(90, 30.0, None, TEMPLATES, 0.3, "kf", "TASK", "fb")
    assert none == [Subtask(0, 90, "TASK", "fb")]
    with pytest.raises(ValueError):
        tray_subtasks(90, 30.0, Marks(lift=70, place=60), TEMPLATES, 0.3, "kf", "T", "fb")


def test_rule_segments_tile_the_episode_and_name_the_hand() -> None:
    assert tile([(10, 40, "a"), (50, 80, "b")], 100) == [(0, 45, "a"), (45, 100, "b")]
    assert tile([(0, 60, "a"), (50, 80, "b")], 100) == [(0, 55, "a"), (55, 100, "b")]
    assert with_hand("pick up the bowl", "right") == "Pick up the bowl with the right hand."
    assert with_hand("place the cup.", None) == "Place the cup."
    subs = rule_subtasks([(5, 20, "pick up the cup")], 30, "left", "rule", "TASK", "fb")
    assert subs == [Subtask(0, 30, "Pick up the cup with the left hand.", "rule")]
    assert rule_subtasks([], 30, "left", "rule", "TASK", "fb") == [Subtask(0, 30, "TASK", "fb")]

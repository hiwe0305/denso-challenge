"""Dynamic ReplayReport from one line of replay_outcomes.jsonl (DA-17 task 2, AC 2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from flywheel.data.replay_check.dynamic import ReplayOutcome, read_outcomes, report_from_outcome
from replay_data import loose_thresholds

TH = loose_thresholds()  # state_error 0.5 per group, hand offset 10 steps


def line(**changes: Any) -> str:
    base: dict[str, Any] = {
        "episode_index": 3,
        "success": True,
        "state_error_by_group": {"hand": 0.1, "arm": 0.05, "torso_rpy": 0.01},
        "hand_event_offset_steps": 2,
        "state_error_peak_frame_by_group": {"hand": 40, "arm": 12, "torso_rpy": 7},
        "replayed_frames": 590,
        "recorded_frames": 581,
    }
    return json.dumps({**base, **changes})


def report(**changes: Any) -> dict[str, list[int]]:
    r = report_from_outcome("ep_3", ReplayOutcome.from_json(line(**changes)), TH)
    assert r.mode == "dynamic" and r.episode_id == "ep_3"
    return {i.code: i.frames for i in r.issues}


def test_clean_replay_has_no_issue_and_carries_its_numbers() -> None:
    r = report_from_outcome("ep_3", ReplayOutcome.from_json(line()), TH)
    assert r.issues == []
    assert r.error_by_group == {"hand": 0.1, "arm": 0.05, "torso_rpy": 0.01}
    assert r.hand_event_offset_steps == 2 and r.sim_success is True


def test_group_over_threshold_points_at_its_peak_frame() -> None:
    errors = {"hand": 0.1, "arm": 0.9, "torso_rpy": 0.01}
    assert report(state_error_by_group=errors) == {"state_error": [12]}


def test_failed_replay_is_an_issue_and_sim_success_false() -> None:
    r = report_from_outcome("ep_3", ReplayOutcome.from_json(line(success=False)), TH)
    assert [i.code for i in r.issues] == ["replay_failed"] and r.sim_success is False
    assert "590 of 581" in r.issues[0].detail


@pytest.mark.parametrize("offset", [11, -11])
def test_hand_event_off_either_way(offset: int) -> None:
    assert report(hand_event_offset_steps=offset) == {"hand_event_offset": []}


def test_no_hand_event_is_no_issue() -> None:
    assert report(hand_event_offset_steps=None) == {}


def test_only_the_four_fields_of_the_plan_are_required() -> None:
    minimal = {k: json.loads(line())[k] for k in ("episode_index", "success",
                                                   "state_error_by_group",
                                                   "hand_event_offset_steps")}
    outcome = ReplayOutcome.from_json(json.dumps(minimal))
    assert report_from_outcome("e", outcome, TH).issues == []


@pytest.mark.parametrize(
    "bad",
    [
        {"success": "yes"},
        {"state_error_by_group": {"arm": float("nan")}},
        {"episode_index": 1.5},
        {"extra": 1},
    ],
)
def test_malformed_line_raises(bad: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        ReplayOutcome.from_json(line(**bad))


def test_read_outcomes_names_the_line_and_refuses_twice(tmp_path: Path) -> None:
    path = tmp_path / "replay_outcomes.jsonl"
    path.write_text(line() + "\n\n" + line(episode_index=4) + "\n")
    assert sorted(read_outcomes(path)) == [3, 4]
    path.write_text(line() + "\n" + line() + "\n")
    with pytest.raises(ValueError, match=":2: episode 3 replayed twice"):
        read_outcomes(path)

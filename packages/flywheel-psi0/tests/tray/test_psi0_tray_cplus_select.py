"""The C+ selection rule of docs/he/tray.md 17.3, on toy conditions (DA-34 task 5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel_psi0.tray.cplus_select import Pick, candidates_of, select

CONDITIONS = ["a", "b", "c", "d"]
PLACE = {"a": 0.08, "b": 0.30, "c": 0.12, "d": 0.20}
CANDIDATES = {
    "a": [(0.1, 10), (0.2, 11)],
    "b": [(0.3, 20), (0.4, 21)],
    "c": [(0.1, 30), (0.5, 31)],
    "d": [(0.2, 40), (0.3, 41)],
}


def test_step_1_takes_the_nearest_passing_seed_in_file_order() -> None:
    picks, unserved = select(CONDITIONS, PLACE, CANDIDATES, {11, 20, 21, 30, 40}, 4)
    assert picks == [
        Pick("a", 11, 1, 1, 0.2),  # 10 failed QA: the next nearest passing one
        Pick("b", 20, 1, 1, 0.3),
        Pick("c", 30, 1, 1, 0.1),
        Pick("d", 40, 1, 1, 0.2),
    ]
    assert unserved == []


def test_step_2_adds_second_seeds_largest_place_error_first() -> None:
    passing = {10, 11, 20, 21, 30, 31, 40, 41}
    picks, _ = select(CONDITIONS, PLACE, CANDIDATES, passing, 6)
    assert [(p.cluster_id, p.seed, p.step) for p in picks[4:]] == [("b", 21, 2), ("d", 41, 2)]
    picks, _ = select(CONDITIONS, PLACE, CANDIDATES, passing, 99)
    assert len(picks) == 8  # every second seed, then it stops short


def test_a_condition_with_no_passing_seed_is_returned_for_step_3() -> None:
    picks, unserved = select(CONDITIONS, PLACE, CANDIDATES, {20, 21, 30, 40}, 5)
    assert [p.seed for p in picks] == [20, 30, 40, 21]
    assert unserved == ["a"]


def test_a_tie_in_place_error_keeps_the_file_order() -> None:
    place = dict.fromkeys(CONDITIONS, 0.1)
    passing = {10, 11, 20, 21, 30, 31, 40, 41}
    picks, _ = select(CONDITIONS, place, CANDIDATES, passing, 5)
    assert picks[-1] == Pick("a", 11, 2, 2, 0.2)


def _targets(path: Path, sha: str, rows: list[tuple[str, int, float]]) -> Path:
    path.write_text(
        "".join(
            json.dumps(
                {
                    "conditions_sha256": sha,
                    "target": {"seed": s, "level": 1, "cluster_id": c, "distance": d},
                }
            )
            + "\n"
            for c, s, d in rows
        )
    )
    return path


def test_candidates_are_nearest_first_and_from_one_conditions_file(tmp_path: Path) -> None:
    first = _targets(tmp_path / "t1.jsonl", "x" * 64, [("a", 11, 0.2), ("a", 10, 0.1)])
    top_up = _targets(tmp_path / "t2.jsonl", "x" * 64, [("a", 12, 0.05)])
    assert candidates_of([first, top_up], "x" * 64) == {"a": [(0.05, 12), (0.1, 10), (0.2, 11)]}
    with pytest.raises(ValueError, match="another conditions file"):
        candidates_of([first], "y" * 64)
    clash = _targets(tmp_path / "t3.jsonl", "x" * 64, [("b", 10, 0.3)])
    with pytest.raises(ValueError, match="seed 10 is a target of a and b"):
        candidates_of([first, clash], "x" * 64)

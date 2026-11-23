"""Tools that read the eval outcome (K1): `signal_presence` and `relaxed_sweep` (DA-43 2.4).

The outcomes are built here with the contract class, so each test states which measure a
rollout carries. The relaxed grid and the measure names are the tray task view's.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import RunOutcomes, RunScores, ToolResult
from flywheel.eval.agentqa.tools.relaxed import relaxed_sweep
from flywheel.eval.agentqa.tools.signals import signal_presence
from flywheel.eval.agentqa.tools.task import TaskView, load_task
from helpers_tools import labelled, outcome, outcomes_of

PLACE = "L-PLACE-POSE"
POSE = {"tray_pos_m": [0.0, 0.0, 0.8], "tray_quat": [1.0, 0.0, 0.0, 0.0],
        "target_xy_m": [0.0, 0.0], "target_yaw_rad": 0.0}


def named(book: FactBook, result: ToolResult) -> dict[str, Any]:
    return {book.get(f).name: book.get(f).value for f in result.facts}


def by_source(book: FactBook, name: str) -> dict[str, Any]:
    return {f.source_ref: f.value for f in book.facts if f.name == name}


def place(d: float | None, yaw: float | None, **pose: Any) -> dict[str, object]:
    final: dict[str, object] = dict(POSE, **pose)
    if d is not None:
        final["place_distance_m"] = d
    if yaw is not None:
        final["place_yaw_error_deg"] = yaw
    return final


# --- the task view ----------------------------------------------------------------------


def test_the_measure_names_live_in_one_block_of_the_task_view(tray: TaskView) -> None:
    assert tray.signal_measures["final_tray_pose"].names == ["tray_pos_m", "tray_quat"]
    assert tray.signal_measures["failure_t"].where == "verdict"
    assert tray.relaxed is not None
    assert tray.relaxed_measures() == ("place_distance_m", "place_yaw_error_deg")
    assert "outcomes" in tray.provides


@pytest.mark.parametrize("edit, match", [
    (lambda raw: raw["signal_measures"].update(x={"where": "verdict", "names": ["nope"]}),
     "not a field"),
    (lambda raw: raw["relaxed"].update(signal="ghost"), "signal_measures"),
    (lambda raw: raw["signal_measures"]["place_error"].update(names=["place_distance_m"]),
     "_deg"),
    (lambda raw: raw["signal_measures"]["place_error"].update(where="extrema"), "final"),
    (lambda raw: raw["signal_measures"]["failure_t"].update(names=["Bad Name"]), "pattern"),
])
def test_a_bad_measure_declaration_is_refused(tmp_path: Path, edit: Any, match: str) -> None:
    src = Path("configs/eval/agentqa/tasks/tray.yaml")
    raw = yaml.safe_load(src.read_text())
    raw["scorer_config"] = str(Path("configs/eval/scorer/tray.yaml").resolve())
    edit(raw)
    (tmp_path / "tray.yaml").write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match=match):
        load_task("tray", tmp_path)


# --- signal_presence with outcomes --------------------------------------------------------


def two_place_failures(run: str) -> RunScores:
    return RunScores(run, f"{run}/scores.jsonl", (
        labelled(run, "a", True), labelled(run, "b", False, PLACE),
        labelled(run, "c", False, PLACE)))


def test_without_outcomes_the_result_is_the_one_of_provides(tray: TaskView) -> None:
    run = two_place_failures("R")
    old, new = FactBook(), FactBook()
    a = signal_presence(old, tray, ["scores", "trace"], [PLACE])
    b = signal_presence(new, tray, ["scores", "trace"], [PLACE], [run], {})
    assert old.facts == new.facts and a == b


def test_outcomes_that_carry_every_measure_make_the_label_judgeable(tray: TaskView) -> None:
    run = two_place_failures("R")
    held = outcomes_of("R", [outcome("R", "a", True, final=POSE),
                             outcome("R", "b", False, PLACE, final=POSE),
                             outcome("R", "c", False, PLACE, final=POSE)])
    book = FactBook()
    got = named(book, signal_presence(book, tray, ["scores", "outcomes"], [PLACE], [run],
                                      {"R": held}))
    assert got[f"{PLACE}_judgeable"] is True
    assert got[f"{PLACE}_signals_missing"] == "none"
    assert got["inputs_kinds"] == "outcomes, scores"
    assert "signal_presence_kinds_not_judged" not in got


def test_a_measure_missing_on_one_failure_names_the_measure(tray: TaskView) -> None:
    run = two_place_failures("R")
    lacking = {k: v for k, v in POSE.items() if k != "target_yaw_rad"}
    held = outcomes_of("R", [outcome("R", "b", False, PLACE, final=POSE),
                             outcome("R", "c", False, PLACE, final=lacking)])
    book = FactBook()
    got = named(book, signal_presence(book, tray, ["scores", "outcomes"], [PLACE], [run],
                                      {"R": held}))
    assert got[f"{PLACE}_judgeable"] is False
    assert got[f"{PLACE}_signals_missing"] == "target_pose (missing: final.target_yaw_rad)"


def test_a_null_measure_and_a_failure_without_outcome_count_as_missing(tray: TaskView) -> None:
    run = two_place_failures("R")
    held = outcomes_of("R", [outcome("R", "b", False, PLACE, final=dict(POSE, tray_quat=None))])
    book = FactBook()
    got = named(book, signal_presence(book, tray, ["scores", "outcomes"], [PLACE], [run],
                                      {"R": held}))
    assert got[f"{PLACE}_signals_missing"] == (
        "final_tray_pose (missing: final.tray_quat, outcome), target_pose (missing: outcome)")


def test_verdict_measures_are_read_from_the_verdict(tray: TaskView) -> None:
    run = RunScores("R", "R/scores.jsonl", (labelled("R", "d", False, "L-PART-DROP"),))
    held = outcomes_of("R", [outcome("R", "d", False, "L-PART-DROP")])
    book = FactBook()
    got = named(book, signal_presence(book, tray, ["scores", "outcomes"], ["L-PART-DROP"],
                                      [run], {"R": held}))
    # failure_t comes from the verdict now; part_positions has no measure declared
    assert got["L-PART-DROP_signals_missing"] == "part_positions"


def test_runs_that_differ_get_their_own_facts_under_the_same_names(tray: TaskView) -> None:
    good, bad = two_place_failures("G"), two_place_failures("B")
    held = {"G": outcomes_of("G", [outcome("G", n, False, PLACE, final=POSE) for n in "bc"])}
    book = FactBook()
    signal_presence(book, tray, ["scores", "outcomes"], [PLACE], [good, bad], held)
    judgeable = by_source(book, f"{PLACE}_judgeable")
    assert judgeable == {tray.source_ref: False, "G/scores.jsonl": True}
    missing = by_source(book, f"{PLACE}_signals_missing")
    assert missing[tray.source_ref] == ("final_tray_pose (missing: outcomes entry), "
                                        "target_pose (missing: outcomes entry)")
    assert missing["G/scores.jsonl"] == "none"


def test_runs_that_agree_get_no_fact_of_their_own(tray: TaskView) -> None:
    runs = [two_place_failures("G"), two_place_failures("H")]
    held = {r: outcomes_of(r, [outcome(r, n, False, PLACE, final=POSE) for n in "bc"])
            for r in ("G", "H")}
    book = FactBook()
    signal_presence(book, tray, ["scores", "outcomes"], [PLACE], runs, held)
    assert by_source(book, f"{PLACE}_judgeable") == {tray.source_ref: True}


# --- relaxed_sweep ------------------------------------------------------------------------


def sweep_set(run: str = "R") -> tuple[RunScores, RunOutcomes]:
    """Two successes; four place failures and one tilt failure with their final measures."""
    rows: list[tuple[str, bool, str | None, int, float | None, float | None]] = [
        ("ok1", True, None, 1, None, None),
        ("ok2", True, None, 2, None, None),
        ("p1", False, PLACE, 1, 0.06, 2.0),     # within from 0.075 m
        ("p2", False, PLACE, 1, 0.12, -3.0),    # within from 0.15 m; the yaw sign is ignored
        ("p3", False, PLACE, 2, 0.08, 15.0),    # never: the yaw stays the scorer's
        ("p4", False, PLACE, 2, 0.30, 0.0),     # never: beyond the grid
        ("t1", False, "L-TRAY-TILT", 1, 0.01, 0.0),  # never: another label is not relaxed
    ]
    scores = tuple(labelled(run, n, ok, lab, lv) for n, ok, lab, lv, _, _ in rows)
    outs = [outcome(run, n, ok, lab, lv, final=place(d, y)) for n, ok, lab, lv, d, y in rows]
    return RunScores(run, f"{run}/scores.jsonl", scores), outcomes_of(run, outs)


def test_relaxed_counts_on_a_hand_made_set(tray: TaskView) -> None:
    run, held = sweep_set()
    book = FactBook()
    result = relaxed_sweep(book, tray, [run], {"R": held})
    got = named(book, result)
    assert result.judged
    assert [got[f"R_relaxed_all_pos{k}_successes"] for k in range(1, 6)] == [2, 3, 3, 4, 4]
    assert [got[f"R_relaxed_l1_pos{k}_successes"] for k in range(1, 6)] == [1, 2, 2, 3, 3]
    assert [got[f"R_relaxed_l2_pos{k}_successes"] for k in range(1, 6)] == [1, 1, 1, 1, 1]
    assert (got["R_relaxed_all_rollouts"], got["R_relaxed_all_successes"]) == (7, 2)
    assert got["R_relaxed_first_grid_matches_scorer"] is True
    assert got["R_relaxed_scorer_mismatch"] == 0
    assert [got[f"relaxed_position_{k}"] for k in range(1, 6)] == [0.05, 0.075, 0.10, 0.15, 0.20]
    assert got["relaxed_position_widest"] == 0.20
    assert (got["relaxed_yaw_tolerance"], got["relaxed_label"]) == (10.0, PLACE)
    units = {book.get(f).name: book.get(f).unit for f in result.facts}
    assert units["relaxed_position_1"] == "m" and units["relaxed_yaw_tolerance"] == "deg"
    assert units["R_relaxed_all_pos1_successes"] == "rollouts"
    sweep = [r for r in result.rows if r["part"] == "all"]
    assert [r["relaxed_successes"] for r in sweep] == [2, 3, 3, 4, 4]
    assert set(result.rows[0]) == {"run", "part", "position_m", "yaw_deg", "rollouts",
                                   "scorer_successes", "relaxed_successes"}


def test_a_place_failure_within_the_scorer_tolerance_is_a_mismatch(tray: TaskView) -> None:
    run, held = sweep_set()
    extra_s = labelled("R", "p0", False, PLACE, 1)
    extra_o = outcome("R", "p0", False, PLACE, 1, final=place(0.03, 1.0))
    run = RunScores("R", run.ref, (*run.scores, extra_s))
    held = RunOutcomes("R", held.ref, (*held.outcomes, extra_o))
    book = FactBook()
    got = named(book, relaxed_sweep(book, tray, [run], {"R": held}))
    assert got["R_relaxed_first_grid_matches_scorer"] is False
    assert got["R_relaxed_scorer_mismatch"] == 1
    assert got["R_relaxed_all_pos1_successes"] == 3


def test_per_cluster_placement_and_the_near_miss(tray: TaskView) -> None:
    run, held = sweep_set()
    book = FactBook()
    result = relaxed_sweep(book, tray, [run], {"R": held})
    got = named(book, result)
    l1, l2 = "R_cluster_place_L-PLACE-POSE_l1", "R_cluster_place_L-PLACE-POSE_l2"
    assert got[f"{l1}_relaxed_distance_median"] == pytest.approx(0.09)
    assert got[f"{l1}_relaxed_distance_max"] == pytest.approx(0.12)
    assert [got[f"{l1}_relaxed_within_pos{k}"] for k in range(1, 6)] == [0, 1, 1, 2, 2]
    assert got[f"{l1}_relaxed_within_widest"] == 2
    assert got[f"{l1}_near_miss"] is True
    assert got[f"{l2}_relaxed_within_widest"] == 0 and got[f"{l2}_near_miss"] is False
    assert not any(n.startswith("R_cluster_place_L-TRAY-TILT") for n in got)
    rows = [r for r in result.rows if r["part"] == "cluster place_L-PLACE-POSE_l1"]
    assert [r["relaxed_successes"] for r in rows] == [0, 1, 1, 2, 2]


def test_half_the_members_within_is_not_a_majority(tray: TaskView) -> None:
    scores = (labelled("R", "a", False, PLACE), labelled("R", "b", False, PLACE))
    outs = [outcome("R", "a", False, PLACE, final=place(0.1, 0.0)),
            outcome("R", "b", False, PLACE, final=place(0.5, 0.0))]
    book = FactBook()
    got = named(book, relaxed_sweep(book, tray, [RunScores("R", "R/s", scores)],
                                    {"R": outcomes_of("R", outs)}))
    assert got["R_cluster_place_L-PLACE-POSE_l1_near_miss"] is False


def test_a_run_without_outcomes_is_not_judged(tray: TaskView) -> None:
    run, _ = sweep_set()
    book = FactBook()
    result = relaxed_sweep(book, tray, [run], {})
    got = named(book, result)
    assert not result.judged
    assert "no outcomes entry" in got["relaxed_sweep_R_not_judged"]
    assert not any(n.startswith("R_relaxed") for n in got)


def test_a_missing_measure_makes_the_run_not_judged_with_its_name(tray: TaskView) -> None:
    run, held = sweep_set()
    outs = tuple(o.model_copy(update={"final": {"place_distance_m": 0.12}})
                 if o.episode_id == "R/p2" else o for o in held.outcomes)
    book = FactBook()
    result = relaxed_sweep(book, tray, [run], {"R": RunOutcomes("R", held.ref, outs)})
    got = named(book, result)
    assert not result.judged
    assert "place_yaw_error_deg" in got["relaxed_sweep_R_not_judged"]
    assert "R_relaxed_all_pos1_successes" not in got


def test_a_place_failure_without_outcome_makes_the_run_not_judged(tray: TaskView) -> None:
    run, held = sweep_set()
    outs = tuple(o for o in held.outcomes if o.episode_id != "R/p1")
    book = FactBook()
    got = named(book, relaxed_sweep(book, tray, [run], {"R": RunOutcomes("R", held.ref, outs)}))
    assert "no outcome" in got["relaxed_sweep_R_not_judged"]
    assert got["R_scores_without_outcome"] == 1


def test_scores_and_outcomes_that_do_not_pair_are_reported(tray: TaskView) -> None:
    run, held = sweep_set()
    ghost = outcome("R", "ghost", True)
    flipped = outcome("R", "ok1", False, PLACE, final=place(0.06, 0.0))
    outs = tuple(flipped if o.episode_id == "R/ok1" else o for o in held.outcomes)
    outs = tuple(o for o in outs if o.episode_id != "R/ok2") + (ghost,)
    book = FactBook()
    result = relaxed_sweep(book, tray, [run], {"R": RunOutcomes("R", held.ref, outs)})
    got = named(book, result)
    assert got["R_outcomes_without_score"] == 1
    assert got["R_scores_without_outcome"] == 1       # ok2: a success needs no measure
    assert got["R_outcome_verdict_disagrees"] == 1    # ok1: the scores say success
    assert got["R_outcomes_matched"] == 6
    assert result.judged and got["R_relaxed_all_successes"] == 2  # the scores' own verdict


def test_outcomes_of_a_run_without_scores_are_reported(tray: TaskView) -> None:
    run, held = sweep_set()
    book = FactBook()
    got = named(book, relaxed_sweep(book, tray, [run], {
        "R": held, "X": outcomes_of("X", [outcome("X", "a", True)])}))
    assert "no scores entry" in got["relaxed_sweep_X_not_judged"]

"""Step pass table, failure clusters and paired comparison on the 60k stage 1 rollouts.

Every expected number is one the team published on the same rollouts: docs/he/tray.md
20.2 (clusters of `C_70`), 19.2 and the stage 1 tables of `eval_results` (step pass,
paired differences). DA-43 AC 1.
"""

from __future__ import annotations

import pytest
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import RunScores, ToolResult
from flywheel.eval.agentqa.tools.clusters import failure_clusters
from flywheel.eval.agentqa.tools.paired import mcnemar_exact, paired_compare, wilson
from flywheel.eval.agentqa.tools.steps import step_pass_table
from flywheel.eval.agentqa.tools.task import TaskView


def named(book: FactBook, result: ToolResult) -> dict[str, object]:
    return {book.get(f).name: book.get(f).value for f in result.facts}


def test_step_pass_shows_the_drop_at_place(tray: TaskView, runs: dict[str, RunScores]) -> None:
    book = FactBook()
    got = named(book, step_pass_table(book, tray, [runs["C_ALL"]]))
    # stage1-C_ALL-table.json, headline (levels 1-2)
    assert got["C_ALL_all_rollouts"] == 60 and got["C_ALL_all_successes"] == 5
    assert got["C_ALL_all_pass_approach_a"] == pytest.approx(0.7333, abs=1e-4)
    assert got["C_ALL_all_pass_reach_b"] == pytest.approx(0.65)
    assert got["C_ALL_all_pass_place"] == pytest.approx(0.10)
    assert got["C_ALL_all_largest_drop_step"] == "place"
    assert got["C_ALL_l1_pass_approach_a"] == pytest.approx(0.6333, abs=1e-4)
    assert got["C_ALL_l2_pass_carry"] == pytest.approx(0.7333, abs=1e-4)


def test_a_run_without_step_states_is_not_judged(tray: TaskView,
                                                  runs: dict[str, RunScores]) -> None:
    bare = RunScores("X", "pack/X/scores.jsonl", tuple(
        s.model_copy(update={"step_status": []}) for s in runs["C_70"].scores[:3]))
    book = FactBook()
    result = step_pass_table(book, tray, [bare])
    assert not result.judged and "lack the 7 step states" in result.not_judged[0]


def test_clusters_of_c70_are_the_ones_of_tray_md_20_2(tray: TaskView,
                                                       runs: dict[str, RunScores]) -> None:
    book = FactBook()
    result = failure_clusters(book, tray, [runs["C_70"], runs["C_ALL"], runs["B_70"]])
    got = named(book, result)
    assert got["C_70_failures"] == 50
    expected = {
        "place_L-PLACE-POSE_l1": 14,          # c1
        "place_L-PLACE-POSE_l2": 12,          # c2
        "approach_a_L-TIMEOUT_l1": 4,         # c3
        "release_stand_L-TRAY-TILT_l2": 4,    # c4
        "place_L-TRAY-TILT_l2": 3,            # c5
        "approach_a_L-PLACE-POSE_l2": 3,      # c6
        "approach_a_L-PLACE-POSE_l1": 2,      # c7
        "approach_a_L-TIMEOUT_l2": 2,         # c8
    }
    for key, size in expected.items():
        assert got[f"C_70_cluster_{key}_size"] == size, key
    rows = [r for r in result.rows if r["run"] == "C_70"]
    assert rows[0]["first_failed_step"] == "place" and rows[0]["size"] == 14
    assert sum(int(r["size"]) for r in rows) == 50
    # c6 and c7 (approach_a, L-PLACE-POSE) repeat in both other runs (tray.md 20.11, H1)
    assert got["C_70_cluster_approach_a_L-PLACE-POSE_l2_in_other_runs"] == 2


@pytest.mark.parametrize(("a", "b", "diff", "ci", "a_only", "b_only", "p"), [
    ("C_70", "C_ALL", 0.0833, (-0.0167, 0.1833), 8, 3, 0.2266),     # (g)
    ("B_70", "C_70", -0.05, (-0.1833, 0.0833), 7, 10, 0.6291),      # (a')
    ("B_ALL", "C_ALL", 0.0167, (-0.0833, 0.1167), 6, 5, 1.0),       # (h)
    ("B_70", "C_ALL", 0.0333, (-0.0833, 0.15), 7, 5, 0.7744),       # (f)
])
def test_paired_compare_gives_the_published_stage1_numbers(
    runs: dict[str, RunScores], a: str, b: str, diff: float, ci: tuple[float, float],
    a_only: int, b_only: int, p: float,
) -> None:
    book = FactBook()
    got = named(book, paired_compare(book, runs[a], runs[b], [1, 2]))
    name = f"{a}_vs_{b}_l1+2"
    assert got[f"{name}_conditions"] == 60
    assert got[f"{name}_diff"] == diff
    assert (got[f"{name}_ci_low"], got[f"{name}_ci_high"]) == ci
    assert got[f"{name}_ci_vs_0"] == "contains"
    assert (got[f"{name}_{a}_only"], got[f"{name}_{b}_only"]) == (a_only, b_only)
    assert got[f"{name}_mcnemar_exact_p"] == p


def test_paired_compare_refuses_runs_on_other_conditions(runs: dict[str, RunScores]) -> None:
    short = RunScores("S", "pack/S/scores.jsonl", runs["C_ALL"].scores[:10])
    book = FactBook()
    result = paired_compare(book, runs["C_70"], short, [1, 2])
    assert not result.judged and "different conditions" in result.not_judged[0]


def test_wilson_and_mcnemar() -> None:
    low, high = wilson(1, 20)
    assert low == pytest.approx(0.0089, abs=1e-4) and high == pytest.approx(0.2361, abs=1e-4)
    assert mcnemar_exact(0, 0) == 1.0 and mcnemar_exact(11, 0) < 0.001

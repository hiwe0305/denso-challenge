"""`coverage_distance` on small synthetic conditions with hand-computed answers (task 3.3).

CROSS-CHECK OWED: docs/he/tray.md reports tau_cov 1.143 (level 1) and 1.524 (level 2) for
the tray task. The train conditions that produce them are not in the repo (the repo holds
seeds, not condition vectors, and the adapter's vector layout is not written anywhere), so
these tests do not reproduce those two numbers.
"""

from __future__ import annotations

import pytest
from flywheel.contracts.entities import Condition
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import ConditionSet, RunScores, ToolResult
from flywheel.eval.agentqa.tools.coverage import coverage_distance
from flywheel.eval.agentqa.tools.task import Component, CoverageSpec, TaskView, load_task
from helpers_tools import condition, score

SPEC = CoverageSpec(
    k=2, percentile=95,
    components=[Component(name="x", scale=1.0), Component(name="yaw", scale=1.0, periodic=True)],
    level_components={1: ["x"], 2: ["x", "yaw"]}, pool_levels=False)
POOLED = SPEC.model_copy(update={"pool_levels": True})


def xy(x: float, yaw: float = 0.0) -> dict[str, object]:
    return {"x": x, "yaw": yaw}


TRAIN = ConditionSet("train.jsonl", "train", tuple(
    [condition(1, s, xy(float(s), 0.0)) for s in range(5)]
    + [condition(2, 10, xy(0.0, 3.1)), condition(2, 11, xy(0.0, -3.1)),
       condition(2, 12, xy(0.0, 3.0))]))


def task(spec: CoverageSpec = SPEC) -> TaskView:
    return load_task("tray").model_copy(update={"coverage": spec})


def failures(spec: dict[str, str]) -> RunScores:
    """`spec`: episode name -> failure label; every rollout failed at step 1."""
    scores = []
    for name, label in spec.items():
        s = score("R", name, False).model_copy(update={
            "failure_kind": label, "first_failed_step": 1, "level": int(name[1])})
        scores.append(s)
    return RunScores("R", "R/scores.jsonl", tuple(scores))


def evals(*conds: Condition) -> ConditionSet:
    return ConditionSet("eval.jsonl", "eval", conds)


def run(run: RunScores, *sets: ConditionSet,
        spec: CoverageSpec = SPEC) -> tuple[ToolResult, dict[str, object]]:
    book = FactBook()
    result = coverage_distance(book, task(spec), [run], sets)
    return result, {book.get(f).name: book.get(f).value for f in result.facts}


def test_tau_cov_is_the_leave_one_out_percentile_of_the_mean_knn_distance() -> None:
    # level 1, x = 0..4, k = 2: leave-one-out means 1.5, 1, 1, 1, 1.5 -> p95 = 1.5
    _, got = run(failures({"l1-s20": "L-A"}), TRAIN, evals(condition(1, 20, xy(2.5, 0.0))))
    assert got["tau_cov_l1"] == pytest.approx(1.5) and got["coverage_train_l1"] == 5
    assert got["coverage_k"] == 2 and got["coverage_percentile"] == 95.0


def test_an_angle_takes_the_shorter_way_round() -> None:
    # level 2: (3.1, -3.1, 3.0) in yaw; wrapped gaps 0.0831853, 0.1, 0.1831853 -> p95 0.1407519
    _, got = run(failures({"l2-s21": "L-A"}), TRAIN, evals(condition(2, 21, xy(0.0, 3.05))))
    assert got["tau_cov_l2"] == pytest.approx(0.1407519, abs=1e-6)


def test_each_cluster_gets_its_distance_domain_and_count_above_tau() -> None:
    rollouts = failures({"l1-s20": "L-A", "l1-s21": "L-A", "l1-s22": "L-B"})
    result, got = run(rollouts, TRAIN, evals(
        condition(1, 20, xy(6.0)), condition(1, 21, xy(2.5)), condition(1, 22, xy(2.5))))
    a = "R_cluster_grasp_L-A_l1_coverage"
    b = "R_cluster_grasp_L-B_l1_coverage"
    # x = 6: nearest 4 and 3 -> 2.5 (above 1.5, outside [0, 4]); x = 2.5: 0.5 (inside)
    assert got[f"{a}_d_mean"] == pytest.approx(1.5) and got[f"{a}_above_tau"] == 1
    assert got[f"{a}_matched"] == 2 and got[f"{a}_in_domain"] is False
    assert got[f"{b}_d_mean"] == pytest.approx(0.5) and got[f"{b}_above_tau"] == 0
    assert got[f"{b}_in_domain"] is True
    assert result.judged and {r["cluster"] for r in result.rows} == {
        "grasp_L-A_l1", "grasp_L-B_l1"}


def test_components_are_read_by_name_not_by_position() -> None:
    swapped = ConditionSet("train.jsonl", "train", tuple(
        Condition(condition_seed=s, level=1, values={"yaw": 0.0, "x": float(s)},
                  vector=[9.0, 9.0], layout_hash="h") for s in range(5)))
    _, got = run(failures({"l1-s20": "L-A"}), swapped, evals(condition(1, 20, xy(2.5))))
    assert got["tau_cov_l1"] == pytest.approx(1.5)


@pytest.mark.parametrize(("bad", "name"), [
    ({"yaw": 0.0}, "'x'"), ({"x": "far", "yaw": 0.0}, "'x'"), ({"x": True, "yaw": 0.0}, "'x'"),
    ({"x": float("nan"), "yaw": 0.0}, "'x'")])
def test_a_missing_or_non_numeric_component_names_itself_in_the_reason(
        bad: dict[str, object], name: str) -> None:
    train = ConditionSet("train.jsonl", "train", (*TRAIN.conditions[:5], condition(1, 50, bad)))
    result, got = run(failures({"l1-s20": "L-A"}), train, evals(condition(1, 20, xy(2.5))))
    assert name in got["coverage_distance_l1_not_judged"] and "tau_cov_l1" not in got  # type: ignore[operator]
    assert not result.judged


def test_an_eval_condition_without_a_component_is_not_judged_for_its_cluster() -> None:
    result, got = run(failures({"l1-s20": "L-A"}), TRAIN, evals(condition(1, 20, {"yaw": 0.0})))
    assert "'x'" in got["coverage_distance_R_grasp_L-A_l1_not_judged"]  # type: ignore[operator]
    assert got["tau_cov_l1"] == pytest.approx(1.5) and not result.rows


def test_failures_without_a_condition_are_counted_and_said() -> None:
    result, got = run(failures({"l1-s20": "L-A", "l1-s99": "L-A"}), TRAIN,
                      evals(condition(1, 20, xy(2.5, 0.0))))
    assert got["R_cluster_grasp_L-A_l1_coverage_matched"] == 1
    assert "1 failed rollouts have no condition" in got["coverage_distance_R_not_judged"]  # type: ignore[operator]
    assert not result.judged


@pytest.mark.parametrize(("sets", "text"), [
    ((ConditionSet("a.jsonl", "", TRAIN.conditions),), "does not declare subject.role"),
    ((TRAIN,), "role eval"),
    ((evals(condition(1, 20, xy(1.0, 0.0))),), "role train"),
])
def test_a_pack_that_does_not_say_which_is_train_and_eval_is_not_judged(
        sets: tuple[ConditionSet, ...], text: str) -> None:
    result, got = run(failures({"l1-s20": "L-A"}), *sets)
    assert not result.judged and text in result.not_judged[0]
    assert "coverage_distance_not_judged" in got and "tau_cov_l1" not in got


def test_too_few_train_conditions_is_not_judged_for_the_level() -> None:
    few = ConditionSet("train.jsonl", "train", TRAIN.conditions[:2])
    _, got = run(failures({"l1-s20": "L-A"}), few, evals(condition(1, 20, xy(1.0, 0.0))))
    assert "leave-one-out needs more than k = 2" in got["coverage_distance_l1_not_judged"]  # type: ignore[operator]


def test_a_task_view_without_a_coverage_block_is_not_judged() -> None:
    book = FactBook()
    bare = load_task("tray").model_copy(update={"coverage": None})
    result = coverage_distance(book, bare, [failures({"l1-s20": "L-A"})], [TRAIN])
    assert not result.judged and "no coverage block" in result.not_judged[0]


def test_the_tray_task_view_declares_the_block() -> None:
    spec = load_task("tray").coverage
    assert spec is not None and (spec.k, spec.percentile) == (5, 95.0)
    assert len(spec.components) == 10 and sorted(spec.level_components) == [1, 2]
    assert spec.pool_levels is True
    assert "light_scale" not in spec.level_components[2]  # light: the visual check of step 7
    assert "light_scale" in {c.name for c in spec.components}


# Pooled train set (spec 6.8: the train set is every train condition of the run)

# level 1 x = 0..4 plus two level-2 conditions at x = 100, 101: pooled and per-level differ
MIXED = ConditionSet("train.jsonl", "train", (
    *TRAIN.conditions[:5], condition(2, 10, xy(100.0)), condition(2, 11, xy(101.0))))


def test_the_default_pools_both_levels_for_tau_d_and_the_domain() -> None:
    probe = evals(condition(1, 20, xy(60.0)))
    _, per = run(failures({"l1-s20": "L-A"}), MIXED, probe)
    _, got = run(failures({"l1-s20": "L-A"}), MIXED, probe, spec=POOLED)
    assert per["tau_cov_l1"] == pytest.approx(1.5) and per["coverage_train_l1"] == 5
    # 7 train conditions, x = 0, 1, 2, 3, 4, 100, 101; leave-one-out means with k = 2:
    # 1.5, 1, 1, 1, 1.5, 48.5 (x = 100: 101 and 4), 49 (x = 101: 100 and 4); p95 = 48.85
    assert got["coverage_train_l1"] == 7
    assert got["tau_cov_l1"] == pytest.approx(48.85)
    a = "R_cluster_grasp_L-A_l1_coverage"
    # x = 60: nearest 100 and 101 -> mean 40.5 (per level: 4 and 3 -> 56.5)
    assert got[f"{a}_d_mean"] == pytest.approx(40.5)
    assert per[f"{a}_d_mean"] == pytest.approx(56.5)
    assert got[f"{a}_in_domain"] is True and per[f"{a}_in_domain"] is False  # [0, 101] vs [0, 4]


def test_a_level_two_vector_has_no_light() -> None:
    spec = load_task("tray").coverage
    assert spec is not None
    names = [c.name for c in spec.components if c.name in spec.level_components[2]]
    assert names == ["tray_x", "tray_y", "tray_yaw", "target_x", "target_y", "target_yaw",
                     "table_gap", "spawn_x", "part_mass"]


# Train conditions per run (subject.run)

def named(run_id: str, role: str, conds: tuple[Condition, ...]) -> ConditionSet:
    return ConditionSet(f"{role}-{run_id}.jsonl", role, conds, run=run_id)


def two_runs(*sets: ConditionSet) -> tuple[ToolResult, dict[str, object]]:
    book = FactBook()
    rolls = [failures({"l1-s20": "L-A"}), failures({"l1-s20": "L-A"})]
    rolls = [RunScores(n, f"{n}/scores.jsonl", r.scores) for n, r in zip(("R", "S"), rolls)]
    result = coverage_distance(book, task(), rolls, sets)
    return result, {book.get(f).name: book.get(f).value for f in result.facts}


WIDE = tuple(condition(1, s, xy(10.0 * s)) for s in range(5))  # x = 0, 10, .. 40


def test_pooled_output_is_unchanged_when_no_entry_names_a_run() -> None:
    result, got = run(failures({"l1-s20": "L-A"}), TRAIN, evals(condition(1, 20, xy(2.5, 0.0))))
    assert [f for f in got if "tau_cov" in f or "coverage_train" in f] == [
        "coverage_train_l1", "tau_cov_l1"]
    assert list(got)[:2] == ["coverage_k", "coverage_percentile"]
    assert got["tau_cov_l1"] == pytest.approx(1.5) and result.rows[0]["tau_cov"] == 1.5


def test_runs_with_different_train_sets_get_different_tau_and_verdicts() -> None:
    probe = evals(condition(1, 20, xy(15.0)))
    _, got = two_runs(named("R", "train", TRAIN.conditions[:5]), named("S", "train", WIDE),
                      probe)
    assert got["R_tau_cov_l1"] == pytest.approx(1.5) and got["S_tau_cov_l1"] == pytest.approx(15.0)
    assert got["R_coverage_train_l1"] == 5 and got["S_coverage_train_l1"] == 5
    assert "tau_cov_l1" not in got and "coverage_train_l1" not in got
    a, b = "R_cluster_grasp_L-A_l1_coverage", "S_cluster_grasp_L-A_l1_coverage"
    assert got[f"{a}_in_domain"] is False and got[f"{a}_above_tau"] == 1
    assert got[f"{b}_in_domain"] is True and got[f"{b}_above_tau"] == 0


def test_a_run_no_train_entry_names_falls_back_to_the_undeclared_train_entries() -> None:
    probe = evals(condition(1, 20, xy(15.0)))
    _, got = two_runs(named("S", "train", WIDE), TRAIN, probe)
    assert got["R_tau_cov_l1"] == pytest.approx(1.5)  # R reads the undeclared TRAIN
    assert got["S_tau_cov_l1"] == pytest.approx(15.0)
    assert "tau_cov_l1" not in got


def test_a_run_with_no_train_conditions_at_all_is_not_judged() -> None:
    result, got = two_runs(named("S", "train", WIDE), evals(condition(1, 20, xy(15.0))))
    assert "no conditions entry of the role train" in got["coverage_distance_R_not_judged"]  # type: ignore[operator]
    assert "S_tau_cov_l1" in got and "R_tau_cov_l1" not in got and not result.judged


def test_eval_entries_naming_a_run_win_over_the_undeclared_ones() -> None:
    _, got = two_runs(TRAIN, named("S", "eval", (condition(1, 20, xy(40.0)),)),
                      evals(condition(1, 20, xy(2.5))))
    assert got["R_cluster_grasp_L-A_l1_coverage_in_domain"] is True
    assert got["S_cluster_grasp_L-A_l1_coverage_in_domain"] is False
    assert got["tau_cov_l1"] == pytest.approx(1.5)  # train still pooled: names no run


def test_a_train_entry_naming_a_run_not_in_the_pack_is_said_not_ignored() -> None:
    result, got = two_runs(named("ghost", "train", WIDE), TRAIN, evals(condition(1, 20, xy(2.5))))
    assert "not in the pack" in got["coverage_distance_train_run_ghost_not_judged"]  # type: ignore[operator]
    assert any("ghost" in r for r in result.not_judged)

"""`measure_compare` and `measure_tally`: one measure of a cluster against a reference (DA-52).

A small run `R` built here: twelve successes, a cluster of four place failures (`place`,
level 1) and a cluster of two carry failures (`carry`, level 1). Each test states which
measure each rollout carries; the measure names are made up, so nothing here depends on a
real task's names.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.entities import Score
from flywheel.contracts.outcome import RolloutOutcome
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import ConditionSet, RunOutcomes, RunScores, ToolResult
from flywheel.eval.agentqa.tools.measures import domains, parse_ref
from flywheel.eval.agentqa.tools.registry import REGISTRY, MeasureContext, check_params
from flywheel.eval.agentqa.tools.task import MeasuresSpec, TaskView, measure_unit
from helpers_tools import condition, labelled

PLACE, TILT = "L-PLACE-POSE", "L-TRAY-TILT"
A = "R/place/L-PLACE-POSE/l1"  # four members
B = "R/carry/L-TRAY-TILT/l1"  # two members
BASE_A = "R_cluster_place_L-PLACE-POSE_l1"
SUCCESS_NAMES = [f"l1-s{k}" for k in range(12)]
A_NAMES = [f"l1-s{k}" for k in range(100, 104)]
B_NAMES = ["l1-s200", "l1-s201"]
SAME = "successes_same_level"
NONE_CARRY = "no rollout of the cluster carries the measure"


def quat_about_x(deg: float) -> list[float]:
    half = math.radians(deg) / 2
    return [math.cos(half), math.sin(half), 0.0, 0.0]


def outcome(name: str, success: bool, label: str | None = None, *,
            final: dict[str, Any] | None = None, extrema: dict[str, Any] | None = None,
            at_failure: dict[str, Any] | None = None) -> RolloutOutcome:
    return RolloutOutcome.model_validate({
        "episode_id": f"R/{name}", "run_plan_id": "rp-1", "task_id": "tray", "run": "R",
        "seed": 1, "level": 1, "sim_time_s": 10.0, "control_steps": 500,
        "final": final or {}, "extrema": extrema or {},
        "verdict": {"scorer_version": "2", "step_names": ["a", "b"],
                    "step_latched": [True, success], "success": success,
                    "failure_label": label, "failure_t": None if label is None else 4.0,
                    "at_failure": at_failure}})


def scores() -> RunScores:
    rows: list[Score] = [labelled("R", n, True) for n in SUCCESS_NAMES]
    rows += [labelled("R", n, False, PLACE) for n in A_NAMES]
    rows += [labelled("R", n, False, TILT, first_failed=3) for n in B_NAMES]
    return RunScores("R", "R/scores.jsonl", tuple(rows))


def default_outcomes() -> list[RolloutOutcome]:
    rows = [outcome(n, True, final={
        "gap_m": 0.01 * k, "pos_m": [0.0, 0.0, 0.80], "body_quat": quat_about_x(0.0),
        "err_deg": 1.0, "table": "B"}) for k, n in enumerate(SUCCESS_NAMES)]
    rows += [outcome(n, False, PLACE, final={
        "gap_m": 0.5, "pos_m": [0.0, 0.0, 0.85], "body_quat": quat_about_x(30.0),
        "err_deg": -20.0, "table": "B" if k else "A"},
        at_failure={"angle_deg": 5.0, "left": k % 2 == 0, "where": "B"})
        for k, n in enumerate(A_NAMES)]
    rows += [outcome(n, False, TILT, final={"gap_m": 0.02},
                     at_failure={"angle_deg": 25.0, "left": True, "where": "none"})
             for n in B_NAMES]
    return rows


def with_spec(task: TaskView, **update: Any) -> TaskView:
    assert task.measures is not None
    raw = task.measures.model_dump()
    raw.update(update)
    return task.model_copy(update={"measures": MeasuresSpec.model_validate(raw)})


def ctx_of(task: TaskView, rows: list[RolloutOutcome] | None = None,
           sets: tuple[ConditionSet, ...] = ()) -> MeasureContext:
    held = RunOutcomes("R", "R/outcomes.jsonl", tuple(default_outcomes() if rows is None
                                                       else rows))
    return MeasureContext(task, {"R": scores()}, frozenset({"scores", "outcomes"}),
                          outcomes={"R": held}, conditions=sets)


def call(tool: str, ctx: MeasureContext, cluster: str, measure: str, against: str,
         book: FactBook | None = None) -> tuple[FactBook, ToolResult, dict[str, Any]]:
    book = book or FactBook()
    params = {"cluster": cluster, "measure": measure, "against": against}
    assert check_params(REGISTRY[tool], params, ctx) == []
    result = REGISTRY[tool].run(book, ctx, params)
    return book, result, {book.get(f).name: book.get(f).value for f in result.facts}


@pytest.fixture
def ctx(tray: TaskView) -> MeasureContext:
    return ctx_of(tray)


# --- the config block -----------------------------------------------------------------------


def test_the_task_view_holds_the_measures_block(tray: TaskView) -> None:
    spec = tray.measures
    assert spec is not None
    assert (spec.low_percentile, spec.high_percentile) == (5, 95)
    for ref, threshold in spec.thresholds.items():
        assert threshold.threshold in tray.thresholds
        assert measure_unit(ref) == tray.threshold_units[threshold.threshold]


def test_a_threshold_of_another_unit_is_refused(tray: TaskView) -> None:
    raw = tray.model_dump()
    raw["measures"]["thresholds"] = {"final.gap_s": {"threshold": "target_pos_tol",
                                                     "beyond": "above"}}
    with pytest.raises(ValueError, match="in s, target_pos_tol in m"):
        TaskView.model_validate(raw)


def test_the_units_follow_the_name() -> None:
    assert measure_unit("final.a_m") == "m"
    assert measure_unit("final.a_m[2]") == "m"
    assert measure_unit("final.q_quat.tilt") == "deg"
    assert measure_unit("verdict.failure_t") == "s"
    assert measure_unit("verdict.step_latch_t[3]") == "s"
    assert measure_unit("condition.mass") == ""


def test_the_tool_code_names_no_measure_of_a_task() -> None:
    import flywheel.eval.agentqa.tools.measures as module

    text = Path(module.__file__).read_text(encoding="utf-8").lower()
    # "carry" is left out: the verb ("a rollout carries a measure") and the module
    # `tools.carry`, whose `measure_value` this one reuses.
    for word in ("tray", "height", "yaw", "place", "distance", "contact", "table", "hand",
                 "jig"):
        assert not re.search(rf"\b{word}", text), word
    assert not re.search(r"\bl-[a-z]", text)  # no failure label


# --- domains --------------------------------------------------------------------------------


def test_the_domains_are_read_off_the_pack(ctx: MeasureContext) -> None:
    found = domains(ctx.task, ctx.runs, ctx.outcomes, ctx.conditions)
    assert found.clusters == (B, A)
    assert {"final.gap_m", "final.pos_m[0]", "final.pos_m[2]", "final.body_quat.tilt",
            "at_failure.angle_deg", "verdict.failure_t"} <= set(found.numbers)
    assert not any(r.startswith("final.body_quat[") for r in found.numbers)
    assert set(found.categories) == {"final.table", "at_failure.left", "at_failure.where",
                                     "verdict.failure_label"}


@pytest.mark.parametrize(("tool", "params", "text"), [
    ("measure_compare", {"cluster": A, "measure": "final.nope_m", "against": SAME},
     "not a numeric measure"),
    ("measure_compare", {"cluster": A, "measure": 0.5, "against": SAME},
     "not a numeric measure"),
    ("measure_compare", {"cluster": A, "measure": "../vault/holdout.json",
                         "against": SAME}, "not a numeric measure"),
    ("measure_compare", {"cluster": A, "measure": "final.body_quat[0]",
                         "against": SAME}, "not a numeric measure"),
    ("measure_compare", {"cluster": A, "measure": "final.table", "against": SAME},
     "not a numeric measure"),
    ("measure_compare", {"cluster": "R/place/L-NOPE/l1", "measure": "final.gap_m",
                         "against": SAME}, "not a failure cluster"),
    ("measure_compare", {"cluster": A, "measure": "final.gap_m", "against": 0.05},
     "neither one of successes_same_level"),
    ("measure_compare", {"cluster": A, "measure": "final.gap_m", "against": A}, "itself"),
    ("measure_compare", {"cluster": A, "measure": "final.gap_m"}, "missing"),
    ("measure_compare", {"cluster": A, "measure": "final.gap_m", "against": SAME,
                         "percentile": 90}, "unknown parameter"),
    ("measure_tally", {"cluster": A, "measure": "final.gap_m", "against": SAME},
     "not a boolean or string measure"),
    ("measure_tally", {"cluster": A, "measure": "/etc/passwd", "against": SAME},
     "not a boolean or string measure"),
])
def test_values_outside_the_domains_are_refused(ctx: MeasureContext, tool: str,
                                                params: dict[str, Any], text: str) -> None:
    problems = check_params(REGISTRY[tool], params, ctx)
    assert problems and any(text in p for p in problems), problems


def test_another_run_s_cluster_is_no_reference(tray: TaskView) -> None:
    base = ctx_of(tray)
    other = RunScores("S", "S/scores.jsonl", (labelled("S", "l1-s1", False, PLACE),))
    two = MeasureContext(tray, {"R": base.runs["R"], "S": other}, base.kinds,
                         outcomes=base.outcomes)
    params = {"cluster": A, "measure": "final.gap_m", "against": "S/place/L-PLACE-POSE/l1"}
    assert any("not a cluster of the run" in p
               for p in check_params(REGISTRY["measure_compare"], params, two))


def test_the_tools_need_outcomes() -> None:
    assert REGISTRY["measure_compare"].needs == ("scores", "outcomes")
    assert REGISTRY["measure_tally"].needs == ("scores", "outcomes")


# --- measure_compare ------------------------------------------------------------------------


def test_a_scalar_against_the_successes(ctx: MeasureContext) -> None:
    _, result, got = call("measure_compare", ctx, A, "final.gap_m", SAME)
    base = f"{BASE_A}_cmp__final__gap_m__vs__successes_same_level"
    assert got[f"{base}_judged"] == 4 and got[f"{base}_ref_judged"] == 12
    assert got[f"{base}_median"] == 0.5
    assert got[f"{base}_ref_median"] == pytest.approx(0.055)
    assert got[f"{base}_ref_p5"] == pytest.approx(0.0055)
    assert got[f"{base}_ref_p95"] == pytest.approx(0.1045)
    assert (got[f"{base}_outside_below"], got[f"{base}_outside_above"],
            got[f"{base}_outside_total"]) == (0, 4, 4)
    assert got[f"{base}_separated"] is True
    assert got["measure_compare_low_percentile"] == 5.0
    assert got["measure_compare_min_reference"] == 10
    assert f"{base}_beyond_threshold" not in got  # final.gap_m is mapped to no threshold
    assert result.judged and result.rows[0]["separated"] is True


def test_a_vector_component(ctx: MeasureContext) -> None:
    _, _, got = call("measure_compare", ctx, A, "final.pos_m[2]", SAME)
    base = f"{BASE_A}_cmp__final__pos_m__i2__vs__successes_same_level"
    assert got[f"{base}_median"] == pytest.approx(0.85)
    assert got[f"{base}_ref_median"] == pytest.approx(0.80)
    assert got[f"{base}_outside_above"] == 4 and got[f"{base}_separated"] is True


def test_the_tilt_of_a_quaternion(ctx: MeasureContext) -> None:
    book, result, got = call("measure_compare", ctx, A, "final.body_quat.tilt", SAME)
    base = f"{BASE_A}_cmp__final__body_quat__tilt__vs__successes_same_level"
    assert got[f"{base}_median"] == pytest.approx(30.0)
    assert got[f"{base}_ref_median"] == pytest.approx(0.0)
    assert got[f"{base}_separated"] is True
    assert {book.get(f).unit for f in result.facts if book.get(f).name == f"{base}_median"} \
        == {"deg"}


def test_a_condition_value(tray: TaskView) -> None:
    conds = [condition(1, k, {"mass": 0.05 + 0.001 * k, "mode": "slow"})
             for k in range(12)]
    conds += [condition(1, k, {"mass": 0.2, "mode": "fast"}) for k in (100, 101, 102)]
    sets = (ConditionSet("conds/eval.jsonl", "eval", tuple(conds)),
            ConditionSet("conds/train.jsonl", "train", (condition(1, 103, {"mass": 9.0}),)))
    c = ctx_of(tray, sets=sets)
    found = domains(c.task, c.runs, c.outcomes, c.conditions)
    assert "condition.mass" in found.numbers and "condition.mode" in found.categories
    book, result, got = call("measure_compare", c, A, "condition.mass", SAME)
    base = f"{BASE_A}_cmp__condition__mass__vs__successes_same_level"
    assert got[f"{base}_judged"] == 3  # s103 has a train condition only: left out
    assert got[f"{base}_median"] == pytest.approx(0.2)
    assert got[f"{base}_separated"] is True
    assert book.get(result.facts[-1]).source_ref == "conds/eval.jsonl"
    _, _, tally = call("measure_tally", c, A, "condition.mode", SAME)
    base = f"{BASE_A}_tally__condition__mode__vs__successes_same_level"
    assert tally[f"{base}_mode"] == "fast" and tally[f"{base}_ref_mode"] == "slow"


def test_against_another_cluster_with_too_small_a_reference(ctx: MeasureContext) -> None:
    book, result, got = call("measure_compare", ctx, A, "at_failure.angle_deg", B)
    base = f"{BASE_A}_cmp__at_failure__angle_deg__vs__carry_L-TRAY-TILT_l1"
    assert got[f"{base}_judged"] == 4 and got[f"{base}_ref_judged"] == 2
    assert got[f"{base}_median"] == 5.0 and got[f"{base}_ref_median"] == 25.0
    assert f"{base}_separated" not in got and f"{base}_outside_total" not in got
    assert got[f"measure_compare_{base}_bounds_not_judged"].startswith("the reference group")
    assert not result.judged


def test_against_another_cluster_with_bounds(tray: TaskView) -> None:
    c = ctx_of(with_spec(tray, min_reference=2))
    _, result, got = call("measure_compare", c, A, "at_failure.angle_deg", B)
    base = f"{BASE_A}_cmp__at_failure__angle_deg__vs__carry_L-TRAY-TILT_l1"
    assert got[f"{base}_outside_below"] == 4 and got[f"{base}_separated"] is True
    assert result.judged


def test_the_reference_of_successes_has_no_measure_at_failure(ctx: MeasureContext) -> None:
    _, result, got = call("measure_compare", ctx, A, "at_failure.angle_deg", SAME)
    base = f"{BASE_A}_cmp__at_failure__angle_deg__vs__successes_same_level"
    assert got[f"{base}_ref_judged"] == 0 and f"{base}_ref_median" not in got
    assert not result.judged


def test_a_threshold_of_the_scorer_is_counted(tray: TaskView) -> None:
    mapped = with_spec(tray, thresholds={
        "final.gap_m": {"threshold": "target_pos_tol", "beyond": "above"},
        "final.err_deg": {"threshold": "target_yaw_tol_deg", "beyond": "above",
                          "absolute": True}})
    c = ctx_of(mapped)
    _, result, got = call("measure_compare", c, A, "final.gap_m", SAME)
    base = f"{BASE_A}_cmp__final__gap_m__vs__successes_same_level"
    assert got["threshold_target_pos_tol"] == tray.thresholds["target_pos_tol"]
    assert got[f"{base}_beyond_threshold"] == 4
    assert got[f"{base}_ref_beyond_threshold"] == 6  # 0.06 .. 0.11 > 0.05
    assert result.rows[0]["threshold"] == "target_pos_tol"
    _, _, err = call("measure_compare", c, A, "final.err_deg", SAME)
    name = f"{BASE_A}_cmp__final__err_deg__vs__successes_same_level_beyond_threshold"
    assert err[name] == 4  # |-20| > 10


def test_below_counts_the_other_side(tray: TaskView) -> None:
    c = ctx_of(with_spec(tray, thresholds={
        "final.gap_m": {"threshold": "target_pos_tol", "beyond": "below"}}))
    _, _, got = call("measure_compare", c, A, "final.gap_m", SAME)
    assert got[f"{BASE_A}_cmp__final__gap_m__vs__successes_same_level_beyond_threshold"] == 0
    assert got[f"{BASE_A}_cmp__final__gap_m__vs__successes_same_level_ref_beyond_threshold"] == 5


def test_a_missing_measure_is_left_out(tray: TaskView) -> None:
    rows = default_outcomes()
    rows[12] = rows[12].model_copy(update={"final": {}})  # first member of A: no measures
    rows[13] = rows[13].model_copy(update={"final": {"gap_m": 0.5, "pos_m": [0.0]}})
    c = ctx_of(tray, rows[:-1])  # and one member of B has no outcome at all
    _, _, got = call("measure_compare", c, A, "final.pos_m[2]", SAME)
    assert got[f"{BASE_A}_cmp__final__pos_m__i2__vs__successes_same_level_judged"] == 2
    _, _, got = call("measure_compare", c, A, "final.gap_m", SAME)
    assert got[f"{BASE_A}_cmp__final__gap_m__vs__successes_same_level_judged"] == 3


def test_a_cluster_without_the_measure_is_not_judged(ctx: MeasureContext) -> None:
    book, result, got = call("measure_compare", ctx, B, "final.pos_m[2]", SAME)
    base = "R_cluster_carry_L-TRAY-TILT_l1_cmp__final__pos_m__i2__vs__successes_same_level"
    assert got[f"measure_compare_{base}_not_judged"] == NONE_CARRY
    assert (got[f"{base}_members"], got[f"{base}_judged"], got[f"{base}_lacking"]) == (2, 0, 2)
    assert (got[f"{base}_ref_members"], got[f"{base}_ref_judged"],
            got[f"{base}_ref_lacking"]) == (12, 12, 0)
    assert f"{base}_median" not in got and not result.judged


def test_a_task_view_without_the_block_judges_nothing(tray: TaskView) -> None:
    c = ctx_of(tray.model_copy(update={"measures": None}))
    _, result, got = call("measure_compare", c, A, "final.gap_m", SAME)
    assert not result.judged and "measures block" in got["measure_compare_not_judged"]


# --- measure_tally --------------------------------------------------------------------------


def test_a_boolean_tally_against_a_cluster(ctx: MeasureContext) -> None:
    _, result, got = call("measure_tally", ctx, A, "at_failure.left", B)
    base = f"{BASE_A}_tally__at_failure__left__vs__carry_L-TRAY-TILT_l1"
    assert got[f"{base}_judged"] == 4 and got[f"{base}_ref_judged"] == 2
    assert got[f"{base}_values"] == 2
    assert (got[f"{base}_v1_value"], got[f"{base}_v1_count"],
            got[f"{base}_v1_ref_count"]) == ("true", 2, 2)
    assert (got[f"{base}_v2_value"], got[f"{base}_v2_count"],
            got[f"{base}_v2_ref_count"]) == ("false", 2, 0)
    assert got[f"{base}_mode"] == "false"  # a tie goes to the first in text order
    assert got[f"{base}_ref_mode"] == "true"
    assert len(result.rows) == 2
    assert not any(isinstance(v, bool) for v in got.values())  # values travel as text


def test_a_string_tally_against_the_successes(ctx: MeasureContext) -> None:
    _, _, got = call("measure_tally", ctx, A, "final.table", SAME)
    base = f"{BASE_A}_tally__final__table__vs__successes_same_level"
    assert (got[f"{base}_v1_value"], got[f"{base}_v1_count"],
            got[f"{base}_v1_ref_count"]) == ("B", 3, 12)
    assert (got[f"{base}_v2_value"], got[f"{base}_v2_count"],
            got[f"{base}_v2_ref_count"]) == ("A", 1, 0)
    assert got[f"{base}_mode"] == "B" and f"{base}_values_left_out" not in got


def test_a_tally_beyond_max_values_sums_the_rest(tray: TaskView) -> None:
    c = ctx_of(with_spec(tray, max_values=1))
    _, result, got = call("measure_tally", c, A, "at_failure.where", B)
    base = f"{BASE_A}_tally__at_failure__where__vs__carry_L-TRAY-TILT_l1"
    assert got[f"{base}_values"] == 2 and got[f"{base}_values_left_out"] == 1
    assert got[f"{base}_v1_value"] == "B"  # 4 over both groups, "none" 2
    assert (got[f"{base}_other_count"], got[f"{base}_other_ref_count"]) == (0, 2)
    assert f"{base}_v2_value" not in got and len(result.rows) == 2


def test_a_tally_of_a_measure_the_cluster_lacks(ctx: MeasureContext) -> None:
    _, result, got = call("measure_tally", ctx, B, "final.table", SAME)
    base = "R_cluster_carry_L-TRAY-TILT_l1_tally__final__table__vs__successes_same_level"
    assert not result.judged
    assert got[f"measure_tally_{base}_not_judged"] == NONE_CARRY
    assert (got[f"{base}_members"], got[f"{base}_judged"], got[f"{base}_lacking"]) == (2, 0, 2)
    assert f"{base}_mode" not in got


# --- one name, one value ------------------------------------------------------------------


def test_a_repeated_call_adds_the_same_facts(ctx: MeasureContext) -> None:
    book, first, _ = call("measure_compare", ctx, A, "final.gap_m", SAME)
    size = len(book.facts)
    _, again, _ = call("measure_compare", ctx, A, "final.gap_m", SAME, book)
    assert again.facts == first.facts and len(book.facts) == size
    _, tally, _ = call("measure_tally", ctx, A, "final.table", SAME, book)
    _, tally2, _ = call("measure_tally", ctx, A, "final.table", SAME, book)
    assert tally.facts == tally2.facts


def test_calls_with_other_parameters_never_clash(tray: TaskView) -> None:
    c = ctx_of(with_spec(tray, min_reference=2, thresholds={
        "final.gap_m": {"threshold": "target_pos_tol", "beyond": "above"}}))
    book = FactBook()
    found = domains(c.task, c.runs, c.outcomes, c.conditions)
    for cluster in found.clusters:
        others = [x for x in found.clusters if x != cluster]
        for against in (SAME, "successes_all_levels", *others):
            for measure in found.numbers:
                call("measure_compare", c, cluster, measure, against, book)
            for measure in found.categories:
                call("measure_tally", c, cluster, measure, against, book)
    names = [f.name for f in book.facts]
    assert len(names) == len(set(names))
    assert all(set(n) <= set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
               for n in names)


# --- review of 28/11: references by level, min_cluster, counts, slugs, bridge --------------


def two_level_ctx(task: TaskView) -> MeasureContext:
    """`R` plus eight level-2 successes whose gap is 0.5, the value of cluster A."""
    held = default_outcomes()
    extra = [f"l2-s{k}" for k in range(8)]
    held += [outcome(n, True, final={"gap_m": 0.5}) for n in extra]
    run = scores()
    run = RunScores("R", run.ref, (*run.scores, *(labelled("R", n, True, level=2)
                                                  for n in extra)))
    return MeasureContext(task, {"R": run}, frozenset({"scores", "outcomes"}),
                          outcomes={"R": RunOutcomes("R", "R/outcomes.jsonl", tuple(held))})


def test_the_successes_of_the_cluster_s_level_and_of_all_levels(tray: TaskView) -> None:
    c = two_level_ctx(tray)
    params = REGISTRY["measure_compare"].params
    assert params["against"] == "reference"
    _, _, same = call("measure_compare", c, A, "final.gap_m", SAME)
    _, _, every = call("measure_compare", c, A, "final.gap_m", "successes_all_levels")
    s = f"{BASE_A}_cmp__final__gap_m__vs__successes_same_level"
    a = f"{BASE_A}_cmp__final__gap_m__vs__successes_all_levels"
    assert (same[f"{s}_ref_members"], every[f"{a}_ref_members"]) == (12, 20)
    assert same[f"{s}_separated"] is True
    assert every[f"{a}_outside_total"] == 0 and every[f"{a}_separated"] is False


def test_the_bare_successes_value_is_gone(ctx: MeasureContext) -> None:
    problems = check_params(REGISTRY["measure_compare"],
                            {"cluster": A, "measure": "final.gap_m", "against": "successes"},
                            ctx)
    assert problems and "neither one of successes_same_level, successes_all_levels" in problems[0]


def with_gaps(task: TaskView, gaps: list[float], **spec: Any) -> MeasureContext:
    """Cluster A's members get these gaps (None drops the measure); successes 0.00-0.11."""
    rows = default_outcomes()
    for k, gap in enumerate(gaps):
        final = dict(rows[12 + k].final)
        final.pop("gap_m")
        if gap is not None:
            final["gap_m"] = gap
        rows[12 + k] = rows[12 + k].model_copy(update={"final": final})
    return ctx_of(with_spec(task, **spec) if spec else task, rows)


@pytest.mark.parametrize(("gaps", "outside", "separated"), [
    ([0.05, 0.05, 0.05, 0.05], 0, False),
    ([0.5, 0.5, 0.05, 0.05], 2, False),  # exactly half is not a majority
    ([0.5, 0.5, 0.5, 0.05], 3, True),  # just over half
])
def test_separated_needs_a_majority(tray: TaskView, gaps: list[float], outside: int,
                                    separated: bool) -> None:
    _, _, got = call("measure_compare", with_gaps(tray, gaps), A, "final.gap_m",
                     "successes_same_level")
    base = f"{BASE_A}_cmp__final__gap_m__vs__successes_same_level"
    assert got[f"{base}_outside_total"] == outside and got[f"{base}_separated"] is separated


def test_below_min_cluster_separated_is_not_judged(tray: TaskView) -> None:
    c = with_gaps(tray, [0.5, 0.5, None, None])  # two judged members, min_cluster 3
    _, result, got = call("measure_compare", c, A, "final.gap_m", SAME)
    base = f"{BASE_A}_cmp__final__gap_m__vs__successes_same_level"
    assert got["measure_compare_min_cluster"] == 3
    assert (got[f"{base}_members"], got[f"{base}_judged"], got[f"{base}_lacking"]) == (4, 2, 2)
    assert got[f"{base}_median"] == 0.5 and got[f"{base}_outside_total"] == 2
    assert f"{base}_separated" not in got
    assert got[f"measure_compare_{base}_separated_not_judged"].startswith(
        "the cluster holds fewer rollouts")
    assert not result.judged
    c = with_gaps(tray, [0.5, 0.5, None, None], min_cluster=2)
    _, _, got = call("measure_compare", c, A, "final.gap_m", SAME)
    assert got[f"{base}_separated"] is True


def test_the_reference_s_missing_rollouts_are_counted(tray: TaskView) -> None:
    rows = default_outcomes()
    rows[0] = rows[0].model_copy(update={"final": {}})
    c = ctx_of(tray, rows[1:2] + rows[2:] + [rows[0]])
    _, _, got = call("measure_compare", c, A, "final.gap_m", SAME)
    base = f"{BASE_A}_cmp__final__gap_m__vs__successes_same_level"
    assert (got[f"{base}_ref_members"], got[f"{base}_ref_judged"],
            got[f"{base}_ref_lacking"]) == (12, 11, 1)
    _, _, tally = call("measure_tally", c, A, "final.table", SAME)
    t = f"{BASE_A}_tally__final__table__vs__successes_same_level"
    assert (tally[f"{t}_ref_members"], tally[f"{t}_ref_judged"],
            tally[f"{t}_ref_lacking"]) == (12, 11, 1)


def test_a_component_and_a_name_that_looks_like_one_never_share_a_slug(tray: TaskView) -> None:
    rows = default_outcomes()
    for k in range(len(rows)):
        final = dict(rows[k].final)
        final["pos_m_i2"] = 7.0  # a measure literally named like the slug of pos_m[2]
        rows[k] = rows[k].model_copy(update={"final": final})
    c = ctx_of(tray, rows)
    found = domains(c.task, c.runs, c.outcomes, c.conditions)
    assert {"final.pos_m[2]", "final.pos_m_i2"} <= set(found.numbers)
    slugs = [parse_ref(r).slug for r in (*found.numbers, *found.categories)]  # type: ignore[union-attr]
    assert len(slugs) == len(set(slugs))
    book = FactBook()
    call("measure_compare", c, A, "final.pos_m[2]", SAME, book)
    call("measure_compare", c, A, "final.pos_m_i2", SAME, book)  # no clash
    names = [f.name for f in book.facts]
    assert len(names) == len(set(names))


def test_the_bridge_offers_the_closed_domains(ctx: MeasureContext) -> None:
    from flywheel.eval.agentqa.mcp.bridge import DESCRIPTIONS, input_schema

    schema = input_schema(REGISTRY["measure_compare"], ctx)
    props = schema["properties"]
    found = domains(ctx.task, ctx.runs, ctx.outcomes, ctx.conditions)
    assert props["cluster"]["enum"] == list(found.clusters)
    assert props["measure"]["enum"] == list(found.numbers)
    assert props["against"]["enum"][:2] == ["successes_same_level", "successes_all_levels"]
    assert props["against"]["enum"][2:] == list(found.clusters)
    tally = input_schema(REGISTRY["measure_tally"], ctx)["properties"]
    assert tally["measure"]["enum"] == list(found.categories)
    assert "closed list" in DESCRIPTIONS["measure_compare"]
    assert "closed list" in DESCRIPTIONS["measure_tally"]

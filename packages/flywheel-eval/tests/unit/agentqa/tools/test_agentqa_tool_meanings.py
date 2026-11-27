"""`meaning_of`: one line of meaning for every fact a model is given (DA-52 task 2.3)."""

from __future__ import annotations

import re
from pathlib import Path

from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.meanings import meaning_of
from flywheel.eval.agentqa.tools.registry import REGISTRY, check_params
from flywheel.eval.agentqa.tools.task import TaskView
from test_agentqa_tool_measures import BASE_A, SAME, A, B, ctx_of

BASE = f"{BASE_A}_cmp__final__gap_m__vs__{SAME}"


def test_compare_names_read_as_their_documented_structure() -> None:
    below = meaning_of(f"{BASE}_outside_below", "measure_compare")
    assert below.startswith("Members of the cluster whose value is below the reference "
                            "group's low percentile")
    assert "measure final.gap_m" in below and f"reference {SAME}" in below
    assert "cluster place_L-PLACE-POSE_l1 of run R" in below
    assert "median of the measure over the reference" in meaning_of(
        f"{BASE}_ref_median", "measure_compare")
    assert "over the members" in meaning_of(f"{BASE}_median", "measure_compare")
    assert "more than half" in meaning_of(f"{BASE}_separated", "measure_compare")
    assert "percentile" in meaning_of(f"{BASE}_ref_p95", "measure_compare")
    assert "lack the measure" in meaning_of(f"{BASE}_ref_lacking", "measure_compare")
    other = f"{BASE_A}_cmp__final__body_quat__tilt__vs__carry_L-TRAY-TILT_l1_outside_total"
    text = meaning_of(other, "measure_compare")
    assert "measure final.body_quat.tilt" in text
    assert "the failure cluster carry_L-TRAY-TILT_l1 of the same run" in text
    assert "measure final.pos_m[2]" in meaning_of(
        f"{BASE_A}_cmp__final__pos_m__i2__vs__{SAME}_median", "measure_compare")
    assert "why separation" in meaning_of(f"measure_compare_{BASE}_separated_not_judged",
                                          "measure_compare").lower()


def test_tally_names_read_as_their_documented_structure() -> None:
    base = f"{BASE_A}_tally__final__table__vs__{SAME}"
    assert meaning_of(f"{base}_v2_value", "measure_tally").startswith(
        "Value number 2 of the tally")
    assert meaning_of(f"{base}_v1_ref_count", "measure_tally").startswith(
        "Rollouts of the reference group whose value is value number 1")
    assert "most common value among the members" in meaning_of(f"{base}_mode",
                                                               "measure_tally")
    assert "not listed one by one" in meaning_of(f"{base}_other_count", "measure_tally")


def test_cluster_facts_and_the_fallback() -> None:
    assert meaning_of("C_70_cluster_place_L-PLACE-POSE_l1_size", "failure_clusters") == (
        "How many failed rollouts the cluster holds; cluster place_L-PLACE-POSE_l1 of run C_70.")
    assert "other runs" in meaning_of("C_70_cluster_place_L-PLACE-POSE_l1_in_other_runs",
                                      "failure_clusters")
    assert meaning_of("C_70_failures", "failure_clusters") == "Failed rollouts of run C_70."
    fallback = meaning_of("C_70_l1_rollouts", "step_pass_table")
    assert fallback.startswith("A fact of the tool step_pass_table: ")
    assert meaning_of("anything", "no_such_tool")
    assert "reason" in meaning_of("lineage_not_judged", "lineage")


def test_every_fact_of_a_measure_run_has_a_meaning(tray: TaskView) -> None:
    ctx = ctx_of(tray)
    book = FactBook()
    tools: dict[str, str] = {}
    calls = [("measure_compare", A, "final.gap_m", SAME),
             ("measure_compare", A, "final.body_quat.tilt", B),
             ("measure_compare", B, "final.gap_m", "successes_all_levels"),
             ("measure_tally", A, "final.table", SAME),
             ("measure_tally", A, "at_failure.left", SAME),
             ("failure_clusters", "", "", "")]
    for tool, cluster, measure, against in calls:
        params = ({"runs": "all"} if tool == "failure_clusters"
                  else {"cluster": cluster, "measure": measure, "against": against})
        assert check_params(REGISTRY[tool], params, ctx) == []
        before = len(book.facts)
        REGISTRY[tool].run(book, ctx, params)
        tools.update({f.fact_id: tool for f in book.facts[before:]})
    assert len(book.facts) > 40
    for fact in book.facts:
        meaning = meaning_of(fact.name, tools[fact.fact_id])
        assert meaning.strip(), fact.name
        # A structured line, not the tool description: the measure tools' names all parse.
        assert not meaning.startswith("A fact of the tool"), fact.name


def test_the_meanings_name_no_task_word() -> None:
    import flywheel.eval.agentqa.tools.meanings as module

    text = Path(module.__file__).read_text(encoding="utf-8").lower()
    for word in ("tray", "height", "yaw", "tilt", "table", "hand", "jig"):
        assert not re.search(rf"\b{word}", text), word

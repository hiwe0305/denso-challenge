"""Step B3, the runtime, coverage and train rules (design 19/11 section 5.3 rows 3, 5-8).

Each test hand-writes the facts and the cluster table of a run directory, so it states
exactly which facts a rule sees. The fixture round of the 4-run pack carries no trace,
train log or conditions, so these rules never fire there (last test).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.eval.agentqa.round.assemble import ASSEMBLY_FILE, assemble
from flywheel.eval.agentqa.round.hypotheses import (
    CHECKS_FILE,
    HYPOTHESES_FILE,
    RULES_DIR,
    RulesRefused,
    hypothesize,
    load_rules,
)
from flywheel.eval.agentqa.round.measure import CALLS_FILE, FACTS_FILE, TABLES_DIR
from flywheel.eval.agentqa.round.pipeline import run_round
from flywheel.eval.agentqa.round.records import (
    FactRecord,
    HypothesisRecord,
    RunRecord,
    ToolCallRecord,
)
from flywheel.eval.agentqa.tools.task import load_task
from helpers_round import (  # noqa: F401  (isolated_store is an autouse fixture)
    NOW,
    isolated_store,
    pack_maker,
)

TIMEOUT = ("C_70", "approach_a", "L-TIMEOUT", 1)
PLACE = ("C_70", "place", "L-PLACE-POSE", 2)
TRACK = {"C_70_failed_exceeds_tau_upper": True, "C_70_tau_separates_upper": True,
         "C_70_failed_track_error_upper": 0.4, "tau_track_upper": 0.2,
         "C_70_succeeded_track_error_upper": 0.1}


def write_dir(out: Path, facts: dict[str, Any],
              clusters: list[tuple[str, str, str, int]]) -> Path:
    """A run directory with `facts` and one failure_clusters table of `clusters`."""
    (out / TABLES_DIR).mkdir(parents=True)
    (out / FACTS_FILE).write_text("".join(
        FactRecord(fact_id=f"F{k}", name=name, value=value, source_ref="x",
                   provenance="code", tool_call_id="T1").model_dump_json() + "\n"
        for k, (name, value) in enumerate(facts.items(), start=1)))
    (out / CALLS_FILE).write_text(ToolCallRecord(
        call_id="T1", tool="failure_clusters", version=1, status="ran").model_dump_json() + "\n")
    rows = [{"run": r, "first_failed_step": s, "label": lab, "level": lv, "size": 3}
            for r, s, lab, lv in clusters]
    (out / TABLES_DIR / "T1-failure_clusters.json").write_text(json.dumps(rows))
    return out


def run(tmp_path: Path, facts: dict[str, Any],
        clusters: list[tuple[str, str, str, int]] | None = None,
        **kw: Any) -> dict[str, list[HypothesisRecord]]:
    out = write_dir(tmp_path / "out", facts, clusters or [TIMEOUT, PLACE])
    by: dict[str, list[HypothesisRecord]] = {}
    for h in hypothesize(out, "tray", **kw):
        by.setdefault(h.cluster.cluster_id, []).append(h)
    return {k: sorted(v, key=lambda h: h.code_rank) for k, v in by.items()}


def ids(hyps: list[HypothesisRecord]) -> list[str]:
    return [h.rule_id for h in hyps]


def fid(facts: dict[str, Any], name: str) -> str:
    return f"F{list(facts).index(name) + 1}"


# --- the rule set and the task view ---------------------------------------------------


def test_the_rule_set_and_the_group_order() -> None:
    rules = {r.id: r for r in load_rules()}
    assert set(rules) == {"scorer_latch_too_strict", "label_signal_missing",
                          "controller_tracking", "weak_skill", "coverage_gap",
                          "out_of_domain", "earlier_stage_train"}
    assert {k: (r.group, r.diagnosis, r.system) for k, r in rules.items()
            if k not in ("scorer_latch_too_strict", "label_signal_missing")} == {
        "controller_tracking": ("runtime", "controller", True),
        "weak_skill": ("coverage", "weak_skill", False),
        "coverage_gap": ("coverage", "coverage_gap", False),
        "out_of_domain": ("coverage", "out_of_domain", False),
        "earlier_stage_train": ("train", "unknown", True)}
    assert rules["coverage_gap"].interventions == ["sim_s1", "sim_s2", "sim_s3", "sim_s4"]
    from flywheel.eval.agentqa.round.hypotheses import GROUPS
    assert GROUPS == ("scorer", "runtime", "train", "data", "coverage")


def test_the_task_view_declares_the_runtime_sets() -> None:
    task = load_task("tray")
    assert "L-TIMEOUT" in task.runtime_labels and "approach_a" in task.motion_steps
    assert "place" not in task.motion_steps


@pytest.mark.parametrize("edit, match", [
    (lambda raw: raw.update(runtime_labels=["L-GHOST"]), "runtime_labels"),
    (lambda raw: raw.update(motion_steps=["fly"]), "not steps"),
])
def test_a_task_view_with_unknown_set_members_is_refused(tmp_path: Path, edit: Any,
                                                         match: str) -> None:
    src = Path("configs/eval/agentqa/tasks/tray.yaml")
    raw = yaml.safe_load(src.read_text())
    raw["scorer_config"] = str(Path("configs/eval/scorer/tray.yaml").resolve())
    edit(raw)
    (tmp_path / "tray.yaml").write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match=match):
        load_task("tray", root=tmp_path)


def _one_rule(tmp_path: Path, rule: dict[str, Any]) -> Path:
    root = tmp_path / "rules"
    root.mkdir()
    (root / "r.yaml").write_text(yaml.safe_dump({"rules": [rule]}))
    return root


BASE = {"id": "r", "title": "A rule", "source": "test", "group": "runtime",
        "diagnosis": "controller", "note": "n", "system": True,
        "interventions": ["repair_ticket"]}


@pytest.mark.parametrize("when, match", [
    ([{"cluster": "label_in"}], "needs a set of labels"),
    ([{"cluster": "label_in", "set": "motion_steps"}], "needs a set of labels"),
    ([{"cluster": "step_in", "set": "runtime_labels"}], "needs a set of steps"),
    ([{"cluster": "chain_broken", "set": "runtime_labels"}], "takes no set"),
    ([{"any": [[{"fact": "a", "is": True}], []]}], "empty"),
    ([{"any": [[{"fact": "a", "is": True}]]}], "at least 2"),
    ([{"fact": "{run}_{nope}", "is": True}], "may be used"),
    (["a bare string"], "dictionary"),
])
def test_bad_conditions_are_refused(tmp_path: Path, when: list[Any], match: str) -> None:
    with pytest.raises(RulesRefused, match=match):
        load_rules(_one_rule(tmp_path, {**BASE, "when": when}))


def test_a_rule_refuting_its_own_diagnosis_is_refused(tmp_path: Path) -> None:
    rule = {**BASE, "when": [{"fact": "a", "is": True}], "refutes": ["controller"]}
    with pytest.raises(RulesRefused, match="own diagnosis"):
        load_rules(_one_rule(tmp_path, rule))


def test_a_numeric_literal_inside_any_is_refused(tmp_path: Path) -> None:
    rule = {**BASE, "when": [{"any": [[{"fact": "a", "is": 1}], [{"fact": "b", "is": 2}]]}]}
    with pytest.raises(RulesRefused, match="numeric literal"):
        load_rules(_one_rule(tmp_path, rule))


# --- controller_tracking ----------------------------------------------------------------


def test_controller_tracking_on_the_upper_body(tmp_path: Path) -> None:
    by = run(tmp_path, TRACK)
    top = by["C_70/approach_a/L-TIMEOUT/l1"][0]
    assert (top.rule_id, top.diagnosis, top.group) == ("controller_tracking", "controller",
                                                       "runtime")
    assert top.blocked_data_spend and top.interventions == ["repair_ticket"]
    assert set(top.support) == {fid(TRACK, n) for n in TRACK}
    assert [c.check_id for c in top.checks] == ["tracking_error_on_successes"]


def test_controller_tracking_on_the_lower_body(tmp_path: Path) -> None:
    facts = {"C_70_failed_exceeds_tau_lower": True, "C_70_tau_separates_lower": True,
             "C_70_failed_exceeds_tau_upper": True, "C_70_tau_separates_upper": False}
    assert ids(run(tmp_path, facts)["C_70/approach_a/L-TIMEOUT/l1"]) == ["controller_tracking"]


@pytest.mark.parametrize("facts", [
    # tau is crossed by the successes too (tray.md 20.11 H2): not separated
    {"C_70_failed_exceeds_tau_upper": True, "C_70_tau_separates_upper": False,
     "C_70_failed_exceeds_tau_lower": True, "C_70_tau_separates_lower": False},
    # separated on one part, but exceeded on the other one only
    {"C_70_failed_exceeds_tau_upper": False, "C_70_tau_separates_upper": True,
     "C_70_failed_exceeds_tau_lower": True, "C_70_tau_separates_lower": False},
    # a missing input is not "clean" and not a match either
    {"C_70_failed_exceeds_tau_upper": True},
    {},
    # a fact of another run says nothing about C_70
    {"C_ALL_failed_exceeds_tau_upper": True, "C_ALL_tau_separates_upper": True},
])
def test_controller_tracking_does_not_match(tmp_path: Path, facts: dict[str, Any]) -> None:
    hyps = run(tmp_path, facts)["C_70/approach_a/L-TIMEOUT/l1"]
    assert "controller_tracking" not in ids(hyps)


@pytest.mark.parametrize("cluster", [
    ("C_70", "place", "L-TIMEOUT", 1),          # not a motion step
    ("C_70", "approach_a", "L-PLACE-POSE", 1),  # not a runtime label
])
def test_controller_tracking_keeps_to_its_scope(tmp_path: Path,
                                                cluster: tuple[str, str, str, int]) -> None:
    hyps = next(iter(run(tmp_path, TRACK, [cluster]).values()))
    assert "controller_tracking" not in ids(hyps)


# --- coverage --------------------------------------------------------------------------


def cov(in_domain: bool | None, above: int | None, key: str = "C_70_cluster_place_L-PLACE-POSE_l2"
        ) -> dict[str, Any]:
    facts: dict[str, Any] = {f"{key}_coverage_matched": 3, f"{key}_coverage_d_mean": 1.2,
                             "tau_cov_l2": 1.5}
    if in_domain is not None:
        facts[f"{key}_coverage_in_domain"] = in_domain
    if above is not None:
        facts[f"{key}_coverage_above_tau"] = above
    return facts


@pytest.mark.parametrize("in_domain, above, expect", [
    (True, 0, ["weak_skill"]),
    (True, 2, ["coverage_gap"]),
    (False, 0, ["out_of_domain"]),
    (False, 2, ["out_of_domain"]),
    (None, 0, ["none"]),
    (True, None, ["none"]),
])
def test_coverage_rules(tmp_path: Path, in_domain: bool | None, above: int | None,
                        expect: list[str]) -> None:
    hyps = run(tmp_path, cov(in_domain, above), [PLACE])["C_70/place/L-PLACE-POSE/l2"]
    assert ids(hyps) == expect


def test_weak_skill_cites_its_facts_and_spends_data(tmp_path: Path) -> None:
    facts = cov(True, 0)
    top = run(tmp_path, facts, [PLACE])["C_70/place/L-PLACE-POSE/l2"][0]
    assert set(top.support) == {fid(facts, n) for n in facts}
    assert not top.blocked_data_spend and top.interventions == ["teleop_correction"]
    # d <= tau_cov does not tell a weak skill from no cause; the planner does (step 5)
    assert [c.check_id for c in top.checks] == ["planner_on_failed_conditions"]


def test_coverage_gap_offers_every_tier(tmp_path: Path) -> None:
    top = run(tmp_path, cov(True, 1), [PLACE])["C_70/place/L-PLACE-POSE/l2"][0]
    assert top.interventions == ["sim_s1", "sim_s2", "sim_s3", "sim_s4"]


def test_the_cluster_slug_of_a_cluster_without_level(tmp_path: Path) -> None:
    facts = cov(True, 0, key="C_70_cluster_place_L-PLACE-POSE_lNone")
    hyps = run(tmp_path, facts, [("C_70", "place", "L-PLACE-POSE", -1)])
    assert ids(hyps["C_70/place/L-PLACE-POSE/lNone"]) == ["weak_skill"]


# --- earlier_stage_train ----------------------------------------------------------------


def test_earlier_stage_train_through_the_job_of_lineage(tmp_path: Path) -> None:
    facts = {"lineage_C_70_job": "job-a", "lineage_C_70_checkpoint": "ck",
             "train_job-a_all_train_nonfinite_losses": 4, "train_job-a_all_rows": 100,
             "train_job-b_all_train_nonfinite_losses": 0}
    top = run(tmp_path, facts, [PLACE])["C_70/place/L-PLACE-POSE/l2"][0]
    assert (top.rule_id, top.group, top.diagnosis, top.note) == (
        "earlier_stage_train", "train", "unknown", "train_fault")
    assert top.blocked_data_spend and top.interventions == ["repair_ticket"]
    assert set(top.support) == {fid(facts, n) for n in list(facts)[:4]}
    assert [c.check_id for c in top.checks] == ["inspect_train_log_window"]


@pytest.mark.parametrize("facts", [
    {"lineage_C_70_job": "job-a", "train_job-a_all_train_nonfinite_losses": 0},
    {"lineage_C_70_job_not_judged": "no row", "train_job-a_all_train_nonfinite_losses": 4},
    {"lineage_C_70_job": "job-b", "train_job-a_all_train_nonfinite_losses": 4},
    {"lineage_C_70_job": "job-a"},
])
def test_earlier_stage_train_does_not_match(tmp_path: Path, facts: dict[str, Any]) -> None:
    assert ids(run(tmp_path, facts, [PLACE])["C_70/place/L-PLACE-POSE/l2"]) == ["none"]


# --- order and blocking across groups ---------------------------------------------------


def test_system_groups_rank_first_and_block_the_data_rules(tmp_path: Path) -> None:
    key = "C_70_cluster_approach_a_L-TIMEOUT_l1"
    facts = {**TRACK, **cov(True, 0, key=key), "lineage_C_70_job": "j",
             "train_j_all_train_nonfinite_losses": 1}
    hyps = run(tmp_path, facts, [TIMEOUT])["C_70/approach_a/L-TIMEOUT/l1"]
    assert ids(hyps) == ["controller_tracking", "earlier_stage_train", "weak_skill"]
    assert all(h.blocked_data_spend for h in hyps)
    assert hyps[2].interventions == ["report_only"]  # teleop_correction is held back


def test_a_data_rule_alone_is_not_blocked(tmp_path: Path) -> None:
    key = "C_70_cluster_approach_a_L-TIMEOUT_l1"
    facts = {"C_70_failed_exceeds_tau_upper": True, "C_70_tau_separates_upper": False,
             **cov(True, 0, key=key)}
    hyps = run(tmp_path, facts, [TIMEOUT])["C_70/approach_a/L-TIMEOUT/l1"]
    assert ids(hyps) == ["weak_skill"]
    assert not hyps[0].blocked_data_spend and hyps[0].interventions == ["teleop_correction"]


# --- refutes ---------------------------------------------------------------------------


REFUTER = {"id": "policy_like", "title": "Tracking does not tell failures from successes",
           "source": "test", "group": "runtime", "diagnosis": "unknown", "note": "n",
           "system": False, "interventions": ["repair_ticket"], "refutes": ["controller"],
           "when": [{"fact": "{run}_tau_separates_upper", "is": False}],
           "support": ["{run}_tau_separates_upper"]}


def _with_refuter(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "rules"
    root.mkdir()
    for path in RULES_DIR.glob("*.yaml"):
        (root / path.name).write_text(path.read_text())
    (root / "zz_test.yaml").write_text(yaml.safe_dump({"rules": [REFUTER]}))
    checks = tmp_path / "checks.yaml"
    checks.write_text(CHECKS_FILE.read_text())
    return root, checks


def test_a_non_system_rule_neither_blocks_nor_hides_its_refutation(tmp_path: Path) -> None:
    rules, checks = _with_refuter(tmp_path)
    facts = {"C_70_failed_exceeds_tau_upper": True, "C_70_tau_separates_upper": False,
             **cov(True, 0, key="C_70_cluster_approach_a_L-TIMEOUT_l1")}
    hyps = run(tmp_path, facts, [TIMEOUT], rules_dir=rules,
               checks_path=checks)["C_70/approach_a/L-TIMEOUT/l1"]
    assert ids(hyps) == ["policy_like", "weak_skill"]
    assert hyps[0].refutes == ["controller"] and hyps[1].refutes == []
    assert not any(h.blocked_data_spend for h in hyps)
    assert hyps[1].interventions == ["teleop_correction"]


def test_refutes_reaches_the_assembly(tmp_path: Path) -> None:
    out = tmp_path / "out"
    run_round(pack_maker(tmp_path)(), out, now=NOW)
    rules, checks = _with_refuter(tmp_path)
    refuter = {**REFUTER, "when": [{"cluster": "chain_broken"}], "support": []}
    (rules / "zz_test.yaml").write_text(yaml.safe_dump({"rules": [refuter]}))
    hypothesize(out, "tray", rules_dir=rules, checks_path=checks)
    record = RunRecord.model_validate_json((out / "run.json").read_text())
    assemble(out, record)
    raw = json.loads((out / ASSEMBLY_FILE).read_text())
    view = next(c for c in raw["clusters"]
                if c["cluster"]["cluster_id"] == "C_70/approach_a/L-PLACE-POSE/l2")
    assert {h["rule_id"]: h["refutes"] for h in view["hypotheses"]}["policy_like"] == [
        "controller"]


def test_an_old_hypothesis_line_without_refutes_still_loads(tmp_path: Path) -> None:
    out = tmp_path / "out"
    run_round(pack_maker(tmp_path)(), out, now=NOW)
    line = json.loads((out / HYPOTHESES_FILE).read_text().splitlines()[0])
    del line["refutes"]
    assert HypothesisRecord.model_validate(line).refutes == []


# --- regression: the fixture round is untouched -----------------------------------------


def test_the_scorer_rules_alone_give_the_same_fixture_hypotheses(tmp_path: Path) -> None:
    """The fixture pack holds no trace, train log or conditions: the new rules never fire,
    and every hypothesis is what the scorer rules alone give (the two rules as before)."""
    out = tmp_path / "out"
    run_round(pack_maker(tmp_path)(), out, now=NOW)
    full = (out / HYPOTHESES_FILE).read_text()
    root = tmp_path / "old"
    root.mkdir()
    (root / "scorer.yaml").write_text((RULES_DIR / "scorer.yaml").read_text())
    raw = yaml.safe_load(CHECKS_FILE.read_text())
    old = {"scorer_latch_too_strict", "label_signal_missing", "none"}
    raw["checks"] = [c for c in raw["checks"] if all(set(p) <= old for p in c["separates"])]
    checks = tmp_path / "checks.yaml"
    checks.write_text(yaml.safe_dump(raw))
    hypothesize(out, "tray", rules_dir=root, checks_path=checks)
    assert (out / HYPOTHESES_FILE).read_text() == full
    assert {json.loads(x)["rule_id"] for x in full.splitlines()} <= old

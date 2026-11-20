"""Step B3, hypothesize (DA-43 task 4.3), on the 4-run round of docs/he/tray.md 20.2 and 20.11."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest
import yaml
from flywheel.eval.agentqa.round.hypotheses import (
    CHECKS_FILE,
    HYPOTHESES_FILE,
    RULES_DIR,
    RulesRefused,
    hypothesize,
)
from flywheel.eval.agentqa.round.pipeline import STEPS, run_round
from flywheel.eval.agentqa.round.records import HypothesisRecord, RunRecord
from helpers_round import NOW, PackMaker, facts_of, pack_maker


@pytest.fixture
def make_pack(tmp_path: Path) -> PackMaker:
    return pack_maker(tmp_path)


@pytest.fixture
def round_out(make_pack: PackMaker, tmp_path: Path) -> Path:
    out = tmp_path / "out"
    run_round(make_pack(), out, now=NOW)
    return out


def read(out: Path) -> list[HypothesisRecord]:
    return [HypothesisRecord.model_validate_json(x)
            for x in (out / HYPOTHESES_FILE).read_text().splitlines()]


def of(out: Path, cluster_id: str) -> list[HypothesisRecord]:
    return sorted((h for h in read(out) if h.cluster.cluster_id == cluster_id),
                  key=lambda h: h.code_rank)


def test_the_approach_place_pose_cluster_is_a_scorer_fault_first(round_out: Path) -> None:
    hyps = of(round_out, "C_70/approach_a/L-PLACE-POSE/l2")
    top = hyps[0]
    assert top.cluster.size == 3 and top.rule_id == "scorer_latch_too_strict"
    facts = facts_of(round_out)
    assert facts["C_70_chain_broken_at_approach_a"].fact_id in top.support
    assert facts["chain_broken_at_approach_a_runs"].fact_id in top.support
    assert top.blocked_data_spend and top.interventions == ["repair_ticket"]
    assert [c.check_id for c in top.checks] == ["inspect_latch_on_successes",
                                                "log_missing_signals"]
    assert {h.rule_id for h in hyps} == {"scorer_latch_too_strict", "label_signal_missing"}


def test_tilt_without_failure_t_is_a_missing_signal(round_out: Path) -> None:
    hyps = of(round_out, "C_70/place/L-TRAY-TILT/l2")
    assert [h.rule_id for h in hyps] == ["label_signal_missing"]
    missing = facts_of(round_out)["L-TRAY-TILT_signals_missing"]
    assert "failure_t" in str(missing.value) and missing.fact_id in hyps[0].support


def test_a_timeout_implies_no_step(round_out: Path) -> None:
    hyps = of(round_out, "C_70/approach_a/L-TIMEOUT/l1")
    assert hyps and all(h.rule_id != "scorer_latch_too_strict" for h in hyps)


def test_the_large_place_pose_cluster_lacks_the_pose_signals(round_out: Path) -> None:
    # scores carry no final_tray_pose / target_pose, so L-PLACE-POSE is not judgeable;
    # place comes after reach_b, so the step chain is whole.
    hyps = of(round_out, "C_70/place/L-PLACE-POSE/l1")
    assert hyps[0].cluster.size == 14
    assert [(h.rule_id, h.code_rank) for h in hyps] == [("label_signal_missing", 1)]
    assert hyps[0].blocked_data_spend and hyps[0].interventions == ["repair_ticket"]
    assert [c.check_id for c in hyps[0].checks] == ["log_missing_signals"]
    assert facts_of(round_out)["L-PLACE-POSE_judgeable"].value is False


def test_every_cluster_is_explained_with_ranks_and_ids(round_out: Path) -> None:
    table = json.loads((round_out / "tables" / "T3-failure_clusters.json").read_text())
    hyps = read(round_out)
    by_cluster: dict[str, list[int]] = defaultdict(list)
    for h in hyps:
        by_cluster[h.cluster.cluster_id].append(h.code_rank)
    assert len(by_cluster) == len(table) == 64
    assert all(ranks == list(range(1, len(ranks) + 1)) for ranks in by_cluster.values())
    assert [h.hypothesis_id for h in hyps] == [f"H{k}" for k in range(1, len(hyps) + 1)]
    fact_ids = {f.fact_id for f in facts_of(round_out).values()}
    assert all(set(h.support) <= fact_ids for h in hyps)


def test_same_round_gives_the_same_bytes(make_pack: PackMaker, tmp_path: Path) -> None:
    pack = make_pack()
    run_round(pack, tmp_path / "a", now=NOW)
    run_round(pack, tmp_path / "b", now=NOW)
    assert ((tmp_path / "a" / HYPOTHESES_FILE).read_bytes()
            == (tmp_path / "b" / HYPOTHESES_FILE).read_bytes())


def _rules_dir(tmp_path: Path, edit: object = None, keep: tuple[str, ...] = ()) -> Path:
    raw = yaml.safe_load((RULES_DIR / "scorer.yaml").read_text())
    if keep:
        raw["rules"] = [r for r in raw["rules"] if r["id"] in keep]
    if edit is not None:
        edit(raw["rules"][0])  # type: ignore[operator]
    root = tmp_path / "rules"
    root.mkdir()
    (root / "scorer.yaml").write_text(yaml.safe_dump(raw))
    return root


def test_a_cluster_no_rule_matches_gets_the_none_hypothesis(
        round_out: Path, tmp_path: Path) -> None:
    rules = _rules_dir(tmp_path, keep=("scorer_latch_too_strict",))
    checks = tmp_path / "checks.yaml"
    raw = yaml.safe_load(CHECKS_FILE.read_text())
    for check in raw["checks"]:
        check["separates"] = [p for p in check["separates"] if "label_signal_missing" not in p]
    checks.write_text(yaml.safe_dump(raw))
    hyps = hypothesize(round_out, "tray", rules_dir=rules, checks_path=checks)
    place = [h for h in hyps if h.cluster.cluster_id == "C_70/place/L-PLACE-POSE/l1"]
    assert [(h.rule_id, h.group, h.diagnosis, h.note) for h in place] == [
        ("none", "data", "unknown", "no_rule_matched")]
    assert place[0].interventions == ["report_only"] and place[0].support == []
    assert not place[0].blocked_data_spend
    latch = [h for h in hyps if h.cluster.cluster_id == "C_70/approach_a/L-PLACE-POSE/l2"]
    assert [h.rule_id for h in latch] == ["scorer_latch_too_strict"]
    assert [c.check_id for c in latch[0].checks] == ["inspect_latch_on_successes",
                                                     "log_missing_signals"]


@pytest.mark.parametrize("edit, match", [
    (lambda r: r.update(diagnosis="haunted"), "diagnosis"),
    (lambda r: r.update(interventions=["sim_s1"]), "not allowed"),
    (lambda r: r.update(when=[{"fact": "{run}_chain_broken", "is": 3}]), "numeric literal"),
])
def test_bad_rules_are_refused(round_out: Path, tmp_path: Path, edit: object,
                               match: str) -> None:
    with pytest.raises(RulesRefused, match=match):
        hypothesize(round_out, "tray", rules_dir=_rules_dir(tmp_path, edit))


def test_a_check_naming_an_unknown_rule_is_refused(round_out: Path, tmp_path: Path) -> None:
    raw = yaml.safe_load(CHECKS_FILE.read_text())
    raw["checks"][0]["separates"].append(["scorer_latch_too_strict", "ghost_rule"])
    path = tmp_path / "checks.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(RulesRefused, match="ghost_rule"):
        hypothesize(round_out, "tray", checks_path=path)


def test_without_a_cluster_table_the_step_is_degraded(
        make_pack: PackMaker, tmp_path: Path) -> None:
    out = tmp_path / "out"
    record = run_round(make_pack(scores=False), out, now=NOW)
    step = record.steps[-1]
    assert step.name == "hypothesize" and step.status == "degraded" and step.rows == 0
    assert (out / HYPOTHESES_FILE).read_text() == ""
    assert any(p.startswith("hypothesize:") and "failure_clusters" in p
               for p in record.problems)


def test_from_hypothesize_rewrites_only_the_hypotheses(round_out: Path,
                                                      make_pack: PackMaker) -> None:
    assert STEPS == ("pack", "admit", "measure", "hypothesize")
    first = RunRecord.model_validate_json((round_out / "run.json").read_text())
    assert [s.name for s in first.steps] == list(STEPS)
    kept = {p: p.read_bytes() for p in round_out.rglob("*")
            if p.is_file() and p.name not in (HYPOTHESES_FILE, "run.json")}
    (round_out / HYPOTHESES_FILE).write_text("stale\n")
    pack = round_out.parent / "round" / "pack.json"
    again = run_round(pack, round_out, from_step="hypothesize")
    assert again.steps[:3] == first.steps[:3] and again.steps[3].rows == first.steps[3].rows
    assert again.steps[3].outputs == first.steps[3].outputs
    assert {p: p.read_bytes() for p in kept} == kept

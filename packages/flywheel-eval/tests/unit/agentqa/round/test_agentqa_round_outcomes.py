"""The round reads eval outcomes (K1): admit, measure, and the `near_miss_placement` rule.

DA-43 task 2.4. The fixture pack of the four 60k runs carries no outcomes: its facts must
stay byte for byte what they were before the outcome kind existed (golden values below,
taken on commit 508e6927 before any change of this task).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.contracts.entities import Score
from flywheel.contracts.outcome import RolloutOutcome
from flywheel.eval.agentqa.round.admit import KINDS, UNCACHED, admit
from flywheel.eval.agentqa.round.hypotheses import load_checks, load_rules
from flywheel.eval.agentqa.round.measure import PlanRefused, _context
from flywheel.eval.agentqa.round.pack import build_pack, read_pack, write_pack
from flywheel.eval.agentqa.round.pipeline import run_round
from helpers_round import (  # noqa: F401  (isolated_store is an autouse fixture)
    NOW,
    PackMaker,
    calls_of,
    facts_of,
    isolated_store,
    pack_maker,
)
from test_agentqa_round_rules_runtime_coverage_train import ids, run

# sha256 of the 417 lines of facts.jsonl, and of the signal_presence table, that the fixture
# round wrote before outcomes were read (commit 508e6927)
GOLDEN_FACTS = "29a0f68247ef50e97ae39430731d79a1b2cc38b607e62d5202d430e89836f4fd"
GOLDEN_FACT_LINES = 417
GOLDEN_SIGNALS_TABLE = "080d993e6f1f0726b3ffb723bdb995a94ec310c977a1b47ffc0e482ff6578e20"
PLACE = "L-PLACE-POSE"
POSE = {"tray_pos_m": [0.0, 0.0, 0.8], "tray_quat": [1.0, 0.0, 0.0, 0.0],
        "target_xy_m": [0.0, 0.0], "target_yaw_rad": 0.0,
        "place_yaw_error_deg": 1.0}


@pytest.fixture
def make_pack(tmp_path: Path) -> PackMaker:
    return pack_maker(tmp_path)


def lines(models: list[Any]) -> str:
    return "".join(m.model_dump_json() + "\n" for m in models)


def score(run_name: str, name: str, success: bool, label: str | None = None,
          level: int = 1) -> Score:
    return Score(episode_id=f"{run_name}/{name}", task_id="tray", config_sha256="0" * 64,
                 trace_sha256="0" * 64, success=success, failure_kind=label, level=level,
                 step_status=["pass"] * 7 if success else
                 ["pass"] * 5 + ["fail", "not_attempted"],  # type: ignore[arg-type]
                 first_failed_step=None if success else 5)


def outcome(run_name: str, name: str, success: bool, label: str | None = None, *,
            d: float | None = None, task_id: str = "tray") -> RolloutOutcome:
    final: dict[str, Any] = dict(POSE)
    if d is not None:
        final["place_distance_m"] = d
    return RolloutOutcome.model_validate({
        "episode_id": f"{run_name}/{name}", "run_plan_id": "rp-1", "task_id": task_id,
        "run": run_name, "seed": 1, "level": 1, "sim_time_s": 10.0, "control_steps": 500,
        "final": final if not success else {},
        "verdict": {"scorer_version": "2", "step_names": ["place"],
                    "step_latched": [success], "success": success, "failure_label": label,
                    "failure_t": None if label is None else 2.0}})


def outcome_pack(root: Path, runs: dict[str, tuple[list[Score], list[RolloutOutcome] | None]],
                 extra: list[dict[str, Any]] | None = None) -> Path:
    root.mkdir()
    entries: list[dict[str, Any]] = []
    for name, (scores, outs) in runs.items():
        (root / name).mkdir()
        (root / name / "scores.jsonl").write_text(lines(scores))
        entries.append({"path": f"{name}/scores.jsonl", "kind": "scores",
                        "subject": {"run": name}})
        if outs is not None:
            (root / name / "outcomes.jsonl").write_text(lines(outs))
            entries.append({"path": f"{name}/outcomes.jsonl", "kind": "outcomes",
                            "subject": {"run": name}})
    entries += extra or []
    decl = root / "round.yaml"
    decl.write_text(yaml.safe_dump({"task_id": "tray", "declared_by": "test",
                                    "data_class": "public", "entries": entries}))
    return write_pack(build_pack(decl), root)


def near_set(run_name: str) -> tuple[list[Score], list[RolloutOutcome]]:
    """One success and three place failures, two of them within the widest grid value."""
    scores = [score(run_name, "ok", True)] + [score(run_name, n, False, PLACE) for n in "abc"]
    outs = [outcome(run_name, "ok", True), outcome(run_name, "a", False, PLACE, d=0.07),
            outcome(run_name, "b", False, PLACE, d=0.18),
            outcome(run_name, "c", False, PLACE, d=0.6)]
    return scores, outs


# --- admit -------------------------------------------------------------------------------


def test_outcomes_are_a_kind_with_a_contract_and_are_kept() -> None:
    assert KINDS["outcomes"].model is RolloutOutcome and not KINDS["outcomes"].one
    assert "outcomes" not in UNCACHED  # small: one line per rollout


def test_outcomes_of_another_task_are_rejected_like_scores(tmp_path: Path) -> None:
    scores, outs = near_set("R")
    foreign = [o.model_copy(update={"task_id": "two_table"}) for o in outs]
    pack = outcome_pack(tmp_path / "p", {"R": (scores, foreign)})
    a = admit(pack).admission
    reasons = {r.ref: r.reason for r in a.rejected}
    assert reasons["R/outcomes.jsonl"] == "outcomes of task two_table, the pack is for tray"
    assert a.accepted == ["R/scores.jsonl"]


def test_a_line_that_is_not_an_outcome_rejects_the_entry(tmp_path: Path) -> None:
    root = tmp_path / "p"
    scores, outs = near_set("R")
    (outcome_pack(root, {"R": (scores, outs)})).unlink()  # declared again below
    bad = root / "bad.jsonl"
    bad.write_text(lines(scores))  # scores are not outcomes
    decl = yaml.safe_load((root / "round.yaml").read_text())
    decl["entries"].append({"path": "bad.jsonl", "kind": "outcomes", "subject": {"run": "R"}})
    (root / "round.yaml").write_text(yaml.safe_dump(decl))
    pack = write_pack(build_pack(root / "round.yaml"), root)
    reasons = {r.ref: r.reason for r in admit(pack).admission.rejected}
    assert reasons["bad.jsonl"].startswith("does not parse as outcomes")


def test_two_outcomes_entries_of_one_run_refuse_the_plan(tmp_path: Path) -> None:
    root = tmp_path / "p"
    scores, outs = near_set("R")
    (outcome_pack(root, {"R": (scores, outs)})).unlink()  # declared again below
    (root / "more.jsonl").write_text(lines(outs[:1]))
    decl = yaml.safe_load((root / "round.yaml").read_text())
    decl["entries"].append({"path": "more.jsonl", "kind": "outcomes", "subject": {"run": "R"}})
    (root / "round.yaml").write_text(yaml.safe_dump(decl))
    pack_path = write_pack(build_pack(root / "round.yaml"), root)
    with pytest.raises(PlanRefused, match="already declared"):
        _context(read_pack(pack_path), admit(pack_path))


def test_measure_holds_the_outcomes_of_each_run(tmp_path: Path) -> None:
    scores, outs = near_set("R")
    pack_path = outcome_pack(tmp_path / "p", {"R": (scores, outs), "S": (scores, None)})
    ctx, _ = _context(read_pack(pack_path), admit(pack_path))
    assert list(ctx.outcomes) == ["R"] and len(ctx.outcomes["R"].outcomes) == 4
    assert ctx.outcomes["R"].ref == "R/outcomes.jsonl" and "outcomes" in ctx.kinds


# --- the round ----------------------------------------------------------------------------


def test_the_fixture_round_without_outcomes_keeps_its_facts_byte_for_byte(
        make_pack: PackMaker, tmp_path: Path) -> None:
    out = tmp_path / "out"
    run_round(make_pack(), out, command="test", now=NOW)
    facts = (out / "facts.jsonl").read_text().splitlines()
    before = [x for x in facts if json.loads(x)["tool_call_id"] != "T13"]
    assert len(before) == GOLDEN_FACT_LINES
    assert hashlib.sha256(("\n".join(before) + "\n").encode()).hexdigest() == GOLDEN_FACTS
    table = (out / "tables" / "T5-signal_presence.json").read_bytes()
    assert hashlib.sha256(table).hexdigest() == GOLDEN_SIGNALS_TABLE
    calls = calls_of(out)
    assert (calls[4].tool, calls[4].version) == ("signal_presence", 2)
    assert (calls[12].tool, calls[12].status) == ("relaxed_sweep", "skipped")
    assert facts_of(out)["relaxed_sweep_not_judged"].value == (
        "no entry of kind outcomes in the pack")


def test_a_round_with_outcomes_sweeps_and_hypothesizes_a_near_miss(tmp_path: Path) -> None:
    scores, outs = near_set("R")
    pack_path = outcome_pack(tmp_path / "p", {"R": (scores, outs)})
    out = tmp_path / "out"
    run_round(pack_path, out, command="test", now=NOW, store=tmp_path / "store")
    facts = facts_of(out)
    assert facts["R_relaxed_all_successes"].value == 1
    assert facts["R_relaxed_all_pos5_successes"].value == 3
    assert facts["R_cluster_place_L-PLACE-POSE_l1_near_miss"].value is True
    assert facts[f"{PLACE}_judgeable"].value is True
    calls = {c.tool: c for c in calls_of(out)}
    assert calls["relaxed_sweep"].status == "ran" and calls["relaxed_sweep"].version == 1
    sha = {e.ref: e.sha256 for e in read_pack(out / "pack.json").entries}
    assert sha["R/outcomes.jsonl"] in calls["relaxed_sweep"].input_sha256
    assert (out / "tables" / "T13-relaxed_sweep.json").is_file()
    hyps = [json.loads(x) for x in (out / "hypotheses.jsonl").read_text().splitlines()]
    place = [h for h in hyps if h["cluster"]["label"] == PLACE]
    assert [h["rule_id"] for h in place] == ["near_miss_placement"]
    assert place[0]["diagnosis"] == "weak_skill"
    assert place[0]["interventions"] == ["teleop_correction"]
    assert not place[0]["blocked_data_spend"]


def test_a_run_judgeable_from_its_outcomes_is_not_blocked_by_another_run(
        tmp_path: Path) -> None:
    scores, outs = near_set("R")
    other = [score("S", n, False, PLACE) for n in "abc"]
    pack_path = outcome_pack(tmp_path / "p", {"R": (scores, outs), "S": (other, None)})
    out = tmp_path / "out"
    run_round(pack_path, out, command="test", now=NOW, store=tmp_path / "store")
    hyps = [json.loads(x) for x in (out / "hypotheses.jsonl").read_text().splitlines()]
    by_run: dict[str, list[str]] = {h["cluster"]["run"]: [] for h in hyps}
    for h in hyps:
        by_run[h["cluster"]["run"]].append(h["rule_id"])
    assert "label_signal_missing" not in by_run["R"]
    assert "label_signal_missing" in by_run["S"]


# --- the near_miss_placement rule ----------------------------------------------------------


PLACE_CLUSTER = ("C_70", "place", PLACE, 2)
KEY = "C_70_cluster_place_L-PLACE-POSE_l2"


def near(miss: bool | None, agrees: bool | None = True) -> dict[str, Any]:
    facts: dict[str, Any] = {f"{KEY}_relaxed_distance_median": 0.08,
                             f"{KEY}_relaxed_within_widest": 2, "relaxed_position_widest": 0.2}
    if miss is not None:
        facts[f"{KEY}_near_miss"] = miss
    if agrees is not None:
        facts["C_70_relaxed_first_grid_matches_scorer"] = agrees
    return facts


def test_the_rule_is_a_data_rule_without_a_numeric_literal() -> None:
    rule = next(r for r in load_rules() if r.id == "near_miss_placement")
    assert (rule.group, rule.diagnosis, rule.system) == ("data", "weak_skill", False)
    assert rule.interventions == ["teleop_correction"]
    check = next(c for c in load_checks(load_rules()) if c.id == "coverage_distance_check")
    assert ["near_miss_placement", "coverage_gap"] in check.separates


@pytest.mark.parametrize("facts, expect", [
    (near(True), ["near_miss_placement"]),
    (near(False), ["none"]),
    (near(None), ["none"]),                 # a missing fact never matches
    (near(True, agrees=False), ["none"]),   # the measures do not reproduce the scorer
    (near(True, agrees=None), ["none"]),
])
def test_near_miss_placement(tmp_path: Path, facts: dict[str, Any], expect: list[str]) -> None:
    assert ids(run(tmp_path, facts, [PLACE_CLUSTER])["C_70/place/L-PLACE-POSE/l2"]) == expect


def test_near_miss_cites_its_facts_and_offers_the_coverage_check(tmp_path: Path) -> None:
    facts = near(True)
    facts[f"{KEY}_coverage_in_domain"] = True
    facts[f"{KEY}_coverage_above_tau"] = 1
    hyps = run(tmp_path, facts, [PLACE_CLUSTER])["C_70/place/L-PLACE-POSE/l2"]
    assert ids(hyps) == ["near_miss_placement", "coverage_gap"]
    top = hyps[0]
    assert len(top.support) == 5 and not top.blocked_data_spend
    assert "coverage_distance_check" in [c.check_id for c in top.checks]

"""Step B2 with a pack that carries scores, trace, metrics, episodes and a dataset report.

The default plan of the tray task does not call the telemetry tools yet (the round tests
pin its six calls), so the plan here is written next to the pack and names only them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from flywheel.contracts.entities import FixRateEvent, Score
from flywheel.eval.agentqa.round.admit import admit
from flywheel.eval.agentqa.round.measure import PlanRefused, measure
from flywheel.eval.agentqa.round.pack import build_pack, read_pack, write_pack
from flywheel.eval.agentqa.round.records import FactRecord, ToolCallRecord
from flywheel.store.ledger_append import append_ledger_entry
from flywheel.store.paths import StorePaths
from flywheel.store.tables import write_record
from helpers_tools import SHA, condition, episode, ledger_row, metric, report, rollout, score

PLAN = {"task_id": "tray", "calls": [
    {"tool": "trace_stats", "params": {"runs": "all"}},
    {"tool": "train_window", "params": {"jobs": "all", "window": "all"}},
    {"tool": "lineage", "params": {}},
]}


def lines(models: list) -> str:  # type: ignore[type-arg]
    return "".join(m.model_dump_json() + "\n" for m in models)


def make(root: Path, *, telemetry: bool = True) -> Path:
    root.mkdir()
    (root / "scores.jsonl").write_text(lines([score("R", "ok", True), score("R", "bad", False)]))
    entries: list[dict[str, object]] = [
        {"path": "scores.jsonl", "kind": "scores",
         "subject": {"run": "R", "checkpoint": "ckpt-1"}}]
    if telemetry:
        steps = rollout("R", "ok", upper_gap=0.01) + rollout("R", "bad", upper_gap=0.5)
        (root / "trace.jsonl").write_text(lines(steps))
        (root / "metrics.jsonl").write_text(lines(
            [metric("J", 10, 1.0, vlm=3.0), metric("J", 20, 0.5, split="val")]))
        (root / "episodes.jsonl").write_text(lines([episode("R/ok", "ckpt-1")]))
        (root / "report.json").write_text(report("ds-9").model_dump_json())
        entries += [
            {"path": "trace.jsonl", "kind": "trace", "subject": {"run": "R"}},
            {"path": "metrics.jsonl", "kind": "metrics", "subject": {"job": "J"}},
            {"path": "episodes.jsonl", "kind": "episodes"},
            {"path": "report.json", "kind": "dataset_report", "subject": {"release": "rel-1"}}]
    decl = root / "round.yaml"
    decl.write_text(yaml.safe_dump({"task_id": "tray", "declared_by": "test",
                                    "data_class": "public", "entries": entries}))
    return write_pack(build_pack(decl), root)


def plan(tmp_path: Path, calls: list[dict[str, object]] | None = None) -> Path:
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump({**PLAN, "calls": calls or PLAN["calls"]}))
    return path


def run(pack: Path, plan_path: Path, out: Path) -> None:
    measure(read_pack(pack), admit(pack), plan_path, out)


def test_facts_and_tables_of_the_three_tools_land_in_the_run_directory(tmp_path: Path) -> None:
    out = tmp_path / "out"
    run(make(tmp_path / "pack"), plan(tmp_path), out)
    facts = {f.name: f for f in map(FactRecord.model_validate_json,
                                    (out / "facts.jsonl").read_text().splitlines())}
    assert facts["R_failed_track_error_upper"].value == pytest.approx(0.5)
    assert facts["R_failed_track_error_upper"].tool_call_id == "T1"
    assert facts["R_tau_separates_upper"].value is True
    assert facts["train_J_all_train_loss_last"].tool_call_id == "T2"
    assert facts["lineage_R_job"].value == "J" and facts["lineage_R_dataset"].value == "ds-9"
    assert facts["lineage_R_release"].tool_call_id == "T3"
    assert all(f.provenance == "code" for f in facts.values())
    assert sorted(p.name for p in (out / "tables").glob("*.json")) == [
        "T1-trace_stats.json", "T2-train_window.json", "T3-lineage.json"]
    assert json.loads((out / "tables" / "T3-lineage.json").read_text()) == [
        {"run": "R", "checkpoint": "ckpt-1", "job": "J", "release": "rel-1",
         "dataset": "ds-9"}]
    calls = [ToolCallRecord.model_validate_json(x)
             for x in (out / "tool_calls.jsonl").read_text().splitlines()]
    assert [c.status for c in calls] == ["ran"] * 3
    assert len(calls[0].input_sha256) == 2 and len(calls[1].input_sha256) == 1
    assert len(calls[2].input_sha256) == 5  # lineage reads every accepted entry


def test_the_same_pack_gives_the_same_bytes(tmp_path: Path) -> None:
    pack = make(tmp_path / "pack")
    run(pack, plan(tmp_path), tmp_path / "a")
    run(pack, plan(tmp_path), tmp_path / "b")
    for name in ("facts.jsonl", "tool_calls.jsonl", "tables/T3-lineage.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_a_pack_without_telemetry_skips_two_calls_and_not_judges_the_chain(
        tmp_path: Path) -> None:
    out = tmp_path / "out"
    run(make(tmp_path / "pack", telemetry=False), plan(tmp_path), out)
    calls = [ToolCallRecord.model_validate_json(x)
             for x in (out / "tool_calls.jsonl").read_text().splitlines()]
    assert [c.status for c in calls] == ["skipped", "skipped", "ran"]
    assert "kind trace" in calls[0].reason and "kind metrics" in calls[1].reason
    names = [f.name for f in map(FactRecord.model_validate_json,
                                 (out / "facts.jsonl").read_text().splitlines())]
    assert "lineage_R_job_not_judged" in names and "lineage_R_checkpoint" in names


def test_a_window_step_that_is_not_logged_refuses_the_plan(tmp_path: Path) -> None:
    bad = plan(tmp_path, [{"tool": "train_window", "params": {"jobs": "all", "window": 15}}])
    with pytest.raises(PlanRefused, match="not a logged step of job J"):
        run(make(tmp_path / "pack"), bad, tmp_path / "out")


def make_coverage(root: Path) -> Path:
    root.mkdir()
    fails = [Score(episode_id=f"R/{n}", task_id="tray", config_sha256=SHA, trace_sha256=SHA,
                   success=False, failure_kind="L-A", first_failed_step=1, level=1)
             for n in ("l1-s20", "l1-s21")]
    (root / "scores.jsonl").write_text(lines(fails))
    def at(x: float) -> dict[str, object]:
        names = ["tray_x", "tray_y", "tray_yaw", "target_x", "target_y", "target_yaw"]
        return {n: (x if n == "tray_x" else 0.0) for n in names}

    train = [condition(1, s, at(float(s))) for s in range(7)]
    eval_ = [condition(1, 20, at(3.0)), condition(1, 21, at(30.0))]
    (root / "train.jsonl").write_text(lines(train))
    (root / "eval.jsonl").write_text(lines(eval_))
    entries = [
        {"path": "scores.jsonl", "kind": "scores", "subject": {"run": "R"}},
        {"path": "train.jsonl", "kind": "conditions", "subject": {"role": "train"}},
        {"path": "eval.jsonl", "kind": "conditions", "subject": {"role": "eval"}}]
    decl = root / "round.yaml"
    decl.write_text(yaml.safe_dump({"task_id": "tray", "declared_by": "test",
                                    "data_class": "public", "entries": entries}))
    return write_pack(build_pack(decl), root)


def test_coverage_cost_and_history_land_in_the_run_directory(tmp_path: Path) -> None:
    store = tmp_path / "store"
    paths = StorePaths(store)
    estimate = ledger_row("estimated", "eval", "gpu_seconds", "s", 600.0, 0.24)
    append_ledger_entry(estimate, paths)
    append_ledger_entry(ledger_row("measured", "eval", "gpu_seconds", "s", 450.0, 0.18,
                                   estimate=estimate.id), paths)
    write_record("fix_rate_event", FixRateEvent(intervention_type="sim_s1", n_conditions=10,
                                                fixed=4), paths)
    calls: list[dict[str, object]] = [{"tool": "coverage_distance", "params": {"runs": "all"}},
             {"tool": "cost_lookup", "params": {"checks": "all", "interventions": ["sim_s1"]}},
             {"tool": "history_lookup", "params": {"interventions": ["sim_s1", "sim_s2"]}}]
    pack, out = make_coverage(tmp_path / "pack"), tmp_path / "out"
    measure(read_pack(pack), admit(pack), plan(tmp_path, calls), out, store)
    facts = {f.name: f for f in map(FactRecord.model_validate_json,
                                    (out / "facts.jsonl").read_text().splitlines())}
    cluster = "R_cluster_grasp_L-A_l1_coverage"
    assert facts["tau_cov_l1"].tool_call_id == "T1" and facts["tau_cov_l1"].unit == "jitter"
    assert facts[f"{cluster}_matched"].value == 2 and facts[f"{cluster}_in_domain"].value is False
    assert facts["cost_log_missing_signals_measured_quantity_median"].value == 450.0
    assert facts["cost_log_missing_signals_measured_quantity_median"].tool_call_id == "T2"
    assert facts["cost_sim_s1_measured_rows"].value == 0
    assert facts["history_sim_s1_fix_rate"].value == pytest.approx(0.4)
    assert "history_lookup_not_judged" in facts  # sim_s2 was never tried
    assert sorted(p.name for p in (out / "tables").glob("*.json")) == [
        "T1-coverage_distance.json", "T3-history_lookup.json"]
    calls_back = [ToolCallRecord.model_validate_json(x)
                  for x in (out / "tool_calls.jsonl").read_text().splitlines()]
    assert [c.status for c in calls_back] == ["ran"] * 3
    assert len(calls_back[0].input_sha256) == 3 and calls_back[1].input_sha256 == []

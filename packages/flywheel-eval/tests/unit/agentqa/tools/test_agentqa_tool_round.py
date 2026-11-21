"""Step B2 with a pack that carries scores, trace, metrics, episodes and a dataset report.

The default plan of the tray task does not call the telemetry tools yet (the round tests
pin its six calls), so the plan here is written next to the pack and names only them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from flywheel.eval.agentqa.round.admit import admit
from flywheel.eval.agentqa.round.measure import PlanRefused, measure
from flywheel.eval.agentqa.round.pack import build_pack, read_pack, write_pack
from flywheel.eval.agentqa.round.records import FactRecord, ToolCallRecord
from helpers_tools import episode, metric, report, rollout, score

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

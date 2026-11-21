"""Step B2 and the runner (DA-43 task 4.2); the pack is built from the tool tests' rollouts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from flywheel.eval.agentqa.round.measure import PlanRefused
from flywheel.eval.agentqa.round.pack import sha256_of
from flywheel.eval.agentqa.round.pipeline import STEPS, RunRefused, run_round
from flywheel.eval.agentqa.round.records import RunRecord
from helpers_round import (  # noqa: F401  (isolated_store is an autouse fixture)
    NOW,
    PackMaker,
    calls_of,
    edited_plan,
    facts_of,
    isolated_store,
    pack_maker,
)


@pytest.fixture
def make_pack(tmp_path: Path) -> PackMaker:
    return pack_maker(tmp_path)


def test_a_round_writes_every_file_and_the_published_numbers(
        make_pack: PackMaker, tmp_path: Path) -> None:
    out = tmp_path / "out"
    record = run_round(make_pack(), out, command="test", now=NOW)
    assert record.status == "degraded" and [s.name for s in record.steps] == list(STEPS)
    # the fixture has no trace and no metrics: admit and measure say so; assemble: no model
    assert [(s.name, s.status) for s in record.steps] == [
        ("pack", "ok"), ("admit", "degraded"), ("measure", "degraded"),
        ("hypothesize", "ok"), ("assemble", "degraded"), ("render", "ok")]
    assert record.data_class == "public"
    for name in ("pack.json", "admission.json", "facts.jsonl", "tool_calls.jsonl", "run.json"):
        assert (out / name).is_file()
    assert RunRecord.model_validate_json((out / "run.json").read_text()) == record
    assert sorted(p.name for p in (out / "tables").glob("*.json")) == [
        "T1-task_lookup.json", "T2-step_pass_table.json", "T3-failure_clusters.json",
        "T4-latch_consistency.json", "T5-signal_presence.json", "T6-paired_compare.json",
        "T9-lineage.json"]
    facts = facts_of(out)
    assert facts["C_70_chain_broken"].value == 7
    assert facts["C_ALL_all_pass_place"].value == pytest.approx(0.1)
    assert facts["C_70_chain_broken"].tool_call_id == "T4"
    assert all(f.provenance == "code" for f in facts.values())
    calls = calls_of(out)
    assert [c.call_id for c in calls] == [f"T{k}" for k in range(1, 13)]
    assert [(c.tool, c.status) for c in calls] == [
        ("task_lookup", "ran"), ("step_pass_table", "ran"), ("failure_clusters", "ran"),
        ("latch_consistency", "ran"), ("signal_presence", "ran"), ("paired_compare", "ran"),
        ("trace_stats", "skipped"), ("train_window", "skipped"), ("lineage", "ran"),
        ("coverage_distance", "skipped"), ("cost_lookup", "ran"), ("history_lookup", "ran")]
    assert calls[0].input_sha256 == [] and len(calls[1].input_sha256) == 4
    assert len(json.loads((out / "tables" / "T6-paired_compare.json").read_text())) == 6


def test_same_pack_and_plan_give_the_same_bytes(make_pack: PackMaker, tmp_path: Path) -> None:
    pack = make_pack()
    run_round(pack, tmp_path / "a", now=NOW)
    run_round(pack, tmp_path / "b", now=NOW)
    for name in ("facts.jsonl", "tool_calls.jsonl", "tables/T6-paired_compare.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_a_plan_naming_an_unknown_run_is_refused_before_measure_writes(
        make_pack: PackMaker, tmp_path: Path) -> None:
    def edit(plan: dict[str, list[dict[str, object]]]) -> None:
        call = next(c for c in plan["calls"] if c["tool"] == "paired_compare")
        call["params"] = {"pairs": [["C_70", "NOPE"]], "levels": "all"}

    out = tmp_path / "out"
    with pytest.raises(PlanRefused, match="NOPE"):
        run_round(make_pack(), out, plan_path=edited_plan(tmp_path, edit), now=NOW)
    assert not (out / "facts.jsonl").exists() and not (out / "tables").exists()
    record = RunRecord.model_validate_json((out / "run.json").read_text())
    assert record.status == "broken"
    assert [(s.name, s.status) for s in record.steps] == [
        ("pack", "ok"), ("admit", "degraded"), ("measure", "broken")]
    assert record.problems[0] == "admit: no accepted entry of kind trace"
    assert record.problems[1:3] == ["admit: no accepted entry of kind metrics",
                                    "admit: no accepted entry of kind conditions"]
    assert "NOPE" in record.problems[3]


def test_a_plan_for_another_task_is_refused(make_pack: PackMaker, tmp_path: Path) -> None:
    def edit(plan: dict[str, object]) -> None:
        plan["task_id"] = "two_table"

    with pytest.raises(PlanRefused, match="two_table"):
        run_round(make_pack(), tmp_path / "out", plan_path=edited_plan(tmp_path, edit))


def test_a_pack_without_scores_skips_calls_and_says_why(
        make_pack: PackMaker, tmp_path: Path) -> None:
    out = tmp_path / "out"
    record = run_round(make_pack(scores=False), out, now=NOW)
    assert record.status == "degraded"
    calls = calls_of(out)
    assert [c.status for c in calls] == ["ran"] + ["skipped"] * 9 + ["ran"] * 2  # cost, history
    facts = facts_of(out)
    for call in calls[1:10]:
        assert call.not_judged and call.reason and len(call.fact_ids) == 1
        assert f"{call.tool}_not_judged" in facts
    assert any("scores" in p for p in record.problems)


def test_from_measure_rewrites_facts_and_keeps_the_admit_record(
        make_pack: PackMaker, tmp_path: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    first = run_round(pack, out, now=NOW)
    before = facts_of(out)

    def edit(plan: dict[str, list[dict[str, object]]]) -> None:
        plan["calls"][4]["params"] = {"labels": "all"}

    again = run_round(pack, out, plan_path=edited_plan(tmp_path, edit), from_step="measure")
    assert again.run_id == first.run_id and again.started_at == first.started_at
    assert again.steps[:2] == first.steps[:2]
    after = facts_of(out)
    assert set(after) > set(before) and "L-PLACE-POSE_judgeable" in after
    assert RunRecord.model_validate_json((out / "run.json").read_text()) == again


def test_a_tampered_kept_step_is_refused(make_pack: PackMaker, tmp_path: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    run_round(pack, out, now=NOW)
    with (out / "admission.json").open("a") as f:
        f.write(" ")
    with pytest.raises(RunRefused, match="admission.json"):
        run_round(pack, out, from_step="measure")


def test_a_changed_admission_is_refused(make_pack: PackMaker, tmp_path: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    run_round(pack, out, now=NOW)
    # a stored admission the recorded hash agrees with, but that is not what admit says now
    stored = json.loads((out / "admission.json").read_text())
    stored["hosted_allowed"] = not stored["hosted_allowed"]
    (out / "admission.json").write_text(json.dumps(stored))
    run = json.loads((out / "run.json").read_text())
    run["steps"][1]["outputs"]["admission.json"] = sha256_of(out / "admission.json")
    (out / "run.json").write_text(json.dumps(run))
    with pytest.raises(RunRefused, match="differs"):
        run_round(pack, out, from_step="measure")


def test_unknown_step_and_existing_directory(make_pack: PackMaker, tmp_path: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    run_round(pack, out, now=NOW)
    with pytest.raises(FileExistsError):
        run_round(pack, out)
    with pytest.raises(RunRefused, match="unknown step"):
        run_round(pack, out, from_step="nonsense")
    shutil.rmtree(out)
    with pytest.raises(RunRefused, match="run.json"):
        run_round(pack, out, from_step="measure")


def test_two_cluster_calls_over_different_runs_do_not_clash(
        make_pack: PackMaker, tmp_path: Path) -> None:
    def edit(plan: dict[str, list[dict[str, object]]]) -> None:
        plan["calls"].insert(3, {"tool": "failure_clusters", "params": {"runs": ["C_70"]}})

    out = tmp_path / "out"
    record = run_round(make_pack(), out, plan_path=edited_plan(tmp_path, edit), now=NOW)
    assert record.status != "broken"
    # "other runs" counts over every run of the pack, whatever runs the call names
    assert facts_of(out)["C_70_cluster_approach_a_L-PLACE-POSE_l2_in_other_runs"].value == 3

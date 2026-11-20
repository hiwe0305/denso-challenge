"""Step B2 and the runner (DA-43 task 4.2); the pack is built from the tool tests' rollouts."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from flywheel.contracts.entities import Score, Source
from flywheel.eval.agentqa.round.measure import PlanRefused
from flywheel.eval.agentqa.round.pack import build_pack, sha256_of, write_pack
from flywheel.eval.agentqa.round.pipeline import STEPS, RunRefused, run_round
from flywheel.eval.agentqa.round.records import FactRecord, RunRecord, ToolCallRecord

PLAN = Path("configs") / "eval" / "agentqa" / "plans" / "tray.yaml"  # from the repo root
PackMaker = Callable[..., Path]
DATA = Path(__file__).parents[1] / "tools" / "data" / "pair60k_stage1.jsonl"
SHA = "0" * 64


def _status(flags: str) -> list[str]:
    out, failed = [], False
    for flag in flags:
        if flag == "1":
            out.append("pass")
        elif not failed:
            out.append("fail")
            failed = True
        else:
            out.append("not_attempted")
    return out


def _score_line(row: dict[str, object]) -> str:
    status = _status(str(row["steps"]))
    run = row["run"]
    return Score(
        episode_id=f"{run}/l{row['level']}-s{row['seed']}", task_id="tray",
        config_sha256=SHA, trace_sha256=SHA, success=bool(row["success"]),
        step_status=status,  # type: ignore[arg-type]
        first_failed_step=next((k for k, s in enumerate(status) if s == "fail"), None),
        failure_kind=row["failure"], level=row["level"],  # type: ignore[arg-type]
    ).model_dump_json()


@pytest.fixture
def make_pack(tmp_path: Path) -> PackMaker:
    """`make_pack(name, scores=True)` -> path of a `pack.json` under tmp_path/name."""

    def make(name: str = "round", *, scores: bool = True) -> Path:
        root = tmp_path / name
        root.mkdir()
        by_run: dict[str, list[str]] = defaultdict(list)
        for line in DATA.read_text().splitlines():
            row = json.loads(line)
            by_run[row["run"]].append(_score_line(row))
        (root / "sources.jsonl").write_text(Source(
            uri="hf://psi-data", sha256=SHA, downloaded_at="2026-11-01",
            data_class="public").model_dump_json() + "\n")
        entries: list[dict[str, object]] = [{"path": "sources.jsonl", "kind": "sources"}]
        links = []
        for run, lines in by_run.items() if scores else []:
            (root / run).mkdir()
            (root / run / "scores.jsonl").write_text("\n".join(lines) + "\n")
            entries.append({"path": f"{run}/scores.jsonl", "kind": "scores",
                            "subject": {"run": run}})
            links.append({"source": f"{run}/scores.jsonl", "target": "sources.jsonl",
                          "relation": "data_of"})
        decl = root / "round.yaml"
        decl.write_text(yaml.safe_dump({"task_id": "tray", "declared_by": "test",
                                        "data_class": "public", "entries": entries,
                                        "links": links}))
        return write_pack(build_pack(decl), root)

    return make

NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)


def facts_of(out: Path) -> dict[str, FactRecord]:
    lines = (out / "facts.jsonl").read_text().splitlines()
    return {f.name: f for f in map(FactRecord.model_validate_json, lines)}


def calls_of(out: Path) -> list[ToolCallRecord]:
    return [ToolCallRecord.model_validate_json(x)
            for x in (out / "tool_calls.jsonl").read_text().splitlines()]


def edited_plan(tmp_path: Path, edit: object) -> Path:
    plan = yaml.safe_load(PLAN.read_text())
    edit(plan)  # type: ignore[operator]
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(plan))
    return path


def test_a_round_writes_every_file_and_the_published_numbers(
        make_pack: PackMaker, tmp_path: Path) -> None:
    out = tmp_path / "out"
    record = run_round(make_pack(), out, command="test", now=NOW)
    assert record.status == "ok" and [s.name for s in record.steps] == list(STEPS)
    assert {s.status for s in record.steps} == {"ok"} and record.data_class == "public"
    for name in ("pack.json", "admission.json", "facts.jsonl", "tool_calls.jsonl", "run.json"):
        assert (out / name).is_file()
    assert RunRecord.model_validate_json((out / "run.json").read_text()) == record
    assert sorted(p.name for p in (out / "tables").glob("*.json")) == [
        "T1-task_lookup.json", "T2-step_pass_table.json", "T3-failure_clusters.json",
        "T4-latch_consistency.json", "T5-signal_presence.json", "T6-paired_compare.json"]
    facts = facts_of(out)
    assert facts["C_70_chain_broken"].value == 7
    assert facts["C_ALL_all_pass_place"].value == pytest.approx(0.1)
    assert facts["C_70_chain_broken"].tool_call_id == "T4"
    assert all(f.provenance == "code" for f in facts.values())
    calls = calls_of(out)
    assert [c.call_id for c in calls] == ["T1", "T2", "T3", "T4", "T5", "T6"]
    assert all(c.status == "ran" for c in calls)
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
        plan["calls"][-1]["params"] = {"pairs": [["C_70", "NOPE"]], "levels": "all"}

    out = tmp_path / "out"
    with pytest.raises(PlanRefused, match="NOPE"):
        run_round(make_pack(), out, plan_path=edited_plan(tmp_path, edit), now=NOW)
    assert not (out / "facts.jsonl").exists() and not (out / "tables").exists()
    record = RunRecord.model_validate_json((out / "run.json").read_text())
    assert record.status == "broken"
    assert [(s.name, s.status) for s in record.steps] == [
        ("pack", "ok"), ("admit", "ok"), ("measure", "broken")]
    assert "NOPE" in record.problems[0]


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
    assert [c.status for c in calls] == ["ran"] + ["skipped"] * 5
    facts = facts_of(out)
    for call in calls[1:]:
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
        run_round(pack, out, from_step="render")
    shutil.rmtree(out)
    with pytest.raises(RunRefused, match="run.json"):
        run_round(pack, out, from_step="measure")

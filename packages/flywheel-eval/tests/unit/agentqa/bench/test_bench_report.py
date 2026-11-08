"""DA-31 AC 4: one command from a spec to a hashed result and a page that says
"trên lỗi cấy", with the job's two ledger rows."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from conftest import CLEAN, INJECTED, QAWork, Report, Seal
from flywheel.contracts.agentqa import AgentModel, AgentReview, FindingDecision
from flywheel.contracts.artifacts import Defect
from flywheel.eval.agentqa.bench.report import BENCH_VERSION, ModelUse, model_uses
from flywheel.eval.agentqa.bench.run import main, run_bench

REASON = "finite_values (D3): NaN or Inf values = 4 > 0"


def _bench(tmp_path: Path, qa_work: QAWork, report: Report, seal: Seal,
           agent_reports: bool = True,
           clean_findings: tuple[tuple[str, str], ...] = (),
           clean_model: AgentModel | None = None) -> tuple[Path, Path]:
    answers = tmp_path / "answers"
    seal(answers, INJECTED, [
        Defect(target_ref="episode_000001", code="D3", parameters={"kind": "nan_values"}),
        Defect(target_ref="episode_000002", code="D7", parameters={"kind": "action_sign_flip"}),
    ])
    seal(answers, CLEAN, [])
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    copies = []
    for copy_id, reasons, findings in (
        (INJECTED, {1: [REASON]}, [("episode_000002", "D7"), ("episode_000000", "D2")]),
        (CLEAN, {}, list(clean_findings)),
    ):
        work = qa_work(spec_dir, copy_id, 4, reasons)
        name = f"agent-{copy_id}.jsonl"
        rep = report(f"r-{copy_id}", findings, inputs=(f"copies/{copy_id}/meta/info.json",))
        if copy_id == CLEAN and clean_model is not None:
            rep = rep.model_copy(update={"model": clean_model})
        (spec_dir / name).write_text(rep.model_dump_json() + "\n")
        copies.append({
            "group": "data", "dataset_id": copy_id, "job_finished_at": "2026-11-05T08:00:00Z",
            "code": {"qa_work": work.name},
            "agent_reports": [name] if agent_reports else [],
        })
    review = AgentReview(report_id=f"r-{INJECTED}", reviewer="hieu",
                         decided_at="2026-11-05T09:00:00+00:00",  # type: ignore[arg-type]
                         decisions=[FindingDecision(finding_id=f"r-{INJECTED}-f0",
                                                    decision="agree")])
    (spec_dir / "review.json").write_text(review.model_dump_json())
    spec = spec_dir / "bench.json"
    spec.write_text(json.dumps({"copies": copies, "reviews": ["review.json"]}))
    return spec, answers


def test_one_run_writes_a_hashed_result_a_labelled_page_and_two_ledger_rows(
    tmp_path: Path, qa_work: QAWork, report: Report, seal: Seal
) -> None:
    spec, answers = _bench(tmp_path, qa_work, report, seal)
    out, store = tmp_path / "out", tmp_path / "store"
    digest = run_bench(spec, [answers], out, store=store, run_plan_id="rp_bench_test")
    text = (out / "bench_result.json").read_text(encoding="utf-8")
    assert hashlib.sha256(text.encode()).hexdigest() == digest
    assert (out / "bench_result.sha256").read_text().strip() == digest
    result = json.loads(text)
    (group,) = result["groups"]
    split = {r["kind"]: r for r in group["split"]}
    assert (split["nan_values"]["by_code"], split["nan_values"]["agent_adds"]) == (1, 0)
    assert (split["action_sign_flip"]["by_code"], split["action_sign_flip"]["agent_adds"]) == (0, 1)
    assert group["layers"]["agent"]["precision_by_code"]["D2"] == {"hit": 0, "total": 1,
                                                                   "value": 0.0}
    assert group["layers"]["code"]["seconds_to_report"][INJECTED] is not None
    assert group["agent_quality"]["reviews"]["hit"] == {"agree": 1}
    # Two defects, none masked: recall on the unmasked part is the plain recall.
    assert group["layers"]["code"]["recall_unmasked_by_kind"] == {
        "nan_values": {"hit": 1, "total": 1, "value": 1.0},
        "action_sign_flip": {"hit": 0, "total": 1, "value": 0.0},
    }
    assert result["false_alarm_on_clean"].startswith("upper bound (cận trên)")
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "trên lỗi cấy" in page and "<title>" in page and digest in page
    assert "cận trên" in page and "by code, unmasked" in page
    rows = [json.loads(line) for p in store.rglob("ledger.jsonl")
            for line in p.read_text().splitlines()]
    assert [r["measure_kind"] for r in rows] == ["estimated", "measured"]
    assert rows[1]["estimate_entry_id"] == rows[0]["id"]
    assert rows[1]["job_id"] == rows[0]["job_id"]
    assert all(r["activity"] == "agent_qa" and r["run_plan_id"] == "rp_bench_test" for r in rows)


def test_each_copy_names_the_agent_model_and_prompt_hash_behind_its_reports(
    tmp_path: Path, qa_work: QAWork, report: Report, seal: Seal
) -> None:
    spec, answers = _bench(tmp_path, qa_work, report, seal)
    out = tmp_path / "out"
    run_bench(spec, [answers], out, store=tmp_path / "store")
    result = json.loads((out / "bench_result.json").read_text(encoding="utf-8"))
    assert result["bench_version"] == BENCH_VERSION == "da31-3"
    (group,) = result["groups"]
    fake = {"name": "fake", "revision": "r0", "temperature": 0.0,
            "prompt_sha256": "0" * 64, "reports": 1}
    assert group["agent_models"] == [{"copy": INJECTED, **fake}, {"copy": CLEAN, **fake}]
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "Agent model per copy" in page and "0" * 64 in page
    assert "different agent models" not in page


def test_reports_of_one_model_are_counted_once_per_copy(report: Report) -> None:
    a, b = report("r-1", [("episode_000001", "D3")]), report("r-2", [])
    other = b.model_copy(update={"model": a.model.model_copy(update={"revision": "r1"})})
    assert model_uses(INJECTED, [a, b, other]) == [
        ModelUse(INJECTED, "fake", "r0", 0.0, "0" * 64, 2),
        ModelUse(INJECTED, "fake", "r1", 0.0, "0" * 64, 1),
    ]
    assert model_uses(CLEAN, []) == []


def test_copies_read_by_different_models_are_both_listed_and_flagged(
    tmp_path: Path, qa_work: QAWork, report: Report, seal: Seal
) -> None:
    other = AgentModel(name="nemotron-3.5-bolt-e4b", revision="q4", temperature=0.2,
                       prompt_sha256="a" * 64)
    spec, answers = _bench(tmp_path, qa_work, report, seal, clean_model=other)
    out = tmp_path / "out"
    run_bench(spec, [answers], out, store=tmp_path / "store")
    (group,) = json.loads((out / "bench_result.json").read_text(encoding="utf-8"))["groups"]
    assert [(m["copy"], m["name"], m["prompt_sha256"]) for m in group["agent_models"]] == [
        (INJECTED, "fake", "0" * 64),
        (CLEAN, "nemotron-3.5-bolt-e4b", "a" * 64),
    ]
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "different agent models" in page


def test_a_result_is_never_overwritten(tmp_path: Path, qa_work: QAWork, report: Report,
                                       seal: Seal) -> None:
    spec, answers = _bench(tmp_path, qa_work, report, seal)
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(FileExistsError):
        run_bench(spec, [answers], out, store=tmp_path / "store")


def test_without_the_agent_run_the_command_stops_before_the_answer(
    tmp_path: Path, qa_work: QAWork, report: Report, seal: Seal,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec, answers = _bench(tmp_path, qa_work, report, seal, agent_reports=False)
    code = main(["--spec", str(spec), "--answers", str(answers), "--out",
                 str(tmp_path / "out"), "--store", str(tmp_path / "store")])
    assert code == 2
    assert "has no AgentReport" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
    rows = [json.loads(line) for p in (tmp_path / "store").rglob("ledger.jsonl")
            for line in p.read_text().splitlines()]
    assert rows[-1]["note"].startswith("wall seconds of the DA-31 bench, failed")


def test_a_clean_agent_report_on_the_dataset_is_a_false_alarm(
    tmp_path: Path, qa_work: QAWork, report: Report, seal: Seal
) -> None:
    spec, answers = _bench(tmp_path, qa_work, report, seal,
                           clean_findings=(("dataset", "T2"),))
    out = tmp_path / "out"
    run_bench(spec, [answers], out, store=tmp_path / "store")
    (group,) = json.loads((out / "bench_result.json").read_text(encoding="utf-8"))["groups"]
    agent = group["layers"]["agent"]
    assert agent["false_alarm_on_clean"] == {"hit": 1, "total": 4, "value": 0.25,
                                             "bound": "upper (cận trên)"}
    assert agent["false_alarm_not_a_unit"] == ["dataset"]
    assert agent["clean_reports"] == [["dataset", "T2"]]
    assert group["layers"]["code"]["false_alarm_not_a_unit"] == []
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "không gắn đơn vị" in page and "1 (dataset)" in page

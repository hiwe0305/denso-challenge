"""DA-20 AC 2, 5, 6: one run end to end, the estimates it keeps, and the CLI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

import pytest
from agentqa_build import EchoModel, config, qa_work, rtc_job, train_job
from flywheel.contracts.agentqa import AgentReport
from flywheel.eval.agentqa import estimates
from flywheel.eval.agentqa.run import run

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)
FIXTURE = files("flywheel.testkit") / "fixtures/artifacts/AgentReport.json"


def _fixture() -> AgentReport:
    return AgentReport.model_validate_json(FIXTURE.read_text())



def test_estimates_and_measurements_are_separate_rows(tmp_path: Path) -> None:
    path = tmp_path / "estimates.jsonl"
    report = _fixture()
    assert estimates.record_estimates(report, path) == len(report.estimates)
    ref = f"{report.report_id}/{report.estimates[0].estimate_id}"
    with pytest.raises(KeyError):
        estimates.record_measurement(path, "rep_x/est_9", 1.0, "m.json")
    estimates.record_measurement(path, ref, report.estimates[0].low, "m.json", NOW)
    rows = estimates.read(path)
    assert [r["kind"] for r in rows] == ["estimated"] * len(report.estimates) + ["measured"]
    assert estimates.compare(path)[0].inside is True


def test_a_run_writes_reports_pages_figures_and_two_ledger_rows(tmp_path: Path) -> None:
    copy = tmp_path / "copy"
    (copy / "meta").mkdir(parents=True)
    (copy / "meta" / "benchmark_copy.json").write_text('{"benchmark_copy_id": "bench-x"}')
    train_job(copy / "train" / "job-nan", loss=lambda s: "NaN" if s == 50 else 1.0 / (s + 1))
    train_job(copy / "train" / "job-ok")
    rtc_job(copy / "rtc" / "job-slow", latency=0.3)
    qa_work(tmp_path / "work", 3, {2: ["finite_values (D1): NaN in action"]})
    out = tmp_path / "out"
    result = run([copy, tmp_path / "work"], out, EchoModel(), config(),
                 store=tmp_path / "store", now=NOW)
    got = {(f.target_ref, f.code) for r in result.reports for f in r.findings}
    assert {("train/job-nan", "T1"), ("rtc/job-slow", "R1"), ("episode_000002", "D1")} <= got
    assert not {t for t, _ in got} & {"train/job-ok"}
    lines = (out / "reports.jsonl").read_text().splitlines()
    assert len(lines) == len(result.reports) == 4
    assert (out / "index.html").is_file() and list((out / "figures").glob("*.svg"))
    ledger = list((tmp_path / "store").rglob("*.jsonl"))
    rows = [json.loads(x) for p in ledger for x in p.read_text().splitlines()]
    kinds = [r["measure_kind"] for r in rows if r["activity"] == "agent_qa"]
    assert kinds == ["estimated", "measured"]
    with pytest.raises(FileExistsError):
        run([copy], out, EchoModel(), config(), store=tmp_path / "store")


def test_the_cli_keeps_a_broken_run_and_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from flywheel.eval.agentqa.cli import app
    from typer.testing import CliRunner

    rtc_job(tmp_path / "in" / "rtc" / "job-slow", latency=0.3)
    monkeypatch.setenv("FW_AGENTQA_AGENT_URL", "http://127.0.0.1:9/v1")
    out = tmp_path / "out"
    result = CliRunner().invoke(app, ["run", "--input", str(tmp_path / "in"), "--out", str(out),
                                      "--store", str(tmp_path / "store")])
    assert result.exit_code == 1
    assert json.loads((out / "reports.jsonl").read_text())["status"] == "broken"


def test_a_run_shows_the_code_candidates_the_model_dropped(tmp_path: Path) -> None:
    from flywheel.eval.agentqa.cli import app
    from typer.testing import CliRunner

    rtc_job(tmp_path / "in" / "rtc" / "job-slow", latency=0.3)
    reply = {"decisions": [{"cid": "C1", "keep": False, "reason": "latency looks fine"}]}
    replay = tmp_path / "replies.jsonl"
    replay.write_text(json.dumps({"model": "m", "reply": json.dumps(reply)}) + "\n")
    out = tmp_path / "out"
    result = CliRunner().invoke(app, ["run", "--input", str(tmp_path / "in"), "--out", str(out),
                                      "--replay", str(replay), "--store", str(tmp_path / "s")])
    assert result.exit_code == 0, result.output
    assert "1 code candidate(s) dropped" in result.output
    assert "see dropped.jsonl" in result.output
    (row,) = [json.loads(x) for x in (out / "dropped.jsonl").read_text().splitlines()]
    assert (row["code"], row["target"], row["reason"]) == ("R1", "rtc/job-slow",
                                                           "latency looks fine")
    assert {e["name"] for e in row["evidence"]} >= {"R1_value", "R1_threshold", "R1_flag_when"}
    page = next(out.glob("*-inference.html")).read_text()
    assert "dropped by the model" in page and "latency looks fine" in page
    assert ">1<" in (out / "index.html").read_text()

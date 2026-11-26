"""The adjudicate role: version 3's reports in a round directory, through the gateway (DA-43 5.2).

No network: every provider is a fake handed to the gateway through `gateway_factory`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.contracts.agentqa import AgentReport
from flywheel.contracts.artifacts import Episode, QACheck, QAReport, RTCInferenceRecord
from flywheel.contracts.entities import Source
from flywheel.contracts.training import TrainingMetric
from flywheel.eval.agentqa.agent import load_agent_config
from flywheel.eval.agentqa.round.adjudicate import (
    DROPPED_FILE,
    ESTIMATES_FILE,
    HOSTED_TEMPERATURE,
    REPORTS_FILE,
    CodeFloorModel,
)
from flywheel.eval.agentqa.round.admit import admit
from flywheel.eval.agentqa.round.declare import declare_jobs, main, write_declaration
from flywheel.eval.agentqa.round.gateway import MODEL_CALLS_FILE
from flywheel.eval.agentqa.round.gateway_config import CONFIG_ROOT, GatewayRefused, Profile
from flywheel.eval.agentqa.round.pack import PackRefused, build_pack, write_pack
from flywheel.eval.agentqa.round.pipeline import run_round
from flywheel.eval.agentqa.round.providers import ChatModel, ProviderError, ProviderReply
from flywheel.eval.agentqa.round.records import ModelCallRecord, RunRecord
from flywheel.eval.agentqa.round.version import agent_hash
from flywheel.eval.agentqa.run import run
from helpers_round import isolated_store  # noqa: F401  (an autouse fixture)

NOW = datetime(2026, 11, 25, tzinfo=timezone.utc)
SHA = "0" * 64
Answer = Callable[[dict[str, Any]], str]


def _lines(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(r.model_dump_json() + "\n" for r in rows), encoding="utf-8")


def _train(job: Path, nan_at: int | None = None) -> None:
    _lines(job / "metrics.jsonl", [TrainingMetric(
        run_plan_id="rp", job_id=job.name, checkpoint_id="ck", release_id="rel", attempt=0,
        step=s, epoch=0, split="train", loss="NaN" if s == nan_at else 1.0 / (s + 1),
        lr=1e-4, vlm_frozen=True, wall_time_s=float(s)) for s in range(0, 100, 10)])


def _rtc(job: Path, latency: float) -> None:
    _lines(job / "rtc.jsonl", [RTCInferenceRecord(
        job_id=job.name, trace_id="t", chunk_index=i, observation_sent_s=i * 0.5,
        chunk_received_s=i * 0.5 + latency, delay_steps=2, buffer_level=0,
        boundary_jump=0.0) for i in range(50)])


def logs(root: Path) -> Path:
    """A log copy: a diverging train job, a healthy one, a slow RTC job."""
    _train(root / "train" / "job-nan", nan_at=50)
    _train(root / "train" / "job-ok")
    _rtc(root / "rtc" / "job-slow", latency=0.3)
    (root / "meta").mkdir()
    (root / "meta" / "benchmark_copy.json").write_text('{"benchmark_copy_id": "bench-x"}')
    return root


def qa_work(root: Path, n: int, reasons: dict[int, list[str]]) -> Path:
    """A `fw data qa` work dir of `n` episodes; `reasons` maps an index to its QA reasons.

    Episodes 3 and 4 carry the same check values, so version 3 raises its duplicate hint.
    """
    text = (files("flywheel.testkit") / "fixtures/artifacts/Episode.json").read_text()
    base = Episode.model_validate_json(text)
    episodes, index, rows = [], {}, []
    for i in range(n):
        eid = f"ep_{i:016x}"
        episodes.append(base.model_copy(update={"episode_id": eid}))
        index[eid] = i + 10  # an index that is not the line number
        why = reasons.get(i, [])
        value = 0.25 if i in (3, 4) else 0.001 * (i + 1)
        checks = [QACheck(name="finite_values", value=1.0 if why else 0.0, threshold=0.0,
                          passed=not why),
                  QACheck(name="action_jump", value=value, threshold=0.5, passed=True),
                  QACheck(name="timestamp_step", value=value / 2, threshold=1.0, passed=True)]
        rows.append(QAReport(report_id=f"qa_{i}", episode_id=eid, threshold_version="v1",
                             decision="reject" if why else "pass", reasons=why, checks=checks))
    _lines(root / "episodes.jsonl", episodes)
    (root / "episode_index.json").write_text(json.dumps(index))
    _lines(root / "qa" / "reports.jsonl", rows)
    (root / "qa" / "summary.json").write_text("{}")
    (root / "source.json").write_text("{}")
    return root


def logs_pack(tmp_path: Path, data_class: str = "public", vouched: bool = False) -> Path:
    root = logs(tmp_path / "copy")
    decl = write_declaration(root, "tray", "test", data_class)  # type: ignore[arg-type]
    if vouched:  # a source record that says public, linked to every entry
        raw = yaml.safe_load(decl.read_text())
        (root / "sources.jsonl").write_text(Source(
            uri="sim://g1", sha256=SHA, downloaded_at="2026-11-01",
            data_class="public").model_dump_json() + "\n")
        raw["links"] = [{"source": e["path"], "target": "sources.jsonl", "relation": "data_of"}
                        for e in raw["entries"]]
        raw["entries"].append({"path": "sources.jsonl", "kind": "sources"})
        decl.write_text(yaml.safe_dump(raw))
    return write_pack(build_pack(decl, now=NOW), root)


def reports(path: Path) -> list[AgentReport]:
    return [AgentReport.model_validate_json(x) for x in path.read_text().splitlines()]


def findings(rs: list[AgentReport]) -> list[tuple[Any, ...]]:
    return sorted((r.stage, f.target_ref, f.code, f.rank, tuple(f.evidence), f.insight,
                   tuple(f.figures)) for r in rs for f in r.findings)


def calls(out: Path) -> list[ModelCallRecord]:
    return [ModelCallRecord.model_validate_json(x)
            for x in (out / MODEL_CALLS_FILE).read_text().splitlines()]


def floor(payload: dict[str, Any]) -> str:
    return CodeFloorModel().complete([{"role": "system", "content": ""},
                                      {"role": "user", "content": json.dumps(payload)}])


class Bot:
    """A fake provider answering each call from the user payload; `answer` decides."""

    def __init__(self, answer: Answer = floor, model: str = "fake-adj",
                 error: Exception | None = None) -> None:
        self.answer, self.error = answer, error
        self.model, self.revision, self.host, self.key_env = model, "r0", "127.0.0.1", None
        self.users: list[str] = []

    def chat(self, system: str, user: str, *, reply_schema: dict[str, Any] | None,
             max_tokens: int, timeout_s: float) -> ProviderReply:
        self.users.append(user)
        if self.error is not None:
            raise self.error
        try:
            payload = json.loads(user)
        except json.JSONDecodeError:  # a resend: the first turn, then the labelled turns
            payload = json.loads(user.split("\n\n[assistant]", 1)[0])
        return ProviderReply(text=self.answer(payload), tokens_in=None, tokens_out=40)


def model_round(pack: Path, out: Path, bot: ChatModel, tmp_path: Path,
                **kw: Any) -> RunRecord:
    return run_round(pack, out, now=NOW, no_model=False, store=tmp_path / "store",
                     gateway_factory=lambda name, profile: bot, **kw)


# the declaration -------------------------------------------------------------------------

def test_the_declaration_lists_each_job_file_with_its_kind_and_job(tmp_path: Path) -> None:
    root = logs(tmp_path / "copy")
    (root / "train" / "job-ok" / "probe_p4.json").write_text("{}")
    declared = declare_jobs(root, "tray", "test", "public")
    got = [(e["path"], e["kind"], e["subject"]["job"]) for e in declared["entries"]]
    assert got == [("train/job-nan/metrics.jsonl", "metrics", "job-nan"),
                   ("train/job-ok/metrics.jsonl", "metrics", "job-ok"),
                   ("train/job-ok/probe_p4.json", "probe_p4", "job-ok"),
                   ("rtc/job-slow/rtc.jsonl", "rtc_log", "job-slow")]
    assert declared["data_class"] == "public" and declared["task_id"] == "tray"
    assert main(["--root", str(root), "--task", "tray", "--declared-by", "t",
                 "--data-class", "internal"]) == 0
    assert yaml.safe_load((root / "round.yaml").read_text())["data_class"] == "internal"
    assert main(["--root", str(root), "--task", "tray", "--declared-by", "t",
                 "--data-class", "internal"]) == 2  # written once
    with pytest.raises(PackRefused, match="no train"):
        declare_jobs(tmp_path, "tray", "test", "public")


def test_a_qa_work_dir_is_declared_alone_or_beside_jobs(tmp_path: Path) -> None:
    root = qa_work(tmp_path / "work", 3, {})
    (root / "report").mkdir()
    (root / "report" / "dataset_report.json").write_text("{}")
    (root / "replay_kinematic.jsonl").write_text("")
    (root / "replay_outcomes.jsonl").write_text("")  # DA-17 outcome rows, no ReplayReport
    got = [(e["path"], e["kind"], e["subject"])
           for e in declare_jobs(root, "tray", "test", "public")["entries"]]
    assert got == [("qa/reports.jsonl", "qa_reports", {}), ("episodes.jsonl", "episodes", {}),
                   ("episode_index.json", "episode_index", {}),
                   ("report/dataset_report.json", "dataset_report", {}),
                   ("replay_kinematic.jsonl", "replay_reports", {})]
    _train(root / "train" / "job-ok")
    paths = [e["path"] for e in declare_jobs(root, "tray", "test", "public")["entries"]]
    assert paths[0] == "train/job-ok/metrics.jsonl" and len(paths) == 6


# the episode index -----------------------------------------------------------------------

@pytest.mark.parametrize(("text", "accepted"), [
    ('{"ep_a": 0, "ep_b": 12}', True), ("{}", True), ('[0, 1]', False),
    ('{"ep_a": "3"}', False), ('{"ep_a": 1.5}', False), ('{"ep_a": true}', False),
    ("not json", False)])
def test_admit_reads_an_episode_index_as_ids_to_ints(tmp_path: Path, text: str,
                                                     accepted: bool) -> None:
    root = tmp_path / "work"
    root.mkdir()
    (root / "episode_index.json").write_text(text)
    _lines(root / "episodes.jsonl", [Episode.model_validate_json(
        (files("flywheel.testkit") / "fixtures/artifacts/Episode.json").read_text())])
    decl = write_declaration(root, "tray", "test", "public")
    got = admit(write_pack(build_pack(decl, now=NOW), root))
    assert ("episode_index.json" in got.admission.accepted) is accepted
    if accepted:
        assert got.records["episode_index.json"][0].root == json.loads(text)
    else:
        reason = next(r.reason for r in got.admission.rejected)
        assert reason.startswith("does not parse as episode_index")


# the code floor --------------------------------------------------------------------------

def test_a_no_model_round_writes_the_reports_version_3_writes(tmp_path: Path) -> None:
    pack = logs_pack(tmp_path)
    out = tmp_path / "out"
    record = run_round(pack, out, now=NOW, store=tmp_path / "store")
    step = next(s for s in record.steps if s.name == "adjudicate")
    assert step.status == "ok" and step.rows == 3
    assert set(step.outputs) == {REPORTS_FILE, DROPPED_FILE, ESTIMATES_FILE}
    assert (out / ESTIMATES_FILE).read_text() == ""  # the floor estimates nothing
    new = reports(out / REPORTS_FILE)
    old = run([tmp_path / "copy" / "train", tmp_path / "copy" / "rtc"], tmp_path / "v3",
              CodeFloorModel(), load_agent_config(), store=tmp_path / "store", now=NOW).reports
    assert findings(new) == findings(old)
    assert {("train/job-nan", "T1"), ("rtc/job-slow", "R1")} <= {
        (f.target_ref, f.code) for r in new for f in r.findings}
    for a, b in zip(new, old, strict=True):
        assert (a.stage, a.status, a.model, a.problems) == (b.stage, b.status, b.model, [])
        assert [(i.kind, i.sha256) for i in a.inputs] == [(i.kind, i.sha256) for i in b.inputs]
        assert [(f.name, f.value) for f in a.facts] == [(f.name, f.value) for f in b.facts]
    assert new[0].subject_ref == "train/job-nan/metrics.jsonl"  # the pack ref
    assert (out / DROPPED_FILE).read_text() == "" and list((out / "figures").glob("*.svg"))
    assert not (out / MODEL_CALLS_FILE).exists()


def test_a_dataset_subject_gets_the_findings_version_3_gives(tmp_path: Path) -> None:
    root = qa_work(tmp_path / "work", 6, {2: ["finite_values (D1): NaN in action"],
                                          5: ["min_frames: too short"]})
    write_declaration(root, "tray", "test", "public")
    pack = write_pack(build_pack(root / "round.yaml", now=NOW), root)
    out = tmp_path / "out"
    record = run_round(pack, out, now=NOW, store=tmp_path / "store")
    step = next(s for s in record.steps if s.name == "adjudicate")
    assert step.status == "ok" and step.rows == 1
    new = reports(out / REPORTS_FILE)
    old = run([root], tmp_path / "v3", CodeFloorModel(), load_agent_config(),
              store=tmp_path / "store", now=NOW).reports
    assert findings(new) == findings(old)
    assert ("episode_000012", "D1") in {(f.target_ref, f.code) for f in new[0].findings}
    (a,), (b,) = new, old
    assert (a.stage, a.status, a.problems) == ("dataset", b.status, [])
    assert a.subject_ref == "qa/reports.jsonl"
    assert sorted((i.kind, i.sha256) for i in a.inputs) == sorted(
        (i.kind, i.sha256) for i in b.inputs)
    assert {i.kind for i in a.inputs} == {"qa_reports", "episodes", "episode_index"}
    assert [(f.name, f.value) for f in a.facts] == [(f.name, f.value) for f in b.facts]
    assert any("same_qa_fingerprint:episode_000013+episode_000014" in f.name for f in a.facts)


def test_a_train_job_is_judged_on_the_admitted_files_only(tmp_path: Path) -> None:
    pack = logs_pack(tmp_path)
    # a layout beside the metrics that the pack does not hold is never read: T5 and T6
    # stay not judged, as for a job without one
    (tmp_path / "copy" / "train" / "job-ok" / "action_layout.json").write_text("not json")
    out = tmp_path / "out"
    run_round(pack, out, now=NOW, store=tmp_path / "store")
    ok = next(r for r in reports(out / REPORTS_FILE) if "job-ok" in r.subject_ref)
    assert ok.status == "ok" and [i.ref for i in ok.inputs] == ["train/job-ok/metrics.jsonl"]


# through the gateway ---------------------------------------------------------------------

def test_the_model_keeps_and_drops_through_the_gateway(tmp_path: Path) -> None:
    def drop_r1(payload: dict[str, Any]) -> str:
        reply = json.loads(floor(payload))
        for d in reply["decisions"]:
            c = next(c for c in payload["candidates"] if c["cid"] == d["cid"])
            if c["code"] == "R1":
                d.update(keep=False, reason=f"A warm-up chunk: {{{c['evidence'][0]}}}.")
        return json.dumps(reply)

    bot = Bot(drop_r1)
    out = tmp_path / "out"
    record = model_round(logs_pack(tmp_path), out, bot, tmp_path)
    assert record.status == "degraded"  # admit and measure: a log pack has no scores
    assert not any(p.startswith("adjudicate") for p in record.problems)
    got = {(f.target_ref, f.code) for r in reports(out / REPORTS_FILE) for f in r.findings}
    assert ("train/job-nan", "T1") in got and ("rtc/job-slow", "R1") not in got
    rows = [json.loads(x) for x in (out / DROPPED_FILE).read_text().splitlines()]
    assert [(r["code"], r["target"], r["kind"]) for r in rows] == [
        ("R1", "rtc/job-slow", "dropped_by_model")]
    report = reports(out / REPORTS_FILE)[0]
    assert (report.model.name, report.model.revision, report.model.temperature) == (
        "fake-adj", "r0", HOSTED_TEMPERATURE)  # a fake reports no temperature of its own
    lines = calls(out)
    assert [(c.role, c.unit, c.attempt, c.status) for c in lines] == [
        ("adjudicate", "train/job-nan/metrics.jsonl#1", 1, "ok"),
        ("adjudicate", "train/job-ok/metrics.jsonl#1", 1, "ok"),
        ("adjudicate", "rtc/job-slow/rtc.jsonl#1", 1, "ok")]
    assert record.totals.calls == 3 and record.model_hosts == ["127.0.0.1"]


def test_a_batch_failing_twice_breaks_its_report_and_degrades_the_run(tmp_path: Path) -> None:
    bot = Bot(lambda payload: "no JSON here")
    out = tmp_path / "out"
    record = model_round(logs_pack(tmp_path), out, bot, tmp_path)
    assert record.status == "degraded"
    assert next(s for s in record.steps if s.name == "adjudicate").status == "degraded"
    broken = [p for p in record.problems if p.startswith("adjudicate:")]
    assert len(broken) == 3 and "model reply rejected" in broken[0]
    rs = reports(out / REPORTS_FILE)
    assert all(r.status == "broken" and not r.findings for r in rs)
    assert [c.attempt for c in calls(out)] == [1, 2] * 3
    assert "[assistant]\nno JSON here" in bot.users[1] and "[user]\nYour reply" in bot.users[1]


def test_a_failed_call_breaks_the_report_without_a_resend(tmp_path: Path) -> None:
    bot = Bot(error=ProviderError("HTTP 400", retryable=False))
    out = tmp_path / "out"
    record = model_round(logs_pack(tmp_path), out, bot, tmp_path)
    assert record.status == "degraded"
    rs = reports(out / REPORTS_FILE)
    assert all(r.status == "broken" for r in rs)
    assert "endpoint failed: gateway call M1 failed: HTTP 400" in rs[0].problems[0]
    assert [(c.attempt, c.status) for c in calls(out)] == [(1, "failed")] * 3


def test_replay_of_model_calls_gives_the_same_reports(tmp_path: Path) -> None:
    pack = logs_pack(tmp_path)
    out = tmp_path / "out"
    model_round(pack, out, Bot(), tmp_path)
    first = reports(out / REPORTS_FILE)
    silent = Bot(error=AssertionError("a replayed request reached the provider"))
    record = model_round(pack, out, silent, tmp_path, from_step="adjudicate")
    again = reports(out / REPORTS_FILE)
    assert findings(again) == findings(first) and silent.users == []
    assert [(r.status, r.model) for r in again] == [(r.status, r.model) for r in first]
    assert record.totals.replayed == 3 and len(calls(out)) == 3


# the data class --------------------------------------------------------------------------

def gateway_dir(tmp_path: Path) -> Path:
    root = tmp_path / "gw"
    root.mkdir()
    routing = yaml.safe_load((CONFIG_ROOT / "routing.yaml").read_text())
    routing["routes"]["adjudicate"]["public"] = "haiku"
    (root / "routing.yaml").write_text(yaml.safe_dump(routing))
    hosted = yaml.safe_load((CONFIG_ROOT / "hosted.yaml").read_text())
    hosted["enabled"] = True
    (root / "hosted.yaml").write_text(yaml.safe_dump(hosted))
    return root


def test_a_pack_not_confirmed_public_makes_no_hosted_call(tmp_path: Path) -> None:
    built: list[str] = []

    def factory(name: str, profile: Profile) -> ChatModel:
        built.append(name)
        return Bot()

    root = gateway_dir(tmp_path)
    # declared public, but no record vouches for it: refused before any call
    out = tmp_path / "out"
    with pytest.raises(GatewayRefused, match="unknown"):
        run_round(logs_pack(tmp_path), out, now=NOW, no_model=False, gateway_root=root,
                  store=tmp_path / "store", gateway_factory=factory)
    record = RunRecord.model_validate_json((out / "run.json").read_text())
    assert record.status == "broken" and record.steps[-1].name == "adjudicate"
    assert built == [] and not (out / MODEL_CALLS_FILE).exists()
    # internal: the local profile answers, the hosted one is never built
    other = tmp_path / "internal"
    other.mkdir()
    run_round(logs_pack(other, "internal"), tmp_path / "out2", now=NOW, no_model=False,
              gateway_root=root, store=tmp_path / "store", gateway_factory=factory)
    assert set(built) == {"local_text"}
    assert {c.hosted for c in calls(tmp_path / "out2")} == {False}


def test_a_confirmed_public_pack_may_reach_the_hosted_route(tmp_path: Path) -> None:
    built: list[str] = []

    def factory(name: str, profile: Profile) -> ChatModel:
        built.append(name)
        return Bot(model="claude-haiku-5-5")

    out = tmp_path / "out"
    run_round(logs_pack(tmp_path, vouched=True), out, now=NOW, no_model=False,
              gateway_root=gateway_dir(tmp_path), store=tmp_path / "store",
              gateway_factory=factory)
    assert "haiku" in built and {c.profile for c in calls(out)} == {"haiku"}
    model = reports(out / REPORTS_FILE)[0].model
    assert (model.name, model.temperature) == ("claude-haiku-5-5", HOSTED_TEMPERATURE)


# the agent hash --------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["eval/agentqa/prompts/system.md",
                                  "eval/diagnosis/train.yaml"])
def test_the_agent_hash_covers_what_adjudicate_uses(tmp_path: Path, name: str) -> None:
    configs = tmp_path / "configs"
    for path in ("eval/agentqa/prompts/system.md", "eval/agentqa/agent.yaml",
                 "eval/diagnosis/train.yaml"):
        (configs / path).parent.mkdir(parents=True, exist_ok=True)
        (configs / path).write_text("a: 1\n")
    root = configs / "eval" / "agentqa"
    first = agent_hash("tray", root=root)
    (configs / name).write_text("a: 2\n")
    assert agent_hash("tray", root=root) != first

"""DA-20 task 5: the sample cases with known answers (design 9.4: "bộ ca mẫu ≥ 10 ca").

Each case writes the artifacts of one subject, runs the agent with a scripted
model, and states the answer: which candidates code must propose and which
findings the report must hold. The same cases run against Nemotron on the 3060
(`docs/g0/agent-qa.md`); there the model's replies are recorded and replayed.

`EchoModel` keeps every code candidate and drops every hint, so a case's
`findings` is what code proved; the hint cases check that a hint reaches the
model as a hint, and that a model which keeps it gets it into the report.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "unit" / "agentqa"))
from agentqa_build import (  # noqa: E402
    SYSTEM_YAML,
    TRAIN_YAML,
    EchoModel,
    ScriptedModel,
    config,
    qa_work,
    rtc_job,
    train_job,
)
from flywheel.contracts.artifacts import ProbeP3  # noqa: E402
from flywheel.eval.agentqa.run import run  # noqa: E402

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)
SHA = "a" * 64
Pairs = set[tuple[str, str]]


@dataclass(frozen=True)
class Case:
    name: str
    build: Callable[[Path], None]
    candidates: Pairs  # (target, code) code must propose, hints included
    findings: Pairs  # (target, code) the report holds under EchoModel


def _nan(root: Path) -> None:
    train_job(root / "train" / "job-nan", loss=lambda s: "NaN" if s == 50 else 1.0 / (s + 1))


def _diverge(root: Path) -> None:
    train_job(root / "train" / "job-div", loss=lambda s: 1.0 / (s + 1) if s < 90 else 50.0)


def _probe(root: Path, name: str, **fields: object) -> None:
    base: dict[str, object] = {
        "checkpoint_id": "ckpt-1", "dataset_sha256": SHA, "error_by_group": {"arm": 0.1},
        "error_by_chunk_pos": [0.1, 0.12], "hand_event_offset_steps": 0.0,
        "out_of_limit_dims": [],
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(ProbeP3(**{**base, **fields}).model_dump_json())  # type: ignore[arg-type]


CASES = [
    Case("train_clean", lambda r: train_job(r / "train" / "job-ok"), set(), set()),
    Case("train_nan_loss", _nan, {("train/job-nan", "T1")}, {("train/job-nan", "T1")}),
    Case("train_divergence", _diverge, {("train/job-div", "T1")}, {("train/job-div", "T1")}),
    Case("rtc_clean", lambda r: rtc_job(r / "rtc" / "job-ok"), set(), set()),
    Case("rtc_latency_over_tau", lambda r: rtc_job(r / "rtc" / "job-slow", latency=0.3),
         {("rtc/job-slow", "R1")}, {("rtc/job-slow", "R1")}),
    Case("rtc_stalls_past_d", lambda r: rtc_job(r / "rtc" / "job-stall", delay_steps=9),
         {("rtc/job-stall", "R2")}, {("rtc/job-stall", "R2")}),
    Case("dataset_clean", lambda r: qa_work(r / "work", 4), set(), set()),
    Case("dataset_nan", lambda r: qa_work(r / "work", 4, {1: ["finite_values (D1): NaN"]}),
         {("episode_000001", "D1")}, {("episode_000001", "D1")}),
    Case("dataset_wrong_instruction",
         lambda r: qa_work(r / "work", 4, {3: ["task_instruction (D6): empty task"]}),
         {("episode_000003", "D6")}, {("episode_000003", "D6")}),
    Case("dataset_duplicate_hint",
         lambda r: qa_work(r / "work", 4, values={0: 0.25, 2: 0.25}),
         {("episode_000002", "D5")}, set()),
    Case("stage3_group_error", lambda r: _probe(r, "probe_p3.json", error_by_group={"arm": 0.6}),
         {("ckpt-1", "O1")}, {("ckpt-1", "O1")}),
    Case("stage3_error_grows_in_chunk",
         lambda r: _probe(r, "probe_p3.json", error_by_chunk_pos=[0.1, 0.2, 0.35]),
         {("ckpt-1", "O2")}, {("ckpt-1", "O2")}),
    Case("stage3_clean", lambda r: _probe(r, "probe_p3.json"), set(), set()),
]


def _run(tmp_path: Path, case: Case, model: object):  # type: ignore[no-untyped-def]
    inputs = tmp_path / "in"
    inputs.mkdir()
    case.build(inputs)
    return run([inputs], tmp_path / "out", model, config(), store=tmp_path / "store", now=NOW)  # type: ignore[arg-type]


def test_there_are_at_least_ten_cases() -> None:
    assert len(CASES) >= 10
    assert len({c.name for c in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_case(tmp_path: Path, case: Case) -> None:
    from flywheel.eval.agentqa.inputs import collect
    from flywheel.eval.agentqa.run import subjects

    result = _run(tmp_path, case, EchoModel())
    assert all(r.status == "ok" for r in result.reports), [r.problems for r in result.reports]
    found = {(f.target_ref, f.code) for r in result.reports for f in r.findings}
    assert found == case.findings
    from flywheel.eval.agentqa.analyze import OfflineThresholds

    analyses = subjects(collect([tmp_path / "in"]), OfflineThresholds(), TRAIN_YAML, SYSTEM_YAML)
    proposed = {(c.target, c.code) for a in analyses for c in a.candidates}
    assert proposed == case.candidates


def test_a_model_that_keeps_the_duplicate_hint_reports_d5(tmp_path: Path) -> None:
    case = next(c for c in CASES if c.name == "dataset_duplicate_hint")
    seen: list[dict[str, object]] = []

    class Keep(EchoModel):
        def complete(self, messages):  # type: ignore[no-untyped-def]
            payload = json.loads(messages[1]["content"])
            seen.extend(payload["candidates"])
            return json.dumps({"decisions": [
                {"cid": c["cid"], "keep": True, "priority": 2,
                 "insight": f"same QA fingerprint as another episode {{{c['evidence'][0]}}}",
                 "suggestion": "Compare the two recordings and drop one.",
                 "evidence": c["evidence"]}
                for c in payload["candidates"]
            ]})

    result = _run(tmp_path, case, Keep())
    assert [c["origin"] for c in seen] == ["hint"]
    assert {(f.target_ref, f.code) for r in result.reports for f in r.findings} == {
        ("episode_000002", "D5")
    }


def test_a_model_that_invents_a_number_gets_a_broken_report(tmp_path: Path) -> None:
    case = next(c for c in CASES if c.name == "rtc_latency_over_tau")
    lie = {"decisions": [{"cid": "C1", "insight": "latency hit 0.9 s", "suggestion": "x"}]}
    result = _run(tmp_path, case, ScriptedModel([lie, lie]))
    (report,) = result.reports
    assert report.status == "broken" and report.findings == []

"""DA-20 AC 3, 5: the agent ranks and explains on code's facts; a reply that breaks a rule
never becomes findings."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentqa_build import (
    SYSTEM_YAML,
    TRAIN_YAML,
    EchoModel,
    ScriptedModel,
    config,
    qa_work,
    rtc_job,
    train_job,
)
from flywheel.eval.agentqa.agent import build_messages, run_agent
from flywheel.eval.agentqa.analyze import analyze_dataset, analyze_rtc, analyze_train
from flywheel.eval.agentqa.inputs import collect, load_file

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)
NAN = "finite_values (D1): 3 non-finite value(s) in action"


def _dataset(tmp_path: Path, reasons: dict[int, list[str]]):  # type: ignore[no-untyped-def]
    work = qa_work(tmp_path / "work", 5, reasons)
    found = collect([work])
    return analyze_dataset(found, "work/qa/reports.jsonl")


def test_code_candidates_become_ranked_findings(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {1: [NAN], 3: [NAN]})
    report = run_agent(analysis, EchoModel(), config(), now=NOW)
    assert report.status == "ok"
    assert [(f.rank, f.code, f.target_ref) for f in report.findings] == [
        (1, "D1", "episode_000001"), (2, "D1", "episode_000003")
    ]
    assert report.findings[0].insight.startswith("D1 on episode_000001: {F")


def test_the_model_reorders_by_priority_and_may_drop(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {1: [NAN], 3: [NAN]})
    c1, c2 = analysis.candidates
    reply = {
        "decisions": [
            {"cid": c1.cid, "keep": False, "reason": "seen before"},
            {"cid": c2.cid, "keep": True, "priority": 1, "insight": f"NaN in {{{c2.evidence[0]}}}",
             "suggestion": "Re-record the episode."},
        ],
    }
    report = run_agent(analysis, ScriptedModel([reply]), config(), now=NOW)
    assert [(f.code, f.target_ref) for f in report.findings] == [("D1", "episode_000003")]


def test_an_invented_number_is_sent_back_then_breaks_the_report(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {1: [NAN]})
    (c1,) = analysis.candidates
    bad = {"decisions": [{"cid": c1.cid, "insight": "NaN in 42 frames", "suggestion": "fix"}]}
    model = ScriptedModel([bad, bad])
    report = run_agent(analysis, model, config(), now=NOW)
    assert report.status == "broken"
    assert report.findings == []
    assert "42" in report.problems[0]
    assert len(model.messages) == 2
    assert "broke the rules" in model.messages[1][-1]["content"]


def test_a_retry_that_follows_the_rules_is_kept(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {1: [NAN]})
    (c1,) = analysis.candidates
    bad = {"decisions": [{"cid": c1.cid, "insight": "NaN in 42 frames", "suggestion": "fix"}]}
    good = {"decisions": [{"cid": c1.cid, "insight": f"NaN, see {{{c1.evidence[0]}}}",
                           "suggestion": "fix"}]}
    report = run_agent(analysis, ScriptedModel([bad, good]), config(), now=NOW)
    assert report.status == "ok" and len(report.findings) == 1


def test_an_added_finding_needs_an_allowed_code_and_a_unit(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {})
    fid = analysis.book.facts[0].fact_id
    off_stage = {"added": [{"code": "T1", "target": "episode_000001", "insight": f"{{{fid}}}",
                            "suggestion": "x", "evidence": [fid]}]}
    report = run_agent(analysis, ScriptedModel([off_stage, off_stage]), config(), now=NOW)
    assert report.status == "broken" and "not allowed" in report.problems[0]
    ok = {"added": [{"code": "D5", "target": "episode_000002", "priority": 2,
                     "insight": f"same as another, {{{fid}}}", "suggestion": "dedupe",
                     "evidence": [fid]}]}
    report = run_agent(analysis, ScriptedModel([ok]), config(), now=NOW)
    assert [(f.code, f.target_ref) for f in report.findings] == [("D5", "episode_000002")]


def test_estimates_keep_their_basis(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {1: [NAN]})
    fid = analysis.book.facts[0].fact_id
    (c1,) = analysis.candidates
    reply = {"decisions": [{"cid": c1.cid, "keep": False, "reason": "seen"}],
             "estimates": [{"quantity": "episodes left after quarantine", "low": 3, "high": 4,
                            "unit": "episodes", "basis": [fid]}]}
    report = run_agent(analysis, ScriptedModel([reply]), config(), now=NOW)
    assert [(e.low, e.high, e.basis) for e in report.estimates] == [(3.0, 4.0, [fid])]


def test_a_candidate_left_without_a_decision_breaks_the_report(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {1: [NAN]})
    report = run_agent(analysis, ScriptedModel([{"decisions": []}] * 2), config(), now=NOW)
    assert report.status == "broken" and report.findings == []
    assert "no decision for candidates" in report.problems[0]


def test_keep_must_be_a_json_boolean(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {1: [NAN]})
    (c1,) = analysis.candidates
    reply = {"decisions": [{"cid": c1.cid, "keep": "false"}]}
    report = run_agent(analysis, ScriptedModel([reply, reply]), config(), now=NOW)
    assert report.status == "broken" and "keep must be true or false" in report.problems[0]


def test_a_number_may_not_borrow_a_fact_the_item_does_not_cite(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {1: [NAN]})
    (c1,) = analysis.candidates
    cited = set(c1.evidence)
    other = next(f for f in analysis.book.facts
                 if f.fact_id not in cited and isinstance(f.value, int) and f.value > 1)
    lie = {"decisions": [{"cid": c1.cid, "insight": f"NaN in {other.value} frames",
                          "suggestion": "Re-record."}]}
    report = run_agent(analysis, ScriptedModel([lie, lie]), config(), now=NOW)
    assert report.status == "broken" and str(other.value) in report.problems[0]


def test_a_stage_without_codes_takes_no_added_finding(tmp_path: Path) -> None:
    from importlib.resources import files

    from flywheel.eval.agentqa.analyze import analyze_stage1

    probe = tmp_path / "probe_p1.json"
    probe.write_text((files("flywheel.testkit") / "fixtures/artifacts/ProbeP1.json").read_text())
    analysis = analyze_stage1(load_file(probe))
    fid, unit = analysis.book.facts[0].fact_id, analysis.units[0]
    added = {"added": [{"code": "T1", "target": unit, "insight": f"{{{fid}}}",
                        "suggestion": "x", "evidence": [fid]}]}
    report = run_agent(analysis, ScriptedModel([added, added]), config(), now=NOW)
    assert report.status == "broken" and "not allowed for stage1" in report.problems[0]


def test_an_unreachable_endpoint_breaks_the_report(tmp_path: Path) -> None:
    from flywheel.eval.agentqa.endpoint import OpenAIEndpoint

    analysis = _dataset(tmp_path, {1: [NAN]})
    dead = OpenAIEndpoint(base_url="http://127.0.0.1:9/v1", model="m", revision="r",
                          timeout_s=0.5)
    report = run_agent(analysis, dead, config(), now=NOW)
    assert report.status == "broken" and "endpoint failed" in report.problems[0]


def test_many_candidates_are_split_into_calls(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {i: [NAN] for i in range(5)})
    small = config().__class__(**{**config().__dict__, "candidates_per_call": 2})
    model = EchoModel()
    report = run_agent(analysis, model, small, now=NOW)
    assert model.calls == 3
    assert [f.rank for f in report.findings] == [1, 2, 3, 4, 5]


def test_the_payload_fits_the_window_by_dropping_uncited_facts(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {1: [NAN]})
    for i in range(3000):
        analysis.book.add(f"filler_{i}", i, "x")
    tight = config().__class__(**{**config().__dict__, "context_tokens": 6000})
    messages, facts = build_messages(analysis, analysis.candidates, tight)
    cited = set(analysis.candidates[0].evidence)
    assert cited <= {f.fact_id for f in facts}
    assert len(facts) < len(analysis.book.facts)
    assert len(messages[1]["content"]) <= (6000 - tight.reply_tokens) * tight.chars_per_token


def test_train_and_rtc_findings_come_from_the_lane_detectors(tmp_path: Path) -> None:
    metrics = train_job(tmp_path / "train" / "job-nan",
                        loss=lambda s: "NaN" if s == 50 else 1.0 / (s + 1))
    train = analyze_train(load_file(metrics), "train/job-nan", TRAIN_YAML)
    assert ("T1", "train/job-nan") in {(c.code, c.target) for c in train.candidates}
    log = rtc_job(tmp_path / "rtc" / "job-slow", latency=0.3)
    rtc = analyze_rtc(load_file(log), "rtc/job-slow", SYSTEM_YAML)
    assert "R1" in {c.code for c in rtc.candidates}
    report = run_agent(rtc, EchoModel(), config(), now=NOW)
    assert report.stage == "inference" and report.findings[0].code == "R1"


def test_dropping_a_code_candidate_needs_a_reason(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {1: [NAN]})
    (c1,) = analysis.candidates
    silent = {"decisions": [{"cid": c1.cid, "keep": False}]}
    report = run_agent(analysis, ScriptedModel([silent, silent]), config(), now=NOW)
    assert report.status == "broken" and "reason missing" in report.problems[0]
    guessed = {"decisions": [{"cid": c1.cid, "keep": False, "reason": "only 2 frames"}]}
    report = run_agent(analysis, ScriptedModel([guessed, guessed]), config(), now=NOW)
    assert report.status == "broken" and "reason states numbers" in report.problems[0]


def test_a_dropped_code_candidate_comes_back_beside_the_report(tmp_path: Path) -> None:
    """#175: every T6 dropped left an ok report with nothing in it and no word why."""
    from flywheel.eval.agentqa.agent import review_subject

    analysis = _dataset(tmp_path, {1: [NAN], 3: [NAN]})
    c1, c2 = analysis.candidates
    reply = {"decisions": [
        {"cid": c1.cid, "keep": False, "reason": f"below the threshold {{{c1.evidence[1]}}}"},
        {"cid": c2.cid, "keep": False, "reason": "same episode as the other"},
    ]}
    run = review_subject(analysis, ScriptedModel([reply]), config(), now=NOW)
    assert run.report.status == "ok" and run.report.findings == []
    assert [(d.cid, d.code, d.target) for d in run.dropped] == [
        (c1.cid, "D1", "episode_000001"), (c2.cid, "D1", "episode_000003")
    ]
    assert run.dropped[0].evidence == c1.evidence
    # an EchoModel drops hints only: nothing a detector raised is reported dropped
    assert review_subject(analysis, EchoModel(), config(), now=NOW).dropped == ()


def test_an_added_finding_may_not_overrule_a_detector_that_found_nothing(tmp_path: Path) -> None:
    """#175, clean job: an added T1 "diverges" whose own text said the loss converged."""
    metrics = train_job(tmp_path / "train" / "job-clean")
    analysis = analyze_train(load_file(metrics), "train/job-clean", TRAIN_YAML)
    assert analysis.candidates == [] and "T1" in analysis.cleared
    assert "T2" not in analysis.cleared  # skipped: too few val measurements to judge
    fid = next(f.fact_id for f in analysis.book.facts if f.name == "train_loss_last")
    t1 = {"added": [{"code": "T1", "target": "train/job-clean", "priority": 1,
                     "insight": f"Loss ended at {{{fid}}}, indicating convergence.",
                     "suggestion": "Stop the job.", "evidence": [fid]}]}
    model = ScriptedModel([t1, t1])
    report = run_agent(analysis, model, config(), now=NOW)
    assert report.status == "broken" and "found no fault" in report.problems[0]
    payload = json.loads(model.messages[0][1]["content"])
    assert "T1" in payload["cleared_by_code"]
    t2 = {"added": [{**t1["added"][0], "code": "T2"}]}
    report = run_agent(analysis, ScriptedModel([t2]), config(), now=NOW)
    assert [(f.code, f.target_ref) for f in report.findings] == [("T2", "train/job-clean")]


def test_rtc_clears_only_what_it_judged(tmp_path: Path) -> None:
    log = rtc_job(tmp_path / "rtc" / "job-slow", latency=0.3)
    rtc = analyze_rtc(load_file(log), "rtc/job-slow", SYSTEM_YAML)
    assert rtc.cleared == ("R2",)

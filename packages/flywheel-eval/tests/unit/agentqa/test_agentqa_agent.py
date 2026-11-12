"""DA-20 AC 3, 5: the agent ranks and explains on code's facts; a reply that breaks a rule
never becomes findings."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from agentqa_build import (
    AGENT_YAML,
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
    from flywheel.eval.agentqa.agent import prompt_budget

    tight = config().__class__(**{**config().__dict__, "context_tokens": 12000})
    messages, facts = build_messages(analysis, analysis.candidates, tight)
    cited = set(analysis.candidates[0].evidence)
    assert cited <= {f.fact_id for f in facts}
    assert len(facts) < len(analysis.book.facts)
    assert sum(len(m["content"]) for m in messages) <= prompt_budget(tight)


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
    from flywheel.eval.agentqa.agent import review_subject

    # refused on its own, shown beside the report; the rest of the reply stands
    t2 = {**t1["added"][0], "code": "T2", "insight": f"Val loss was never measured, {{{fid}}}."}
    model = ScriptedModel([{"added": [t1["added"][0], t2]}])
    run = review_subject(analysis, model, config(), now=NOW)
    assert run.report.status == "ok" and len(model.messages) == 1
    assert [(f.code, f.target_ref) for f in run.report.findings] == [("T2", "train/job-clean")]
    (refused,) = run.dropped
    assert (refused.kind, refused.cid, refused.code) == ("refused_by_code", "added[0]", "T1")
    assert "found no fault" in refused.detail and "convergence" in refused.reason
    payload = json.loads(model.messages[0][1]["content"])
    assert "T1" in payload["cleared_by_code"]
    assert "T4" not in payload["cleared_by_code"]  # T4 can end with no verdict and no skip


def test_rtc_clears_only_what_it_judged(tmp_path: Path) -> None:
    log = rtc_job(tmp_path / "rtc" / "job-slow", latency=0.3)
    rtc = analyze_rtc(load_file(log), "rtc/job-slow", SYSTEM_YAML)
    assert rtc.cleared == ("R2",)


def test_a_prompt_over_the_window_is_refused_not_sent(tmp_path: Path) -> None:
    """#175: the server ran 16K while the budget assumed 64K; Ollama cuts without a word."""
    from flywheel.eval.agentqa.agent import prompt_budget

    analysis = _dataset(tmp_path, {i: [NAN] for i in range(5)})
    for c in analysis.candidates:  # every candidate cites a long fact: nothing left to drop
        analysis.book.facts[int(c.evidence[0][1:]) - 1] = analysis.book.get(
            c.evidence[0]).model_copy(update={"value": "x" * 8000})
    model = ScriptedModel([])
    report = run_agent(analysis, model, config(), now=NOW)
    assert report.status == "broken" and model.messages == []
    assert f"over the budget of {prompt_budget(config())}" in report.problems[0]
    assert "context_tokens 16384" in report.problems[0]


def test_a_retry_that_would_overflow_the_window_is_not_sent(tmp_path: Path) -> None:
    analysis = _dataset(tmp_path, {1: [NAN]})
    rambling = "no json here " * 3000  # a reply that breaks the rules and fills the window
    model = ScriptedModel([rambling, rambling])
    report = run_agent(analysis, model, config(), now=NOW)
    assert report.status == "broken" and len(model.messages) == 1
    assert "the retry turn is" in report.problems[0]


def test_the_budget_is_the_served_window() -> None:
    cfg = config()
    assert (cfg.context_tokens, cfg.chars_per_token) == (16384, 2.5)


def _t6_job(tmp_path: Path, n: int, collapsed: set[int]):  # type: ignore[no-untyped-def]
    from test_agentqa_analyze import collapsed_job

    ratios = [0.05 if d in collapsed else 0.9 for d in range(n)]
    metrics = collapsed_job(tmp_path / "train" / "job-t6", ratios)
    return analyze_train(load_file(metrics), "train/job-t6", TRAIN_YAML)


def test_a_dimension_index_in_a_sentence_is_a_fact(tmp_path: Path) -> None:
    """PR #185 review B1, Hưng's rerun: "dimension 20" broke the report; 20 was no fact."""
    from flywheel.eval.agentqa.agent import review_subject

    analysis = _t6_job(tmp_path, 21, {2, 20})
    c2, c20 = [c for c in analysis.candidates if c.code == "T6"]
    names = {f.fact_id: f.name for f in analysis.book.facts}
    assert "T6_dimension_dim20" in {names[e] for e in c20.evidence}
    reply = {"decisions": [
        {"cid": c2.cid, "keep": True, "insight": "Mode collapse on dimension 2.",
         "suggestion": "Check the action head for dimension 2.", "evidence": list(c2.evidence)},
        {"cid": c20.cid, "keep": False, "reason": "dimension 20 is a gripper held still"},
    ]}
    run = review_subject(analysis, ScriptedModel([reply]), config(), now=NOW)
    assert run.report.status == "ok" and run.report.findings[0].insight.endswith("dimension 2.")
    assert run.dropped[0].reason.startswith("dimension 20")
    # another candidate's index is still not this sentence's fact
    borrowed = {"decisions": [{**reply["decisions"][0], "insight": "Dimensions 2 and 20."},
                              reply["decisions"][1]]}
    report = run_agent(analysis, ScriptedModel([borrowed, borrowed]), config(), now=NOW)
    assert report.status == "broken" and "20" in report.problems[0]


def test_a_failed_batch_keeps_what_the_other_batches_decided(tmp_path: Path) -> None:
    """Hưng's proposal 2: one rejected batch no longer throws away the valid one."""
    analysis = _dataset(tmp_path, {1: [NAN], 3: [NAN]})
    c1, c3 = analysis.candidates
    one = config().__class__(**{**config().__dict__, "candidates_per_call": 1})
    good = {"decisions": [{"cid": c1.cid, "insight": f"NaN, see {{{c1.evidence[0]}}}",
                           "suggestion": "Re-record."}]}
    bad = {"decisions": [{"cid": c3.cid, "insight": "NaN in 42 frames", "suggestion": "fix"}]}
    report = run_agent(analysis, ScriptedModel([good, bad, bad]), one, now=NOW)
    assert report.status == "broken"
    assert [(f.code, f.target_ref) for f in report.findings] == [("D1", "episode_000001")]
    assert report.problems[0].startswith(f"{c3.cid}: model reply rejected")


class CutModel(EchoModel):
    """A server whose reply is cut whenever it is asked about more than `fits` candidates."""

    def __init__(self, fits: int) -> None:
        super().__init__()
        self.fits, self.sizes = fits, []  # type: ignore[var-annotated]

    def complete(self, messages):  # type: ignore[no-untyped-def]
        from flywheel.eval.agentqa.endpoint import ReplyCut

        n = len(json.loads(str(messages[1]["content"]))["candidates"])
        self.sizes.append(n)
        if n > self.fits:
            raise ReplyCut("cut", '{"decisions": [{"cid": "C1", "insi')
        return super().complete(messages)


def test_a_cut_reply_splits_its_batch_instead_of_being_sent_back(tmp_path: Path) -> None:
    """PR #185 review S1: both first replies of Hưng's rerun stopped at max_tokens."""
    analysis = _dataset(tmp_path, {i: [NAN] for i in range(5)})
    model = CutModel(fits=2)
    report = run_agent(analysis, model, config(), now=NOW)
    assert report.status == "ok" and len(report.findings) == 5
    assert model.sizes == [5, 2, 3, 1, 2]
    report = run_agent(analysis, CutModel(fits=0), config(), now=NOW)
    assert report.status == "broken" and "raise models.agent.max_tokens" in report.problems[0]


def test_the_reply_budget_is_one_number(tmp_path: Path) -> None:
    import yaml
    from flywheel.eval.agentqa.agent import load_agent_config

    raw = yaml.safe_load(AGENT_YAML.read_text())
    assert config().reply_tokens == raw["models"]["agent"]["max_tokens"]
    raw["limits"]["reply_tokens"] = 4096
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "system.md").write_text("p")
    (tmp_path / "agent.yaml").write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="models.agent.max_tokens"):
        load_agent_config(tmp_path / "agent.yaml")

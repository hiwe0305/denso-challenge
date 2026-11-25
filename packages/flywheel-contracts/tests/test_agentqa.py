"""Unit and contract tests for AgentReport and AgentReview (Issue #34)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from flywheel.contracts.agentqa import (
    AgentEstimate,
    AgentFact,
    AgentFinding,
    AgentInput,
    AgentModel,
    AgentReport,
    AgentReview,
    FindingDecision,
    RoundDiagnosis,
)
from pydantic import ValidationError

FIXTURES_DIR = (
    Path(__file__).resolve().parents[2]
    / "flywheel-testkit"
    / "src"
    / "flywheel"
    / "testkit"
    / "fixtures"
    / "artifacts"
)
SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"


def test_valid_agent_report_dataset() -> None:
    path = FIXTURES_DIR / "AgentReport.json"
    content = path.read_text(encoding="utf-8")
    report = AgentReport.model_validate_json(content)
    assert report.stage == "dataset"
    assert report.status == "ok"
    assert len(report.findings) == 2
    assert report.findings[0].code == "D2"
    # Round-trip check
    assert AgentReport.model_validate_json(report.model_dump_json()) == report


def test_valid_agent_report_train() -> None:
    path = FIXTURES_DIR / "AgentReport-train.json"
    content = path.read_text(encoding="utf-8")
    report = AgentReport.model_validate_json(content)
    assert report.stage == "train"
    assert report.findings[0].code == "T1"
    assert AgentReport.model_validate_json(report.model_dump_json()) == report


def test_valid_agent_report_broken() -> None:
    path = FIXTURES_DIR / "AgentReport-broken.json"
    content = path.read_text(encoding="utf-8")
    report = AgentReport.model_validate_json(content)
    assert report.status == "broken"
    assert len(report.problems) == 2


def test_invalid_agent_report_uncited_placeholder() -> None:
    path = FIXTURES_DIR / "invalid-AgentReport.json"
    content = path.read_text(encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        AgentReport.model_validate_json(content)
    assert "outside its evidence" in str(exc.value)


def test_invalid_agent_report_suggestion_uncited_placeholder() -> None:
    model_info = AgentModel(
        name="test",
        revision="r1",
        temperature=0.0,
        prompt_sha256="0" * 64,
    )
    inputs = [AgentInput(ref="test/data.json", kind="data", sha256="1" * 64)]
    facts = [AgentFact(fact_id="F1", name="loss", value=0.1, source_ref="test/data.json")]
    finding = AgentFinding(
        finding_id="f1",
        code="D1",
        rank=1,
        target_ref="ep1",
        evidence=["F1"],
        insight="Insight with {F1}",
        suggestion="Suggestion citing missing {F2}",
    )
    with pytest.raises(ValidationError) as exc:
        AgentReport(
            report_id="rep1",
            subject_ref="subject/test",
            stage="dataset",
            created_at=datetime.now(timezone.utc),
            model=model_info,
            inputs=inputs,
            facts=facts,
            findings=[finding],
            status="ok",
        )
    assert "suggestion cites fact(s) outside its evidence" in str(exc.value)


def test_vault_isolation_checks() -> None:
    with pytest.raises(ValidationError) as exc1:
        AgentInput(ref="vault/secrets.json", kind="raw", sha256="0" * 64)
    assert "vault" in str(exc1.value)

    with pytest.raises(ValidationError) as exc2:
        AgentFinding(
            finding_id="f1",
            code="D1",
            rank=1,
            target_ref="ep1",
            evidence=["F1"],
            figures=["path/to/vault/fig.png"],
            insight="test",
            suggestion="test",
        )
    assert "vault" in str(exc2.value)


@pytest.mark.parametrize("code", ["D1", "D8", "T1", "T8", "O1", "O4", "R1", "R6"])
def test_finding_code_accepts_design_section_10_codes(code: str) -> None:
    finding = AgentFinding(
        finding_id="f1",
        code=code,
        rank=1,
        target_ref="ep1",
        evidence=["F1"],
        insight="test",
        suggestion="test",
    )
    assert finding.code == code


@pytest.mark.parametrize("code", ["Z99", "D0", "D9", "T9", "O5", "R7", "d1", "D1 ", "D10", ""])
def test_finding_code_refuses_codes_outside_design_section_10(code: str) -> None:
    with pytest.raises(ValidationError) as exc:
        AgentFinding(
            finding_id="f1",
            code=code,
            rank=1,
            target_ref="ep1",
            evidence=["F1"],
            insight="test",
            suggestion="test",
        )
    assert "code" in str(exc.value)


def test_estimate_ordering_check() -> None:
    with pytest.raises(ValidationError) as exc:
        AgentEstimate(
            estimate_id="e1",
            quantity="latency",
            low=5.0,
            high=2.0,
            unit="s",
            basis=["F1"],
        )
    assert "low must not exceed high" in str(exc.value)


def test_status_and_problems_consistency() -> None:
    model_info = AgentModel(
        name="test",
        revision="r1",
        temperature=0.0,
        prompt_sha256="0" * 64,
    )
    inputs = [AgentInput(ref="test/data.json", kind="data", sha256="1" * 64)]

    # status ok but with problems
    with pytest.raises(ValidationError) as exc1:
        AgentReport(
            report_id="rep1",
            subject_ref="subject/test",
            stage="dataset",
            created_at=datetime.now(timezone.utc),
            model=model_info,
            inputs=inputs,
            status="ok",
            problems=["Something broke"],
        )
    assert "status ok needs no problems" in str(exc1.value)

    # status broken but without problems
    with pytest.raises(ValidationError) as exc2:
        AgentReport(
            report_id="rep1",
            subject_ref="subject/test",
            stage="dataset",
            created_at=datetime.now(timezone.utc),
            model=model_info,
            inputs=inputs,
            status="broken",
            problems=[],
        )
    assert "status broken needs at least one" in str(exc2.value)


def test_valid_agent_review() -> None:
    path = FIXTURES_DIR / "AgentReview.json"
    content = path.read_text(encoding="utf-8")
    review = AgentReview.model_validate_json(content)
    assert review.reviewer == "long"
    assert len(review.decisions) == 2
    assert review.decisions[0].decision == "agree"
    assert review.decisions[1].decision == "override"
    assert review.decisions[1].reason != ""
    assert AgentReview.model_validate_json(review.model_dump_json()) == review


def test_invalid_agent_review_override_needs_reason() -> None:
    path = FIXTURES_DIR / "invalid-AgentReview.json"
    content = path.read_text(encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        AgentReview.model_validate_json(content)
    assert "an override needs a reason" in str(exc.value)


@pytest.mark.parametrize("stamp", ["2026-11-03T10:00:00", "2026-11-03 10:00:00"])
def test_datetimes_without_timezone_are_refused(stamp: str) -> None:
    report = json.loads((FIXTURES_DIR / "AgentReport.json").read_text(encoding="utf-8"))
    report["created_at"] = stamp
    with pytest.raises(ValidationError) as exc1:
        AgentReport.model_validate(report)
    assert "timezone" in str(exc1.value)

    review = json.loads((FIXTURES_DIR / "AgentReview.json").read_text(encoding="utf-8"))
    review["decided_at"] = stamp
    with pytest.raises(ValidationError) as exc2:
        AgentReview.model_validate(review)
    assert "timezone" in str(exc2.value)


def test_datetimes_with_offset_are_accepted() -> None:
    review = json.loads((FIXTURES_DIR / "AgentReview.json").read_text(encoding="utf-8"))
    review["decided_at"] = "2026-11-03T18:00:00+07:00"
    assert AgentReview.model_validate(review).decided_at.utcoffset() is not None


def _reports_by_id() -> dict[str, AgentReport]:
    reports = [
        AgentReport.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURES_DIR.glob("AgentReport*.json"))
    ]
    return {report.report_id: report for report in reports}


@pytest.mark.parametrize(
    "name", sorted(path.name for path in FIXTURES_DIR.glob("*AgentReview*.json"))
)
def test_review_fixtures_point_at_findings_that_exist(name: str) -> None:
    # Checked on the raw JSON so an invalid fixture fails only for its own reason.
    raw = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    report = _reports_by_id()[raw["report_id"]]
    known = {finding.finding_id for finding in report.findings}
    assert {d["finding_id"] for d in raw["decisions"]} <= known


def test_check_against_accepts_the_shared_fixtures() -> None:
    review = AgentReview.model_validate_json(
        (FIXTURES_DIR / "AgentReview.json").read_text(encoding="utf-8")
    )
    review.check_against(_reports_by_id()[review.report_id])


def test_check_against_refuses_unknown_findings_and_other_reports() -> None:
    reports = _reports_by_id()
    review = AgentReview.model_validate_json(
        (FIXTURES_DIR / "AgentReview.json").read_text(encoding="utf-8")
    )
    with pytest.raises(ValueError, match="not in the report"):
        review.model_copy(
            update={
                "decisions": [
                    *review.decisions,
                    FindingDecision(finding_id="find_999", decision="agree"),
                ]
            }
        ).check_against(reports[review.report_id])
    with pytest.raises(ValueError, match="answers report"):
        review.check_against(reports["rep_train_001"])


def test_schemas_match_committed_files() -> None:
    for model in (AgentReport, AgentReview, RoundDiagnosis):
        schema_path = SCHEMAS_DIR / f"{model.__name__}.json"
        assert schema_path.is_file(), f"Missing schema file: {schema_path}"
        committed = json.loads(schema_path.read_text(encoding="utf-8"))
        assert committed == model.model_json_schema()


# --- DA-43 K3: origin and agent version, optional ------------------------------------


@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES_DIR.glob("AgentReport*.json")))
def test_reports_without_k3_fields_default_to_code(name: str) -> None:
    raw = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    assert "agent_version" not in raw
    report = AgentReport.model_validate(raw)
    assert report.agent_version is None
    assert all(f.origin == "code" for f in report.facts)
    assert all(f.origin == "code" for f in report.findings)


def test_k3_fields_round_trip_and_refuse_unknown_origin() -> None:
    raw = json.loads((FIXTURES_DIR / "AgentReport.json").read_text(encoding="utf-8"))
    raw["agent_version"] = "4.0.0"
    raw["facts"][0]["origin"] = "vision"
    raw["findings"][0]["origin"] = "hint"
    report = AgentReport.model_validate(raw)
    assert AgentReport.model_validate_json(report.model_dump_json()) == report
    raw["facts"][0]["origin"] = "guess"
    with pytest.raises(ValidationError):
        AgentReport.model_validate(raw)


# --- DA-43 K2: RoundDiagnosis ---------------------------------------------------------


def _round() -> dict:
    return json.loads((FIXTURES_DIR / "RoundDiagnosis.json").read_text(encoding="utf-8"))


def test_round_fixture_validates_and_round_trips() -> None:
    value = RoundDiagnosis.model_validate(_round())
    assert value.status == "degraded"
    assert [h.rank for h in value.hypotheses] == [1, 2]
    assert RoundDiagnosis.model_validate_json(value.model_dump_json()) == value


def test_invalid_round_fixture_fails_on_a_bare_number() -> None:
    raw = json.loads((FIXTURES_DIR / "invalid-RoundDiagnosis.json").read_text(encoding="utf-8"))
    with pytest.raises(ValidationError, match="writes number"):
        RoundDiagnosis.model_validate(raw)


def test_round_explanation_may_name_a_run_id() -> None:
    raw = _round()
    raw["hypotheses"][1]["explanation"] = (
        "Run pair60k-C_ALL-60000-rp_abc of 19/11/2026 fails the carry step ({F1})."
    )
    assert RoundDiagnosis.model_validate(raw).hypotheses[1].explanation


def test_round_explanation_refuses_a_non_ascii_digit() -> None:
    raw = _round()
    raw["hypotheses"][1]["explanation"] = "Only \uff13 of the rollouts pass."
    with pytest.raises(ValidationError, match="H2: explanation writes number"):
        RoundDiagnosis.model_validate(raw)


def _broken(mutate) -> dict:  # type: ignore[no-untyped-def]
    raw = _round()
    mutate(raw)
    return raw


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r["facts"].append(dict(r["facts"][0])), "fact ids must be unique"),
        (lambda r: r["report_ids"].append("rep_eval_001"), "report ids must be unique"),
        (lambda r: r["hypotheses"][1].update(hypothesis_id="H1"), "hypothesis ids must be unique"),
        (lambda r: r["hypotheses"][1].update(rank=1), "rank 1 is taken"),
        (lambda r: r["hypotheses"][0].update(cluster_id="nope"), "unknown cluster"),
        (lambda r: r["hypotheses"][0].update(support=["F9"]), "unknown fact"),
        (lambda r: r["hypotheses"][0].update(explanation="see {F9}"), "unknown fact"),
        (lambda r: r["hypotheses"][0].update(support=["F4"]), "beyond vision facts"),
        (lambda r: r["checks"][0].update(separates=[["H1", "H9"]]), "unknown hypothesis"),
        (lambda r: r["checks"][0].update(separates=[["H1", "H1"]]), "two different"),
        (lambda r: r["checks"][0].update(cluster_id="nope"), "unknown cluster"),
        (lambda r: r["proposals"][0].update(hypothesis_id="H9"), "unknown hypothesis"),
        (lambda r: r["proposals"][0].update(hypothesis_id="H2"), "weak_skill may propose"),
        (lambda r: r["not_judged"][0].update(fact_id="F9"), "unknown fact"),
        (lambda r: r.update(headline_cluster_id="nope"), "headline cluster"),
        (lambda r: r.update(problems=[]), "degraded or broken needs at least one"),
        (lambda r: r.update(status="ok"), "status ok needs no problems"),
        (lambda r: r.update(agent_hash="abc"), "agent_hash"),
        (lambda r: r.update(created_at="2026-11-21T10:00:00"), "timezone"),
        (lambda r: r["facts"][0].update(source_ref="vault/x.json"), "vault"),
    ],
)
def test_round_rules(mutate, message: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError, match=message):
        RoundDiagnosis.model_validate(_broken(mutate))


def _data_proposal(raw: dict) -> dict:
    """A teleop correction for H2 (weak_skill): the kind of proposal that spends data budget."""
    return {
        "proposal_id": "P2",
        "hypothesis_id": "H2",
        "proposal": {
            "kind": "teleop_correction",
            "description": "Record teleop corrections of the carry turn.",
            "consumes_budget": True,
            "quantity": 6,
            "unit": "corrections",
            "gain": {
                "n_failures": 6,
                "cap": 6,
                "n_effective": 6,
                "n_dev": 60,
                "fix_rate_alpha": 1.0,
                "fix_rate_beta": 1.0,
                "expected_gain_pp": 5.0,
            },
            "cost": raw["checks"][0]["cost"],
        },
        "source": "code",
    }


def test_round_refuses_data_spend_on_a_blocked_cluster() -> None:
    raw = _round()
    assert raw["clusters"][0]["blocked_data_spend"] is True
    raw["proposals"].append(_data_proposal(raw))
    with pytest.raises(ValidationError, match="P2: cluster .* is blocked"):
        RoundDiagnosis.model_validate(raw)


def test_round_allows_data_spend_on_an_open_cluster() -> None:
    raw = _round()
    raw["clusters"][0]["blocked_data_spend"] = False
    raw["proposals"].append(_data_proposal(raw))
    value = RoundDiagnosis.model_validate(raw)
    assert value.proposals[1].proposal.consumes_budget


def test_round_ok_with_no_hypotheses() -> None:
    raw = _round()
    raw.update(status="ok", problems=[], hypotheses=[], checks=[], proposals=[])
    assert RoundDiagnosis.model_validate(raw).status == "ok"

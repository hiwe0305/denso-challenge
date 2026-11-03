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
    for model in (AgentReport, AgentReview):
        schema_path = SCHEMAS_DIR / f"{model.__name__}.json"
        assert schema_path.is_file(), f"Missing schema file: {schema_path}"
        committed = json.loads(schema_path.read_text(encoding="utf-8"))
        assert committed == model.model_json_schema()

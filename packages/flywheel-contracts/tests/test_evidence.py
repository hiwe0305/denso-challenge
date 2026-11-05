"""Contract tests for EvidenceCard (DA-39 AC 2-7)."""

import json
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.entities import Decision
from flywheel.contracts.evidence import (
    OVERRIDE_DIAGNOSIS_KEY,
    OVERRIDE_INTERVENTION_KEY,
    REQUIRED_CHECKS,
    CheckResult,
    EngineerDecision,
    EvidenceCard,
    ExpectedGain,
    RetrainResult,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "packages/flywheel-contracts/schemas/EvidenceCard.json"
EXAMPLE = (
    ROOT / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/EvidenceCard.json"
)
DECISION_ID = "dec_01M6HXNZ0P000000000000000P"
LEDGER_ID = "led_01M6HXNZ0M000000000000000M"


def example() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    return data


def first_check(card: dict[str, Any], name: str, rep: int = 0) -> dict[str, Any]:
    checks = card["representatives"][rep]["checks"]
    return next(check for check in checks if check["check"] == name)


def test_shared_example_round_trips() -> None:
    card = EvidenceCard.model_validate(example())
    assert EvidenceCard.model_validate_json(card.model_dump_json()) == card
    assert card.diagnosis == "coverage_gap"
    assert card.proposal is not None and card.proposal.kind == "sim_s1"
    camera = [
        c for rep in card.representatives for c in rep.checks if c.check == "camera_reference"
    ]
    assert {c.threshold for c in camera} == {
        "fc7f9c90ebbf8c4662fd70e58de5aed668c0fbc5ccfbbd951dce705729cdeea2"
    }


def test_schema_matches_committed_file() -> None:
    assert json.loads(SCHEMA.read_text(encoding="utf-8")) == EvidenceCard.model_json_schema()


@pytest.mark.parametrize(
    "check",
    [
        {"check": "latency_p99", "outcome": "not_fired", "value": 0.08},
        {"check": "infra_status", "outcome": "not_fired", "value": "ok"},
        {"check": "camera_reference", "outcome": "not_fired", "value": "a" * 64},
        {"check": "latency_p99", "outcome": "not_judged"},
        {"check": "latency_p99", "outcome": "not_judged", "skipped_reason": ""},
        {"check": "latency_p99", "outcome": "not_judged", "value": 0.08, "skipped_reason": "x"},
        {"check": "latency_p99", "outcome": "not_fired", "skipped_reason": "no RTC log"},
        {"check": "planner_feasible", "outcome": "not_fired", "value": True, "threshold": 0.5},
    ],
    ids=[
        "number-without-threshold",
        "status-without-accepted",
        "hash-without-reference",
        "not-judged-without-reason",
        "empty-reason",
        "not-judged-with-value",
        "judged-but-skipped",
        "flag-with-threshold",
    ],
)
def test_check_has_its_threshold_or_a_reason(check: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CheckResult.model_validate(check)


@pytest.mark.parametrize(
    ("check", "outcome"),
    [
        ({"check": "latency_p99", "value": 0.2, "threshold": 0.15}, "fired"),
        ({"check": "latency_p99", "value": 0.15, "threshold": 0.15}, "not_fired"),
        ({"check": "camera_reference", "value": "b" * 64, "threshold": "a" * 64}, "fired"),
        ({"check": "infra_status", "value": "sim_crash", "threshold": ["ok"]}, "fired"),
        ({"check": "planner_feasible", "value": False}, "fired"),
        ({"check": "nominal_visuals", "value": False}, "not_fired"),
        (
            {
                "check": "reset_success",
                "value": 0.8,
                "threshold": 0.8,
                "n_success": 8,
                "n_runs": 10,
            },
            "fired",
        ),
    ],
)
def test_outcome_is_recomputed_from_value_and_threshold(
    check: dict[str, Any], outcome: str
) -> None:
    assert CheckResult.model_validate({**check, "outcome": outcome}).outcome == outcome
    other = "not_fired" if outcome == "fired" else "fired"
    with pytest.raises(ValidationError, match="not " + other):
        CheckResult.model_validate({**check, "outcome": other})


def test_reset_success_carries_its_counts() -> None:
    base = {"check": "reset_success", "outcome": "not_fired", "value": 0.3, "threshold": 0.8}
    with pytest.raises(ValidationError):
        CheckResult.model_validate(base)
    with pytest.raises(ValidationError):
        CheckResult.model_validate({**base, "n_success": 4, "n_runs": 10})
    assert CheckResult.model_validate({**base, "n_success": 3, "n_runs": 10}).n_runs == 10


@pytest.mark.parametrize("name", sorted(REQUIRED_CHECKS))
def test_a_missing_check_is_refused_not_read_as_a_pass(name: str) -> None:
    card = example()
    rep = card["representatives"][0]
    rep["checks"] = [check for check in rep["checks"] if check["check"] != name]
    with pytest.raises(ValidationError, match="checks missing"):
        EvidenceCard.model_validate(card)


def test_data_diagnosis_needs_every_system_check_judged() -> None:
    card = example()
    first_check(card, "camera_reference").update(
        outcome="not_judged", value=None, skipped_reason="no camera_params.jsonl"
    )
    with pytest.raises(ValidationError, match="every system check judged"):
        EvidenceCard.model_validate(card)


def test_diagnosis_needs_the_check_that_fired() -> None:
    card = example()
    first_check(card, "coverage_distance").update(value=0.05, outcome="not_fired")
    with pytest.raises(ValidationError, match="coverage_gap needs one of"):
        EvidenceCard.model_validate(card)


def test_cluster_diagnosis_is_the_majority() -> None:
    card = example()
    card["diagnosis"] = "bad_start_state"
    with pytest.raises(ValidationError, match="majority"):
        EvidenceCard.model_validate(card)


def tie(card: dict[str, Any]) -> dict[str, Any]:
    """One coverage gap and one bad start state: no majority."""
    reps = card["representatives"]
    card["representatives"] = [reps[0], reps[2]]
    card["diagnosis"] = None
    card["proposal"] = None
    for rep in card["representatives"]:
        for hypothesis in rep.get("stage_hypotheses", []):
            hypothesis["confirmed"] = False
    card["decision"] = None
    return card


def test_a_tie_is_left_to_the_engineer() -> None:
    card = tie(example())
    assert EvidenceCard.model_validate(card).diagnosis is None
    card["decision"] = {"verdict": "accept", "decision_id": DECISION_ID, "signed_by": "hieu"}
    with pytest.raises(ValidationError, match="tie"):
        EvidenceCard.model_validate(card)
    card["decision"] = {
        "verdict": "override",
        "decision_id": DECISION_ID,
        "signed_by": "hieu",
        "reason": "s_k = 0.9 chỉ ở một đại diện; P3 nhóm `hand` cao trên cả hai",
        "diagnosis": "coverage_gap",
    }
    assert EvidenceCard.model_validate(card).decision is not None


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_override_without_a_reason_is_refused(reason: str | None) -> None:
    with pytest.raises(ValidationError, match="needs a reason"):
        EngineerDecision(
            verdict="override",
            decision_id=DECISION_ID,
            signed_by="hieu",
            reason=reason,
            intervention="teleop_correction",
        )


def test_override_names_what_it_changes() -> None:
    with pytest.raises(ValidationError, match="names the diagnosis or intervention"):
        EngineerDecision(
            verdict="override", decision_id=DECISION_ID, signed_by="hieu", reason="disagree"
        )
    with pytest.raises(ValidationError, match="an accept changes neither"):
        EngineerDecision(
            verdict="accept", decision_id=DECISION_ID, signed_by="hieu", diagnosis="weak_skill"
        )
    card = example()
    card["decision"] = {
        "verdict": "override",
        "decision_id": DECISION_ID,
        "signed_by": "hieu",
        "reason": "same",
        "intervention": "sim_s1",
    }
    with pytest.raises(ValidationError, match="is an accept"):
        EvidenceCard.model_validate(card)


def test_stage_hypothesis_is_confirmed_only_by_a_decision() -> None:
    card = example()
    card["decision"] = None
    with pytest.raises(ValidationError, match="confirmed by the engineer"):
        EvidenceCard.model_validate(card)


def test_proposal_follows_the_diagnosis_table() -> None:
    card = example()
    card["proposal"]["kind"] = "teleop_correction"
    with pytest.raises(ValidationError, match="coverage_gap proposes"):
        EvidenceCard.model_validate(card)


def test_proposal_cost_is_estimated() -> None:
    card = example()
    card["proposal"]["cost"]["measure_kind"] = "measured"
    with pytest.raises(ValidationError, match="estimated"):
        EvidenceCard.model_validate(card)
    card = example()
    card["proposal"]["cost"]["ledger_entry_ids"] = []
    with pytest.raises(ValidationError):
        EvidenceCard.model_validate(card)


def test_expected_gain_follows_section_6_11() -> None:
    gain = {
        "n_failures": 12,
        "cap": 10,
        "n_effective": 10,
        "n_dev": 90,
        "fix_rate_alpha": 1.0,
        "fix_rate_beta": 1.0,
        "expected_gain_pp": 100 * 10 / 90 * 0.5,
    }
    assert ExpectedGain.model_validate(gain).n_effective == 10
    with pytest.raises(ValidationError, match="min"):
        ExpectedGain.model_validate({**gain, "n_effective": 12})
    with pytest.raises(ValidationError, match="expected_gain_pp"):
        ExpectedGain.model_validate({**gain, "expected_gain_pp": 10.0})


def retrain(**changes: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "parent_checkpoint_id": "ckpt_psi0_base",
        "candidate_checkpoint_id": "ckpt_psi0_c1",
        "n_conditions": 30,
        "runs_per_condition": 3,
        "p_parent": 0.2,
        "p_candidate": 0.5,
        "fixed": 9,
        "cost": {"measure_kind": "measured", "usd_amount": 3.1, "ledger_entry_ids": [LEDGER_ID]},
    }
    result.update(changes)
    return result


def test_retrain_result_is_measured_and_follows_section_6_13() -> None:
    assert RetrainResult.model_validate(retrain()).fixed == 9
    assert RetrainResult.model_validate(retrain(p_candidate=0.1, fixed=0)).fixed == 0
    with pytest.raises(ValidationError, match="fixed"):
        RetrainResult.model_validate(retrain(fixed=12))
    with pytest.raises(ValidationError, match="measured"):
        RetrainResult.model_validate(
            retrain(
                cost={
                    "measure_kind": "estimated",
                    "usd_amount": 3.1,
                    "ledger_entry_ids": [LEDGER_ID],
                }
            )
        )
    card = example()
    card["result"] = retrain()
    assert EvidenceCard.model_validate(card).result is not None
    card["decision"] = None
    for rep in card["representatives"]:
        for hypothesis in rep.get("stage_hypotheses", []):
            hypothesis["confirmed"] = False
    with pytest.raises(ValidationError, match="follows the engineer"):
        EvidenceCard.model_validate(card)


def test_representatives_drawn_from_members_record_the_seed() -> None:
    card = example()
    card["representative_seed"] = None
    with pytest.raises(ValidationError, match="seed"):
        EvidenceCard.model_validate(card)
    card = example()
    card["member_episode_ids"] = card["member_episode_ids"][1:]
    with pytest.raises(ValidationError, match="members"):
        EvidenceCard.model_validate(card)


def engineer_decision(verdict: str, criteria: dict[str, Any], reason: str) -> Decision:
    return Decision(
        id=DECISION_ID,
        kind="plan_review",
        subject_kind="cluster",
        subject_id="clu_8406056e72ff77ac",
        verdict=verdict,  # type: ignore[arg-type]
        criteria=criteria,
        signed_by="hieu",
        reason=reason,
    )


def test_override_round_trips_through_decision_criteria() -> None:
    criteria = {
        OVERRIDE_DIAGNOSIS_KEY: "weak_skill",
        OVERRIDE_INTERVENTION_KEY: "teleop_correction",
    }
    decision = engineer_decision("overridden", criteria, "Demo gần nhất mâu thuẫn ở bước 2")
    stored = Decision.model_validate_json(decision.model_dump_json())
    engineer = EngineerDecision.from_decision(stored)
    assert (engineer.verdict, engineer.diagnosis, engineer.intervention) == (
        "override",
        "weak_skill",
        "teleop_correction",
    )
    assert engineer.decision_id == decision.id and engineer.criteria() == criteria
    card = example()
    card["decision"] = engineer.model_dump(mode="json")
    assert EvidenceCard.model_validate(card).decision == engineer


def test_accept_reads_from_an_approved_decision() -> None:
    engineer = EngineerDecision.from_decision(engineer_decision("approved", {}, ""))
    assert (engineer.verdict, engineer.reason, engineer.criteria()) == ("accept", None, {})


@pytest.mark.parametrize(
    "decision",
    [
        engineer_decision("overridden", {}, "no change named"),
        engineer_decision("overridden", {OVERRIDE_DIAGNOSIS_KEY: "weak_skill"}, ""),
        engineer_decision("overridden", {OVERRIDE_DIAGNOSIS_KEY: "not_a_diagnosis"}, "x"),
        engineer_decision("pass", {}, "a gate verdict"),
    ],
    ids=["no-key", "no-reason", "unknown-diagnosis", "not-an-engineer-verdict"],
)
def test_decision_that_is_not_a_valid_engineer_decision_is_refused(decision: Decision) -> None:
    with pytest.raises(ValueError):
        EngineerDecision.from_decision(decision)

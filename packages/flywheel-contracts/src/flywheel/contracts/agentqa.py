"""Contracts for Agent QA/QC reports and engineer reviews (issue #34).

Enforces fact-placeholder consistency (in both insight and suggestion), vault
isolation, problem-status consistency, unique identifiers, and override reasons.
"""

from __future__ import annotations

import re
from typing import Literal

from flywheel.contracts.artifacts import Artifact
from pydantic import AwareDatetime, Field, model_validator
from typing_extensions import Self

FACT_ID = r"^F[0-9]+$"
# Error codes of design 27/10/2026 section 10 (issue #34): data, train, offline, runtime.
FINDING_CODE = r"^(D[1-8]|T[1-8]|O[1-4]|R[1-6])$"
_PLACEHOLDER = re.compile(r"\{(F[0-9]+)\}")

Stage = Literal["dataset", "train", "stage1", "stage3", "inference", "eval"]


def _in_vault(ref: str) -> bool:
    parts = [p.lower() for p in ref.replace("\\", "/").split("/")]
    return "vault" in parts


class AgentModel(Artifact):
    """Identification and configuration of the LLM generating the report."""

    name: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    temperature: float = Field(ge=0.0)
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AgentInput(Artifact):
    """An input artifact inspected by the agent."""

    ref: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def ref_not_in_vault(self) -> Self:
        if _in_vault(self.ref):
            raise ValueError("inputs must not point into vault/")
        return self


class AgentFact(Artifact):
    """A deterministic fact computed by code that the agent's prose can reference."""

    fact_id: str = Field(pattern=FACT_ID)
    name: str = Field(min_length=1)
    value: float | int | str | bool
    unit: str = ""
    source_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def source_not_in_vault(self) -> Self:
        if _in_vault(self.source_ref):
            raise ValueError("source_ref must not point into vault/")
        return self


class AgentFinding(Artifact):
    """A specific problem or observation identified by the agent."""

    finding_id: str = Field(min_length=1)
    code: str = Field(pattern=FINDING_CODE)
    rank: int = Field(ge=1)
    target_ref: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    figures: list[str] = Field(default_factory=list)
    insight: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_finding(self) -> Self:
        if any(_in_vault(path) for path in self.figures):
            raise ValueError("figures must not point into vault/")
        if _in_vault(self.target_ref):
            raise ValueError("target_ref must not point into vault/")
        for ev in self.evidence:
            if not re.match(FACT_ID, ev):
                raise ValueError(f"evidence item '{ev}' must be a valid fact ID (e.g. F1)")
        return self


class AgentEstimate(Artifact):
    """A range the agent predicts; the measured value lives in a later record, never here."""

    estimate_id: str = Field(min_length=1)
    quantity: str = Field(min_length=1)
    low: float
    high: float
    unit: str = Field(min_length=1)
    basis: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.low > self.high:
            raise ValueError("low must not exceed high")
        for b in self.basis:
            if not re.match(FACT_ID, b):
                raise ValueError(f"basis item '{b}' must be a valid fact ID (e.g. F1)")
        return self


class AgentReport(Artifact):
    """The complete QA/QC report produced by the agent for a single job or artifact."""

    report_id: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    stage: Stage
    created_at: AwareDatetime
    model: AgentModel
    inputs: list[AgentInput] = Field(min_length=1)
    facts: list[AgentFact] = Field(default_factory=list)
    findings: list[AgentFinding] = Field(default_factory=list)
    estimates: list[AgentEstimate] = Field(default_factory=list)
    status: Literal["ok", "broken"]
    problems: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if _in_vault(self.subject_ref):
            raise ValueError("subject_ref must not point into vault/")

        fact_ids = [fact.fact_id for fact in self.facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("fact ids must be unique")
        known_facts = set(fact_ids)

        finding_ids = [f.finding_id for f in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("finding ids must be unique")

        ranks = [finding.rank for finding in self.findings]
        if len(ranks) != len(set(ranks)):
            raise ValueError("finding ranks must be unique")

        for finding in self.findings:
            ev_set = set(finding.evidence)
            if not ev_set <= known_facts:
                unknown = ev_set - known_facts
                raise ValueError(f"{finding.finding_id}: evidence cites unknown fact(s): {unknown}")

            cited_insight = set(_PLACEHOLDER.findall(finding.insight))
            if not cited_insight <= ev_set:
                missing = cited_insight - ev_set
                raise ValueError(
                    f"{finding.finding_id}: insight cites fact(s) outside its evidence: {missing}"
                )

            cited_suggestion = set(_PLACEHOLDER.findall(finding.suggestion))
            if not cited_suggestion <= ev_set:
                missing = cited_suggestion - ev_set
                raise ValueError(
                    f"{finding.finding_id}: suggestion cites fact(s) outside its evidence: "
                    f"{missing}"
                )

        estimate_ids = [e.estimate_id for e in self.estimates]
        if len(estimate_ids) != len(set(estimate_ids)):
            raise ValueError("estimate ids must be unique")

        for estimate in self.estimates:
            basis_set = set(estimate.basis)
            if not basis_set <= known_facts:
                unknown = basis_set - known_facts
                raise ValueError(
                    f"{estimate.estimate_id}: basis cites unknown fact(s): {unknown}"
                )

        if (self.status == "ok") == bool(self.problems):
            raise ValueError("status ok needs no problems; status broken needs at least one")

        return self


class FindingDecision(Artifact):
    """The engineer's review decision for a single finding."""

    finding_id: str = Field(min_length=1)
    decision: Literal["agree", "override"]
    reason: str = ""

    @model_validator(mode="after")
    def override_needs_reason(self) -> Self:
        if self.decision == "override" and not self.reason.strip():
            raise ValueError("an override needs a reason")
        return self


class AgentReview(Artifact):
    """The engineer's answer to an AgentReport, recorded in fw review."""

    report_id: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    decided_at: AwareDatetime
    decisions: list[FindingDecision] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_decisions(self) -> Self:
        finding_ids = [d.finding_id for d in self.decisions]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("decision finding ids must be unique")
        return self

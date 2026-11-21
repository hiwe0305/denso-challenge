"""Contracts for Agent QA/QC reports and engineer reviews (issue #34).

Enforces fact-placeholder consistency (in both insight and suggestion), vault
isolation, problem-status consistency, unique identifiers, and override reasons.

DA-43 (K2, K3) adds `RoundDiagnosis`, the diagnosis of one round across several
subjects, and the origin of a fact or finding (`code`, `hint`, `vision`,
`history`) plus the agent version on `AgentReport`. The new fields are optional
with defaults, so a report written before DA-43 still validates.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from flywheel.contracts.artifacts import Artifact
from flywheel.contracts.evidence import (
    INTERVENTIONS_OF_DIAGNOSIS,
    Cost,
    Diagnosis,
    InterventionProposal,
)
from pydantic import AwareDatetime, Field, model_validator
from typing_extensions import Self

FACT_ID = r"^F[0-9]+$"
# Error codes of design 27/10/2026 section 10 (issue #34): data, train, offline, runtime.
FINDING_CODE = r"^(D[1-8]|T[1-8]|O[1-4]|R[1-6])$"
_PLACEHOLDER = re.compile(r"\{(F[0-9]+)\}")

Stage = Literal["dataset", "train", "stage1", "stage3", "inference", "eval"]
# Where a fact or finding comes from (design 19/11/2026 section 6, rule 4): computed by
# a tool, a hint of the engineer, a vision model's answer, or a result of an earlier round.
Origin = Literal["code", "hint", "vision", "history"]


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
    origin: Origin = "code"

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
    origin: Origin = "code"

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
    agent_version: str | None = Field(default=None, min_length=1)

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
                raise ValueError(f"{estimate.estimate_id}: basis cites unknown fact(s): {unknown}")

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

    def check_against(self, report: AgentReport) -> None:
        """Raise ValueError unless this review answers ``report`` and only its findings."""
        if self.report_id != report.report_id:
            raise ValueError(f"review answers report {self.report_id!r}, not {report.report_id!r}")
        known = {finding.finding_id for finding in report.findings}
        unknown = sorted(d.finding_id for d in self.decisions if d.finding_id not in known)
        if unknown:
            raise ValueError(f"review decides finding(s) not in the report: {unknown}")


# --- DA-43 K2: the diagnosis of one round --------------------------------------------

HYPOTHESIS_ID = r"^H[1-9][0-9]*$"
SHA256 = r"^[0-9a-f]{64}$"
Source = Literal["code", "model"]
RunStatus = Literal["ok", "degraded", "broken"]
# A digit that starts a number: not glued to a letter, digit or underscore of a name, so
# `p99`, `H2`, `T1` and `episode_000012` pass and `0.4`, `12 ms`, `45/90` do not.
_BARE_NUMBER = re.compile(r"(?<![A-Za-z0-9_])[0-9]")


def bare_numbers(text: str) -> list[str]:
    """The numbers `text` writes itself, outside `{F#}` placeholders."""
    stripped = _PLACEHOLDER.sub(" ", text)
    return [m.group(0) for m in _BARE_NUMBER.finditer(stripped)]


class RoundCluster(Artifact):
    """A failure cluster of the round: which run, step, label and level, and how many."""

    cluster_id: str = Field(min_length=1)
    run: str = Field(min_length=1)
    step: str = Field(min_length=1)
    label: str = Field(min_length=1)
    level: int = Field(ge=0)
    size: int = Field(ge=0)
    # A system or scorer hypothesis of the cluster still stands: no data budget is spent.
    blocked_data_spend: bool


class RoundHypothesis(Artifact):
    """A ranked cause of one cluster; its text writes no number, only `{F#}` placeholders."""

    hypothesis_id: str = Field(pattern=HYPOTHESIS_ID)
    cluster_id: str = Field(min_length=1)
    diagnosis: Diagnosis
    note: str = Field(min_length=1, description="Subtype of the diagnosis, as the rule names it.")
    rule_id: str | None = Field(default=None, min_length=1)
    rank: int = Field(ge=1)
    support: list[Annotated[str, Field(pattern=FACT_ID)]] = Field(default_factory=list)
    contra: list[Annotated[str, Field(pattern=FACT_ID)]] = Field(default_factory=list)
    explanation: str = ""
    source: Source

    @model_validator(mode="after")
    def no_bare_number(self) -> Self:
        numbers = bare_numbers(self.explanation)
        if numbers:
            raise ValueError(
                f"{self.hypothesis_id}: explanation writes number(s) {numbers}; "
                "a number is a {F#} placeholder"
            )
        return self


class SeparatingCheck(Artifact):
    """A check that tells two hypotheses of one cluster apart, and what it would cost."""

    check_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    cluster_id: str = Field(min_length=1)
    separates: list[tuple[str, str]] = Field(min_length=1)
    cost: Cost | None = None
    source: Source

    @model_validator(mode="after")
    def distinct_pairs(self) -> Self:
        for a, b in self.separates:
            if a == b:
                raise ValueError(f"{self.check_id}: a check separates two different hypotheses")
        return self


class RoundProposal(Artifact):
    """An intervention proposed for one hypothesis; the engineer decides on the card."""

    proposal_id: str = Field(min_length=1)
    hypothesis_id: str = Field(pattern=HYPOTHESIS_ID)
    proposal: InterventionProposal
    source: Source


class NotJudged(Artifact):
    """Something the round could not judge, and why (missing signal or artifact)."""

    what: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    fact_id: str | None = Field(default=None, pattern=FACT_ID)


class RoundDiagnosis(Artifact):
    """The agent's diagnosis of one round, read by the Console and the loop lane (DA-43 K2).

    `status` is the run status of architecture 20/11/2026 section 9: `ok` needs no
    problem, `degraded` and `broken` need at least one that says why.
    """

    round_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    data_class: Literal["public", "internal", "restricted"]
    created_at: AwareDatetime
    agent_version: str = Field(min_length=1)
    agent_hash: str = Field(pattern=SHA256)
    status: RunStatus
    problems: list[str] = Field(default_factory=list)
    report_ids: list[str] = Field(default_factory=list)
    facts: list[AgentFact] = Field(default_factory=list)
    clusters: list[RoundCluster] = Field(default_factory=list)
    headline_cluster_id: str | None = Field(default=None, min_length=1)
    hypotheses: list[RoundHypothesis] = Field(default_factory=list)
    checks: list[SeparatingCheck] = Field(default_factory=list)
    proposals: list[RoundProposal] = Field(default_factory=list)
    not_judged: list[NotJudged] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        def unique(name: str, ids: list[str]) -> set[str]:
            if len(ids) != len(set(ids)):
                raise ValueError(f"{name} must be unique")
            return set(ids)

        unique("report ids", self.report_ids)
        facts = {f.fact_id: f for f in self.facts}
        unique("fact ids", [f.fact_id for f in self.facts])
        clusters = unique("cluster ids", [c.cluster_id for c in self.clusters])
        hypotheses = {h.hypothesis_id: h for h in self.hypotheses}
        unique("hypothesis ids", [h.hypothesis_id for h in self.hypotheses])
        unique("check ids", [c.check_id for c in self.checks])
        unique("proposal ids", [p.proposal_id for p in self.proposals])

        if self.headline_cluster_id is not None and self.headline_cluster_id not in clusters:
            raise ValueError(f"headline cluster {self.headline_cluster_id!r} is not a cluster")

        ranks: set[tuple[str, int]] = set()
        for h in self.hypotheses:
            if h.cluster_id not in clusters:
                raise ValueError(f"{h.hypothesis_id}: unknown cluster {h.cluster_id!r}")
            if (h.cluster_id, h.rank) in ranks:
                raise ValueError(f"{h.hypothesis_id}: rank {h.rank} is taken in its cluster")
            ranks.add((h.cluster_id, h.rank))
            cited = set(h.support) | set(h.contra) | set(_PLACEHOLDER.findall(h.explanation))
            unknown = cited - facts.keys()
            if unknown:
                raise ValueError(f"{h.hypothesis_id}: cites unknown fact(s): {sorted(unknown)}")
            # Rule 4 of design 19/11/2026 section 6: a vision answer is not a measurement.
            if h.rank == 1 and h.support and all(facts[f].origin == "vision" for f in h.support):
                raise ValueError(f"{h.hypothesis_id}: rank 1 needs support beyond vision facts")

        for c in self.checks:
            if c.cluster_id not in clusters:
                raise ValueError(f"{c.check_id}: unknown cluster {c.cluster_id!r}")
            for pair in c.separates:
                for hid in pair:
                    if hid not in hypotheses:
                        raise ValueError(f"{c.check_id}: unknown hypothesis {hid!r}")
                    if hypotheses[hid].cluster_id != c.cluster_id:
                        raise ValueError(f"{c.check_id}: {hid} is not of cluster {c.cluster_id}")

        for p in self.proposals:
            if p.hypothesis_id not in hypotheses:
                raise ValueError(f"{p.proposal_id}: unknown hypothesis {p.hypothesis_id!r}")
            diagnosis = hypotheses[p.hypothesis_id].diagnosis
            allowed = INTERVENTIONS_OF_DIAGNOSIS.get(diagnosis, frozenset())
            if p.proposal.kind not in allowed:
                raise ValueError(
                    f"{p.proposal_id}: {diagnosis} may propose {sorted(allowed)}, "
                    f"not {p.proposal.kind}"
                )

        for n in self.not_judged:
            if n.fact_id is not None and n.fact_id not in facts:
                raise ValueError(f"not judged {n.what!r}: unknown fact {n.fact_id}")

        if (self.status == "ok") == bool(self.problems):
            raise ValueError("status ok needs no problems; degraded or broken needs at least one")
        return self

"""Facts the code computes and findings the code proposes, before the model sees anything.

Design 27/10/2026 section 9.1: every number is computed by code; the agent only
reads, ranks, explains and suggests. An analysis of one subject (a dataset copy,
a train job, an RTC log...) therefore hands the agent two lists:

    facts       `AgentFact` F1..Fn, each a value with its unit and the file it came from
    candidates  what code thinks may be wrong: a design 10 code, a target, the facts
                that back it. `origin` says whether a detector of the lanes said so
                ("code": a QA check, DA-08, DA-13) or a cheaper hint computed here
                ("hint": e.g. two episodes with the same QA fingerprint). The agent
                keeps or drops each one and may raise its own, citing facts.

The split matters for DA-31: the bench measures what the agent adds over the code
layer, so a hint is never presented to the model as a verdict.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from flywheel.contracts.agentqa import AgentFact, AgentInput, Stage

FactValue = float | int | str | bool
Origin = Literal["code", "hint"]


@dataclass(frozen=True)
class Candidate:
    cid: str
    code: str
    target: str
    evidence: tuple[str, ...]
    origin: Origin
    detail: str


@dataclass
class FactBook:
    """Numbers facts F1.. in the order they are added; the same name and source twice is one."""

    facts: list[AgentFact] = field(default_factory=list)
    _index: dict[tuple[str, str], str] = field(default_factory=dict)

    def add(self, name: str, value: FactValue, source_ref: str, unit: str = "") -> str:
        key = (name, source_ref)
        if key in self._index:
            return self._index[key]
        if isinstance(value, float) and not math.isfinite(value):
            value = str(value)  # NaN and Inf travel as text: JSON has no spelling for them
        fact_id = f"F{len(self.facts) + 1}"
        self.facts.append(
            AgentFact(fact_id=fact_id, name=name, value=value, unit=unit, source_ref=source_ref)
        )
        self._index[key] = fact_id
        return fact_id

    def get(self, fact_id: str) -> AgentFact:
        for fact in self.facts:
            if fact.fact_id == fact_id:
                return fact
        raise KeyError(fact_id)


@dataclass
class Analysis:
    """Everything the code knows about one subject, ready for the agent."""

    subject_ref: str
    stage: Stage
    inputs: list[AgentInput]
    book: FactBook = field(default_factory=FactBook)
    candidates: list[Candidate] = field(default_factory=list)
    units: tuple[str, ...] = ()  # targets a finding may name (episodes, jobs)
    figures: list[str] = field(default_factory=list)  # paths relative to the report dir
    notes: list[str] = field(default_factory=list)  # what the code could not judge

    def propose(
        self, code: str, target: str, evidence: Sequence[str], origin: Origin, detail: str
    ) -> Candidate:
        candidate = Candidate(
            f"C{len(self.candidates) + 1}", code, target, tuple(evidence), origin, detail
        )
        self.candidates.append(candidate)
        return candidate

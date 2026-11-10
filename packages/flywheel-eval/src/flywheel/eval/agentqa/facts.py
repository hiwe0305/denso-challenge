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


@dataclass(frozen=True)
class DroppedCandidate:
    """A candidate a lane detector raised and the model dropped, with the model's reason."""

    cid: str
    code: str
    target: str
    detail: str
    reason: str
    evidence: tuple[str, ...]


class FactClash(ValueError):
    """Two values under one fact name: the second would have been dropped (issue #175)."""


@dataclass
class FactBook:
    """Numbers facts F1.. in the order they are added; the same name and source twice is one.

    Adding a name again with the same value returns the first id. Adding it with
    another value raises `FactClash`: until 11/11/2026 the book returned the old id
    and dropped the new value, so 36 T6 findings, one per dimension, all cited the
    ratio of dimension 0 (#175). Callers name per-group and per-dim facts apart.
    """

    facts: list[AgentFact] = field(default_factory=list)
    _index: dict[tuple[str, str], str] = field(default_factory=dict)

    def add(self, name: str, value: FactValue, source_ref: str, unit: str = "") -> str:
        if isinstance(value, float) and not math.isfinite(value):
            value = str(value)  # NaN and Inf travel as text: JSON has no spelling for them
        key = (name, source_ref)
        if key in self._index:
            fact_id = self._index[key]
            old = self.get(fact_id).value
            if type(old) is not type(value) or old != value:
                raise FactClash(
                    f"fact {name!r} of {source_ref} holds {old!r}; {value!r} needs its own name"
                )
            return fact_id
        fact_id = f"F{len(self.facts) + 1}"
        self.facts.append(
            AgentFact(fact_id=fact_id, name=name, value=value, unit=unit, source_ref=source_ref)
        )
        self._index[key] = fact_id
        return fact_id

    def value_of(self, name: str, source_ref: str) -> FactValue | None:
        """The value already held under this name and source, or None."""
        fact_id = self._index.get((name, source_ref))
        return None if fact_id is None else self.get(fact_id).value

    def shared(self, name: str, own: str, value: FactValue, source_ref: str,
               unit: str = "") -> str:
        """One fact for a value many findings share (a threshold); `own` when it differs."""
        held = self.value_of(name, source_ref)
        if held is None or (type(held) is type(value) and held == value):
            return self.add(name, value, source_ref, unit)
        return self.add(own, value, source_ref, unit)

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
    # Codes a detector judged on this subject and found clean. The agent may not add
    # one (#175: an added T1 "diverges" on a clean job, its own text saying converged).
    cleared: tuple[str, ...] = ()

    def propose(
        self, code: str, target: str, evidence: Sequence[str], origin: Origin, detail: str
    ) -> Candidate:
        candidate = Candidate(
            f"C{len(self.candidates) + 1}", code, target, tuple(evidence), origin, detail
        )
        self.candidates.append(candidate)
        return candidate

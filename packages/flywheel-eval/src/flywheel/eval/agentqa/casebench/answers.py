"""The sealed answer file: strict models, and the one place it is opened."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal

import yaml
from flywheel.contracts.evidence import Diagnosis, InterventionKind
from flywheel.eval.agentqa.inputs import forbidden_part
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from typing_extensions import Self

ANSWERS_PART = "answers"
Kind = Literal["finding", "diagnosis", "refuted", "intervention", "blocked", "not_blocked",
               "check"]
CLUSTER_KINDS = ("diagnosis", "refuted", "intervention", "blocked", "not_blocked", "check")


class Refused(ValueError):
    """A reason the case bench will not score (sealing, run state, bad answer)."""


class Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ClusterKey(Strict):
    run: str = Field(min_length=1)
    step: str = Field(min_length=1)
    label: str = Field(min_length=1)
    level: int


class FactExpect(Strict):
    name: str = Field(min_length=1)
    equals: float | int | str | bool | None = None
    approx: float | None = None
    tol: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _one_form(self) -> Self:
        if self.approx is None:
            if self.equals is None or self.tol is not None:
                raise ValueError("a fact needs `equals`, or `approx` with `tol`")
        elif self.equals is not None or self.tol is None:
            raise ValueError("a fact needs `equals`, or `approx` with `tol`")
        return self


class Point(Strict):
    id: str = Field(min_length=1)
    kind: Kind
    must: bool = False
    quote: str = ""
    fact: FactExpect | None = None
    cluster: ClusterKey | None = None
    diagnosis: Diagnosis | None = None
    note: str | None = None
    intervention: InterventionKind | None = None
    any_of: list[str] | None = None

    @model_validator(mode="after")
    def _fields_of_the_kind(self) -> Self:
        need: dict[str, object] = {"fact": self.fact, "cluster": self.cluster,
                                   "diagnosis": self.diagnosis,
                                   "intervention": self.intervention,
                                   "any_of": self.any_of or None}
        required = {"finding": ["fact"], "diagnosis": ["cluster", "diagnosis"],
                    "refuted": ["cluster", "diagnosis"],
                    "intervention": ["cluster", "intervention"],
                    "blocked": ["cluster"], "not_blocked": ["cluster"],
                    "check": ["cluster", "any_of"]}[self.kind]
        for name in required:
            if need[name] is None:
                raise ValueError(f"{self.id}: kind {self.kind} needs `{name}`")
        for name, value in need.items():
            if name not in required and value is not None:
                raise ValueError(f"{self.id}: kind {self.kind} takes no `{name}`")
        if self.note is not None and self.kind not in ("diagnosis", "refuted"):
            raise ValueError(f"{self.id}: `note` only goes with a diagnosis or refuted point")
        return self


class Answer(Strict):
    case_id: str = Field(min_length=1)
    set: Literal["dev", "test"]
    task_id: str = Field(min_length=1)
    focus_run: str = Field(min_length=1)
    written_by: str = Field(min_length=1)
    source: list[str] = Field(default_factory=list)
    points: list[Point] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        ids = [p.id for p in self.points]
        if len(set(ids)) != len(ids):
            raise ValueError("point ids are not unique")
        return self


def refuse_path(path: Path) -> None:
    """Rule 1: the answer must live under a directory named `answers`."""
    parts = [p.lower() for p in path.resolve().parts] + [p.lower() for p in path.parts]
    if ANSWERS_PART not in parts:
        raise Refused(f"{path}: an answer file must sit under a directory named "
                      f"`{ANSWERS_PART}/`")
    # The agent's own input gate must refuse the same path (it is what keeps it out).
    if forbidden_part(path) is None:  # pragma: no cover - same rule, kept as a guard
        raise Refused(f"{path}: the agent input gate would not refuse this path")


def open_answer(path: Path, sha256: str | None = None) -> tuple[Answer, str]:
    """Read and parse the answer. Call this last, after the run is verified (rule 2)."""
    refuse_path(path)
    if not path.is_file():
        raise Refused(f"{path}: no answer file there")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if sha256 is not None and digest != sha256.lower():
        raise Refused(f"{path}: sha256 is {digest}, expected {sha256}")
    try:
        data: Any = yaml.safe_load(raw)
        return Answer.model_validate(data), digest
    except (yaml.YAMLError, ValidationError) as error:
        raise Refused(f"{path}: not a valid answer file: {error}") from error

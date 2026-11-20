"""Records of the files the pipeline steps hand to each other (architecture section 24).

Private to the eval lane: written and read here, so they are not contracts. Only what
crosses a lane boundary (`RoundDiagnosis`, the eval outcome) goes to `flywheel.contracts`.
"""

from __future__ import annotations

from typing import Any, Literal

from flywheel.contracts.evidence import Diagnosis, InterventionKind
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

DataClass = Literal["public", "internal", "restricted"]
CLASS_ORDER: dict[str, int] = {"public": 0, "internal": 1, "restricted": 2}
SHA256 = r"^[0-9a-f]{64}$"


def highest(classes: list[DataClass]) -> DataClass:
    """The most restrictive class of `classes`; `restricted` when there is none."""
    return max(classes, key=CLASS_ORDER.__getitem__, default="restricted")


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PackEntry(Record):
    """One artifact file of a round: where it is, what it is, whose it is."""

    ref: str = Field(min_length=1, description="Path under the pack root, POSIX form.")
    kind: str = Field(min_length=1)
    sha256: str = Field(pattern=SHA256)
    bytes: int = Field(ge=0)
    data_class: DataClass
    subject: dict[str, str] = Field(default_factory=dict)


class PackLink(Record):
    """A declared relation between two entries (eval run -> checkpoint -> train job ...)."""

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    relation: str = Field(min_length=1)


class Pack(Record):
    """`pack.json`: the frozen list of what one round gives the agent (step B0)."""

    pack_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    created_at: AwareDatetime
    declared_by: str = Field(min_length=1)
    entries: list[PackEntry] = Field(min_length=1)
    links: list[PackLink] = Field(default_factory=list)


class Rejected(Record):
    ref: str
    reason: str


class Admission(Record):
    """`admission.json`: what step B1 let through, and which models may see it."""

    pack_id: str
    pack_sha256: str = Field(pattern=SHA256)
    accepted: list[str]
    rejected: list[Rejected] = Field(default_factory=list)
    missing_kinds: list[str] = Field(default_factory=list)
    data_class: DataClass
    data_class_basis: list[str] = Field(
        default_factory=list,
        description="Entries whose own records carry a data class and all say public.")
    unconfirmed: list[str] = Field(
        default_factory=list,
        description="Accepted entries no source record vouches for, directly or by a link.")
    hosted_allowed: bool


Status = Literal["ok", "degraded", "broken"]


class FactRecord(Record):
    """One line of `facts.jsonl`: a number the code computed, and the call that made it."""

    fact_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    value: float | int | str | bool
    unit: str = ""
    source_ref: str = Field(min_length=1)
    provenance: Literal["code", "vision", "history"]
    tool_call_id: str = Field(min_length=1)


class ToolCallRecord(Record):
    """One line of `tool_calls.jsonl`: a call of the plan, what it read and what it made."""

    call_id: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    version: int = Field(ge=1)
    params: dict[str, Any] = Field(default_factory=dict)
    input_sha256: list[str] = Field(default_factory=list)
    fact_ids: list[str] = Field(default_factory=list)
    not_judged: list[str] = Field(default_factory=list)
    status: Literal["ran", "skipped", "refused"]
    reason: str = ""


class StepRecord(Record):
    name: str = Field(min_length=1)
    status: Status
    seconds: float = Field(ge=0)
    rows: int = Field(ge=0)
    outputs: dict[str, str] = Field(default_factory=dict, description="file name -> sha256")


class RunRecord(Record):
    """`run.json`: what happened in one run directory, rewritten after every step."""

    run_id: str = Field(min_length=1)
    command: str = ""
    started_at: AwareDatetime
    pack_id: str = ""
    pack_sha256: str = ""
    data_class: DataClass = "restricted"
    status: Status
    steps: list[StepRecord] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)


# Groups of hypothesis rules, in the order spec 6.4 asks for: system and scorer first,
# data last. `code_rank` sorts by this order first.
Group = Literal["scorer", "runtime", "train", "data", "coverage"]


class ClusterRef(Record):
    """A failure cluster of the `failure_clusters` table, by its key."""

    cluster_id: str = Field(min_length=1, description='"<run>/<step>/<label>/l<level>"')
    run: str = Field(min_length=1)
    step: str = Field(min_length=1)
    label: str = Field(min_length=1)
    level: int
    size: int = Field(ge=0)


class CheckRef(Record):
    """A check of the catalog that tells this hypothesis from another one of its cluster."""

    check_id: str = Field(min_length=1)
    separates: list[list[str]] = Field(default_factory=list)
    cost_key: str = Field(min_length=1)
    cost_rank: int


class HypothesisRecord(Record):
    """One line of `hypotheses.jsonl` (step B3): a rule that matched a cluster.

    It carries no number of its own, only ids of facts in `facts.jsonl`.
    """

    hypothesis_id: str = Field(pattern=r"^H[1-9][0-9]*$")
    cluster: ClusterRef
    rule_id: str = Field(min_length=1)
    group: Group
    diagnosis: Diagnosis
    note: str = Field(min_length=1)
    support: list[str] = Field(default_factory=list)
    contra: list[str] = Field(default_factory=list)
    interventions: list[InterventionKind] = Field(min_length=1)
    code_rank: int = Field(ge=1)
    blocked_data_spend: bool
    checks: list[CheckRef] = Field(default_factory=list)

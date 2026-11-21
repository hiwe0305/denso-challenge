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


class StoreReadRecord(Record):
    """What a store-reading tool read: the table, the rows that parsed, a sha256 over them."""

    table: str = Field(min_length=1)
    rows: int = Field(ge=0)
    sha256: str = Field(pattern=SHA256)
    unreadable: int = Field(default=0, ge=0)


class ToolCallRecord(Record):
    """One line of `tool_calls.jsonl`: a call of the plan, what it read and what it made."""

    call_id: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    version: int = Field(ge=1)
    params: dict[str, Any] = Field(default_factory=dict)
    input_sha256: list[str] = Field(
        default_factory=list,
        description="Accepted pack entries read, then the sha256 of each store table read.")
    store_reads: list[StoreReadRecord] = Field(
        default_factory=list,
        description="Set only for tools that read the site store; empty means pack only.")
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
    plan_path: str = Field(default="", description="The measure plan this run used.")
    plan_sha256: str = ""
    status: Status
    steps: list[StepRecord] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)
    agent_version: str = ""
    agent_hash: str = ""


class ModelRequest(Record):
    """What a role asks the model gateway for one unit (a source or a cluster)."""

    unit: str = Field(min_length=1)
    attempt: Literal[1, 2] = 1
    system: str = Field(min_length=1)
    user: str = Field(min_length=1)
    reply_schema: dict[str, Any] | None = None
    max_tokens: int = Field(ge=1)


CallStatus = Literal["ok", "cut", "failed", "budget_exhausted"]


class ModelCallRecord(Record):
    """One line of `model_calls.jsonl` (step B4): one request through the gateway.

    The only file of a run that holds durations; no key or header is ever in it.
    `tries` counts provider calls (0 when the budget stopped the request).
    """

    call_id: str = Field(pattern=r"^M[1-9][0-9]*$")
    role: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    attempt: Literal[1, 2]
    request_sha256: str = Field(pattern=SHA256)
    prompt_sha256: str = Field(pattern=SHA256)
    data_class: DataClass
    profile: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    hosted: bool
    model: str
    revision: str
    host: str
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    tokens_estimated: bool = False
    usd: float = Field(ge=0)
    seconds: float = Field(ge=0)
    tries: int = Field(ge=0)
    status: CallStatus
    reply: str = ""
    error: str = ""


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


class HypothesisView(Record):
    """A hypothesis as the page shows it: the code floor now, a model's choice later."""

    hypothesis_id: str
    rule_id: str
    title: str
    group: Group
    diagnosis: Diagnosis
    note: str
    rank: int
    source: Literal["model", "code"]
    support: list[str] = Field(default_factory=list)
    contra: list[str] = Field(default_factory=list)
    explanation: str = ""


class ClusterView(Record):
    cluster: ClusterRef
    hypotheses: list[HypothesisView]
    blocked_data_spend: bool
    check: CheckRef | None = None
    intervention: str | None = None
    intervention_source: Literal["model", "code"] = "code"
    costed: bool = False


class NotJudged(Record):
    what: str
    reason: str
    fact_id: str = ""


class Assembly(Record):
    """`assembly.json` (step B6): everything the page shows, with no new number."""

    run_id: str
    pack_id: str
    task_id: str
    data_class: DataClass
    status: Status
    agent_version: str
    agent_hash: str
    model: str = ""
    clusters: list[ClusterView]
    headline: ClusterView | None = None
    not_judged: list[NotJudged] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

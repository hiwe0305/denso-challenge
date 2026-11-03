"""Pydantic v2 models for the 12 L0-lite catalog entities (03 §4.3)."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from flywheel.contracts.artifacts import (
    Episode as ArtifactEpisode,
)
from flywheel.contracts.artifacts import (
    QACheck,
)
from flywheel.contracts.artifacts import (
    QAReport as ArtifactQAReport,
)
from flywheel.contracts.base import (
    BaseRecord,
    content_id,
    event_id,
    is_valid_event_id,
)
from pydantic import Field, model_validator
from typing_extensions import Self


class ContentEntity(BaseRecord):
    """Base class for immutable, content-addressed entities."""

    ID_PREFIX: ClassVar[str] = "obj"
    id: str = ""

    @model_validator(mode="after")
    def _compute_and_verify_id(self) -> Self:
        expected_id = content_id(self.ID_PREFIX, self)
        if self.id:
            if self.id != expected_id:
                raise ValueError(
                    f"Content ID mismatch: provided '{self.id}', "
                    f"expected '{expected_id}' based on content"
                )
        else:
            object.__setattr__(self, "id", expected_id)
        return self


class EventEntity(BaseRecord):
    """Base class for append-only, event-addressed entities with ULID."""

    ID_PREFIX: ClassVar[str] = "evt"
    id: str = ""

    @model_validator(mode="after")
    def _populate_or_validate_id(self) -> Self:
        if not self.id:
            object.__setattr__(self, "id", event_id(self.ID_PREFIX))
        else:
            if not is_valid_event_id(self.id, self.ID_PREFIX):
                raise ValueError(f"Invalid event ID '{self.id}' for prefix '{self.ID_PREFIX}'")
        return self


# 1. Source (content)
class Source(ContentEntity):
    """External or ingested raw data source with lineage and provenance."""

    ID_PREFIX: ClassVar[str] = "src"

    kind: Literal["dataset", "checkpoint", "video_upload", "code"] = "dataset"
    uri: str
    repo: str | None = None
    revision: str | None = None
    path: str | None = None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license: str = "unknown"
    data_class: Literal["public", "internal", "restricted"] = "restricted"
    clean_for_main_task: Literal["true", "false", "unknown"] = "unknown"
    provenance: dict[str, Any] = Field(default_factory=dict)
    downloaded_at: str


# 2. Condition (content)
class Condition(ContentEntity):
    """Environment initial condition with seed and typed vector values."""

    ID_PREFIX: ClassVar[str] = "cond"

    condition_seed: int
    level: int = 0
    values: dict[str, Any] = Field(default_factory=dict)
    vector: list[float] = Field(default_factory=list)
    layout_hash: str
    split: Literal["train", "dev"] = "train"
    origin: Literal["generated", "extracted_from_demo"] = "generated"
    set_id: str | None = None
    quarantined: bool = False
    quarantine_reason: str | None = None
    layout_uri: str | None = None


# 3. Episode (event)
class Episode(ArtifactEpisode):
    """Demonstration or rollout episode bundle (reused from artifacts.py)."""

    episode_id: str = Field(default="")
    site_id: str = "local"
    task_id: str = "default"
    schema_version: str = "1.0.0"
    deid_status: Literal["raw", "blurred", "verified"] = "raw"

    @model_validator(mode="before")
    @classmethod
    def _populate_id_before(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            eid = data.get("episode_id") or data.get("id")
            if not eid:
                eid = event_id("ep")
            else:
                eid = str(eid).strip()
                if not eid:
                    raise ValueError("episode_id cannot be empty")
            data["episode_id"] = str(eid)
        return data

    @property
    def id(self) -> str:
        return self.episode_id


# 4. QAReport (event)
class QAReport(ArtifactQAReport):
    """Episode QA verification report (reused from artifacts.py)."""

    report_id: str = Field(default="")
    site_id: str = "local"
    task_id: str = "default"
    embodiment_id: str = "default"
    schema_version: str = "1.0.0"
    meta: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _populate_id_before(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            rid = data.get("report_id") or data.get("id")
            if not rid:
                rid = event_id("qa")
            else:
                rid = str(rid).strip()
                if not rid:
                    raise ValueError("report_id cannot be empty")
            data["report_id"] = str(rid)
        return data

    @property
    def id(self) -> str:
        return self.report_id


# 5. Release (content)
class Release(ContentEntity):
    """Frozen or draft dataset release manifest."""

    ID_PREFIX: ClassVar[str] = "rel"

    name: str
    kind: Literal["robot", "egocentric"] = "robot"
    parent_release_id: str | None = None
    split_plan_cfg_id: str | None = None
    status: Literal["draft", "frozen"] = "draft"
    manifest_sha256: str | None = None
    holdout_guard_passed: bool | None = None
    combined_license: str | None = None
    counts: dict[str, Any] = Field(default_factory=dict)
    items: list[dict[str, Any]] = Field(default_factory=list)
    frozen_at: str | None = None


# 6. Checkpoint (content)
class Checkpoint(ContentEntity):
    """Model checkpoint reference with origin and weights hash."""

    ID_PREFIX: ClassVar[str] = "ckpt"

    origin: Literal["upstream", "trained"] = "trained"
    method: Literal["psi0", "act", "dp"] = "psi0"
    branch: str | None = None
    base_source_id: str | None = None
    parent_checkpoint_id: str | None = None
    release_id: str | None = None
    seed: int | None = None
    step: int | None = None
    weights_sha256: str
    uri: str
    is_final: bool = False


# 7. RunPlan (content)
class RunPlan(ContentEntity):
    """Experimental RunPlan specification."""

    ID_PREFIX: ClassVar[str] = "rp"

    name: str
    purpose: Literal[
        "g0_repro",
        "e1",
        "branch_train",
        "aa_test",
        "round",
        "holdout",
        "hd",
    ] = "round"
    branch: str = "main"
    method: Literal["psi0", "act", "dp"] = "psi0"
    status: Literal["draft", "frozen"] = "draft"
    lock_path: str | None = None
    lock_sha256: str | None = None
    frozen_at: str | None = None
    body: dict[str, Any] = Field(default_factory=dict)


# 8. Score (content)
class Score(ContentEntity):
    """Episode task evaluation score."""

    ID_PREFIX: ClassVar[str] = "sc"

    episode_id: str
    # No default: a score is only reproducible against the task it was scored
    # on, so the caller names it instead of inheriting "default" (PO, #62).
    task_id: str = Field(min_length=1)
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    # sha256 of the trace file that was scored; with scorer_version it is what
    # tells a re-score of the same episode apart (03 §4.3, #59 item 7).
    trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scorer_version: str = "1.0.0"
    success: bool | None = None
    step_status: list[str] = Field(default_factory=list)
    first_failed_step: int | None = None
    failure_kind: str | None = None
    failure_class: Literal["approach", "grasp", "carry", "place", "balance"] | None = None
    level: int | None = None
    balance_violated: bool = False


# 9. Cluster (content)
class Cluster(ContentEntity):
    """Failure cluster grouping rollout failures."""

    ID_PREFIX: ClassVar[str] = "clu"

    run_plan_id: str = "default"
    first_failed_step: int
    failure_kind: str
    level: int = 0
    failure_class: Literal["approach", "grasp", "carry", "place", "balance"] | None = None
    parent_cluster_id: str | None = None
    representative_seed: int | None = None
    member_episode_ids: list[str] = Field(default_factory=list)
    card_uri: str | None = None


# 10. FixRateEvent (event)
class FixRateEvent(EventEntity):
    """Measured intervention fix rate event."""

    ID_PREFIX: ClassVar[str] = "fre"

    round_id: str | None = None
    cluster_id: str | None = None
    intervention_id: str = "default"
    intervention_type: str = "sim_s1"
    diagnosis: str | None = None
    failure_kind: str = "L-UNKNOWN"
    failure_class: Literal["approach", "grasp", "carry", "place", "balance"] | None = None
    task_family: str = "pick_place"
    n_conditions: int = 1
    p_parent: float = 0.0
    p_candidate: float = 0.0
    fixed: int = 0


# 11. LedgerEntry (event)
class LedgerEntry(EventEntity):
    """Cost ledger entry recording estimated or measured resource consumption."""

    ID_PREFIX: ClassVar[str] = "led"

    activity: Literal[
        "data_download",
        "teleop_session",
        "data_generation",
        "pipeline",
        "qa",
        "replay",
        "export",
        "train",
        "probe",
        "eval",
        "diagnosis",
        "agent_qa",
        "holdout",
        "storage",
        "hd",
        "review",
        "other",
    ]
    resource_type: str
    quantity: float
    unit: str
    pricebook_id: str = "default"
    usd_amount: float
    human_hours: float = 0.0
    measure_kind: Literal["estimated", "measured"]
    estimate_entry_id: str | None = None
    branch: str | None = None
    # Every job runs under a RunPlan, so every row names one (PO decision D4).
    # job_id may be left out only on an estimate made for the whole run plan.
    run_plan_id: str = Field(min_length=1)
    cluster_id: str | None = None
    intervention_id: str | None = None
    job_id: str | None = Field(default=None, min_length=1)
    person_code: str | None = None
    reverses_entry_id: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _validate_ledger_entry(self) -> Self:
        if self.measure_kind == "estimated":
            if self.estimate_entry_id is not None:
                raise ValueError("estimated entry cannot have an estimate_entry_id")
        elif self.measure_kind == "measured":
            if self.job_id is None:
                raise ValueError("measured entry must have a job_id: it measures one job")
            if not self.estimate_entry_id:
                raise ValueError("measured entry must have an estimate_entry_id")
            if not is_valid_event_id(self.estimate_entry_id, "led"):
                raise ValueError(
                    f"Invalid estimate_entry_id '{self.estimate_entry_id}': "
                    f"must be a valid 'led_' event ID"
                )

        if self.reverses_entry_id is not None and not is_valid_event_id(
            self.reverses_entry_id, "led"
        ):
            raise ValueError(
                f"Invalid reverses_entry_id '{self.reverses_entry_id}': "
                f"must be a valid 'led_' event ID"
            )

        if self.reverses_entry_id is None:
            if self.quantity < 0:
                raise ValueError(
                    f"quantity cannot be negative ({self.quantity}) "
                    "unless reverses_entry_id is set"
                )
            if self.usd_amount < 0:
                raise ValueError(
                    f"usd_amount cannot be negative ({self.usd_amount}) "
                    "unless reverses_entry_id is set"
                )
        return self


# 12. Decision (event)
class Decision(EventEntity):
    """Logged lifecycle gate, review, or milestone decision."""

    ID_PREFIX: ClassVar[str] = "dec"

    kind: Literal[
        "plan_review",
        "dev_gate",
        "aa_test",
        "holdout",
        "milestone",
        "repair_ticket",
    ]
    subject_kind: str
    subject_id: str
    verdict: Literal[
        "approved", "overridden", "rejected", "pass", "fail", "open", "closed", "recorded"
    ] = "pass"
    metrics: dict[str, Any] = Field(default_factory=dict)
    criteria: dict[str, Any] = Field(default_factory=dict)
    signed_by: str
    reason: str
    supersedes_decision_id: str | None = None


__all__ = [
    "Checkpoint",
    "Cluster",
    "Condition",
    "ContentEntity",
    "Decision",
    "Episode",
    "EventEntity",
    "FixRateEvent",
    "LedgerEntry",
    "QACheck",
    "QAReport",
    "Release",
    "RunPlan",
    "Score",
    "Source",
]

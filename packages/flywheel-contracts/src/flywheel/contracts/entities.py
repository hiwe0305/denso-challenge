"""Pydantic v2 models for the 12 L0-lite catalog entities (03 §4.3)."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import Field, model_validator

from flywheel.contracts.base import (
    BaseRecord,
    content_id,
    event_id,
    is_valid_content_id,
    is_valid_event_id,
)


class ContentEntity(BaseRecord):
    """Base class for immutable, content-addressed entities."""

    ID_PREFIX: ClassVar[str] = "obj"
    id: str = ""

    @model_validator(mode="before")
    @classmethod
    def _populate_or_validate_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            existing_id = data.get("id")
            if not existing_id:
                data = dict(data)
                data["id"] = content_id(cls.ID_PREFIX, data)
            else:
                if not is_valid_content_id(str(existing_id), cls.ID_PREFIX):
                    raise ValueError(f"Invalid content ID '{existing_id}' for prefix '{cls.ID_PREFIX}'")
        return data


class EventEntity(BaseRecord):
    """Base class for append-only, event-addressed entities with ULID."""

    ID_PREFIX: ClassVar[str] = "evt"
    id: str = ""

    @model_validator(mode="before")
    @classmethod
    def _populate_or_validate_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            existing_id = data.get("id")
            if not existing_id:
                data = dict(data)
                data["id"] = event_id(cls.ID_PREFIX)
            else:
                if not is_valid_event_id(str(existing_id), cls.ID_PREFIX):
                    raise ValueError(f"Invalid event ID '{existing_id}' for prefix '{cls.ID_PREFIX}'")
        return data


# 1. Source (content)
class Source(ContentEntity):
    """External or ingested raw data source with lineage and provenance."""

    ID_PREFIX: ClassVar[str] = "src"

    kind: Literal["dataset", "checkpoint", "video_upload", "code"] = "dataset"
    uri: str
    repo: str | None = None
    revision: str | None = None
    path: str | None = None
    sha256: str
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
    split: Literal["train", "dev", "holdout"] = "train"
    origin: Literal["generated", "extracted_from_demo"] = "generated"
    set_id: str | None = None
    quarantined: bool = False
    quarantine_reason: str | None = None
    layout_uri: str | None = None


# 3. Episode (event)
class Episode(EventEntity):
    """Demonstration or rollout episode bundle."""

    ID_PREFIX: ClassVar[str] = "ep"

    kind: Literal[
        "teleop_demo",
        "teleop_correction",
        "recovery",
        "sim_rollout",
        "variant",
        "eval_rollout",
        "diag_rollout",
        "ego_demo",
    ]
    operator_kind: Literal["human", "machine"]
    is_root: bool = False
    root_id: str | None = None
    parent_id: str | None = None
    condition_id: str | None = None
    source_id: str | None = None
    intervention_id: str | None = None
    run_plan_id: str = "default"
    bundle_uri: str
    license: str = "unknown"
    data_class: Literal["public", "internal", "restricted"] = "restricted"
    split: Literal["train", "dev", "holdout"] = "train"
    source_kind: Literal["teleop", "synthetic", "egocentric"] | None = None
    action_quality: Literal["measured", "planned", "retargeted", "pseudo", "none"] = "measured"
    deid_status: Literal["raw", "blurred", "verified"] = "verified"

    # Trace attributes
    checkpoint_id: str | None = None
    rollout_seed: int | None = None
    sim_success: bool | None = None
    infra_status: str | None = None
    camera_params_hash: str | None = None

    # Video / sensory info
    n_frames: int | None = None
    fps: float | None = None
    renderer: Literal["mujoco", "isaac"] | None = None
    injected_defect: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_root_invariant(self) -> "Episode":
        if self.is_root:
            if self.operator_kind != "human" or self.kind not in {"teleop_demo", "teleop_correction", "recovery"}:
                raise ValueError("is_root=True requires human operator and demonstration/correction/recovery kind")
        return self


# 4. QAReport (event)
class QAReport(EventEntity):
    """Episode QA verification report."""

    ID_PREFIX: ClassVar[str] = "qa"

    episode_id: str
    threshold_version: str = "v1"
    decision: Literal["pass", "flag", "quarantine", "reject"]
    reasons: list[str] = Field(default_factory=list)
    checks: list[dict[str, Any]] | dict[str, Any] = Field(default_factory=dict)
    reviewed_by: str | None = None


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
        "he",
        "stage1",
        "tray_he",
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
    measure_kind: Literal["estimated", "measured"] = "measured"
    branch: str | None = None
    run_plan_id: str | None = None
    cluster_id: str | None = None
    intervention_id: str | None = None
    job_id: str | None = None
    person_code: str | None = None
    reverses_entry_id: str | None = None
    note: str | None = None


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
        "stage_review",
        "agent_report_review",
        "v3_controller",
        "scope_reduction",
    ]
    subject_kind: str
    subject_id: str
    verdict: Literal["approved", "overridden", "rejected", "pass", "fail", "open", "closed", "recorded"] = "pass"
    metrics: dict[str, Any] = Field(default_factory=dict)
    criteria: dict[str, Any] = Field(default_factory=dict)
    signed_by: str
    reason: str
    supersedes_decision_id: str | None = None

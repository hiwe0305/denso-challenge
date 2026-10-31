"""Artifact contracts shared between data, evaluation and loop packages."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class InjectedDefect(Artifact):
    code: str = Field(min_length=1)
    parameters: dict[str, bool | float | int | str] = Field(default_factory=dict)


class EpisodeMetadata(Artifact):
    source_detail: (
        Literal["psi_data", "teleop_keyboard", "teleop_pico", "planner_wbc", "planner_amo"] | None
    ) = None
    renderer: Literal["mujoco", "isaac"] | None = None
    synthetic_tier: Literal["S1", "S2", "S3", "S4"] | None = None
    injected_defect: InjectedDefect | None = None


class Episode(Artifact):
    episode_id: str = Field(min_length=1)
    kind: Literal[
        "teleop_demo",
        "teleop_correction",
        "recovery",
        "sim_rollout",
        "variant",
        "eval_rollout",
        "diag_rollout",
    ]
    operator_kind: Literal["human", "machine"]
    is_root: bool
    condition_id: str = Field(min_length=1)
    root_id: str | None = None
    parent_id: str | None = None
    source_id: str | None = None
    intervention_id: str | None = None
    checkpoint_id: str | None = None
    rollout_seed: int | None = None
    sim_success: bool | None = None
    infra_status: str | None = None
    camera_params_hash: str | None = None
    run_plan_id: str = Field(min_length=1)
    bundle_uri: str = Field(min_length=1)
    license: str = Field(min_length=1)
    data_class: Literal["public", "internal", "restricted"]
    split: str = Field(min_length=1)
    source_kind: Literal["teleop", "synthetic", "egocentric"]
    action_quality: Literal["measured", "planned", "retargeted", "pseudo", "none"]
    deid_status: Literal["raw", "blurred", "verified"]
    embodiment_id: str = Field(min_length=1)
    meta: EpisodeMetadata

    @model_validator(mode="after")
    def validate_root(self) -> "Episode":
        if self.is_root and (
            self.operator_kind != "human"
            or self.kind not in {"teleop_demo", "teleop_correction", "recovery"}
        ):
            raise ValueError("root episodes require a human demonstration, correction or recovery")
        return self


class ActionDimension(Artifact):
    name: str = Field(min_length=1)
    group: str = Field(min_length=1)
    masked: bool
    limit_low: float | None = None
    limit_high: float | None = None

    @model_validator(mode="after")
    def validate_limits(self) -> "ActionDimension":
        if (self.limit_low is None) != (self.limit_high is None):
            raise ValueError("both action limits must be specified together")
        if (
            self.limit_low is not None
            and self.limit_high is not None
            and self.limit_low > self.limit_high
        ):
            raise ValueError("limit_low must not exceed limit_high")
        return self


class ActionLayout(Artifact):
    dimensions: list[ActionDimension] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_names(self) -> "ActionLayout":
        names = [dimension.name for dimension in self.dimensions]
        if len(names) != len(set(names)):
            raise ValueError("action dimension names must be unique")
        return self


class ReplayIssue(Artifact):
    code: str = Field(min_length=1)
    frames: list[int] = Field(default_factory=list)
    detail: str


class ReplayReport(Artifact):
    episode_id: str = Field(min_length=1)
    mode: Literal["kinematic", "dynamic"]
    issues: list[ReplayIssue]
    error_by_group: dict[str, float] = Field(default_factory=dict)
    hand_event_offset_steps: int | None = None
    sim_success: bool | None = None


class DatasetReport(Artifact):
    dataset_id: str = Field(min_length=1)
    episode_count: int = Field(ge=0)
    counts_by_source: dict[str, int] = Field(default_factory=dict)
    failed_checks_by_source: dict[str, dict[str, int]] = Field(default_factory=dict)


class Defect(Artifact):
    target_ref: str = Field(min_length=1)
    code: str = Field(min_length=1)
    parameters: dict[str, bool | float | int | str] = Field(default_factory=dict)


class DefectManifest(Artifact):
    dataset_id: str = Field(min_length=1)
    seed: int = Field(ge=0)
    defects: list[Defect]


class RTCInferenceRecord(Artifact):
    job_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    observation_sent_s: float = Field(ge=0)
    chunk_received_s: float = Field(ge=0)
    delay_steps: int = Field(ge=0)
    buffer_level: int = Field(ge=0)
    boundary_jump: float = Field(ge=0)

    @model_validator(mode="after")
    def received_after_sent(self) -> "RTCInferenceRecord":
        if self.chunk_received_s < self.observation_sent_s:
            raise ValueError("chunk_received_s must not precede observation_sent_s")
        return self


class ProbeP1(Artifact):
    probe: Literal["P1"] = "P1"
    checkpoint_id: str = Field(min_length=1)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    accuracy_by_question_type: dict[str, float]


class ProbeP2(Artifact):
    probe: Literal["P2"] = "P2"
    checkpoint_id: str = Field(min_length=1)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    token_loss: float = Field(ge=0)


class ProbeP3(Artifact):
    probe: Literal["P3"] = "P3"
    checkpoint_id: str = Field(min_length=1)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    error_by_group: dict[str, float]
    error_by_chunk_pos: list[float]
    hand_event_offset_steps: float
    out_of_limit_dims: list[int]


class ProbeP4(Artifact):
    probe: Literal["P4"] = "P4"
    checkpoint_id: str = Field(min_length=1)
    parent_checkpoint_id: str = Field(min_length=1)
    p1: ProbeP1
    p3: ProbeP3

    @model_validator(mode="after")
    def matching_checkpoint(self) -> "ProbeP4":
        if (
            self.p1.checkpoint_id != self.checkpoint_id
            or self.p3.checkpoint_id != self.checkpoint_id
        ):
            raise ValueError("P4 component checkpoints must match checkpoint_id")
        return self


class QACheck(Artifact):
    name: str = Field(min_length=1)
    value: float
    threshold: float
    passed: bool


class QAReport(Artifact):
    report_id: str = Field(min_length=1)
    episode_id: str = Field(min_length=1)
    threshold_version: str = Field(min_length=1)
    decision: Literal["pass", "flag", "quarantine", "reject"]
    reasons: list[str]
    checks: list[QACheck]

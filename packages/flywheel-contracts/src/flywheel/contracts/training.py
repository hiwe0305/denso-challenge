"""Proposed training telemetry contracts for DA-08 (issue #5).

Non-finite loss is encoded as a string so JSONL stays valid JSON. A line is
one measurement; train and validation measurements share the same file.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


NonFinite = Literal["NaN", "Infinity", "-Infinity"]
FindingCode = Literal["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "O1", "O2", "O3", "O4"]


class TrainingMetric(Contract):
    run_plan_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    checkpoint_id: str = Field(min_length=1)
    release_id: str = Field(min_length=1)
    attempt: int = Field(ge=0)
    step: int = Field(ge=0)
    epoch: int = Field(ge=0)
    split: Literal["train", "val"]
    loss: float | NonFinite
    lr: float = Field(ge=0)
    vlm_frozen: bool
    loss_by_group: dict[str, float] = Field(default_factory=dict)
    loss_by_chunk_pos: list[float] = Field(default_factory=list)
    grad_norm_vlm: float | None = Field(default=None, ge=0)
    grad_norm_action: float | None = Field(default=None, ge=0)
    pred_var_by_dim: list[float] = Field(default_factory=list)
    pred_std: list[float] = Field(default_factory=list)
    target_std: list[float] = Field(default_factory=list)
    hand_open_hist: list[float] = Field(default_factory=list)
    vram_gb: float | None = Field(default=None, ge=0)
    throughput: float | None = Field(default=None, ge=0)
    wall_time_s: float = Field(ge=0)


class DiagnosisFinding(Contract):
    code: FindingCode
    start_step: int = Field(ge=0)
    group: str | None = None
    dim: int | None = Field(default=None, ge=0)
    value: float | NonFinite
    threshold: float | None = None
    stop_job: bool = False

    @model_validator(mode="after")
    def validate_stop(self) -> "DiagnosisFinding":
        if self.stop_job and self.code != "T1":
            raise ValueError("stop_job is reserved for T1")
        return self


class TrainDiagnosis(Contract):
    checkpoint_id: str = Field(min_length=1)
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    findings: list[DiagnosisFinding]

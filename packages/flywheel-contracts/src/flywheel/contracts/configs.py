"""Configuration YAML models with content hashing (03 §4.1, §4.3)."""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from flywheel.contracts.artifacts import ActionLayout
from flywheel.contracts.base import canonical_json
from pydantic import BaseModel, ConfigDict, Field


class ConfigArtifact(BaseModel):
    """Base class for configuration YAML artifacts outside the catalog."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
    )

    def cfg_hash(self) -> str:
        """Return 64-character SHA-256 hash of canonical JSON representation."""
        canon = canonical_json(self.model_dump(mode="json"))
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    def cfg_id(self) -> str:
        """Return config ID with cfg_ prefix followed by 16 hex characters."""
        return f"cfg_{self.cfg_hash()[:16]}"


class EmbodimentConfig(ConfigArtifact):
    """Configuration for an embodiment / robot embodiment."""

    name: str
    version: str = "1.0.0"
    domain: Literal["sim", "real"] = "sim"
    controller: str = "sonic_dwbc"
    camera_ref_hash: str | None = None
    action_layout: ActionLayout | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ConditionFieldSpec(ConfigArtifact):
    """Specification of one field in a ConditionSchema."""

    name: str
    type: str = "float"
    description: str = ""
    bounds: list[float] | None = None


class ConditionSchemaConfig(ConfigArtifact):
    """Schema for condition vector / map."""

    version: str = "1.0.0"
    fields: list[ConditionFieldSpec] = Field(default_factory=list)


class StageSpecConfig(ConfigArtifact):
    """Specification of one task step / stage."""

    stage_no: int
    name: str
    failure_class: Literal["approach", "grasp", "carry", "place", "balance"] | None = None


class FailureKindSpecConfig(ConfigArtifact):
    """Specification of a failure code and its common failure class."""

    code: str
    description: str
    failure_class: Literal["approach", "grasp", "carry", "place", "balance"] | None = None


class TaskConfig(ConfigArtifact):
    """Task configuration including ConditionSchema and failure classes."""

    task_id: str
    version: str = "1.0.0"
    family: str = "pick_place"
    n_steps: int = 6
    condition_schema: ConditionSchemaConfig = Field(default_factory=ConditionSchemaConfig)
    stages: list[StageSpecConfig] = Field(default_factory=list)
    failure_kinds: list[FailureKindSpecConfig] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class SeedRange(ConfigArtifact):
    """Half-open seed range [start, stop)."""

    start: int
    stop: int


class SplitPlanConfig(ConfigArtifact):
    """Configuration for dataset split rules, seed ranges, and duplicate guards."""

    name: str = "default"
    version: int | str = 1
    seed_ranges: dict[str, SeedRange | list[int]] = Field(default_factory=dict)
    author_ranges_to_avoid: list[list[int]] = Field(default_factory=list)
    near_duplicate_threshold_d_dup: float = 0.05
    meta: dict[str, Any] = Field(default_factory=dict)


class PriceRateConfig(ConfigArtifact):
    """Rate specification for a single resource type."""

    resource_type: str
    unit: str
    usd_per_unit: float
    human_hours_per_unit: float = 0.0
    is_assumption: bool = True
    note: str = ""


class PriceBookConfig(ConfigArtifact):
    """Pricebook configuration containing resource cost rates."""

    name: str
    version: str = "1.0.0"
    rates: list[PriceRateConfig] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

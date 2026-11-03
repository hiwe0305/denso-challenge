"""Declarative evaluation configuration loader (DA-23, AC 4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


def _default_timing_by_purpose() -> dict[str, Literal["sync", "async"]]:
    return {
        "g0_repro": "sync",
        "he": "sync",
        "branch_train": "async",
        "round": "async",
        "holdout": "async",
    }


class EvalConfig(BaseModel):
    """Configuration mapping RunPlan purposes and default timing modes."""

    model_config = ConfigDict(extra="forbid")

    default_timing: Literal["sync", "async"] = "async"
    timing_by_purpose: dict[str, Literal["sync", "async"]] = Field(
        default_factory=_default_timing_by_purpose
    )
    control_hz: float = 50.0
    chunk_size: int = 16
    latency_profiles: dict[str, Any] = Field(default_factory=dict)
    # Async: control steps an RTC log may leave the robot without an action before the
    # rollout counts as failed.
    max_starved_steps: int = Field(default=0, ge=0)

    def timing_for_purpose(self, purpose: str) -> Literal["sync", "async"]:
        """Return evaluation timing mode for the specified RunPlan purpose."""
        return self.timing_by_purpose.get(purpose, self.default_timing)


def load_eval_config(config_path: str | Path | None = None) -> EvalConfig:
    """Load EvalConfig from configs/loop/eval.yaml or default."""
    if config_path is None:
        config_path = Path("configs/loop/eval.yaml")
    else:
        config_path = Path(config_path)

    if not config_path.is_file():
        return EvalConfig()

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return EvalConfig()
    return EvalConfig.model_validate(raw)

"""A Psi0 training stage as data: `configs/models/psi0-stage{1,2,3}.yaml`.

A recipe holds the author's command-line args for one stage, keyed by flag name so
a RunPlan override replaces a value instead of appending a second `--flag` that tyro
would have to resolve. `argv` renders the arguments `scripts/train.py` takes after
its own name: the config module, any tyro subcommand, the per-job args, the rest.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

# `true` is a bare flag (`--model.rtc`); a list is `--key v1 v2`; anything else `--key=v`.
ArgValue = bool | int | float | str | list[int | float | str]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ParentCheckpoint(_Frozen):
    """The two halves Psi0 loads: a VLM and, from stage 3 on, an action header."""

    model_name_or_path: str
    pretrained_action_header_path: str | None = None


class RecipeEstimate(_Frozen):
    seconds_per_step: float = Field(gt=0)  # an assumption until a run is measured


class Psi0Recipe(_Frozen):
    stage: Literal[1, 2, 3]
    config_module: str
    trainer_module: str
    source: str
    job_args: dict[str, ArgValue]
    positional: list[str] = Field(default_factory=list)
    args: dict[str, ArgValue]
    parents: dict[str, ParentCheckpoint]
    estimate: RecipeEstimate

    @classmethod
    def load(cls, path: Path) -> Psi0Recipe:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def with_overrides(self, overrides: Mapping[str, ArgValue]) -> Psi0Recipe:
        """The same recipe with some `args` replaced, e.g. a short smoke run's step count."""
        clash = sorted(set(overrides) & set(self.job_args))
        if clash:
            raise ValueError(f"{clash} are set per job by Psi0Trainer, not by overrides")
        return self.model_copy(update={"args": {**self.args, **overrides}})

    @property
    def vlm_frozen(self) -> bool:
        return self.args.get("model.no-tune-vlm") is True

    @property
    def rtc_prefix(self) -> int:
        """Leading chunk positions RTC can leave out of the train loss (`max-delay`)."""
        return self.int_arg("model.max-delay", 0) if self.args.get("model.rtc") is True else 0

    def int_arg(self, key: str, default: int) -> int:
        value = self.args.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"{key} must be a number, got {value!r}")
        return int(float(value))

    def argv(self, fill: Mapping[str, str]) -> list[str]:
        """`scripts/train.py`'s arguments, with `{placeholders}` of `job_args` filled."""
        job = {
            key: value.format_map(fill) if isinstance(value, str) else value
            for key, value in self.job_args.items()
        }
        return [
            self.config_module,
            *self.positional,
            *_render(job),
            *_render(self.args),
        ]


def _render(args: Mapping[str, ArgValue]) -> list[str]:
    rendered: list[str] = []
    for key, value in args.items():
        if value is True:
            rendered.append(f"--{key}")
        elif value is False:
            raise ValueError(f"--{key}: false has no flag form; use the --no- flag instead")
        elif isinstance(value, list):
            rendered += [f"--{key}", *(str(item) for item in value)]
        else:
            rendered.append(f"--{key}={value}")
    return rendered

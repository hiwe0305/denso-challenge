"""Outcome of one eval rollout, the same for every task (DA-43 K1, design 19/11/2026 7.2).

It replaces the adapter-private `outcomes.jsonl` row of the tray task: the adapter
writes one `RolloutOutcome` per rollout, and lanes read it without knowing the task.

* **Identity.** `run` names the eval run, `seed` and `level` the condition, `repeat`
  which rollout of that condition it is (`eval_batch --repeats`, DA-42). The data
  class is not here: the pack that hands the outcome to a lane declares it.
* **Verdicts.** `verdict` is the task's own scorer; `other_verdicts` are other scorer
  versions run on the same states (DA-42's shadow scorer version 1), so two versions
  compare on one rollout. Each names its steps, so the outcome does not depend on a
  step list kept elsewhere.
* **Measures.** `final` holds the state at the end of the episode, `extrema` the
  smallest or largest value of a quantity over the episode, and a verdict's
  `at_failure` the state in the cycle the failure label was set. Names are not a
  closed list: the task config declares which names a task provides. A name is
  lower_snake; a number or a list of numbers must end in a unit suffix (`_m`, `_deg`,
  `_rad`, `_s`) or a unitless one (`_quat`, `_frac`), so a reader never guesses units.
"""

from __future__ import annotations

import re
from typing import Annotated

from flywheel.contracts.artifacts import Artifact
from pydantic import Field, StrictBool, model_validator
from typing_extensions import Self

MeasureValue = StrictBool | float | str | list[float] | None
MEASURE_NAME = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
STEP_NAME = MEASURE_NAME
# A number carries its unit in its name; `_quat` is (w, x, y, z), `_frac` is in [0, 1].
NUMERIC_SUFFIXES = ("_m", "_deg", "_rad", "_s", "_quat", "_frac")

Measures = dict[Annotated[str, Field(pattern=MEASURE_NAME)], MeasureValue]


def _check_measures(where: str, measures: dict[str, MeasureValue]) -> None:
    for name, value in measures.items():
        numeric = isinstance(value, list) or (
            isinstance(value, float) and not isinstance(value, bool)
        )
        if numeric and not name.endswith(NUMERIC_SUFFIXES):
            raise ValueError(f"{where}.{name}: a numeric measure ends in one of {NUMERIC_SUFFIXES}")
        if (
            name.endswith("_quat")
            and value is not None
            and (not isinstance(value, list) or len(value) != 4)
        ):
            raise ValueError(f"{where}.{name}: a quaternion is a list of four numbers")
        if name.endswith("_frac") and isinstance(value, float) and not 0.0 <= value <= 1.0:
            raise ValueError(f"{where}.{name}: a fraction lies in [0, 1]")


def relative_path(ref: str) -> bool:
    """True for a relative POSIX or Windows path without `..` and outside `vault/`."""
    parts = ref.replace("\\", "/").split("/")
    return (
        bool(ref)
        and not ref.startswith(("/", "\\"))
        and not re.match(r"^[A-Za-z]:", ref)
        and ".." not in parts
        and "vault" not in [p.lower() for p in parts]
    )


class ScorerVerdict(Artifact):
    """One scorer version's verdict on a rollout: latched steps, success, failure."""

    scorer_version: str = Field(min_length=1)
    step_names: list[Annotated[str, Field(pattern=STEP_NAME)]] = Field(min_length=1)
    step_latched: list[bool]
    # Sim time each step first held, in step order; null for a step never latched.
    step_latch_t: list[float | None] | None = None
    success: bool
    failure_label: str | None = Field(default=None, min_length=1)
    failure_t: float | None = Field(default=None, ge=0)
    at_failure: Measures | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if len(set(self.step_names)) != len(self.step_names):
            raise ValueError("step names must be unique")
        if len(self.step_latched) != len(self.step_names):
            raise ValueError("step_latched has one entry per step name")
        if self.step_latch_t is not None:
            if len(self.step_latch_t) != len(self.step_names):
                raise ValueError("step_latch_t has one entry per step name")
            for name, latched, t in zip(
                self.step_names, self.step_latched, self.step_latch_t, strict=True
            ):
                if latched != (t is not None):
                    raise ValueError(f"{name}: a latch time is set exactly when the step latched")
                if t is not None and t < 0:
                    raise ValueError(f"{name}: a latch time is not negative")
        # A rollout may end with neither success nor a label (cut before the timeout).
        if self.success and self.failure_label is not None:
            raise ValueError("a successful rollout has no failure label")
        if (self.failure_label is None) != (self.failure_t is None):
            raise ValueError("failure_t is set exactly when failure_label is")
        if self.at_failure is not None:
            if self.failure_label is None:
                raise ValueError("at_failure needs a failure label")
            _check_measures("at_failure", self.at_failure)
        return self


class RolloutOutcome(Artifact):
    """The outcome of one eval rollout: who it is, what the scorers said, what was measured."""

    episode_id: str = Field(min_length=1)
    run_plan_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    run: str = Field(min_length=1)
    seed: int
    level: int = Field(ge=0)
    repeat: int = Field(default=0, ge=0)
    sim_time_s: float = Field(ge=0)
    control_steps: int = Field(ge=0)
    verdict: ScorerVerdict
    other_verdicts: list[ScorerVerdict] = Field(default_factory=list)
    final: Measures = Field(default_factory=dict)
    extrema: Measures = Field(default_factory=dict)
    videos: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        versions = [self.verdict.scorer_version] + [v.scorer_version for v in self.other_verdicts]
        if len(set(versions)) != len(versions):
            raise ValueError("scorer versions must be unique across verdict and other_verdicts")
        for verdict in (self.verdict, *self.other_verdicts):
            if verdict.failure_t is not None and verdict.failure_t > self.sim_time_s:
                raise ValueError(
                    f"scorer {verdict.scorer_version}: failure_t is after the episode ended"
                )
            late = [t for t in verdict.step_latch_t or [] if t is not None and t > self.sim_time_s]
            if late:
                raise ValueError(
                    f"scorer {verdict.scorer_version}: a step latched after the episode ended"
                )
        _check_measures("final", self.final)
        _check_measures("extrema", self.extrema)
        bad = [v for v in self.videos if not relative_path(v)]
        if bad:
            raise ValueError(f"videos are relative paths, without '..' and outside vault/: {bad}")
        if len(set(self.videos)) != len(self.videos):
            raise ValueError("video paths must be unique")
        return self


__all__ = ["MeasureValue", "RolloutOutcome", "ScorerVerdict", "relative_path"]

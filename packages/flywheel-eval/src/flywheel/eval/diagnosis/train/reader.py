"""What the F-TRAIN detectors read, and the one place a contract change stops.

`TrainSeries` is a whole train job as arrays on the step axis: one array per
signal, with the train and val splits kept apart because they are measured at
different steps. Every detector of DA-08 takes one of these and nothing else,
so a field renamed in `flywheel.contracts` reaches `read_series` and goes no
further (plan, task 1).

Three questions only a real file can raise, answered here once:

* **A resumed job logs the same step twice.** `TrainingMetric.attempt` rises on
  every restart, so the record kept for a `(split, step)` pair is the one with
  the highest attempt, never "the last line in the file" - line order is not
  guaranteed (issue #5, point 2c).
* **A loss that is not finite is the JSON string `"NaN"`.** It becomes a float
  the moment it is read, so no detector ever sees a string (issue #5, 31/10).
* **Signals logged at different rates.** Per-dimension statistics cost more to
  compute than a loss, so a job may log them every hundredth record. A record
  that omits one gets a nan row rather than shifting the step axis, and the
  detectors already judge only finite values.

`parent_checkpoint_id` is deliberately absent: the contract puts it on
`ProbeP4`, not in the log, so T7 reads it from the probe (issue #5, point 2b).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

import numpy as np
from flywheel.contracts.artifacts import ActionLayout, ProbeP1, ProbeP3, ProbeP4
from flywheel.contracts.training import TrainingMetric
from numpy.typing import NDArray
from pydantic import ValidationError

Steps = NDArray[np.int64]
Values = NDArray[np.float64]
PerDim = NDArray[np.float64]

_ARTIFACT = TypeVar("_ARTIFACT", ActionLayout, ProbeP1, ProbeP3, ProbeP4)


class ReaderError(ValueError):
    """A log or probe file no detector of this story may run on."""


def _no_steps() -> Steps:
    return np.empty(0, dtype=np.int64)


def _no_values() -> Values:
    return np.empty(0, dtype=np.float64)


def _no_dims() -> PerDim:
    return np.empty((0, 0), dtype=np.float64)


# eq=False: two series are the same run or not, which element-wise array
# comparison cannot answer - it raises on the ambiguous truth of an array.
@dataclass(frozen=True, eq=False)
class TrainSeries:
    """Every signal of one train job, already on the step axis.

    `step` and `loss_train` are the train split, `val_step` and `loss_val` the
    val split; both ascend by step and neither holds a duplicate measurement.
    A loss that is not finite is a float here, never a string. The per-dimension
    arrays are shaped `(n_records, n_dims)` over the train records.

    `vlm_frozen` is None when the records disagree about it, which is a log T8
    must refuse to judge rather than read as an unfrozen VLM.
    """

    step: Steps = field(default_factory=_no_steps)
    loss_train: Values = field(default_factory=_no_values)
    val_step: Steps = field(default_factory=_no_steps)
    loss_val: Values = field(default_factory=_no_values)
    loss_by_group: dict[str, Values] = field(default_factory=dict)
    pred_var_by_dim: PerDim = field(default_factory=_no_dims)
    pred_std: PerDim = field(default_factory=_no_dims)
    target_std: PerDim = field(default_factory=_no_dims)
    grad_norm_vlm: Values = field(default_factory=_no_values)
    grad_norm_action: Values = field(default_factory=_no_values)
    vlm_frozen: bool | None = None
    job_id: str = ""
    checkpoint_id: str = ""
    release_id: str = ""
    run_plan_id: str = ""
    n_dropped_duplicates: int = 0


def read_series(path: Path) -> TrainSeries:
    """The `metrics.jsonl` of one train job as a `TrainSeries`.

    Raises `ReaderError` on a line that is not a valid `TrainingMetric`, on a
    file holding records of more than one job, and on a file with no record:
    each is a log the caller has to fix, not a checkpoint verdict to reach.
    """
    return build_series(_read_records(path), source=str(path))


def build_series(records: Iterable[TrainingMetric], source: str = "<records>") -> TrainSeries:
    """The same reading, from records already in memory - what the tests drive."""
    kept, dropped = _deduplicate(list(records))
    if not kept:
        raise ReaderError(f"{source}: không có bản ghi nào")
    jobs = {record.job_id for record in kept}
    if len(jobs) > 1:
        raise ReaderError(f"{source}: một tệp phải là log của đúng một job, thấy {sorted(jobs)}")
    train = [record for record in kept if record.split == "train"]
    val = [record for record in kept if record.split == "val"]
    first = kept[0]
    frozen = {record.vlm_frozen for record in kept}
    return TrainSeries(
        step=_steps(train),
        loss_train=_losses(train),
        val_step=_steps(val),
        loss_val=_losses(val),
        loss_by_group=_group_losses(train),
        pred_var_by_dim=_per_dim(train, "pred_var_by_dim", source),
        pred_std=_per_dim(train, "pred_std", source),
        target_std=_per_dim(train, "target_std", source),
        grad_norm_vlm=_optional(train, "grad_norm_vlm"),
        grad_norm_action=_optional(train, "grad_norm_action"),
        vlm_frozen=first.vlm_frozen if len(frozen) == 1 else None,
        job_id=first.job_id,
        checkpoint_id=first.checkpoint_id,
        release_id=first.release_id,
        run_plan_id=first.run_plan_id,
        n_dropped_duplicates=dropped,
    )


def read_probe_p1(path: Path) -> ProbeP1:
    """The P1 probe result of one checkpoint (AC 2)."""
    return _read_artifact(path, ProbeP1)


def read_probe_p3(path: Path) -> ProbeP3:
    """The P3 probe result O1-O4 are measured on (AC 2)."""
    return _read_artifact(path, ProbeP3)


def read_probe_p4(path: Path) -> ProbeP4:
    """The P4 probe result T7 compares against the parent checkpoint (AC 2)."""
    return _read_artifact(path, ProbeP4)


def read_action_layout(path: Path) -> ActionLayout:
    """The action layout of the embodiment, which holds the joint limits O4 uses."""
    return _read_artifact(path, ActionLayout)


@dataclass(frozen=True)
class LayoutView:
    """The action layout as the detectors ask about it (AC 2).

    T5 must never mark a dimension the layout calls masked, T4 needs the group
    a dimension belongs to, and O4 needs its joint limits. All three read them
    from here, so no story copies a number into code.
    """

    layout: ActionLayout

    @property
    def n_dims(self) -> int:
        return len(self.layout.dimensions)

    @property
    def unmasked(self) -> NDArray[np.bool_]:
        """True for the dimensions a detector is allowed to judge."""
        return np.asarray([not dim.masked for dim in self.layout.dimensions], dtype=np.bool_)

    @property
    def groups(self) -> list[str]:
        """The action groups, in the order their first dimension appears."""
        seen: dict[str, None] = {}
        for dimension in self.layout.dimensions:
            seen.setdefault(dimension.group, None)
        return list(seen)

    def name(self, dim: int) -> str:
        return self.layout.dimensions[dim].name

    def limits(self) -> tuple[Values, Values]:
        """Lower and upper joint limit per dimension; nan where the layout sets none."""
        low = np.asarray(
            [_or_nan(dim.limit_low) for dim in self.layout.dimensions], dtype=np.float64
        )
        high = np.asarray(
            [_or_nan(dim.limit_high) for dim in self.layout.dimensions], dtype=np.float64
        )
        return low, high

    def check_width(self, values: PerDim, what: str) -> None:
        """Raise unless `values` has one column per dimension of the layout.

        A log written under a different action layout would otherwise be judged
        dimension by dimension against the wrong names and limits.
        """
        if values.size and values.shape[1] != self.n_dims:
            raise ReaderError(f"{what} có {values.shape[1]} chiều, action_layout có {self.n_dims}")


def _read_records(path: Path) -> Iterator[TrainingMetric]:
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield TrainingMetric.model_validate_json(line)
            except ValidationError as error:
                raise ReaderError(f"{path}:{number}: bản ghi sai schema: {error}") from error


def _read_artifact(path: Path, record: type[_ARTIFACT]) -> _ARTIFACT:
    try:
        return record.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (ValidationError, json.JSONDecodeError) as error:
        raise ReaderError(f"{path}: không đọc được {record.__name__}: {error}") from error


def _deduplicate(records: list[TrainingMetric]) -> tuple[list[TrainingMetric], int]:
    """One record per `(split, step)`, the one from the highest attempt.

    A restarted job writes the steps it redid a second time. Keeping the
    highest attempt keeps the measurements that actually produced the
    checkpoint, and does so whatever order the lines are in (issue #5, 2c).
    """
    best: dict[tuple[str, int], TrainingMetric] = {}
    dropped = 0
    for record in records:
        key = (record.split, record.step)
        previous = best.get(key)
        if previous is None:
            best[key] = record
            continue
        dropped += 1
        if record.attempt > previous.attempt:
            best[key] = record
    return sorted(best.values(), key=lambda record: (record.split, record.step)), dropped


def _steps(records: list[TrainingMetric]) -> Steps:
    return np.asarray([record.step for record in records], dtype=np.int64)


def _losses(records: list[TrainingMetric]) -> Values:
    # `float("NaN")`, `float("Infinity")` and `float("-Infinity")` are exactly
    # the three strings the contract allows, so one call covers both forms.
    return np.asarray([float(record.loss) for record in records], dtype=np.float64)


def _group_losses(records: list[TrainingMetric]) -> dict[str, Values]:
    """One array per action group, aligned with `step`; nan where a record omits it."""
    names = sorted({name for record in records for name in record.loss_by_group})
    return {
        name: np.asarray(
            [_or_nan(record.loss_by_group.get(name)) for record in records], dtype=np.float64
        )
        for name in names
    }


def _per_dim(records: list[TrainingMetric], attribute: str, source: str) -> PerDim:
    """A `(n_records, n_dims)` array; a record that omits the signal is a nan row.

    Raises when two records that do carry it disagree on the number of
    dimensions: that is one log written under two action layouts, and judging
    dimension `i` across it would compare two different joints.
    """
    rows: list[list[float]] = [getattr(record, attribute) for record in records]
    widths = {len(row) for row in rows if row}
    if not widths:
        return np.zeros((len(rows), 0), dtype=np.float64)
    if len(widths) > 1:
        raise ReaderError(
            f"{source}: {attribute} có số chiều khác nhau giữa các bản ghi: {sorted(widths)}"
        )
    width = widths.pop()
    return np.asarray([row if row else [float("nan")] * width for row in rows], dtype=np.float64)


def _optional(records: list[TrainingMetric], attribute: str) -> Values:
    return np.asarray([_or_nan(getattr(record, attribute)) for record in records], dtype=np.float64)


def _or_nan(value: float | None) -> float:
    return float("nan") if value is None else float(value)

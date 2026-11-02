"""What the F-TRAIN detectors read, and the one place a contract change stops.

`TrainSeries` is a whole train job as arrays on the step axis: one array per
signal, with the train and val splits kept apart because they are measured at
different steps. Every detector of DA-08 takes one of these and nothing else,
so a field renamed in `flywheel.contracts` reaches `read_series` and goes no
further (plan, task 1).

`read_series`, the probe readers and `LayoutView` are task 1 and need the
`TrainingMetric`, `ProbeP3`, `ProbeP4` and `ActionLayout` records of DA-25
(PR #22), which is not merged yet. The container below names no contract type,
so the detectors of tasks 2 and 3 are written and tested against it while that
PR waits; the questions that only a file can answer - resume attempts, a loss
written as the string `"NaN"`, two logging rates - stay with the reader test
that will own them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

Steps = NDArray[np.int64]
Values = NDArray[np.float64]
PerDim = NDArray[np.float64]


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
    parent_checkpoint_id: str | None = None
    n_dropped_duplicates: int = 0

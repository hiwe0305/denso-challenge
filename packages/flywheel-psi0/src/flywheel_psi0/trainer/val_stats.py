"""Statistics Psi0 does not log, recomputed from its own validation predictions.

`FinetuneTrainer.evaluate()` already samples actions for `val_num_batches` val
batches through `inference()`; the launcher hands each `(predicted, target)`
pair to `ValStats.add` so nothing runs the model twice (docs/g0/psi0-logging.md).

Arrays are `(batch, chunk, dims)` in Psi0's normalised action space (bounds
normalisation puts every dimension in [-1, 1]), so the per-group errors are
comparable across groups. Psi0's own `eval/<dataset>/err_l1_*` stays in
de-normalised units and is not used here.

Dimensions the `ActionLayout` marks `masked` are padding: they are left out of
the group and chunk-position errors but keep their slot in the per-dimension
lists, because the evaluation lane indexes those lists by dimension.

Hand openness (DA-07) needs to know where "open" lies in that normalised space.
SIMPLE's open Dex3 pose is `init_qpos = 0` on all 7 joints of each hand
(`simple/robots/g1_sonic.py`), and in the two-table data every hand joint has
0 as one of its `stats_psi0.json` bounds, the other bound being the deepest
grasp the operators made - deeper than SIMPLE's scripted `close_qpos`, which is
why the closed end comes from the data, not from SIMPLE.
`normalised_open_pose` turns the bounds into the open pose the histogram needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from flywheel.contracts.artifacts import ActionLayout
from numpy.typing import NDArray

Array = NDArray[np.float64]

HAND_GROUP = "hand"
HAND_HIST_BINS = 10


HANDS = 2


def normalised_open_pose(
    low: NDArray[np.floating], high: NDArray[np.floating], open_qpos: float = 0.0
) -> Array:
    """Where the open hand pose lands after Psi0's bounds normalisation, per hand dim.

    `low` and `high` are the action `min` and `max` of `stats_psi0.json` for the
    hand dims; Psi0 maps `q` to `2 * (q - low) / (high - low) - 1`.
    """
    lo = np.asarray(low, dtype=np.float64)
    hi = np.asarray(high, dtype=np.float64)
    return 2 * (open_qpos - lo) / (hi - lo) - 1


def hand_openness(hand: Array, open_pose: Array) -> Array:
    """How open each hand is in each predicted action: 1 open, 0 fully closed.

    `hand` is `(samples, hand_dims)` in normalised units with the left hand's
    joints first; `open_pose` is `normalised_open_pose` for the same dims. A
    joint's openness falls linearly with its distance from the open pose, reaching
    0 at the bound farthest from it; a hand's openness is the mean over its joints.
    The result has one value per hand per sample, so the histogram pools both hands.
    """
    farthest = 1 + np.abs(open_pose)  # distance from the open pose to the far bound
    per_joint = 1 - np.clip(np.abs(hand - open_pose) / farthest, 0.0, 1.0)
    by_hand: Array = per_joint.reshape(len(hand), HANDS, -1).mean(axis=2)
    return by_hand.ravel()


@dataclass
class ValStats:
    """Accumulates one evaluation's predictions, then reduces them to log fields."""

    layout: ActionLayout
    # `normalised_open_pose` of the hand dims; without it no histogram is logged.
    hand_open_pose: Array | None = None
    _predicted: list[Array] = field(default_factory=list)
    _target: list[Array] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.hand_open_pose is None:
            return
        hand = [d for d in self.layout.dimensions if d.group == HAND_GROUP and not d.masked]
        if len(self.hand_open_pose) != len(hand) or len(hand) % HANDS:
            raise ValueError(
                f"hand_open_pose has {len(self.hand_open_pose)} values for {len(hand)} "
                f"hand dims; expected one per dim, split evenly over {HANDS} hands"
            )

    def add(self, predicted: NDArray[np.floating], target: NDArray[np.floating]) -> None:
        """One val batch: both `(batch, chunk, dims)`, same shape."""
        pred = np.asarray(predicted, dtype=np.float64)
        tgt = np.asarray(target, dtype=np.float64)
        dims = len(self.layout.dimensions)
        if pred.shape != tgt.shape or pred.ndim != 3 or pred.shape[2] != dims:
            raise ValueError(
                f"expected predicted and target of shape (batch, chunk, {dims}), "
                f"got {pred.shape} and {tgt.shape}"
            )
        self._predicted.append(pred)
        self._target.append(tgt)

    def __bool__(self) -> bool:
        return bool(self._predicted)

    def summary(self) -> dict[str, object]:
        """The `TrainingMetric` fields for the batches added since the last summary."""
        if not self._predicted:
            return {}
        pred = np.concatenate(self._predicted)
        tgt = np.concatenate(self._target)
        self._predicted.clear()
        self._target.clear()

        unmasked = np.array([not dim.masked for dim in self.layout.dimensions])
        squared = (pred - tgt) ** 2
        groups: dict[str, list[int]] = {}
        for index, dim in enumerate(self.layout.dimensions):
            if not dim.masked:
                groups.setdefault(dim.group, []).append(index)

        flat_pred = pred.reshape(-1, pred.shape[2])
        flat_tgt = tgt.reshape(-1, tgt.shape[2])
        fields: dict[str, object] = {
            "loss_by_group": {
                name: float(squared[:, :, indices].mean()) for name, indices in groups.items()
            },
            "loss_by_chunk_pos": squared[:, :, unmasked].mean(axis=(0, 2)).tolist(),
            "pred_var_by_dim": flat_pred.var(axis=0).tolist(),
            "pred_std": flat_pred.std(axis=0).tolist(),
            "target_std": flat_tgt.std(axis=0).tolist(),
        }
        if HAND_GROUP in groups and self.hand_open_pose is not None:
            openness = hand_openness(flat_pred[:, groups[HAND_GROUP]], self.hand_open_pose)
            counts, _ = np.histogram(openness, bins=HAND_HIST_BINS, range=(0.0, 1.0))
            fields["hand_open_hist"] = (counts / max(counts.sum(), 1)).tolist()
        return fields

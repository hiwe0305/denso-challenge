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
    hand dims; Psi0 maps `q` to `2 * (q - low) / (high - low) - 1`. A dim whose
    range Psi0 calls ill, `|high - low| < 1e-4 * (|high| + |low| + 1e-8)` in float32,
    it does not normalise: it passes the raw value through. Then it clips every dim to
    [-1, 1] (src/psi/config/transform.py at cda3fdf), and the pose returned here is
    where the model's targets land. A demo subset can have ill dims: in DA-26's N20
    one hand never moves, so its 7 joints have min = max = 0, and the division gave
    NaN. (Psi0 sets ill *state* dims to 0 instead; this helper reads action bounds.)
    """
    lo = np.asarray(low, dtype=np.float64)
    hi = np.asarray(high, dtype=np.float64)
    lo32, hi32 = lo.astype(np.float32), hi.astype(np.float32)
    ill = np.abs(hi32 - lo32) < 1e-4 * (np.abs(hi32) + np.abs(lo32) + 1e-8)
    span = np.where(ill, 1.0, hi - lo)
    pose: Array = np.clip(np.where(ill, open_qpos, 2 * (open_qpos - lo) / span - 1), -1, 1)
    return pose


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


def _groups(layout: ActionLayout) -> dict[str, list[int]]:
    """Unmasked dimension indices by group, in layout order."""
    groups: dict[str, list[int]] = {}
    for index, dim in enumerate(layout.dimensions):
        if not dim.masked:
            groups.setdefault(dim.group, []).append(index)
    return groups


def error_split(squared: Array, layout: ActionLayout) -> dict[str, object]:
    """`loss_by_group` and `loss_by_chunk_pos` of a `(batch, chunk, dims)` squared error."""
    unmasked = np.array([not dim.masked for dim in layout.dimensions])
    return {
        "loss_by_group": {
            name: float(squared[:, :, indices].mean()) for name, indices in _groups(layout).items()
        },
        "loss_by_chunk_pos": squared[:, :, unmasked].mean(axis=(0, 2)).tolist(),
    }


@dataclass
class LossBreakdown:
    """Splits the train loss itself by action group and chunk position.

    Psi0 computes `F.mse_loss(..., reduction="none")`, a `(batch, chunk, dims)` error
    on the flow-matching velocity, before masking and summing it; the launcher hands
    that array here on every micro-batch. The split is in velocity space, so it is
    comparable between groups of one train line, not with the val line's action
    error.

    The array is taken before Psi0's RTC mask, which leaves a random prefix of
    `delay < --model.max-delay` positions out of each sample's loss. `rtc_prefix`
    drops the first `max-delay` positions from both splits so they match the loss
    Psi0 trains on (Hiếu, 3/11/2026): `loss_by_chunk_pos[i]` on a train line is chunk
    position `rtc_prefix + i`. Without RTC it is 0 and nothing is dropped.
    """

    layout: ActionLayout
    rtc_prefix: int = 0
    _squared: list[Array] = field(default_factory=list)

    def add(self, squared: NDArray[np.floating]) -> None:
        array = np.asarray(squared, dtype=np.float64)
        dims = len(self.layout.dimensions)
        if array.ndim != 3 or array.shape[2] != dims:
            raise ValueError(f"expected (batch, chunk, {dims}), got {array.shape}")
        if array.shape[1] <= self.rtc_prefix:
            raise ValueError(f"chunk of {array.shape[1]} has nothing past {self.rtc_prefix}")
        self._squared.append(array[:, self.rtc_prefix :])

    def summary(self) -> dict[str, object]:
        """The split over the micro-batches added since the last summary."""
        if not self._squared:
            return {}
        squared = np.concatenate(self._squared)
        self._squared.clear()
        return error_split(squared, self.layout)


@dataclass
class ValStats:
    """Accumulates sampled actions and their targets, then reduces them to log fields.

    The val split feeds it from `evaluate()`; a second instance takes the train batch
    the launcher samples at each validation step.
    """

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

    def summary(self, errors: bool = True) -> dict[str, object]:
        """The `TrainingMetric` fields for the batches added since the last summary.

        `errors=False` leaves out `loss_by_group` and `loss_by_chunk_pos`, for a
        train line whose split comes from `LossBreakdown` instead.
        """
        if not self._predicted:
            return {}
        pred = np.concatenate(self._predicted)
        tgt = np.concatenate(self._target)
        self._predicted.clear()
        self._target.clear()

        groups = _groups(self.layout)
        flat_pred = pred.reshape(-1, pred.shape[2])
        flat_tgt = tgt.reshape(-1, tgt.shape[2])
        fields: dict[str, object] = {
            **(error_split((pred - tgt) ** 2, self.layout) if errors else {}),
            "pred_var_by_dim": flat_pred.var(axis=0).tolist(),
            "pred_std": flat_pred.std(axis=0).tolist(),
            "target_std": flat_tgt.std(axis=0).tolist(),
        }
        if HAND_GROUP in groups and self.hand_open_pose is not None:
            openness = hand_openness(flat_pred[:, groups[HAND_GROUP]], self.hand_open_pose)
            counts, _ = np.histogram(openness, bins=HAND_HIST_BINS, range=(0.0, 1.0))
            fields["hand_open_hist"] = (counts / max(counts.sum(), 1)).tolist()
        return fields

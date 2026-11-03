"""Data defect injection logic for G1 humanoid episodes (Design 27/10/2026 section 9.2)."""

import copy
import math
import random
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field

from flywheel.contracts.artifacts import ActionLayout, Defect, EpisodeMetadata
from flywheel.data.inject.codes import DATA_DEFECT_CODES
from flywheel.data.inject.config import DataDefectConfig

Parameters = dict[str, bool | float | int | str]

# G1 36-D action of SIMPLE (ACTION_SLICES_36D of Psi0 at cda3fdf, design 9.2): 0-13 hands,
# 14-27 arms, 28-30 waist are joints; 31 height (m), 32-33 velocities, 34 turn flag,
# 35 heading (rad).
JOINT_ACTION_DIMS = tuple(range(31))
ANGLE_ACTION_DIMS = (*JOINT_ACTION_DIMS, 35)


class NotApplicable(ValueError):
    """The episode has nothing this defect kind can change; pick another episode."""


@dataclass
class EpisodeData:
    episode_id: str
    timestamps_state: list[float]
    timestamps_image: list[float]
    states: list[list[float]]
    actions: list[list[float]]
    images: list[str] = field(default_factory=list)
    instruction: str = "pick object from table 1 and place on table 2"
    sim_success: bool = True
    seed: int | None = 1000  # condition seed; psi-data records none
    meta: EpisodeMetadata = field(default_factory=EpisodeMetadata)


# Per-frame lists of an episode: one entry per parquet row in LeRobot, where images
# live in the video and a frame is a row (DA-03 reader).
FRAME_FIELDS = ("timestamps_state", "timestamps_image", "states", "actions", "images")


def _keep_frames(ep: EpisodeData, keep: list[int]) -> None:
    for name in FRAME_FIELDS:
        values = getattr(ep, name)
        setattr(ep, name, [values[i] for i in keep])


def _join(values: list[int]) -> str:
    """Encode an index list as a scalar, since contract parameters hold scalars only."""
    return ",".join(str(v) for v in values)


def _defect(ep: EpisodeData, kind: str, parameters: Parameters) -> Defect:
    """Build the manifest entry for a defect injected into `ep`.

    The design code goes in `code`; the kind stays in `parameters["kind"]`. Nothing is
    written on the episode: the answer lives only in the DefectManifest (design 9.2).
    """
    code = DATA_DEFECT_CODES[kind]
    return Defect(target_ref=ep.episode_id, code=code, parameters={"kind": kind, **parameters})


class DataDefectInjector:
    """Injects 11 standardized data defects into episodes.

    An injector raises NotApplicable instead of listing a defect it cannot apply.
    """

    def __init__(
        self,
        config: DataDefectConfig | None = None,
        rng_seed: int = 42,
        layout: ActionLayout | None = None,
    ):
        self.config = config or DataDefectConfig()
        self.rng = random.Random(rng_seed)
        # With a layout, action defects skip masked dims and dims the layout does not name.
        self.layout = layout

    def _limits(self, dim: int) -> tuple[float, float] | None:
        """Joint limits of an action dim: from the layout, else +-pi without a layout."""
        if self.layout is None:
            return (-math.pi, math.pi)
        d = self.layout.dimensions[dim]
        if d.limit_low is None or d.limit_high is None:
            return None
        return (d.limit_low, d.limit_high)

    def _choose_dim(
        self,
        ep: EpisodeData,
        dims: tuple[int, ...],
        kind: str,
        qualifies: Callable[[int, list[float]], bool] = lambda dim, col: True,
    ) -> int:
        """Pick one action dim among `dims` that exists and qualifies on this episode."""
        width = len(ep.actions[0]) if ep.actions else 0
        if self.layout is not None:
            named = self.layout.dimensions
            width = min(width, len(named))
            dims = tuple(d for d in dims if d < width and not named[d].masked)
        eligible = [d for d in dims if d < width and qualifies(d, [a[d] for a in ep.actions])]
        if not eligible:
            raise NotApplicable(f"{kind}: no eligible action dimension")
        return self.rng.choice(eligible)

    def inject_drop_frames(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        # A dropped frame is a missing row: every per-frame list loses it.
        rate = self.config.drop_frames_rate
        count = len(ep.images)
        dropped = [i for i in range(1, count) if self.rng.random() < rate]
        if not dropped:
            if count <= 2:
                raise NotApplicable("drop_frames needs more than two images")
            dropped = [1]
        new_ep = copy.deepcopy(ep)
        _keep_frames(new_ep, [i for i in range(count) if i not in set(dropped)])
        return new_ep, _defect(
            new_ep,
            "drop_frames",
            {"dropped_count": len(dropped), "indices": _join(dropped[:5])},
        )

    def inject_timestamp_sync_offset(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        # Image times are fixed by the video; the state timestamp column moves.
        if not ep.timestamps_state:
            raise NotApplicable("timestamp_sync_offset needs state timestamps")
        new_ep = copy.deepcopy(ep)
        offset = self.config.timestamp_offset_seconds
        new_ep.timestamps_state = [ts + offset for ts in new_ep.timestamps_state]
        return new_ep, _defect(
            new_ep,
            "timestamp_sync_offset",
            {"offset_seconds": offset},
        )

    def inject_joint_jump(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        dim = self._choose_dim(ep, JOINT_ACTION_DIMS, "joint_jump")
        new_ep = copy.deepcopy(ep)
        mag = self.config.joint_jump_magnitude
        step = len(new_ep.actions) // 2
        new_ep.actions[step][dim] += mag
        return new_ep, _defect(
            new_ep,
            "joint_jump",
            {"step": step, "dimension": dim, "magnitude": mag},
        )

    def inject_joint_limit_exceeded(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        dim = self._choose_dim(
            ep,
            JOINT_ACTION_DIMS,
            "joint_limit_exceeded",
            lambda d, col: self._limits(d) is not None,
        )
        low, high = self._limits(dim) or (-math.pi, math.pi)
        # Past the high limit by (factor - 1) of the joint range.
        exceeded = high + (self.config.joint_limit_excess_factor - 1) * (high - low)
        new_ep = copy.deepcopy(ep)
        for a in new_ep.actions:
            a[dim] = exceeded
        return new_ep, _defect(
            new_ep,
            "joint_limit_exceeded",
            {"dimension": dim, "limit_low": low, "limit_high": high, "exceeded_value": exceeded},
        )

    def inject_nan_values(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        width = len(ep.actions[0]) if ep.actions else 0
        dim = self._choose_dim(
            ep, tuple(range(width)), "nan_values", lambda d, col: not math.isnan(col[len(col) // 2])
        )
        new_ep = copy.deepcopy(ep)
        step = len(new_ep.actions) // 2
        new_ep.actions[step][dim] = float("nan")
        return new_ep, _defect(
            new_ep,
            "nan_values",
            {"step": step, "dimension": dim, "type": "nan"},
        )

    def inject_unit_deg_rad(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        # Scaling a dim that is all zero changes nothing, so only nonzero angle dims qualify.
        dim = self._choose_dim(
            ep, ANGLE_ACTION_DIMS, "unit_deg_rad", lambda d, col: any(v != 0 for v in col)
        )
        new_ep = copy.deepcopy(ep)
        scale = self.config.unit_deg_rad_scale
        for a in new_ep.actions:
            a[dim] *= scale
        return new_ep, _defect(
            new_ep,
            "unit_deg_rad",
            {"dimension": dim, "scale": scale},
        )

    def inject_action_sign_flip(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        width = len(ep.actions[0]) if ep.actions else 0
        dim = self._choose_dim(
            ep, tuple(range(width)), "action_sign_flip", lambda d, col: statistics.pstdev(col) > 0
        )
        new_ep = copy.deepcopy(ep)
        for a in new_ep.actions:
            a[dim] = -a[dim]
        return new_ep, _defect(
            new_ep,
            "action_sign_flip",
            {"dimension": dim},
        )

    def inject_corrupted_success_label(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        # Design 9.2: a broken episode still labelled a success. Cut it before the task
        # can finish and keep the label; psi-data's teleop demos are all labelled
        # successful by being in the authors' training set.
        if ep.sim_success is not True:
            raise NotApplicable("corrupted_success_label needs an episode labelled a success")
        count = len(ep.actions)
        kept = max(1, math.floor(count * self.config.success_label_keep_fraction))
        if kept >= count:
            raise NotApplicable("corrupted_success_label: episode too short to cut")
        new_ep = copy.deepcopy(ep)
        _keep_frames(new_ep, list(range(kept)))
        return new_ep, _defect(
            new_ep,
            "corrupted_success_label",
            {"label": "success", "kept_frames": kept, "original_frames": count},
        )

    def inject_wrong_task_instruction(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        if ep.instruction == self.config.corrupted_prompt:
            raise NotApplicable("wrong_task_instruction: episode already has the wrong prompt")
        new_ep = copy.deepcopy(ep)
        new_ep.instruction = self.config.corrupted_prompt
        return new_ep, _defect(
            new_ep,
            "wrong_task_instruction",
            {"instruction": self.config.corrupted_prompt},
        )

    def inject_duplicate_episode(
        self, ep: EpisodeData, dup_id: str | None = None
    ) -> tuple[EpisodeData, Defect]:
        new_ep = copy.deepcopy(ep)
        new_ep.episode_id = dup_id or f"{ep.episode_id}_dup"
        return new_ep, _defect(
            new_ep,
            "duplicate_episode",
            {"original_id": ep.episode_id},
        )

    def inject_holdout_seed_leak(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        low, high = self.config.holdout_seed_range
        if ep.seed is not None and low <= ep.seed <= high:
            raise NotApplicable("holdout_seed_leak: seed is already in the holdout range")
        new_ep = copy.deepcopy(ep)
        leaked_seed = self.rng.randint(low, high)
        new_ep.seed = leaked_seed
        return new_ep, _defect(
            new_ep,
            "holdout_seed_leak",
            {"leaked_seed": leaked_seed, "holdout_low": low, "holdout_high": high},
        )

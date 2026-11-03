"""Data defect injection logic for G1 humanoid episodes (Design 27/10/2026 section 9.2)."""

import copy
import math
import random
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field

from flywheel.contracts.artifacts import ActionLayout, Defect, EpisodeMetadata, InjectedDefect
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
    seed: int = 1000
    meta: EpisodeMetadata = field(default_factory=EpisodeMetadata)


def _join(values: list[int]) -> str:
    """Encode an index list as a scalar, since contract parameters hold scalars only."""
    return ",".join(str(v) for v in values)


def _mark(ep: EpisodeData, kind: str, parameters: Parameters) -> Defect:
    """Stamp the episode with its injected defect and return the matching manifest entry.

    The design code goes in `code`; the kind stays in `parameters["kind"]`.
    """
    code = DATA_DEFECT_CODES[kind]
    parameters = {"kind": kind, **parameters}
    ep.meta = ep.meta.model_copy(
        update={"injected_defect": InjectedDefect(code=code, parameters=parameters)}
    )
    return Defect(target_ref=ep.episode_id, code=code, parameters=parameters)


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
        new_ep = copy.deepcopy(ep)
        rate = self.config.drop_frames_rate
        kept_images = []
        kept_ts = []
        dropped_indices = []
        for idx, (img, ts) in enumerate(zip(new_ep.images, new_ep.timestamps_image)):
            if self.rng.random() >= rate or (idx == 0 and len(new_ep.images) > 1):
                kept_images.append(img)
                kept_ts.append(ts)
            else:
                dropped_indices.append(idx)
        if not dropped_indices:
            if len(new_ep.images) <= 2:
                raise NotApplicable("drop_frames needs more than two images")
            dropped_indices.append(1)
            kept_images.pop(1)
            kept_ts.pop(1)
        new_ep.images = kept_images
        new_ep.timestamps_image = kept_ts
        return new_ep, _mark(
            new_ep,
            "drop_frames",
            {
                "dropped_count": len(dropped_indices),
                "indices": _join(dropped_indices[:5]),
            },
        )

    def inject_timestamp_sync_offset(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        if not ep.timestamps_image:
            raise NotApplicable("timestamp_sync_offset needs image timestamps")
        new_ep = copy.deepcopy(ep)
        offset = self.config.timestamp_offset_seconds
        new_ep.timestamps_image = [ts + offset for ts in new_ep.timestamps_image]
        return new_ep, _mark(
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
        return new_ep, _mark(
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
        return new_ep, _mark(
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
        return new_ep, _mark(
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
        return new_ep, _mark(
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
        return new_ep, _mark(
            new_ep,
            "action_sign_flip",
            {"dimension": dim},
        )

    def inject_corrupted_success_label(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        new_ep = copy.deepcopy(ep)
        original_success = new_ep.sim_success
        new_ep.sim_success = not original_success
        return new_ep, _mark(
            new_ep,
            "corrupted_success_label",
            {"original": original_success, "corrupted": new_ep.sim_success},
        )

    def inject_wrong_task_instruction(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        if ep.instruction == self.config.corrupted_prompt:
            raise NotApplicable("wrong_task_instruction: episode already has the wrong prompt")
        new_ep = copy.deepcopy(ep)
        new_ep.instruction = self.config.corrupted_prompt
        return new_ep, _mark(
            new_ep,
            "wrong_task_instruction",
            {"instruction": self.config.corrupted_prompt},
        )

    def inject_duplicate_episode(
        self, ep: EpisodeData, dup_id: str | None = None
    ) -> tuple[EpisodeData, Defect]:
        new_ep = copy.deepcopy(ep)
        new_ep.episode_id = dup_id or f"{ep.episode_id}_dup"
        return new_ep, _mark(
            new_ep,
            "duplicate_episode",
            {"original_id": ep.episode_id},
        )

    def inject_holdout_seed_leak(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        low, high = self.config.holdout_seed_range
        if low <= ep.seed <= high:
            raise NotApplicable("holdout_seed_leak: seed is already in the holdout range")
        new_ep = copy.deepcopy(ep)
        leaked_seed = self.rng.randint(low, high)
        new_ep.seed = leaked_seed
        return new_ep, _mark(
            new_ep,
            "holdout_seed_leak",
            {"leaked_seed": leaked_seed, "holdout_low": low, "holdout_high": high},
        )

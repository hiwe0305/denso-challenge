"""Data defect injection logic for G1 humanoid episodes (Design 27/10/2026 section 9.2)."""

import copy
import math
import random
from dataclasses import dataclass, field

from flywheel.contracts.artifacts import Defect, EpisodeMetadata, InjectedDefect
from flywheel.data.inject.codes import DATA_DEFECT_CODES
from flywheel.data.inject.config import DataDefectConfig

Parameters = dict[str, bool | float | int | str]


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
    """Injects 11 standardized data defects into episodes."""

    def __init__(self, config: DataDefectConfig | None = None, rng_seed: int = 42):
        self.config = config or DataDefectConfig()
        self.rng = random.Random(rng_seed)

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
        if not dropped_indices and len(new_ep.images) > 2:
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
        new_ep = copy.deepcopy(ep)
        offset = self.config.timestamp_offset_seconds
        new_ep.timestamps_image = [ts + offset for ts in new_ep.timestamps_image]
        return new_ep, _mark(
            new_ep,
            "timestamp_sync_offset",
            {"offset_seconds": offset},
        )

    def inject_joint_jump(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        new_ep = copy.deepcopy(ep)
        mag = self.config.joint_jump_magnitude
        step = len(new_ep.states) // 2 if len(new_ep.states) > 2 else 0
        dim = 0
        if new_ep.states:
            new_ep.states[step][dim] += mag
        return new_ep, _mark(
            new_ep,
            "joint_jump",
            {"step": step, "dimension": dim, "magnitude": mag},
        )

    def inject_joint_limit_exceeded(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        new_ep = copy.deepcopy(ep)
        factor = self.config.joint_limit_excess_factor
        limit = math.pi
        dim = 1
        for s in new_ep.states:
            if len(s) > dim:
                s[dim] = limit * factor
        return new_ep, _mark(
            new_ep,
            "joint_limit_exceeded",
            {"dimension": dim, "limit": limit, "exceeded_value": limit * factor},
        )

    def inject_nan_values(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        new_ep = copy.deepcopy(ep)
        step = len(new_ep.actions) // 2 if len(new_ep.actions) > 0 else 0
        dim = 0
        if new_ep.actions and len(new_ep.actions[step]) > 0:
            new_ep.actions[step][dim] = float("nan")
        return new_ep, _mark(
            new_ep,
            "nan_values",
            {"step": step, "dimension": dim, "type": "nan"},
        )

    def inject_unit_deg_rad(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        new_ep = copy.deepcopy(ep)
        scale = self.config.unit_deg_rad_scale
        dim = 2
        for s in new_ep.states:
            if len(s) > dim:
                s[dim] *= scale
        return new_ep, _mark(
            new_ep,
            "unit_deg_rad",
            {"dimension": dim, "scale": scale},
        )

    def inject_action_sign_flip(self, ep: EpisodeData) -> tuple[EpisodeData, Defect]:
        new_ep = copy.deepcopy(ep)
        dims = list(self.config.action_sign_flip_dims)
        for act in new_ep.actions:
            for d in dims:
                if len(act) > d:
                    act[d] = -act[d]
        return new_ep, _mark(
            new_ep,
            "action_sign_flip",
            {"dimensions": _join(dims)},
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
        new_ep = copy.deepcopy(ep)
        low, high = self.config.holdout_seed_range
        leaked_seed = self.rng.randint(low, high)
        new_ep.seed = leaked_seed
        return new_ep, _mark(
            new_ep,
            "holdout_seed_leak",
            {"leaked_seed": leaked_seed, "holdout_low": low, "holdout_high": high},
        )

"""Check that a manifest entry describes a change that is really in the data.

DA-31 computes recall per kind from the DefectManifest, so an entry whose defect left the
episode unchanged would count as a miss the detector could never have caught.
"""

import math
from collections.abc import Callable

from flywheel.contracts.artifacts import Defect
from flywheel.data.inject.data_defects import EpisodeData


def _column(ep: EpisodeData, dim: int) -> list[float]:
    return [a[dim] for a in ep.actions]


def content(ep: EpisodeData) -> tuple[object, ...]:
    """Everything a detector can see in an episode, without its id and metadata."""
    return (
        ep.timestamps_state,
        ep.timestamps_image,
        ep.states,
        ep.actions,
        ep.images,
        ep.instruction,
        ep.sim_success,
        ep.seed,
    )


def _int(defect: Defect, key: str) -> int:
    return int(defect.parameters[key])


def _drop_frames(before: EpisodeData, after: EpisodeData, d: Defect) -> bool:
    count = _int(d, "dropped_count")
    return count > 0 and len(after.images) == len(before.images) - count


def _joint_jump(before: EpisodeData, after: EpisodeData, d: Defect) -> bool:
    step, dim = _int(d, "step"), _int(d, "dimension")
    return after.actions[step][dim] != before.actions[step][dim]


def _joint_limit(before: EpisodeData, after: EpisodeData, d: Defect) -> bool:
    dim, high = _int(d, "dimension"), float(d.parameters["limit_high"])
    col = _column(after, dim)
    return col != _column(before, dim) and all(v > high for v in col)


def _nan(before: EpisodeData, after: EpisodeData, d: Defect) -> bool:
    step, dim = _int(d, "step"), _int(d, "dimension")
    return math.isnan(after.actions[step][dim]) and not math.isnan(before.actions[step][dim])


def _action_column(before: EpisodeData, after: EpisodeData, d: Defect) -> bool:
    dim = _int(d, "dimension")
    return _column(after, dim) != _column(before, dim)


def _seed_leak(before: EpisodeData, after: EpisodeData, d: Defect) -> bool:
    low, high = _int(d, "holdout_low"), _int(d, "holdout_high")
    return after.seed != before.seed and low <= after.seed <= high


CHECKS: dict[str, Callable[[EpisodeData, EpisodeData, Defect], bool]] = {
    "drop_frames": _drop_frames,
    "timestamp_sync_offset": lambda b, a, d: a.timestamps_image != b.timestamps_image,
    "joint_jump": _joint_jump,
    "joint_limit_exceeded": _joint_limit,
    "nan_values": _nan,
    "unit_deg_rad": _action_column,
    "action_sign_flip": _action_column,
    "corrupted_success_label": lambda b, a, d: a.sim_success != b.sim_success,
    "wrong_task_instruction": lambda b, a, d: a.instruction != b.instruction,
    "holdout_seed_leak": _seed_leak,
}


def defect_applied(
    before: EpisodeData,
    after: EpisodeData,
    defect: Defect,
    source: EpisodeData | None = None,
) -> bool:
    """True when `after` differs from `before` exactly where `defect` says it does.

    `before` is the episode the slot held; for `duplicate_episode`, `source` is the episode
    that was copied into it.
    """
    kind = str(defect.parameters["kind"])
    if kind == "duplicate_episode":
        return source is not None and content(after) == content(source) != content(before)
    return CHECKS[kind](before, after, defect)

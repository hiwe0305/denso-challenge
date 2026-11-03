"""Thresholds of the replay checks: `configs/data/replay.yaml` (DA-17 AC 3).

Every key is required; the file has no defaults here, as qa.yaml has none (design
10: thresholds live in configs/ with a hash). `version` of a loaded file is its
`version` and the first 12 hex of the sha256 of its bytes, like QA's
`threshold_version`.

Kinematic thresholds sit at quantile `kinematic_quantile` of the clean episodes,
dynamic ones at `dynamic_quantile` of the episodes whose replay succeeded (design
6.3: p99). A kinematic failure rejects the episode and a dynamic one only flags
it, which is why the two quantiles are separate keys.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flywheel.data.config import (
    ConfigError,
    _exact_keys,
    _integer,
    _mapping,
    _number,
    _parse,
    _read,
    _text,
)

REPLAY_YAML = Path("configs/data/replay.yaml")
KEYS = ("version", "calibration", "kinematic", "dynamic")
KINEMATIC_KEYS = (
    "quantile",
    "timestamp_tolerance_frames",
    "limit_tolerance",
    "joint_jump",
    "unit_ratio",
    "min_std",
    "mapping_correlation",
)
DYNAMIC_KEYS = ("quantile", "state_error", "hand_event_offset_steps")
ARRAYS = ("action", "states")


@dataclass(frozen=True)
class ReplayThresholds:
    """What a kinematic or dynamic replay may show before it is an issue.

    Kinematic: `timestamp_tolerance_frames` |timestamp * fps - frame_index|;
    `limit_tolerance[array]` rad past a joint limit of the action layout, per
    array (action, states); `joint_jump[group]` largest |s[t+1] - s[t]| of the
    recorded joint states; `unit_ratio[group]` std(action) / std(state) of one
    joint; `mapping_correlation[dim]` the lowest correlation of a joint's action
    with its state (a joint without an entry is not checked); `min_std` the
    spread a joint needs, in both arrays, for the last two to apply.
    Dynamic: `state_error[group]` largest |replayed - recorded| state, rad;
    `hand_event_offset_steps` |replayed - recorded| step of a hand closing.
    """

    version: str
    kinematic_quantile: float
    timestamp_tolerance_frames: float
    limit_tolerance: Mapping[str, float]
    joint_jump: Mapping[str, float]
    unit_ratio: Mapping[str, float]
    min_std: float
    mapping_correlation: Mapping[str, float]
    dynamic_quantile: float
    state_error: Mapping[str, float]
    hand_event_offset_steps: int


def load_thresholds(path: Path = REPLAY_YAML) -> ReplayThresholds:
    """`configs/data/replay.yaml` as ReplayThresholds; a missing or unknown key raises."""
    raw = _read(path)
    data = _mapping(_parse(raw, path), str(path))
    _exact_keys(data, KEYS, str(path))
    kin = _mapping(data["kinematic"], "kinematic")
    _exact_keys(kin, KINEMATIC_KEYS, "kinematic")
    dyn = _mapping(data["dynamic"], "dynamic")
    _exact_keys(dyn, DYNAMIC_KEYS, "dynamic")
    _text(data["calibration"], "calibration")
    limits = _numbers(kin["limit_tolerance"], "kinematic.limit_tolerance")
    _exact_keys(dict(limits), ARRAYS, "kinematic.limit_tolerance")
    digest = hashlib.sha256(raw).hexdigest()[:12]
    return ReplayThresholds(
        version=f"{_text(data['version'], 'version')}@{digest}",
        kinematic_quantile=_quantile(kin["quantile"], "kinematic.quantile"),
        timestamp_tolerance_frames=_number(
            kin["timestamp_tolerance_frames"], "kinematic.timestamp_tolerance_frames"
        ),
        limit_tolerance=limits,
        joint_jump=_numbers(kin["joint_jump"], "kinematic.joint_jump"),
        unit_ratio=_numbers(kin["unit_ratio"], "kinematic.unit_ratio"),
        min_std=_number(kin["min_std"], "kinematic.min_std"),
        mapping_correlation=_numbers(kin["mapping_correlation"], "kinematic.mapping_correlation"),
        dynamic_quantile=_quantile(dyn["quantile"], "dynamic.quantile"),
        state_error=_numbers(dyn["state_error"], "dynamic.state_error"),
        hand_event_offset_steps=_integer(
            dyn["hand_event_offset_steps"], "dynamic.hand_event_offset_steps"
        ),
    )


def _numbers(value: Any, where: str) -> dict[str, float]:
    mapping = _mapping(value, where)
    return {str(k): _number(v, f"{where}.{k}") for k, v in mapping.items()}


def _quantile(value: Any, where: str) -> float:
    q = _number(value, where)
    if not 0.5 <= q <= 1.0:
        raise ConfigError(f"{where} must lie in [0.5, 1], got {q}")
    return q

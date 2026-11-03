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
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from flywheel.contracts.artifacts import ActionLayout
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
from flywheel.data.ingest.lerobot import EpisodeFrames
from flywheel.data.replay_check.dynamic import ReplayOutcome
from flywheel.data.replay_check.kinematic import (
    correlations,
    joint_dims,
    past_limits,
    spread_ratios,
)

REPLAY_YAML = Path("configs/data/replay.yaml")
VERSION = "replay-1"
# Not calibrated: clean timestamps sit exactly on frame_index / fps (psi-data e78fb93),
# and half a period is where a stamp starts to name the next frame.
TIMESTAMP_TOLERANCE_FRAMES = 0.5
# A joint must move this much (rad, std) for correlation and spread to mean anything.
MIN_STD = 1e-3
# qa.yaml joint_limits: the G1 layout rounds URDF limits to 5-6 digits.
LIMIT_FLOOR = 1e-5
# A joint whose action and state both move in fewer clean episodes gets no
# mapping threshold (psi-data's left hand moves in 2 of 99).
MIN_EPISODES = 10
# A mapping floor never sits above this: a flipped joint correlates negatively, and a
# higher floor only rejects sources that track a little more loosely than the clean
# set (tray S1's right elbow at 0.953 against psi-data's lowest 0.960, 4/11/2026).
MAPPING_CEILING = 0.5
KEYS = ("version", "calibration", "kinematic", "dynamic")
KINEMATIC_KEYS = (
    "quantile",
    "timestamp_tolerance_frames",
    "limit_tolerance",
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
    array (action, states); `unit_ratio[group]` std(action) / std(state) of one
    joint; `mapping_correlation[dim]` the lowest correlation of a joint's action
    with its state, at most MAPPING_CEILING (a joint without an entry is not
    checked); `min_std` the spread a joint needs, in both arrays, for the last
    two to apply.
    Dynamic: `state_error[group]` largest |replayed - recorded| state, rad;
    `hand_event_offset_steps` |replayed - recorded| step of a hand closing.
    """

    version: str
    kinematic_quantile: float
    timestamp_tolerance_frames: float
    limit_tolerance: Mapping[str, float]
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


def calibrate(
    outcomes: Sequence[ReplayOutcome],
    quantile: float = 0.99,
    *,
    frames: Sequence[EpisodeFrames],
    layout: ActionLayout,
    kinematic_quantile: float = 1.0,
) -> ReplayThresholds:
    """Thresholds from clean episodes: dynamic ones at `quantile` of the outcomes whose
    replay succeeded, kinematic ones at `kinematic_quantile` of `frames`."""
    passed = [o for o in outcomes if o.success]
    if not passed or not frames:
        raise ValueError("calibration needs successful replays and clean frames")
    groups = sorted({g for o in passed for g in o.state_error_by_group})
    offsets = [abs(o.hand_event_offset_steps) for o in passed
               if o.hand_event_offset_steps is not None]
    kin = _kinematic(frames, layout, kinematic_quantile)
    return ReplayThresholds(
        version=f"{VERSION}@uncommitted",
        kinematic_quantile=kinematic_quantile,
        timestamp_tolerance_frames=TIMESTAMP_TOLERANCE_FRAMES,
        min_std=MIN_STD,
        dynamic_quantile=quantile,
        state_error={
            g: _q([o.state_error_by_group[g] for o in passed if g in o.state_error_by_group],
                  quantile)
            for g in groups
        },
        hand_event_offset_steps=math.ceil(_q(offsets, quantile)) if offsets else 0,
        **kin,
    )


def _kinematic(
    frames: Sequence[EpisodeFrames], layout: ActionLayout, q: float
) -> dict[str, Any]:
    dims = joint_dims(layout, frames[0].states.shape[1])
    group = {i: layout.dimensions[i].group for i in dims}
    limit = {
        array: max(LIMIT_FLOOR, _q([float(past_limits(getattr(f, array), layout, dims).max())
                                    for f in frames], q))
        for array in ARRAYS
    }
    ratios: dict[str, list[float]] = {}
    corr: dict[int, list[float]] = {}
    for f in frames:
        by_group: dict[str, float] = {}
        for i, r in spread_ratios(f, dims, MIN_STD).items():
            by_group[group[i]] = max(by_group.get(group[i], 0.0), r)
        for g, r in by_group.items():
            ratios.setdefault(g, []).append(r)
        for i, c in correlations(f, dims, MIN_STD).items():
            corr.setdefault(i, []).append(c)
    return {
        "limit_tolerance": limit,
        "unit_ratio": {g: _q(v, q) for g, v in ratios.items()},
        "mapping_correlation": {
            layout.dimensions[i].name: min(_q(v, 1.0 - q), MAPPING_CEILING)
            for i, v in sorted(corr.items())
            if len(v) >= MIN_EPISODES
        },
    }


def dump_thresholds(th: ReplayThresholds, calibration: str) -> str:
    """replay.yaml text of calibrated thresholds; load_thresholds reads it back."""
    data = {
        "version": th.version.split("@")[0],
        "calibration": calibration,
        "kinematic": {
            "quantile": th.kinematic_quantile,
            "timestamp_tolerance_frames": th.timestamp_tolerance_frames,
            "limit_tolerance": _rounded(th.limit_tolerance, up=True),
            "unit_ratio": _rounded(th.unit_ratio, up=True),
            "min_std": th.min_std,
            "mapping_correlation": _rounded(th.mapping_correlation, up=False),
        },
        "dynamic": {
            "quantile": th.dynamic_quantile,
            "state_error": _rounded(th.state_error, up=True),
            "hand_event_offset_steps": th.hand_event_offset_steps,
        },
    }
    return str(yaml.safe_dump(data, sort_keys=False, width=100))


def _q(values: Sequence[float], q: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=np.float64), q))


def _rounded(values: Mapping[str, float], *, up: bool) -> dict[str, float]:
    """6 significant digits, rounded away from the clean data so that it still passes:
    up for a ceiling, down for a floor."""
    return {k: _round(v, up) for k, v in values.items()}


def _round(value: float, up: bool) -> float:
    if value == 0.0:
        return 0.0
    step = 10.0 ** (math.floor(math.log10(abs(value))) - 5)
    out = float(f"{(math.ceil if up else math.floor)(value / step) * step:.6g}")
    if up and out < value:
        out = float(f"{out + step:.6g}")
    if not up and out > value:
        out = float(f"{out - step:.6g}")
    return out

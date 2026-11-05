"""Kinematic replay of one episode: the recorded frames checked as joint positions (DA-17 AC 1).

Design 6.3 sets `qpos` from the recorded state frame by frame. What that shows
without a renderer is read here straight from `EpisodeFrames`, on CPU, in the
lane (03 section 7.3; no MuJoCo):

    timestamp_offset  |timestamp * fps - frame_index| above tolerance: the state
                      clock moved against the video, whose frame k is at k / fps
    joint_limit       action or state past a joint limit of the action layout
    unit_deg_rad      a joint in degrees: a value past 2 pi (no G1 joint turns that
                      far) that fits the limits once divided by 180 / pi, or an
                      action that moves `unit_ratio` times more than its state
    joint_mapping     a joint's action that does not follow its state: correlation
                      under `mapping_correlation` (a sign flip turns it negative)

A joint that jumps between two frames (D3) is not a replay issue: design 6.3 lists
none for the kinematic mode, and QA's `action_jump` flags it.

The joints are the layout dimensions with limits that the 32-D `states` also
holds at the same index: G1's 0-30 (hands, arms, waist; DA-01, and the tray
export's STATE_SLICES), where `states` 28-30 are the waist joints in the order
of action 28-30. Dimensions 31-35 are WBC commands and are not joints.

Every issue lists its frames by `frame_index`; `joint_mapping` is a property
of the whole episode and lists none. Self-collision (story AC 1) needs the
robot's geometry, so it is left to the adapter and not checked here.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from flywheel.contracts.artifacts import ActionLayout, ReplayIssue, ReplayReport
from flywheel.data.ingest.lerobot import EpisodeFrames
from numpy.typing import NDArray

if TYPE_CHECKING:
    from flywheel.data.replay_check.thresholds import ReplayThresholds

DEG_PER_RAD = 180.0 / math.pi
FULL_TURN = 2.0 * math.pi


def joint_dims(layout: ActionLayout, state_width: int) -> list[int]:
    """Action dimensions that are joints the states hold at the same index."""
    return [
        i
        for i, d in enumerate(layout.dimensions)
        if i < state_width and not d.masked and d.limit_low is not None
    ]


def check_kinematic(
    frames: EpisodeFrames,
    layout: ActionLayout,
    th: ReplayThresholds,
    *,
    episode_id: str,
    fps: float,
) -> ReplayReport:
    """The kinematic ReplayReport of one episode; an episode under 2 frames has no issue
    here (QA rejects it by `min_frames`)."""
    issues: list[ReplayIssue] = []
    if len(frames.timestamp) >= 2:
        issues += _timestamp(frames, fps, th)
        dims = joint_dims(layout, frames.states.shape[1])
        for array in ("action", "states"):
            issues += _limits(frames, layout, dims, array, th)
        issues += _units(frames, layout, dims, th)
        issues += _mapping(frames, layout, dims, th)
    return ReplayReport(episode_id=episode_id, mode="kinematic", issues=issues)


def correlations(frames: EpisodeFrames, dims: list[int], min_std: float) -> dict[int, float]:
    """Correlation of each joint's action with its state, where both move by min_std."""
    out: dict[int, float] = {}
    for i in dims:
        a = frames.action[:, i].astype(np.float64)
        s = frames.states[:, i].astype(np.float64)
        if a.std() > min_std and s.std() > min_std:
            out[i] = float(np.corrcoef(a, s)[0, 1])
    return out


def spread_ratios(frames: EpisodeFrames, dims: list[int], min_std: float) -> dict[int, float]:
    """std(action) / std(state) of each joint whose state moves by min_std."""
    out: dict[int, float] = {}
    for i in dims:
        s = float(frames.states[:, i].astype(np.float64).std())
        if s > min_std:
            out[i] = float(frames.action[:, i].astype(np.float64).std()) / s
    return out


def past_limits(
    values: NDArray[np.float32], layout: ActionLayout, dims: list[int]
) -> NDArray[np.float64]:
    """(T, len(dims)) rad past the layout limits, 0 inside them."""
    return _past(values[:, dims].astype(np.float64), layout, dims)


def _timestamp(frames: EpisodeFrames, fps: float, th: ReplayThresholds) -> list[ReplayIssue]:
    off = np.abs(frames.timestamp * fps - frames.frame_index)
    bad = ~(off <= th.timestamp_tolerance_frames)  # NaN counts as off
    if not bad.any():
        return []
    worst = float(np.nanmax(off)) if np.isfinite(off).any() else math.nan
    detail = (
        f"timestamp off frame_index/fps by up to {worst:.3g} frames at {int(bad.sum())}"
        f" frames (tolerance {th.timestamp_tolerance_frames})"
    )
    return [_issue("timestamp_offset", frames, bad, detail)]


def _limits(
    frames: EpisodeFrames,
    layout: ActionLayout,
    dims: list[int],
    array: str,
    th: ReplayThresholds,
) -> list[ReplayIssue]:
    values = frames.action if array == "action" else frames.states
    past = past_limits(values, layout, dims)
    bad = past > th.limit_tolerance[array]
    if not bad.any():
        return []
    named = [
        f"{layout.dimensions[dims[j]].name} by {past[:, j].max():.3g}"
        for j in np.flatnonzero(bad.any(axis=0))
    ]
    detail = f"{array} past the joint limits (tolerance {th.limit_tolerance[array]} rad): "
    return [_issue("joint_limit", frames, bad.any(axis=1), detail + ", ".join(named))]


def _units(
    frames: EpisodeFrames, layout: ActionLayout, dims: list[int], th: ReplayThresholds
) -> list[ReplayIssue]:
    issues = []
    for array in ("action", "states"):
        x = (frames.action if array == "action" else frames.states)[:, dims].astype(np.float64)
        fits = _past(x / DEG_PER_RAD, layout, dims).max(axis=0) <= th.limit_tolerance[array]
        turned = (np.abs(x) > FULL_TURN).any(axis=0) & fits
        if turned.any():
            names = [layout.dimensions[dims[j]].name for j in np.flatnonzero(turned)]
            rows = (np.abs(x[:, turned]) > FULL_TURN).any(axis=1)
            detail = f"{array} past 2 pi rad, inside the limits in degrees: {', '.join(names)}"
            issues.append(_issue("unit_deg_rad", frames, rows, detail))
    ratios = spread_ratios(frames, dims, th.min_std)
    groups = {i: layout.dimensions[i].group for i in ratios}
    high = {i: r for i, r in ratios.items() if r > th.unit_ratio.get(groups[i], math.inf)}
    if high:
        named = [f"{layout.dimensions[i].name} {r:.3g}x" for i, r in high.items()]
        detail = "action moves more than its state by std(action)/std(state): " + ", ".join(named)
        issues.append(ReplayIssue(code="unit_deg_rad", frames=[], detail=detail))
    return issues


def _mapping(
    frames: EpisodeFrames, layout: ActionLayout, dims: list[int], th: ReplayThresholds
) -> list[ReplayIssue]:
    low = {}
    for i, r in correlations(frames, dims, th.min_std).items():
        name = layout.dimensions[i].name
        if name in th.mapping_correlation and not r >= th.mapping_correlation[name]:
            low[name] = (r, th.mapping_correlation[name])
    if not low:
        return []
    named = [f"{name} {r:.3g} (min {floor:.3g})" for name, (r, floor) in low.items()]
    detail = "action does not follow its state, correlation: " + ", ".join(named)
    return [ReplayIssue(code="joint_mapping", frames=[], detail=detail)]


def _issue(
    code: str, frames: EpisodeFrames, rows: NDArray[np.bool_] | np.bool_, detail: str
) -> ReplayIssue:
    picked = frames.frame_index[np.asarray(rows, dtype=bool)]
    return ReplayIssue(code=code, frames=[int(f) for f in picked], detail=detail)


def _past(x: NDArray[np.float64], layout: ActionLayout, dims: list[int]) -> NDArray[np.float64]:
    low = np.array([layout.dimensions[i].limit_low for i in dims], dtype=np.float64)
    high = np.array([layout.dimensions[i].limit_high for i in dims], dtype=np.float64)
    past: NDArray[np.float64] = np.maximum(np.maximum(low - x, x - high), 0.0)
    return past

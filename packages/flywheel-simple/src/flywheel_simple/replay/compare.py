"""A replayed episode against its recording: one line of replay_outcomes.jsonl (DA-17 AC 2).

Pure numpy, so it runs without SIMPLE. The replay gives the joint positions
after each recorded action; the recording holds the state before it, so the
state after action k is compared with recorded state k + 1.

Only the joints are compared: `states` 0-30 of SIMPLE's psi0 layout (hands 0-13,
arms 14-27, waist 28-30, the dims of `tray.export.STATE_SLICES` plus the waist).
State 31 is the last base height command, not a measurement. The error of a
group is the largest |replayed - recorded| over its joints and the frames both
cover.

A hand closes at the first frame its mean joint travel from the episode's first
frame reaches half of the largest travel in the recording; a hand that never
travels HAND_MIN_TRAVEL rad in the recording has no event (psi-data's left hand,
docs/g0/psi-data.md). A replayed hand that never gets there counts as closing
at the end of the replay, so the offset is a lower bound then.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

GROUPS: dict[str, range] = {"hand": range(0, 14), "arm": range(14, 28), "torso_rpy": range(28, 31)}
HANDS: dict[str, range] = {"left": range(0, 7), "right": range(7, 14)}
JOINTS = 31
HAND_MIN_TRAVEL = 0.2  # rad, mean over the hand's 7 joints


def outcome(
    episode_index: int,
    recorded: NDArray[np.floating[Any]],
    replayed: NDArray[np.floating[Any]],
    success: bool,
) -> dict[str, Any]:
    """recorded: (T, >=31) states; replayed: (N, 31) joints after each action."""
    rec = np.asarray(recorded, dtype=np.float64)[:, :JOINTS]
    rep = np.asarray(replayed, dtype=np.float64).reshape(-1, JOINTS)
    n = min(len(rep), len(rec) - 1)
    after = rec[1 : n + 1]
    gap = np.abs(rep[:n] - after)
    errors: dict[str, float] = {}
    peaks: dict[str, int] = {}
    for group, dims in GROUPS.items():
        per_frame = gap[:, dims].max(axis=1) if n else np.zeros(0)
        errors[group] = round(float(per_frame.max()), 6) if n else 0.0
        peaks[group] = int(per_frame.argmax()) + 1 if n else 0
    return {
        "episode_index": int(episode_index),
        "success": bool(success),
        "state_error_by_group": errors,
        "hand_event_offset_steps": hand_event_offset(rec, rep[:n]),
        "state_error_peak_frame_by_group": peaks,
        "replayed_frames": int(len(rep)),
        "recorded_frames": int(len(rec)),
    }


def hand_event_offset(
    recorded: NDArray[np.float64], replayed: NDArray[np.float64]
) -> int | None:
    """Replayed minus recorded frame of the hand event with the largest gap, or None."""
    offsets: list[int] = []
    for dims in HANDS.values():
        start = recorded[0, dims]
        travel = np.abs(recorded[:, dims] - start).mean(axis=1)
        if travel.max() < HAND_MIN_TRAVEL:
            continue
        level = travel.max() / 2
        at = int(np.argmax(travel >= level))
        moved = np.abs(replayed[:, dims] - start).mean(axis=1) if len(replayed) else np.zeros(0)
        hits = np.flatnonzero(moved >= level)
        # replayed[k] is frame k + 1 of the recording
        offsets.append((int(hits[0]) + 1 if len(hits) else len(replayed) + 1) - at)
    return max(offsets, key=abs) if offsets else None


def joint_order(qpos_names: Sequence[str], state_names: Sequence[str]) -> list[int]:
    """Index into the sim's joint vector of each of the 31 state joints, by name."""
    position = {name: i for i, name in enumerate(qpos_names)}
    missing = [n for n in state_names[:JOINTS] if n not in position]
    if missing:
        raise KeyError(f"sim joints lack {missing}; it has {list(qpos_names)}")
    return [position[n] for n in state_names[:JOINTS]]


def base_yaw(quat_wxyz: Sequence[float] | NDArray[np.floating[Any]]) -> float:
    """Yaw about world z of a MuJoCo `xquat` (w, x, y, z), in rad."""
    w, x, y, z = (float(v) for v in np.asarray(quat_wxyz, dtype=np.float64)[:4])
    return float(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))

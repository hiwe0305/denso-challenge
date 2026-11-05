"""Re-deriving the recording's lag from a replay and its parent (DA-35 task 9)."""

from __future__ import annotations

import numpy as np
from flywheel_simple.tray.s2.leads import best_shift, derive_lags
from flywheel_simple.tray.s2.parents import HAND_LEAD, NAV_LEAD, ParentDemo
from test_s2_replay import recorded


def replayed(parent: ParentDemo, lags: dict[str, int]) -> ParentDemo:
    """What an exact replay with the current leads records if the pipeline lags by `lags`."""
    n = parent.frames

    def played(values: np.ndarray, lead: int, lag: int) -> np.ndarray:
        # step t sends frame t + lead; the recording at t shows what was sent at t - lag
        idx = np.clip(np.arange(n) + lead - lag, 0, n - 1)
        return values[idx]

    nav = parent.navigate.copy()
    for k, name in enumerate(("vx", "vy", "vyaw", "target_yaw")):
        nav[:, k] = played(parent.navigate[:, k], NAV_LEAD[k], lags[name])
    return ParentDemo(
        **{
            **parent.__dict__,
            "eef": played(parent.eef, 0, lags["wrists"]),
            "navigate": nav,
            "hands_closed": played(parent.hands_closed, HAND_LEAD, lags["hands"]),
        }
    )


def varied() -> ParentDemo:
    """The replay test's demo with sticks that change every frame."""
    parent = recorded()
    t = np.arange(parent.frames) * 0.02
    nav = np.stack([0.3 * np.sin(t), 0.1 * np.cos(1.3 * t), 0.5 * np.sin(0.7 * t), 0.01 * t], 1)
    return ParentDemo(**{**parent.__dict__, "navigate": nav})


def test_the_current_leads_come_back_from_a_replay_with_those_lags() -> None:
    parent = varied()
    lags = {"wrists": 0, "hands": 1, "vx": 2, "vy": 2, "vyaw": 1, "target_yaw": 2}
    assert derive_lags(replayed(parent, lags), parent) == lags


def test_a_different_lag_is_found() -> None:
    parent = varied()
    lags = {"wrists": 1, "hands": 1, "vx": 3, "vy": 2, "vyaw": 1, "target_yaw": 2}
    assert derive_lags(replayed(parent, lags), parent)["vx"] == 3
    assert derive_lags(replayed(parent, lags), parent)["wrists"] == 1


def test_a_channel_that_never_changes_has_no_lag() -> None:
    flat = np.zeros((100, 1))
    assert best_shift(flat, flat) is None

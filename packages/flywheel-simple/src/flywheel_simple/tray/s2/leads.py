"""Re-derive how many steps the recording lags the operator's signals (DA-35 task 9).

The replay operator sends each channel of frame `t + lead` at step `t`
(flywheel_simple.tray.s2.parents.HAND_LEAD, NAV_LEAD). A recording made at step
`t` shows what was sent `lag` steps earlier, so an exact replay records parent
frame `t + lead - lag` there. Comparing a replay with its parent at shifts
`s = -max_shift .. max_shift` and taking the shift that matches best gives
`lag = lead - s`; with the right leads every channel matches at `s = 0`.

The sticks and hands are played open loop, so they match exactly at the right
shift however far the replayed body drifts. A channel that does not change over
the compared frames tells nothing; its lag is None.

Pure numpy: runs in the workspace.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.s2.parents import HAND_LEAD, NAV_LEAD, ParentDemo

SKIP = 3  # frames at each end left out: activation, and the end of the recording
CHANNELS: Mapping[str, tuple[str, slice, int]] = {
    # name: (ParentDemo field, columns, lead the replay used)
    "wrists": ("eef", slice(0, 14), 0),
    "hands": ("hands_closed", slice(0, 2), HAND_LEAD),
    "vx": ("navigate", slice(0, 1), NAV_LEAD[0]),
    "vy": ("navigate", slice(1, 2), NAV_LEAD[1]),
    "vyaw": ("navigate", slice(2, 3), NAV_LEAD[2]),
    "target_yaw": ("navigate", slice(3, 4), NAV_LEAD[3]),
}


def best_shift(
    recorded: NDArray[np.float64], parent: NDArray[np.float64], max_shift: int = 3
) -> int | None:
    """The shift `s` with recorded[t] closest to parent[t + s]; None if it is not unique."""
    n = min(len(recorded), len(parent))
    lo, hi = SKIP + max_shift, n - SKIP - max_shift
    if hi <= lo:
        return None
    errors = {
        s: float(np.abs(recorded[lo:hi] - parent[lo + s : hi + s]).mean())
        for s in range(-max_shift, max_shift + 1)
    }
    best = min(errors.values())
    winners = [s for s, e in errors.items() if e == best]
    return winners[0] if len(winners) == 1 else None


def derive_lags(
    replay: ParentDemo, parent: ParentDemo, max_shift: int = 3
) -> dict[str, int | None]:
    """Each channel's lag (steps) measured on one exact replay of `parent`."""
    out: dict[str, int | None] = {}
    for name, (field, cols, lead) in CHANNELS.items():
        a = np.asarray(getattr(replay, field)[:, cols], dtype=np.float64)
        b = np.asarray(getattr(parent, field)[:, cols], dtype=np.float64)
        shift = best_shift(a, b, max_shift)
        out[name] = None if shift is None else lead - shift
    return out

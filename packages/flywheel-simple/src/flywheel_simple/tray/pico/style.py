"""Motion-style metrics of teleop trajectories, to set the virtual operator's style ranges.

Pure numpy over sampled trajectories (positions in metres, `dt` in seconds).
The measuring script computes wrist and elbow positions by forward kinematics
from the authors' human PICO teleop (psi-data) and summarises these metrics per
episode; the virtual operator then draws its per-episode style inside the
measured ranges (DA-35 AC 2, 8).

A movement segment is a stretch where a point moves faster than `on` m/s,
ended when it drops below `off` (hysteresis), lasting at least `min_s`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]

SEGMENT_ON = 0.05  # m/s
SEGMENT_OFF = 0.03  # m/s
SEGMENT_MIN_S = 0.2


def _smooth_valid(x: Array, window: int) -> Array:
    """Moving average along axis 0, valid part only (a straight line stays straight)."""
    if window <= 1:
        return np.asarray(x, np.float64)
    kernel = np.ones(window) / window
    x2 = np.asarray(x, np.float64).reshape(len(x), -1)
    out = np.stack([np.convolve(x2[:, k], kernel, mode="valid") for k in range(x2.shape[1])], 1)
    return out.reshape((out.shape[0], *np.shape(x)[1:]))


def speeds(pos: Array, dt: float, smooth: int = 5) -> Array:
    """Speed per sample of a (T, 3) path, smoothed over `smooth` samples; same length T."""
    p = _smooth_valid(pos, smooth)
    v = np.linalg.norm(np.gradient(p, dt, axis=0), axis=1)
    lead = (smooth - 1) // 2 if smooth > 1 else 0
    return np.pad(v, (lead, len(pos) - len(v) - lead), mode="edge")


def movement_segments(
    speed: Array,
    dt: float,
    on: float = SEGMENT_ON,
    off: float = SEGMENT_OFF,
    min_s: float = SEGMENT_MIN_S,
) -> list[tuple[int, int]]:
    """(start, end) index pairs, end exclusive, of movements lasting at least `min_s`."""
    out: list[tuple[int, int]] = []
    start: int | None = None
    for i, v in enumerate(speed):
        if start is None and v > on:
            start = i
        elif start is not None and v < off:
            if (i - start) * dt >= min_s:
                out.append((start, i))
            start = None
    if start is not None and (len(speed) - start) * dt >= min_s:
        out.append((start, len(speed)))
    return out


def segment_shape(pos: Array, speed: Array, seg: tuple[int, int], dt: float) -> dict[str, float]:
    """Peak speed, duration, path length, curvature and when the peak comes, for one segment.

    Curvature is the largest distance of the path from its chord over the chord
    length (0 for a straight reach). `peak_time_frac` is 0.5 for a symmetric
    bell-shaped speed profile such as min-jerk.
    """
    i0, i1 = seg
    p, v = np.asarray(pos[i0:i1], np.float64), np.asarray(speed[i0:i1], np.float64)
    chord = p[-1] - p[0]
    chord_len = float(np.linalg.norm(chord))
    if chord_len > 1e-9:
        u = chord / chord_len
        rel = p - p[0]
        off_line = rel - np.outer(rel @ u, u)
        curvature = float(np.linalg.norm(off_line, axis=1).max() / chord_len)
    else:
        curvature = float("nan")
    return {
        "peak_speed": float(v.max()),
        "duration": (i1 - i0) * dt,
        "length": float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()),
        "curvature": curvature,
        "peak_time_frac": float(np.argmax(v) / max(len(v) - 1, 1)),
    }


def pauses(still: NDArray[np.bool_], dt: float, min_s: float = 0.3) -> list[float]:
    """Durations of runs of `still` lasting at least `min_s`."""
    out: list[float] = []
    run = 0
    for s in list(np.asarray(still, bool)) + [False]:
        if s:
            run += 1
        else:
            if run * dt >= min_s - 1e-9:
                out.append(round(run * dt, 6))
            run = 0
    return out


def jerk_rms(pos: Array, dt: float, smooth: int = 9) -> float:
    """RMS of the third derivative of a (T, 3) path (m/s^3), after smoothing."""
    p = _smooth_valid(pos, smooth)
    if len(p) < 4:
        return 0.0
    j = np.gradient(np.gradient(np.gradient(p, dt, axis=0), dt, axis=0), dt, axis=0)
    return float(np.sqrt(np.mean(np.sum(j**2, axis=1))))


def band_fraction(signal: Array, dt: float, lo: float, hi: float) -> float:
    """Fraction of the (Hann-windowed, mean-removed) power between `lo` and `hi` Hz."""
    x = np.asarray(signal, np.float64).reshape(len(signal), -1)
    x = (x - x.mean(axis=0)) * np.hanning(len(x))[:, None]
    power = (np.abs(np.fft.rfft(x, axis=0)) ** 2).sum(axis=1)[1:]
    freqs = np.fft.rfftfreq(len(x), dt)[1:]
    total = float(power.sum())
    if total <= 1e-18:
        return 0.0
    return float(power[(freqs >= lo) & (freqs <= hi)].sum() / total)


def percentiles(values: Sequence[float]) -> dict[str, Any]:
    """n, p10, p50, p90 of the finite values."""
    v = np.asarray([x for x in values if np.isfinite(x)], np.float64)
    if len(v) == 0:
        return {"n": 0}
    p10, p50, p90 = np.percentile(v, [10, 50, 90])
    return {"n": int(len(v)), "p10": float(p10), "p50": float(p50), "p90": float(p90)}

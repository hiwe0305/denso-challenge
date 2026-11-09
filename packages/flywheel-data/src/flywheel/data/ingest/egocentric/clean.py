"""Cleaning of the E-A pose before it is written (DA-04 task 10, 9/11/2026).

The E-A job (`estimate_job.py`) gives one hand pose per frame and a camera track from
monocular VO. On the team's tray clips the stage 1 export made from it had 41.6 % of
its normalized actions clipped at +-1 (EgoDex 2.2 %; docs/he/stage1.md 2.7). Offline,
only these steps together brought it under 5 % (2.8):

    frame     the hands in each frame's camera frame, `camera` the identity: the VO
              track is not a measurement (translation a fixed step, rotation drifting)
    flip      MediaPipe sometimes gives a mirrored hand for a frame; the wrist axes
              (`estimate_job.wrist_frame`, signs fixed by the landmarks) then turn by
              pi, mostly about y (81 % of 1052 flips on the 153 tray clips). Each frame
              is turned pi about a wrist axis when that brings it more than `flip_deg`
              closer to the previous seen frame. Then the whole track gets one sign by
              two votes of its seen frames: fingertips on the palm side (+z for a right
              hand, -z for a left one) and fingers along +y; the one pi turn (about x,
              y or z) that satisfies both is applied. Forcing the chirality frame by
              frame was tried and gave more flips (6.4 % of steps instead of 4.9 %).
              A pi turn of the whole track leaves every delta unchanged.
              The tips are points and are not turned: on the tray clips 14.9 % of seen
              frames keep their fingertips on the wrong side of the cleaned wrist frame
              (33 % of the frames the cleaning turned, 8 % of the others; median 2.6 cm
              off the palm plane). Reflecting those tips in depth about the wrist, along
              the camera ray, was tried and made the export worse (4.0 % of actions
              clipped instead of 3.5 % with the other steps then in place).
    jumps     steps between seen frames (wrist position, wrist rotation, mean tip
              position) above median + `jump_mad` x MAD of the clip's steps (MAD x
              1.4826) cut each run of seen frames into pieces; a piece of at most
              `jump_burst` frames that is not the run's longest is bad and is replaced:
              position and tips linearly, rotation by slerp, between the nearest good
              frames of its run; a run edge holds the nearest good frame. A spike, a
              burst and an outlier first or last frame are caught; one real fast step
              splits a run into two long pieces and marks nothing. Review of PR 174: the
              first version marked the frame after each big step, which widened bursts
              and never judged a run's first frame. A centred-median (Hampel) test was
              tried and marked the ends of every moving run. Never dropped.
    smooth    Savitzky-Golay of order `savgol_order` over `savgol_window` frames on each
              run of seen frames: wrist position, tips, and wrist quaternion (signs made
              continuous, renormalized after). A run shorter than the window uses the
              longest odd window it holds; edges fit the polynomial to the first or last
              window, as scipy's `savgol_filter(mode="interp")`. On EgoDex, window 21
              kept most real motion: p90 of the 0.1 s wrist delta fell 4 % (2.8).

Parameters are `pose_ea.clean` of `configs/data/egocentric.yaml`. E-B (EgoDex tracking)
is never cleaned. Frames are never dropped or added: DA-18 reads the video and the pose
by the same frame index. A frame where a hand was not seen stays NaN.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from typing import Any

import numpy as np
from flywheel.data.ingest.egocentric.estimate import POSE_FRAMES
from flywheel.data.ingest.egocentric.pose import SIDES, EgoPose
from numpy.typing import NDArray

F64 = NDArray[np.float64]
# pi about the wrist's x, y, z: R @ FLIP keeps that axis and negates the other two
FLIPS = (np.diag([1.0, -1.0, -1.0]), np.diag([-1.0, 1.0, -1.0]), np.diag([-1.0, -1.0, 1.0]))
CHIRALITY = {"left": -1.0, "right": 1.0}  # side of the palm plane the fingertips are on


@dataclass(frozen=True)
class CleanParams:
    frame: str = "world"
    flip_deg: float | None = None  # None: no continuity guard, no track sign
    jump_mad: float | None = None  # None: no jump interpolation
    jump_burst: int = 4  # longest piece of frames the jump test may mark as bad
    savgol_window: int | None = None  # frames, odd; None: no smoothing
    savgol_order: int = 2

    def __post_init__(self) -> None:
        if self.frame not in POSE_FRAMES:
            raise ValueError(f"pose_ea.clean.frame {self.frame!r} is not one of {POSE_FRAMES}")
        if self.savgol_window is not None and (
                self.savgol_window % 2 == 0 or self.savgol_window <= self.savgol_order):
            raise ValueError(f"pose_ea.clean.savgol_window {self.savgol_window} must be odd and"
                             f" above savgol_order {self.savgol_order}")

    @classmethod
    def from_config(cls, pose_ea: Mapping[str, Any]) -> CleanParams:
        raw = dict(pose_ea.get("clean") or {})
        unknown = set(raw) - {f for f in cls.__dataclass_fields__}
        if unknown:
            raise ValueError(f"pose_ea.clean has unknown keys {sorted(unknown)}")
        return cls(**raw)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def angle(a: F64, b: F64) -> F64:
    """Rotation angle between rotation matrices, radians; broadcasts over leading axes."""
    cos = (np.trace(a @ np.swapaxes(b, -1, -2), axis1=-2, axis2=-1) - 1) / 2
    out: F64 = np.arccos(np.clip(cos, -1.0, 1.0))
    return out


def finite_frames(wrist: F64) -> NDArray[np.bool_]:
    return np.asarray(np.isfinite(wrist.reshape(len(wrist), -1)).all(axis=1))


def keep_continuous(rotations: F64, flip_deg: float) -> tuple[F64, int]:
    """(T, 3, 3) with NaN rows where the hand was not seen: each seen frame turned pi
    about a wrist axis when that is more than `flip_deg` closer to the previous seen
    (already turned) frame. Returns the rotations and how many frames were turned."""
    out = rotations.copy()
    seen = np.flatnonzero(np.isfinite(rotations.reshape(len(rotations), -1)).all(axis=1))
    turned = 0
    for previous, t in zip(seen, seen[1:]):
        candidates = np.stack([out[t], *(out[t] @ flip for flip in FLIPS)])
        gaps = angle(candidates, out[previous][None])
        best = int(np.argmin(gaps))
        if best and gaps[0] - gaps[best] > np.radians(flip_deg):
            out[t] = candidates[best]
            turned += 1
    return out, turned


def chirality(wrist: F64, tips: F64) -> F64:
    """(T,) +1 where the four fingertips (not the thumb) are on the +z side of the wrist
    frame, -1 on the -z side; NaN where the hand was not seen."""
    offset = tips[:, 1:] - wrist[:, None, :3, 3]
    out: F64 = np.sign(np.einsum("tfi,ti->t", offset, wrist[:, :3, 2]) / 4)
    return out


def pointing(wrist: F64, tips: F64) -> F64:
    """(T,) +1 where the four fingertips are on the +y side of the wrist (y runs from the
    wrist to the middle knuckle, so a real hand points along +y), -1 else; NaN unseen."""
    offset = tips[:, 1:] - wrist[:, None, :3, 3]
    out: F64 = np.sign(np.einsum("tfi,ti->t", offset, wrist[:, :3, 1]) / 4)
    return out


def majority(votes: F64, want: float) -> bool:
    """True when the seen frames' votes for `want` are at least those against."""
    votes = votes[np.isfinite(votes)]
    return bool(np.sum(votes == want) >= np.sum(votes == -want))


def one_sign(wrist: F64, tips: F64, side: str) -> tuple[F64, str]:
    """The whole track turned by the pi turn that gives it its side's chirality (z) and
    fingers along +y, each by a vote of the seen frames. Returns the track and the turn:
    "none", "x" (y and z were both wrong), "y" (z only) or "z" (y only)."""
    z_ok = majority(chirality(wrist, tips), CHIRALITY[side])
    y_ok = majority(pointing(wrist, tips), 1.0)
    turn = {(True, True): "none", (False, True): "y", (False, False): "x",
            (True, False): "z"}[(z_ok, y_ok)]
    if turn == "none":
        return wrist, turn
    out = wrist.copy()
    out[:, :3, :3] = wrist[:, :3, :3] @ FLIPS["xyz".index(turn)]
    return out, turn


def seen_runs(seen: NDArray[np.bool_]) -> list[tuple[int, int]]:
    """Half-open [start, stop) of each run of consecutive seen frames."""
    edges = np.diff(np.r_[0, seen.astype(np.int8), 0])
    return list(zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist()))


def to_quaternion(rotations: F64) -> F64:
    """(T, 3, 3) rotations to (T, 4) unit quaternions w, x, y, z (Shepperd's method)."""
    m = rotations
    trace = np.trace(m, axis1=-2, axis2=-1)
    candidates = np.stack([trace, m[:, 0, 0], m[:, 1, 1], m[:, 2, 2]], axis=1)
    choice = np.argmax(candidates, axis=1)
    q = np.empty((len(m), 4))
    for i, (r, k) in enumerate(zip(m, choice)):
        if k == 0:
            w = np.sqrt(max(1.0 + trace[i], 0.0)) / 2
            q[i] = [w, (r[2, 1] - r[1, 2]) / (4 * w), (r[0, 2] - r[2, 0]) / (4 * w),
                    (r[1, 0] - r[0, 1]) / (4 * w)]
        else:
            a = k - 1
            b, c = (a + 1) % 3, (a + 2) % 3
            v = np.sqrt(max(1.0 + r[a, a] - r[b, b] - r[c, c], 0.0)) / 2
            q[i, 0] = (r[c, b] - r[b, c]) / (4 * v)
            q[i, 1 + a] = v
            q[i, 1 + b] = (r[b, a] + r[a, b]) / (4 * v)
            q[i, 1 + c] = (r[c, a] + r[a, c]) / (4 * v)
    out: F64 = q / np.linalg.norm(q, axis=1, keepdims=True)
    return out


def to_rotation(q: F64) -> F64:
    """(T, 4) quaternions w, x, y, z (normalized here) to (T, 3, 3) rotations."""
    w, x, y, z = (q / np.linalg.norm(q, axis=1, keepdims=True)).T
    out: F64 = np.stack([
        np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
        np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
        np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1),
    ], axis=1)
    return out


def slerp(a: F64, b: F64, u: float) -> F64:
    """Unit quaternion between `a` (u = 0) and `b` (u = 1) on the shorter arc."""
    if np.dot(a, b) < 0:
        b = -b
    cos = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if cos > 1 - 1e-9:
        out: F64 = (1 - u) * a + u * b
    else:
        theta = np.arccos(cos)
        out = (np.sin((1 - u) * theta) * a + np.sin(u * theta) * b) / np.sin(theta)
    return out / np.linalg.norm(out)


def big_steps(wrist: F64, tips: F64, k: float) -> NDArray[np.bool_]:
    """(T,) True at frame t when the step from t - 1 (both seen) is above median + k x
    1.4826 x MAD of the clip's steps, in wrist position, wrist rotation or mean tip
    position."""
    seen = finite_frames(wrist) & finite_frames(tips)
    steps = np.flatnonzero(seen[1:] & seen[:-1]) + 1
    big = np.zeros(len(wrist), dtype=bool)
    if len(steps) < 3:
        return big
    sizes = (
        np.linalg.norm(wrist[steps, :3, 3] - wrist[steps - 1, :3, 3], axis=1),
        angle(wrist[steps, :3, :3], wrist[steps - 1, :3, :3]),
        np.linalg.norm(tips[steps] - tips[steps - 1], axis=2).mean(axis=1),
    )
    for size in sizes:
        median = np.median(size)
        mad = 1.4826 * np.median(np.abs(size - median)) + 1e-9
        big[steps[size > median + k * mad]] = True
    return big


def jump_frames(wrist: F64, tips: F64, k: float, burst: int) -> NDArray[np.bool_]:
    """(T,) True for the frames of a piece of at most `burst` frames that big steps
    (`big_steps`) cut off from the rest of its run of seen frames, unless the piece is
    the run's longest. A spike, a burst of up to `burst` frames and an outlier at either
    end of a run are caught; one real fast step only splits a run into two long pieces
    and marks nothing."""
    big = big_steps(wrist, tips, k)
    bad = np.zeros(len(wrist), dtype=bool)
    for start, stop in seen_runs(finite_frames(wrist) & finite_frames(tips)):
        edges = [start, *(t for t in range(start + 1, stop) if big[t]), stop]
        pieces = list(zip(edges, edges[1:]))
        longest = max(pieces, key=lambda piece: piece[1] - piece[0])
        for a, b in pieces:
            if (a, b) != longest and b - a <= burst:
                bad[a:b] = True
    return bad


def interpolate(wrist: F64, tips: F64, bad: NDArray[np.bool_]) -> tuple[F64, F64, int]:
    """Bad frames rebuilt from the nearest good frames of their run; edges hold."""
    wrist, tips = wrist.copy(), tips.copy()
    done = 0
    for start, stop in seen_runs(finite_frames(wrist)):
        frames = np.arange(start, stop)
        good = frames[~bad[start:stop]]
        fix = frames[bad[start:stop]]
        if len(good) < 2 or not len(fix):
            continue
        for column in range(3):
            wrist[fix, column, 3] = np.interp(fix, good, wrist[good, column, 3])
        flat = tips.reshape(len(tips), -1)
        for column in range(flat.shape[1]):
            flat[fix, column] = np.interp(fix, good, flat[good, column])
        quats = to_quaternion(wrist[good, :3, :3])
        for t in fix:
            after = int(np.searchsorted(good, t))
            if after == 0 or after == len(good):  # before the first or after the last
                q = quats[0 if after == 0 else -1]
            else:
                a, b = good[after - 1], good[after]
                q = slerp(quats[after - 1], quats[after], (t - a) / (b - a))
            wrist[t, :3, :3] = to_rotation(q[None])[0]
        done += len(fix)
    return wrist, tips, done


def fitted_window(window: int, frames: int) -> int:
    """The longest odd window up to `window` that `frames` hold."""
    return min(window, frames if frames % 2 else frames - 1)


def savgol(values: F64, window: int, order: int) -> F64:
    """Savitzky-Golay along axis 0 of (T, ...), as scipy's `savgol_filter(mode="interp")`:
    the least-squares polynomial of `order` over `window` frames, evaluated at the centre;
    the first and last `window // 2` frames from the fit to the first or last window.
    `window` shrinks to the longest odd length T holds; no change when that is at most
    `order + 1` (the fit goes through every point)."""
    t = len(values)
    window = fitted_window(window, t)
    if window <= order + 1:
        same: F64 = np.array(values, dtype=np.float64)
        return same
    half = window // 2
    vander = np.vander(np.arange(window) - half, order + 1, increasing=True).astype(np.float64)
    hat = vander @ np.linalg.pinv(vander)  # fitted values from the window's values
    flat = values.reshape(t, -1)
    out = np.empty_like(flat)
    windows = np.lib.stride_tricks.sliding_window_view(flat, window, axis=0)  # (n, d, w)
    out[half:t - half] = windows @ hat[half]
    out[:half] = hat[:half] @ flat[:window]
    out[t - half:] = hat[window - half:] @ flat[t - window:]
    result: F64 = out.reshape(values.shape)
    return result


def continuous_signs(q: F64) -> F64:
    """Quaternions with each sign chosen to be nearest the previous one."""
    out: F64 = np.array(q, dtype=np.float64)
    for t in range(1, len(out)):
        if np.dot(out[t], out[t - 1]) < 0:
            out[t] = -out[t]
    return out


def smooth(wrist: F64, tips: F64, window: int, order: int) -> tuple[F64, F64, int]:
    """Savitzky-Golay on each run of seen frames; returns how many runs changed."""
    wrist, tips = wrist.copy(), tips.copy()
    changed = 0
    for start, stop in seen_runs(finite_frames(wrist)):
        if fitted_window(window, stop - start) <= order + 1:
            continue
        span = slice(start, stop)
        wrist[span, :3, 3] = savgol(wrist[span, :3, 3], window, order)
        tips[span] = savgol(tips[span], window, order)
        q = savgol(continuous_signs(to_quaternion(wrist[span, :3, :3])), window, order)
        wrist[span, :3, :3] = to_rotation(q)
        changed += 1
    return wrist, tips, changed


def clean_pose(pose: EgoPose, params: CleanParams) -> tuple[EgoPose, dict[str, Any]]:
    """The cleaned pose and what was done, for `bundle.json` `pose_cleaning`."""
    values = {name: np.asarray(getattr(pose, name), np.float64) for name in (
        "left_wrist", "right_wrist", "left_tips", "right_tips")}
    report: dict[str, Any] = {"params": params.to_dict()}
    for side in SIDES:
        wrist, tips = values[f"{side}_wrist"], values[f"{side}_tips"]
        done: dict[str, Any] = {"seen_frames": int(finite_frames(wrist).sum())}
        if params.flip_deg is not None:
            wrist = wrist.copy()
            wrist[:, :3, :3], done["flipped_frames"] = keep_continuous(wrist[:, :3, :3],
                                                                       params.flip_deg)
            wrist, done["track_turn"] = one_sign(wrist, tips, side)
        if params.jump_mad is not None:
            wrist, tips, done["interpolated_frames"] = interpolate(
                wrist, tips, jump_frames(wrist, tips, params.jump_mad, params.jump_burst))
        if params.savgol_window is not None:
            wrist, tips, done["smoothed_runs"] = smooth(wrist, tips, params.savgol_window,
                                                        params.savgol_order)
        values[f"{side}_wrist"], values[f"{side}_tips"] = wrist, tips
        report[side] = done
    cleaned = replace(pose, **{k: v.astype(np.float32) for k, v in values.items()})
    return cleaned, report

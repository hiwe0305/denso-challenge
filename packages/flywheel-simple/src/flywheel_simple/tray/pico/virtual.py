"""Pieces of the virtual PICO operator that do not need the tray planner (DA-35 task 5).

The virtual operator takes its intent (wrist targets, walking, hand closure)
from DA-33's TrayPlanner and plays it into SIMPLE's PICO pipeline the way a
person with a headset would. Three pieces sit between the two:

- `robot_to_teleop` inverts decoupled_wbc's `WristsPreProcessor`, so a wrist
  target in the robot model's frame becomes the controller pose that PICO would
  have to send for the pipeline to produce it (`teleop_to_robot` is the forward
  map, kept for tests and as documentation).
- `StyleFollower` makes a target stream move like a person: a second-order
  follower (velocity peaks early, overshoot and correction when underdamped), a
  bow perpendicular to the remaining distance (curved paths), and a small
  4-12 Hz tremor. Parameters are drawn per episode by `sample_style`, inside the
  ranges measured on the authors' human teleop (docs/g0/tray/virtual-teleop.md).
- `JoystickShaper` limits how fast the walking command changes, as a thumb on
  a stick does.

Pure numpy: runs in the workspace.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]

# Per-episode style ranges [Đề xuất], from the human p10-p90 (virtual-teleop.md).
STYLE_RANGES: dict[str, tuple[float, float]] = {
    "omega": (5.0, 12.0),  # rad/s, follower natural frequency: lag 80-200 ms
    "zeta": (0.65, 1.0),  # damping: up to ~7 % overshoot, then a correction
    "curvature": (0.05, 0.4),  # bow per metre still to go
    "tremor_mm": (0.5, 2.0),  # amplitude of the 4-12 Hz tremor
    # m/s^2 of the walking command: the human p10-p90 is 0.15-1.8; below 0.5 the
    # planner's 0.12 m/s corrective steps at table B came too late (DA-35 task 6).
    "joystick_accel": (0.5, 1.8),
    "arc_seed": (0.0, 2 * math.pi),  # direction of the bow around the motion
    # rad/s of the right stick when turning: the human 0.45-1.0 capped at 0.75, as faster
    # turns tilt the carried tray (DA-35 task 6). Drawn last, so earlier draws keep their values.
    "turn_rate": (0.45, 0.75),
}
TREMOR_BAND = (5.0, 11.0)  # Hz, inside the measured 4-12 Hz band
TREMOR_PARTIALS = 3
SUBSTEPS = 4


def teleop_to_robot(
    ctrl: Array, ee0: Array, ctrl0: Array, scale: float, align: Array | None = None
) -> Array:
    """decoupled_wbc's WristsPreProcessor: controller pose -> wrist target, robot frame.

    `ee0` is the calibration wrist pose, `ctrl0` the controller pose at
    activation, `scale` the model's teleop motion scale; `align` is the
    controller-to-wrist rotation (identity for PICO).
    """
    a = np.eye(4) if align is None else align
    m = np.linalg.inv(a) @ np.linalg.inv(ctrl0) @ ctrl @ a
    m[:3, 3] *= scale
    out: Array = ee0 @ m
    return out


def robot_to_teleop(
    robot: Array, ee0: Array, ctrl0: Array, scale: float, align: Array | None = None
) -> Array:
    """Inverse of `teleop_to_robot`: the controller pose that yields wrist target `robot`."""
    a = np.eye(4) if align is None else align
    m = np.linalg.inv(ee0) @ robot
    m[:3, 3] /= scale
    out: Array = ctrl0 @ a @ m @ np.linalg.inv(a)
    return out


@dataclass(frozen=True)
class Style:
    omega: float
    zeta: float
    curvature: float
    tremor_mm: float
    joystick_accel: float
    arc_seed: float
    turn_rate: float


def style_seed_for(base: int, level: int, seed: int, attempt: int) -> int:
    """The style seed of one attempt: another style per attempt, the same on a rerun."""
    return int(np.random.SeedSequence([base, level, seed, attempt]).generate_state(1)[0])


def sample_style(seed: int) -> Style:
    """One episode's style, uniform inside STYLE_RANGES; the same seed gives the same style."""
    rng = np.random.default_rng(seed)
    values = {name: float(rng.uniform(lo, hi)) for name, (lo, hi) in STYLE_RANGES.items()}
    return Style(**{f.name: values[f.name] for f in fields(Style)})


class StyleFollower:
    """Follows a 3-D target stream with one episode's style; one call per control step."""

    def __init__(self, style: Style, dt: float, seed: int = 0) -> None:
        self.style = style
        self.dt = dt
        rng = np.random.default_rng(seed)
        self._freqs = rng.uniform(*TREMOR_BAND, size=(TREMOR_PARTIALS, 3))
        self._phases = rng.uniform(0, 2 * math.pi, size=(TREMOR_PARTIALS, 3))
        self._arc = np.array([0.0, math.cos(style.arc_seed), math.sin(style.arc_seed)])
        self.x: Array = np.zeros(3)
        self.v: Array = np.zeros(3)
        self.t = 0.0

    def reset(self, start: Array) -> None:
        self.x = np.asarray(start, np.float64).copy()
        self.v = np.zeros(3)
        self.t = 0.0

    def _bow(self, target: Array) -> Array:
        e = target - self.x
        dist = float(np.linalg.norm(e))
        if dist < 1e-9 or self.style.curvature == 0.0:
            return np.zeros(3)
        u = e / dist
        p = self._arc - (self._arc @ u) * u
        if np.linalg.norm(p) < 1e-6:  # bow direction along the motion: use another axis
            p = np.array([0.0, 0.0, 1.0]) - u[2] * u
        out: Array = self.style.curvature * dist * p / np.linalg.norm(p)
        return out

    def step(self, target: Array) -> Array:
        target = np.asarray(target, np.float64)
        w, z, h = self.style.omega, self.style.zeta, self.dt / SUBSTEPS
        for _ in range(SUBSTEPS):  # semi-implicit Euler
            ref = target + self._bow(target)
            self.v = self.v + h * (w * w * (ref - self.x) - 2 * z * w * self.v)
            self.x = self.x + h * self.v
        self.t += self.dt
        amp = self.style.tremor_mm / 1000 / math.sqrt(TREMOR_PARTIALS)
        tremor = amp * np.sin(2 * math.pi * self._freqs * self.t + self._phases).sum(axis=0)
        out: Array = self.x + tremor
        return out


class JoystickShaper:
    """Rate-limits one walking command channel to `accel` per second."""

    def __init__(self, accel: float, dt: float) -> None:
        self.accel = accel
        self.dt = dt
        self.value = 0.0

    def reset(self, value: float = 0.0) -> None:
        self.value = value

    def step(self, target: float) -> float:
        limit = self.accel * self.dt
        self.value += float(np.clip(target - self.value, -limit, limit))
        return self.value


TURN_FLAG = 0.1  # rad/s: G1GearWbcPolicy turns only while |vyaw| reaches this


def _wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


class YawStick:
    """The right stick's yaw as PICO turns it into `navigate_cmd[2:4]`, steered closed loop.

    PicoStreamer integrates `target_yaw += vyaw * dt` from the stick, and the lower
    body turns towards `target_yaw` (not towards the operator's wish) only while
    |vyaw| >= TURN_FLAG. Pushing the stick by the body's error let `target_yaw`
    run away from the heading, after which pushing back turned the body the wrong
    way (level 1 seed 20: no progress for 10 s). So once the body is `engage` off
    the heading, the operator steers `target_yaw` to `lead` x error (at most
    `engage`) beyond the heading, at `gain` x the gap, between `rate_min` and
    `rate_max` (near the goal the stick dithers at `rate_min`, keeping the flag
    up), and lets go once the body is within `release` and the target within
    `engage` of its goal. `target_yaw` stays next to the heading.
    """

    def __init__(
        self,
        dt: float,
        rate_max: float,
        gain: float = 2.0,
        rate_min: float = 0.12,
        engage: float = math.radians(2.0),
        release: float = math.radians(0.5),
        lead: float = 0.5,
    ) -> None:
        if rate_min < TURN_FLAG:
            raise ValueError(f"rate_min {rate_min} would not raise the turn flag")
        self.dt, self.rate_max, self.gain = dt, rate_max, gain
        self.rate_min, self.engage, self.release, self.lead = rate_min, engage, release, lead
        self.target_yaw = 0.0
        self._pushing = False
        self._direction = 0.0

    def reset(self) -> None:
        """PicoStreamer starts every episode at target yaw 0 (the robot spawns at yaw 0)."""
        self.target_yaw = 0.0
        self._pushing = False
        self._direction = 0.0

    def step(self, heading: float, yaw: float, steer: bool = True) -> tuple[float, float]:
        """(vyaw, target_yaw) for this control step; `steer` False lets go of the stick."""
        if not steer:
            self._pushing, self._direction = False, 0.0
            return 0.0, self.target_yaw
        error = _wrap(heading - yaw)
        lead = max(-self.engage, min(self.engage, self.lead * error))
        gap = _wrap(heading + lead - self.target_yaw)
        # Let go only with both the body and the target there: the body passes the
        # heading on its way to a target left further out.
        if self._pushing and abs(error) < self.release and abs(gap) < self.engage:
            self._pushing = False
        elif not self._pushing and abs(error) > self.engage:
            self._pushing = True
        vyaw = 0.0
        if self._pushing:
            # A turn near 180 degrees keeps the way it started: the wrapped gap
            # flips sign with the body's first wobble.
            if abs(gap) <= math.pi / 2 or self._direction == 0.0:
                self._direction = math.copysign(1.0, gap)
            speed = min(self.rate_max, max(self.rate_min, self.gain * abs(gap)))
            vyaw = self._direction * speed
        else:
            self._direction = 0.0
        self.target_yaw = _wrap(self.target_yaw + vyaw * self.dt)
        return vyaw, self.target_yaw


# PICO closes a Dex3 hand in one of three fixed grasps (decoupled_wbc's
# G1GripperInverseKinematicsSolver): trigger -> index, trigger + grip -> middle,
# grip -> ring. PicoStreamer encodes the choice as one fingertip moved onto the thumb.
GRASP_FINGERTIP = {"trigger": 9, "trigger_grip": 14, "grip": 19}
THUMB_TIP = 4


def pico_fingers(closed: bool, grasp: str = "trigger_grip") -> NDArray[np.float64]:
    """PicoStreamer's 25 x 4 x 4 fingertip array: thumb open, `grasp`'s finger closed or not."""
    tips = np.zeros((25, 4, 4))
    tips[THUMB_TIP, 0, 3] = 1.0
    if closed:
        tips[GRASP_FINGERTIP[grasp], 0, 3] = 1.0
    return tips

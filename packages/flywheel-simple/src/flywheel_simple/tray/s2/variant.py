"""An S2 variant's references: a parent demo moved onto a new condition, MimicGen style (task 10).

The scene of a condition differs from the parent's by where the tray stands on
table A and where the target zone lies on table B (level 1 jitters both by up
to 5 cm and 10 degrees; level 0 is the default scene). Two planar transforms
of the world carry the parent over:

- `T_K = T_tray_new * T_tray_parent^-1` for segment K: what the hands did
  relative to the tray, they now do relative to the new tray;
- `T_P = T_target_new * T_target_parent^-1` for segment P, relative to the
  target zone.

One transform per frame moves both the parent's base path and its wrists in the
world. It is the identity until the parent starts walking to table A, grows to
`T_K` along that walk (by the share of the path walked), stays `T_K` through K,
turns into `T_P` along the carry to table B, and stays `T_P` through P. The base
reference is the transformed base path; the lower body is steered onto it
(flywheel_simple.tray.s2.replay). The wrists keep the parent's robot-frame
targets while the robot walks and follow the transformed world targets while
the hands reach for and grasp the tray, or place it (the anchors of
flywheel_simple.tray.s2.segments);
at every change of anchor they blend over `stitch_s` (position interpolated,
rotation slerped) so the switch from one frame to the other is smooth.

Pure numpy: runs in the workspace.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.geometry import Pose2D
from flywheel_simple.tray.planner import rpy_matrix
from flywheel_simple.tray.predicates import quat_to_mat
from flywheel_simple.tray.randomize import EpisodeSample
from flywheel_simple.tray.s2.parents import ParentDemo
from flywheel_simple.tray.s2.segments import FPS, Segmentation

Array = NDArray[np.float64]


def wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


@dataclass(frozen=True)
class Planar:
    """A rigid motion of the world in the floor plane: rotate by `yaw` about z, then shift."""

    dx: float = 0.0
    dy: float = 0.0
    yaw: float = 0.0

    @staticmethod
    def between(old: Pose2D, new: Pose2D) -> Planar:
        """The motion that takes a frame at `old` to `new` (new * old^-1)."""
        yaw = wrap(new.yaw - old.yaw)
        c, s = math.cos(yaw), math.sin(yaw)
        return Planar(new.x - (c * old.x - s * old.y), new.y - (s * old.x + c * old.y), yaw)

    @staticmethod
    def of_matrix(m: Array) -> Planar:
        """The planar part of a 4 x 4 world motion (shift in x, y; turn about z)."""
        return Planar(float(m[0, 3]), float(m[1, 3]), math.atan2(float(m[1, 0]), float(m[0, 0])))

    def matrix(self) -> Array:
        out = np.eye(4)
        out[:3, :3] = rpy_matrix(0.0, 0.0, self.yaw)
        out[:3, 3] = [self.dx, self.dy, 0.0]
        return out

    def lerp(self, other: Planar, s: float) -> Planar:
        return Planar(
            self.dx + s * (other.dx - self.dx),
            self.dy + s * (other.dy - self.dy),
            self.yaw + s * wrap(other.yaw - self.yaw),
        )

    def as_dict(self) -> dict[str, float]:
        return {"dx": self.dx, "dy": self.dy, "yaw_deg": math.degrees(self.yaw)}


def pose_matrix(pose: Array) -> Array:
    """A 7-wide pose row (position, quaternion wxyz) as 4 x 4."""
    out = np.eye(4)
    out[:3, :3] = quat_to_mat(pose[3:7])
    out[:3, 3] = pose[:3]
    return out


def base_frame(pose: Array) -> Array:
    """The robot frame S2 moves the wrists in: pelvis position and yaw, no roll or pitch.

    DA-33's planner made the parents' wrist targets in this frame (base_transform),
    so the parent's hands sway with the pelvis as they did there; with the full
    pelvis pose the world-anchored targets would shake with every step's roll.
    """
    out = np.eye(4)
    out[:3, :3] = rpy_matrix(0.0, 0.0, yaw_of(pose))
    out[:3, 3] = pose[:3]
    return out


def yaw_of_matrix(m: Array) -> float:
    return math.atan2(float(m[1, 0]), float(m[0, 0]))


def yaw_of(pose: Array) -> float:
    w, x, y, z = (float(v) for v in pose[3:7])
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def stitch_for(gen_seed: int, low: float, high: float) -> float:
    """A variant's blend time at anchor switches, drawn from its generation seed."""
    return float(np.random.default_rng(gen_seed).uniform(low, high))


def condition_distance(parent: EpisodeSample, new: EpisodeSample) -> dict[str, float]:
    """How far the new condition's tray and target lie from the parent's (m, degrees)."""
    out = {}
    for name in ("tray_pose", "target_pose"):
        a, b = getattr(parent, name), getattr(new, name)
        out[f"{name[:-5]}_m"] = round(math.hypot(b.x - a.x, b.y - a.y), 4)
        out[f"{name[:-5]}_deg"] = round(math.degrees(abs(wrap(b.yaw - a.yaw))), 2)
    return out


def _progress(base_xy: Array, start: int, end: int) -> Array:
    """0..1 over frames [start, end]: the share of the base path walked (time if it stood)."""
    steps = np.linalg.norm(np.diff(base_xy[start : end + 1], axis=0), axis=1)
    total = float(steps.sum())
    if end <= start:
        return np.ones(1)
    if total < 1e-6:
        return np.linspace(0.0, 1.0, end - start + 1)
    out: Array = np.r_[0.0, np.cumsum(steps)] / total
    return out


def _ramp(n: int, at: int, frames: int, up: bool) -> Array:
    """0 before `at`, rising to 1 over `frames` (falling from 1 when not `up`)."""
    x = np.clip((np.arange(n) - at + 1) / max(frames, 1), 0.0, 1.0)
    return x if up else 1.0 - x


@dataclass(frozen=True)
class VariantPlan:
    """Per-frame references of one variant (arrays over the parent's frames)."""

    parent: ParentDemo
    cut: Segmentation
    t_k: Planar
    t_p: Planar
    stitch_s: float
    transforms: tuple[Planar, ...]  # of the base path
    anchors: tuple[Planar, ...]  # of the tray and target zone: T_K through K, T_P after
    base_ref: Array  # (T, 3): x, y, yaw, world
    wrist_world: Array  # (T, 2, 4, 4): transformed world wrist targets
    world_weight: Array  # (T,): 0 robot-frame targets, 1 world targets
    yaw_rate: Array  # (T,): rad/s at which the transform turns (added to the parent's vyaw)
    gates: tuple[int, ...]  # frames at which the replay waits for the base

    @property
    def frames(self) -> int:
        return self.parent.frames

    def meta(self) -> dict[str, Any]:
        return {
            "t_k": self.t_k.as_dict(),
            "t_p": self.t_p.as_dict(),
            "stitch_s": round(self.stitch_s, 3),
            "gates": list(self.gates),
        }


def plan_variant(
    parent: ParentDemo,
    cut: Segmentation,
    parent_sample: EpisodeSample,
    new_sample: EpisodeSample,
    stitch_s: float,
) -> VariantPlan:
    """The references that replay `parent` on `new_sample`'s scene."""
    n = parent.frames
    t_k = Planar.between(parent_sample.tray_pose, new_sample.tray_pose)
    t_p = Planar.between(parent_sample.target_pose, new_sample.target_pose)
    bases = [base_frame(parent.base_pose[i]) for i in range(n)]

    # The base keeps the parent's path through K; after the lift it moves so that the tray,
    # held T_K off the parent's grip, comes down at the target moved by T_P.
    lift = int(cut.step_frames[2] or cut.k_end)
    # The new grip in the robot frame: from the lift on, the tray sits `grip` x the
    # parent's tray pose relative to the body (C = B_lift^-1 T_K^-1 B_lift, constant).
    grip = np.linalg.inv(bases[lift]) @ np.linalg.inv(t_k.matrix()) @ bases[lift]
    carry = np.zeros(n)
    s_c = _progress(parent.base_pose[:, :2], cut.k_end, cut.place_start)
    carry[cut.k_end : cut.place_start + 1] = s_c[: min(len(s_c), n - cut.k_end)]
    carry[cut.place_start :] = 1.0
    identity = Planar()
    transforms = []
    for i in range(n):
        if i < cut.k_end:
            transforms.append(identity)
            continue
        world_grip = bases[i] @ grip @ np.linalg.inv(bases[i])  # where the body is at i
        transforms.append(
            identity.lerp(Planar.of_matrix(t_p.matrix() @ world_grip), float(carry[i]))
        )
    anchors = tuple(t_k if i < cut.k_end else t_p for i in range(n))

    base_ref = np.zeros((n, 3))
    wrist_world = np.zeros((n, 2, 4, 4))
    for i, (tf, anchor) in enumerate(zip(transforms, anchors)):
        pelvis = tf.matrix() @ bases[i]
        base_ref[i] = [pelvis[0, 3], pelvis[1, 3], wrap(yaw_of(parent.base_pose[i]) + tf.yaw)]
        anchored = anchor.matrix() @ bases[i]
        if not parent.eef[i].any():  # the activation frame has no wrist data
            wrist_world[i] = anchored
            continue
        for k, off in enumerate((0, 7)):
            wrist_world[i, k] = anchored @ pose_matrix(parent.eef[i, off : off + 7])

    # World anchors: the tray while reaching and grasping, the target from place_start on.
    blend = max(1, round(stitch_s * FPS))
    world_weight = np.minimum(
        _ramp(n, cut.reach_start, blend, up=True), _ramp(n, cut.grasp_end, blend, up=False)
    )
    world_weight = np.maximum(world_weight, _ramp(n, cut.place_start, blend, up=True))

    yaws = np.array([tf.yaw for tf in transforms])
    yaw_rate = np.r_[np.diff(np.unwrap(yaws)), 0.0] * FPS
    return VariantPlan(
        parent=parent,
        cut=cut,
        t_k=t_k,
        t_p=t_p,
        stitch_s=stitch_s,
        transforms=tuple(transforms),
        anchors=anchors,
        base_ref=base_ref,
        wrist_world=wrist_world,
        world_weight=world_weight,
        yaw_rate=yaw_rate,
        gates=(cut.place_start,),
    )

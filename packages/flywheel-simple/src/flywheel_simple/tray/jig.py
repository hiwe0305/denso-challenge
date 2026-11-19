"""Fixed target with a locating jig on table B (DA-41, docs/g0/tray/jig.md).

Until DA-41 the target pose on table B was jittered by +-5 cm and +-10 degrees at
levels 1-2 and shown only as a flat rectangle that the carried tray hides on the way
in. Here the target is fixed to table B, and four low corner guides with chamfered
inner faces stand around it on a thin low-friction slide pad: a tray lowered a few
centimetres off centre lands on a slope and slides into place. Without the pad the
far edge grips the steel table (friction 1.0) harder than the 45-degree slope pushes,
and a dropped tray stays propped on the slope.

The guides and the pad are geoms of the `table_b` body, not a body of their own:
the step tracker counts a tray as on table B by its contacts with that body
(`simple_task.tray_state`), so a tray resting on the pad or against a guide is on B.
The pad is invisible, so the target zone under it shows as before.

Everything here is added beside the scene of DA-32/33, not into it. `randomize.py`,
`mjcf.py`, `simple_task.py` and `configs/sim/tray.yaml` stay byte for byte as the
frozen DA-34 run plans pin them, so their evals keep running on the scene they were
frozen with. `sample_jig_episode` takes the episode of `sample_episode` (same tray
pose, spawn, part mass and light for a seed) and only swaps the target.

Pure logic down to `add_jig`; MuJoCo is imported lazily, as in mjcf.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.config import TrayConfig, find_config, load_flat_config
from flywheel_simple.tray.geometry import Pose2D, rect_corners, scene_geometry_with_gap
from flywheel_simple.tray.mjcf import Visuals, task_scene_spec
from flywheel_simple.tray.randomize import EpisodeSample, sample_episode

JIG_CONFIG_RELPATH = Path("configs/sim/tray_jig.yaml")
# Appended to visuals_revision for scenes with the jig (recorder.visuals_revision).
# Bump whenever the jig's look or place changes.
JIG_REVISION = "jig1"
# Blue: apart from the orange zone, the green crate and the grey steel table.
JIG_RGBA = (0.05, 0.40, 0.95, 1.0)
JIG_PRIORITY = 1  # above the tray's 0: tray-on-guide contacts take the guide's friction
# Seeds the slot choice apart from the episode's stream (np.random.default_rng([seed, 41])),
# so slots never shift the tray pose, spawn, mass or light of a seed.
SLOT_STREAM = 41


@dataclass(frozen=True)
class JigConfig:
    clearance: float
    height: float
    chamfer_deg: float
    thickness: float
    side_arm: float
    end_arm: float
    handle_gap: float
    friction: float
    pad_thickness: float
    slots: int
    slot_spacing: float

    @staticmethod
    def default_path() -> Path:
        return find_config(JIG_CONFIG_RELPATH)

    @classmethod
    def load(cls, path: Path | None = None) -> JigConfig:
        return load_flat_config(cls, path or cls.default_path())

    @property
    def chamfer(self) -> float:
        return math.radians(self.chamfer_deg)

    @property
    def lead_in(self) -> float:
        """Off-centre distance per axis that still lands the tray on a guide's slope."""
        return self.clearance + self.height * math.tan(self.chamfer)

    def check(self, cfg: TrayConfig) -> list[str]:
        """Reasons this jig does not fit the tray of `cfg`; empty when it does."""
        problems = []
        if self.slots not in (1, 2, 3):
            problems.append(f"slots must be 1, 2 or 3, got {self.slots}")
        if not 0.0 <= self.chamfer_deg < 60.0:
            problems.append(f"chamfer_deg must be in [0, 60), got {self.chamfer_deg}")
        if self.pad_thickness < 0 or self.pad_thickness >= self.height:
            problems.append(f"pad_thickness must be in [0, height), got {self.pad_thickness}")
        if min(self.clearance, self.height, self.thickness, self.side_arm, self.end_arm) <= 0:
            problems.append("clearance, height, thickness and arms must be positive")
        handle_edge = cfg.handle_length / 2 + self.handle_gap
        if cfg.tray_width / 2 - self.end_arm < handle_edge:
            problems.append(
                f"end_arm {self.end_arm} reaches within handle_gap of the handles "
                f"(|x| < {handle_edge:.3f})"
            )
        if self.side_arm > cfg.tray_length / 2:
            problems.append(f"side_arm {self.side_arm} is longer than half the tray")
        handle_bottom = cfg.tray_height - cfg.handle_thickness
        if self.height >= handle_bottom:
            problems.append(f"height {self.height} reaches the handles ({handle_bottom:.3f})")
        return problems


# -- target ------------------------------------------------------------------


def slot_offsets(jig: JigConfig) -> list[float]:
    """y offsets of the jig positions from table B's default target, centred."""
    return [(k - (jig.slots - 1) / 2) * jig.slot_spacing for k in range(jig.slots)]


def jig_target_pose(cfg: TrayConfig, jig: JigConfig, table_gap: float, seed: int) -> Pose2D:
    """Target pose on table B: the default pose for `table_gap`, or a slot when slots > 1."""
    base = scene_geometry_with_gap(cfg, table_gap).target_pose
    if jig.slots == 1:
        return base
    k = int(np.random.default_rng([seed, SLOT_STREAM]).integers(jig.slots))
    return Pose2D(base.x, base.y + slot_offsets(jig)[k], base.yaw)


def with_jig_target(cfg: TrayConfig, jig: JigConfig, sample: EpisodeSample) -> EpisodeSample:
    """`sample` with its target moved onto the jig; every other field as it was."""
    return replace(sample, target_pose=jig_target_pose(cfg, jig, sample.table_gap, sample.seed))


def sample_jig_episode(cfg: TrayConfig, jig: JigConfig, level: int, seed: int) -> EpisodeSample:
    """Deterministic episode for (level, seed) on the jig scene: target fixed to table B."""
    return with_jig_target(cfg, jig, sample_episode(cfg, level, seed))


# -- guides ------------------------------------------------------------------


@dataclass(frozen=True)
class GuideBox:
    """One slanted guide arm: a box in the jig frame (origin on the table top)."""

    name: str
    half: tuple[float, float, float]  # along the arm, thickness, slant length
    pos: tuple[float, float, float]
    rot: NDArray[np.float64]  # 3 x 3, columns: arm axis, thickness axis, slant axis

    def corners(self) -> NDArray[np.float64]:
        """(8, 3) corners in the jig frame."""
        signs = np.array([[i, j, k] for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)], float)
        return np.asarray(np.array(self.pos) + (signs * np.array(self.half)) @ self.rot.T)


def _arm(
    name: str,
    jig: JigConfig,
    normal: tuple[float, float],
    edge: float,
    centre: float,
    length: float,
) -> GuideBox:
    """Arm on the footprint side with outward `normal`, the side `edge` from the centre.

    `centre` is the arm's middle on the jig axis the side runs along (y for a long
    side, x for a short end). The inner face's bottom edge lies `clearance` outside
    the side on the table top; the face leans outward by the chamfer up to `height`.
    """
    z = np.array([0.0, 0.0, 1.0])
    n = np.array([normal[0], normal[1], 0.0])
    a = np.array([abs(normal[1]), abs(normal[0]), 0.0])  # +x or +y, along the side
    th, t = jig.chamfer, jig.thickness
    slant = jig.height / math.cos(th)
    up = math.sin(th) * n + math.cos(th) * z  # inner face, rising
    out = math.cos(th) * n - math.sin(th) * z  # into the guide
    bottom_inner = (edge + jig.clearance) * n + centre * a
    middle = bottom_inner + up * slant / 2 + out * t / 2
    rot = np.column_stack([a, out, up])
    if np.linalg.det(rot) < 0:  # keep it a rotation: flip the arm axis
        rot[:, 0] *= -1
    pos = (float(middle[0]), float(middle[1]), float(middle[2]))
    return GuideBox(name, (length / 2, t / 2, slant / 2), pos, rot)


def guide_boxes(cfg: TrayConfig, jig: JigConfig) -> list[GuideBox]:
    """The eight guide arms, two per corner, in the jig frame."""
    hx, hy = cfg.tray_width / 2, cfg.tray_length / 2
    c = jig.clearance
    boxes = []
    for sx, sy, corner in ((1, 1, "pp"), (1, -1, "pn"), (-1, 1, "np"), (-1, -1, "nn")):
        # Long side (x = sx * hx): from side_arm inside the corner out to the end clearance.
        lo, hi = hy - jig.side_arm, hy + c
        side = _arm(f"jig_{corner}_side", jig, (sx, 0.0), hx, sy * (lo + hi) / 2, hi - lo)
        # Short end (y = sy * hy): from end_arm inside the corner out to the side clearance.
        lo, hi = hx - jig.end_arm, hx + c
        end = _arm(f"jig_{corner}_end", jig, (0.0, sy), hy, sx * (lo + hi) / 2, hi - lo)
        boxes += [side, end]
    return boxes


def jig_footprint(cfg: TrayConfig, jig: JigConfig) -> tuple[float, float]:
    """Outer (x, y) extent of the guides on the table, centred on the target."""
    pts = np.concatenate([b.corners() for b in guide_boxes(cfg, jig)])
    return (2 * float(np.max(np.abs(pts[:, 0]))), 2 * float(np.max(np.abs(pts[:, 1]))))


def jig_on_table(cfg: TrayConfig, jig: JigConfig, table_gap: float) -> bool:
    """Every slot's guides lie on table B."""
    geo = scene_geometry_with_gap(cfg, table_gap)
    half = np.array([cfg.table_depth, cfg.table_length]) / 2
    size = jig_footprint(cfg, jig)
    base = geo.target_pose
    for dy in slot_offsets(jig):
        corners = rect_corners(Pose2D(base.x, base.y + dy, base.yaw), size)
        if not np.all(np.abs(corners - geo.table_b_center) <= half + 1e-9):
            return False
    return True


def rotation_quat(rot: NDArray[np.float64]) -> list[float]:
    """MuJoCo (w, x, y, z) quaternion of a 3 x 3 rotation matrix."""
    m = rot
    trace = float(m[0, 0] + m[1, 1] + m[2, 2])
    if trace > 0:
        s = 2.0 * math.sqrt(trace + 1.0)
        q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = 2.0 * math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
        q = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
    elif m[1, 1] > m[2, 2]:
        s = 2.0 * math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
        q = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
    else:
        s = 2.0 * math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
        q = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    return [float(v) for v in q]


# -- MuJoCo --------------------------------------------------------------------


def _mujoco() -> Any:
    import importlib

    return importlib.import_module("mujoco")


def _yaw_matrix(yaw: float) -> NDArray[np.float64]:
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def add_jig(spec: Any, cfg: TrayConfig, jig: JigConfig, pose: Pose2D, table_gap: float) -> None:
    """Guides `jig_*` and the slide pad `jig_pad` on body `table_b`, around `pose`."""
    problems = jig.check(cfg)
    if problems:
        raise ValueError("jig does not fit the tray: " + "; ".join(problems))
    mj = _mujoco()
    table = scene_geometry_with_gap(cfg, table_gap).table_b_center
    body = spec.body("table_b")
    yaw = _yaw_matrix(pose.yaw)
    origin = np.array([pose.x - table[0], pose.y - table[1], cfg.table_height])
    common = {
        "type": mj.mjtGeom.mjGEOM_BOX,
        "friction": [jig.friction, 0.005, 0.0001],
        "priority": JIG_PRIORITY,
        "condim": 3,
    }
    for box in guide_boxes(cfg, jig):
        body.add_geom(
            name=box.name,
            size=list(box.half),
            pos=list(origin + yaw @ np.array(box.pos)),
            quat=rotation_quat(yaw @ box.rot),
            rgba=list(JIG_RGBA),
            **common,
        )
    if jig.pad_thickness > 0:
        half = (
            cfg.tray_width / 2 + jig.clearance,
            cfg.tray_length / 2 + jig.clearance,
            jig.pad_thickness / 2,
        )
        body.add_geom(
            name="jig_pad",
            size=list(half),
            pos=list(origin + np.array([0.0, 0.0, jig.pad_thickness / 2])),
            quat=rotation_quat(yaw),
            rgba=[0.0, 0.0, 0.0, 0.0],
            **common,
        )


def jig_scene_spec(
    cfg: TrayConfig,
    jig: JigConfig,
    tray_pose: Pose2D | None = None,
    visuals: Visuals | None = None,
    table_gap: float | None = None,
    light_diffuse: float | None = None,
    target_pose: Pose2D | None = None,
) -> Any:
    """`mjcf.task_scene_spec` with the zone at the jig target and the jig on table B.

    The target defaults to the jig pose for `table_gap` (slot 0 of seed 0 when slots
    > 1; pass `target_pose` from `sample_jig_episode` for an episode).
    """
    gap = cfg.corridor if table_gap is None else table_gap
    target = target_pose or jig_target_pose(cfg, jig, gap, 0)
    spec = task_scene_spec(cfg, tray_pose, visuals, table_gap, light_diffuse, target)
    add_jig(spec, cfg, jig, target, gap)
    return spec


def write_jig_scene_mjcf(
    cfg: TrayConfig,
    jig: JigConfig,
    path: Path,
    tray_pose: Pose2D | None = None,
    visuals: Visuals | None = None,
    table_gap: float | None = None,
    light_diffuse: float | None = None,
    target_pose: Pose2D | None = None,
) -> Path:
    """Write jig_scene_spec as MJCF for SIMPLE's articulated actor (as mjcf.write_scene_mjcf)."""
    spec = jig_scene_spec(cfg, jig, tray_pose, visuals, table_gap, light_diffuse, target_pose)
    spec.compile()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(spec.to_xml())
    return path

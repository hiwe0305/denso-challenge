"""Tray, parts and tables as MuJoCo MjSpec, from TrayConfig (design 3.1).

Collision is built from boxes only. Optional SimReady meshes (flywheel_simple.tray.visuals)
dress the boxes as render-only geoms (contype 0, no mass); the boxes they cover move
to HIDDEN_GROUP, which default renderers do not draw. Handles and dividers stay
visible because the SimReady crate has neither.

World frame as in geometry.py; `tray_handle_left` is on the robot's left as it
faces table A. The tray body's origin is the centre of its underside.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from flywheel_simple.tray.config import TrayConfig
from flywheel_simple.tray.geometry import Pose2D, scene_geometry, scene_geometry_with_gap
from flywheel_simple.tray.visuals import (
    FitMode,
    VisualAsset,
    default_manifest_path,
    fit_box,
    load_manifest,
)

TIMESTEP = 0.005  # SIMPLE G1 tasks' physics_dt
SPAWN_GAP = 0.002  # parts above the tray floor, tray above the table top
VISUAL_GROUP = 2
HIDDEN_GROUP = 3
TRAY_RGBA = (0.25, 0.55, 0.30, 1.0)
HANDLE_RGBA = (0.15, 0.15, 0.17, 1.0)
PART_RGBA = (0.72, 0.72, 0.75, 1.0)
TABLE_RGBA = (0.60, 0.62, 0.65, 1.0)

Visuals = dict[str, list[VisualAsset]]


def _mujoco() -> Any:
    import importlib

    return importlib.import_module("mujoco")


@dataclass
class _Box:
    name: str
    half: tuple[float, float, float]
    pos: tuple[float, float, float]
    rgba: tuple[float, float, float, float]
    dressed: bool  # hidden when a visual mesh covers it


def _yaw_quat(yaw: float) -> list[float]:
    return [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]


def _tray_boxes(cfg: TrayConfig) -> list[_Box]:
    w, ln, h = cfg.tray_width, cfg.tray_length, cfg.tray_height
    t, f, d = cfg.tray_wall, cfg.tray_floor, cfg.tray_divider
    dh = cfg.divider_height_ratio * (h - f)
    boxes = [
        _Box("tray_base", (w / 2, ln / 2, f / 2), (0, 0, f / 2), TRAY_RGBA, True),
        _Box("tray_wall_px", (t / 2, ln / 2, h / 2), (w / 2 - t / 2, 0, h / 2), TRAY_RGBA, True),
        _Box("tray_wall_nx", (t / 2, ln / 2, h / 2), (-w / 2 + t / 2, 0, h / 2), TRAY_RGBA, True),
        _Box("tray_wall_py", (w / 2, t / 2, h / 2), (0, ln / 2 - t / 2, h / 2), TRAY_RGBA, True),
        _Box("tray_wall_ny", (w / 2, t / 2, h / 2), (0, -ln / 2 + t / 2, h / 2), TRAY_RGBA, True),
        # One divider along y splits the two columns, two along x split the three rows.
        _Box("tray_divider_0", (d / 2, ln / 2 - t, dh / 2), (0, 0, f + dh / 2), HANDLE_RGBA, False),
    ]
    for i, y in enumerate((-ln / 6, ln / 6), start=1):
        boxes.append(
            _Box(
                f"tray_divider_{i}",
                (w / 2 - t, d / 2, dh / 2),
                (0, y, f + dh / 2),
                HANDLE_RGBA,
                False,
            )
        )
    hl, hd, ht = cfg.handle_length / 2, cfg.handle_depth / 2, cfg.handle_thickness / 2
    for side, sign in (("left", 1.0), ("right", -1.0)):  # robot's left facing A (+x)
        boxes.append(
            _Box(
                f"tray_handle_{side}",
                (hl, hd, ht),
                (0, sign * (ln / 2 + hd), h - ht),
                HANDLE_RGBA,
                False,
            )
        )
    return boxes


class _Dresser:
    """Adds render-only meshes to a spec, one mesh asset per (asset, scale)."""

    def __init__(self, spec: Any, visuals: Visuals) -> None:
        self.spec, self.visuals = spec, visuals
        self._meshes: dict[tuple[str, tuple[float, ...]], str] = {}
        self._materials: dict[str, str] = {}

    def has(self, role: str) -> bool:
        return bool(self.visuals.get(role))

    def dress(
        self,
        body: Any,
        role: str,
        index: int,
        size: tuple[float, float, float],
        centre: tuple[float, float, float],
        mode: FitMode,
    ) -> None:
        mj = _mujoco()
        assets = self.visuals[role]
        asset = assets[index % len(assets)]
        fit = fit_box(asset, size, mode)
        key = (asset.asset, tuple(round(s, 9) for s in fit.scale))
        if key not in self._meshes:
            mesh = self.spec.add_mesh(
                name=f"vis_{asset.asset}_{len(self._meshes)}", file=str(asset.obj.resolve())
            )
            mesh.scale = list(fit.scale)
            mesh.inertia = mj.mjtMeshInertia.mjMESH_INERTIA_SHELL
            self._meshes[key] = mesh.name
        geom = body.add_geom(
            name=f"vis_{body.name}_{index}",
            type=mj.mjtGeom.mjGEOM_MESH,
            meshname=self._meshes[key],
            material=self._material(asset),
            pos=list(np.add(centre, fit.pos)),
            quat=_yaw_quat(fit.yaw),
            contype=0,
            conaffinity=0,
            group=VISUAL_GROUP,
            density=0,
        )
        del geom

    def _material(self, asset: VisualAsset) -> str:
        mj = _mujoco()
        if asset.asset not in self._materials:
            name = f"vis_{asset.asset}_mat"
            if asset.texture is not None:
                tex = self.spec.add_texture(
                    name=f"vis_{asset.asset}_tex",
                    type=mj.mjtTexture.mjTEXTURE_2D,
                    file=str(asset.texture.resolve()),
                )
                mat = self.spec.add_material(name=name)
                mat.textures[mj.mjtTextureRole.mjTEXROLE_RGB] = tex.name
            else:
                self.spec.add_material(name=name, rgba=list(asset.rgba))
            self._materials[asset.asset] = name
        return self._materials[asset.asset]


def _resolve(visuals: Visuals | None) -> Visuals:
    return load_manifest(default_manifest_path()) if visuals is None else visuals


def _add_box(body: Any, box: _Box, hidden: bool, friction: float, mass: float | None) -> None:
    mj = _mujoco()
    geom = body.add_geom(
        name=box.name,
        type=mj.mjtGeom.mjGEOM_BOX,
        size=list(box.half),
        pos=list(box.pos),
        rgba=list(box.rgba),
        group=HIDDEN_GROUP if hidden else 0,
        friction=[friction, 0.005, 0.0001],
        condim=4,
    )
    if mass is not None:
        geom.mass = mass


def add_tray(
    spec: Any, cfg: TrayConfig, pose: Pose2D, z: float, visuals: Visuals | None = None
) -> None:
    """Tray (free joint `tray_joint`, underside at `z`) and parts `part_0..5` in its compartments.

    Bodies go straight into `spec` rather than through MjSpec.attach, whose
    unnamed default class does not survive a round trip through XML.
    """
    visuals = _resolve(visuals)
    dresser = _Dresser(spec, visuals)
    quat = _yaw_quat(pose.yaw)
    tray = spec.worldbody.add_body(name="tray", pos=[pose.x, pose.y, z], quat=quat)
    tray.add_freejoint(name="tray_joint")
    boxes = _tray_boxes(cfg)
    volumes = [8 * b.half[0] * b.half[1] * b.half[2] for b in boxes]
    for box, vol in zip(boxes, volumes):
        hidden = box.dressed and dresser.has("tray")
        _add_box(tray, box, hidden, cfg.friction, cfg.tray_mass * vol / sum(volumes))
    if dresser.has("tray"):
        size = (cfg.tray_width, cfg.tray_length, cfg.tray_height)
        dresser.dress(tray, "tray", 0, size, (0, 0, cfg.tray_height / 2), "stretch")

    c, s = math.cos(pose.yaw), math.sin(pose.yaw)
    part_z = z + cfg.tray_floor + SPAWN_GAP + cfg.part_height / 2
    for i, (x, y) in enumerate(scene_geometry(cfg).compartment_centers):
        pos = [pose.x + c * x - s * y, pose.y + s * x + c * y, part_z]
        part = spec.worldbody.add_body(name=f"part_{i}", pos=pos, quat=quat)
        part.add_freejoint(name=f"part_{i}_joint")
        half = (cfg.part_size / 2, cfg.part_size / 2, cfg.part_height / 2)
        box = _Box(f"part_{i}_geom", half, (0, 0, 0), PART_RGBA, True)
        _add_box(part, box, dresser.has("part"), cfg.friction, cfg.part_mass)
        if dresser.has("part"):
            size = (cfg.part_size, cfg.part_size, cfg.part_height)
            dresser.dress(part, "part", i, size, (0, 0, 0), "uniform")


def add_tables(
    spec: Any, cfg: TrayConfig, visuals: Visuals | None = None, table_gap: float | None = None
) -> None:
    """Static tables `table_a` and `table_b`, `table_gap` apart: a top slab on four legs."""
    visuals = _resolve(visuals)
    dresser = _Dresser(spec, visuals)
    geo = scene_geometry_with_gap(cfg, cfg.corridor if table_gap is None else table_gap)
    d, ln, h = cfg.table_depth, cfg.table_length, cfg.table_height
    top, leg = cfg.table_top, cfg.table_leg
    hidden = dresser.has("table")
    for name, (cx, cy) in (("table_a", geo.table_a_center), ("table_b", geo.table_b_center)):
        body = spec.worldbody.add_body(name=name, pos=[float(cx), float(cy), 0.0])
        _add_box(
            body,
            _Box(f"{name}_top", (d / 2, ln / 2, top / 2), (0, 0, h - top / 2), TABLE_RGBA, True),
            hidden,
            cfg.friction,
            None,
        )
        lh = (h - top) / 2
        for k, (sx, sy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
            pos = (sx * (d / 2 - leg / 2), sy * (ln / 2 - leg / 2), lh)
            _add_box(
                body,
                _Box(f"{name}_leg_{k}", (leg / 2, leg / 2, lh), pos, TABLE_RGBA, True),
                hidden,
                cfg.friction,
                None,
            )
        if hidden:
            dresser.dress(body, "table", 0, (d, ln, h), (0, 0, h / 2), "stretch")


def task_scene_spec(
    cfg: TrayConfig,
    tray_pose: Pose2D | None = None,
    visuals: Visuals | None = None,
    table_gap: float | None = None,
    light_diffuse: float | None = None,
) -> Any:
    """Both tables and the tray with its parts on table A (default pose unless `tray_pose`).

    `light_diffuse` adds a directional light `tray_scene_light` over the scene.
    """
    mj = _mujoco()
    visuals = _resolve(visuals)
    spec = mj.MjSpec()
    spec.option.timestep = TIMESTEP
    add_tables(spec, cfg, visuals, table_gap)
    if light_diffuse is not None:
        spec.worldbody.add_light(
            name="tray_scene_light",
            pos=[0, 0, 3],
            dir=[0, 0, -1],
            castshadow=False,
            type=mj.mjtLightType.mjLIGHT_DIRECTIONAL,
            diffuse=[light_diffuse] * 3,
        )
    pose = tray_pose or scene_geometry(cfg).tray_pose
    add_tray(spec, cfg, pose, cfg.table_height + SPAWN_GAP, visuals)
    return spec


def static_scene_spec(cfg: TrayConfig, visuals: Visuals | None = None) -> Any:
    """task_scene_spec on a floor, under one light: the scene without a robot."""
    mj = _mujoco()
    spec = task_scene_spec(cfg, visuals=visuals)
    spec.worldbody.add_geom(
        name="floor", type=mj.mjtGeom.mjGEOM_PLANE, size=[5, 5, 0.1], rgba=[0.35, 0.37, 0.40, 1]
    )
    spec.worldbody.add_light(
        pos=[0, 0, 4], dir=[0, 0, -1], type=mj.mjtLightType.mjLIGHT_DIRECTIONAL
    )
    return spec


def write_scene_mjcf(
    cfg: TrayConfig,
    path: Path,
    tray_pose: Pose2D | None = None,
    visuals: Visuals | None = None,
    table_gap: float | None = None,
    light_diffuse: float | None = None,
) -> Path:
    """Write task_scene_spec as MJCF (absolute asset paths) for SIMPLE's articulated actor."""
    spec = task_scene_spec(cfg, tray_pose, visuals, table_gap, light_diffuse)
    spec.compile()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(spec.to_xml())
    return path

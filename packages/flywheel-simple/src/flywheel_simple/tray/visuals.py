"""Render-only meshes for the tray scene, from nvidia/simready-assets (CC-BY-4.0).

Physics never reads these: collision stays on the primitive boxes built from
TrayConfig, because MuJoCo collides meshes by their convex hull and would turn
an open tray into a solid block. scripts/g0/tray/import_simready.py converts the
USD assets to OBJ + PNG under fwdata/ and writes a manifest; this module reads
that manifest and fits each mesh onto the box it dresses. With no manifest the
scene renders the primitives in plain colours.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

FitMode = Literal["stretch", "uniform"]


@dataclass(frozen=True)
class VisualAsset:
    role: str  # "tray", "table" or "part"
    asset: str  # SimReady asset folder name
    obj: Path
    texture: Path | None
    rgba: tuple[float, float, float, float]  # used when there is no texture
    bbox_min: tuple[float, float, float]  # mesh frame, metres
    bbox_max: tuple[float, float, float]


@dataclass(frozen=True)
class Fit:
    """Mesh scale (mesh frame), then yaw about z, then translation from the box centre."""

    scale: tuple[float, float, float]
    yaw: float
    pos: tuple[float, float, float]


def fit_box(asset: VisualAsset, size: tuple[float, float, float], mode: FitMode) -> Fit:
    """Place `asset` in a box of `size` (x, y, z) centred at the origin.

    The mesh turns 90 degrees about z when its long horizontal side would
    otherwise lie across the box's. `stretch` fills the box on every axis;
    `uniform` keeps the mesh's proportions, fits it inside the box and rests
    it on the box floor.
    """
    lo, hi = np.asarray(asset.bbox_min, float), np.asarray(asset.bbox_max, float)
    extent, target = hi - lo, np.asarray(size, float)
    turn = bool((extent[0] > extent[1]) != (target[0] > target[1]))
    # Target extent seen along each mesh axis.
    along_mesh = target[[1, 0, 2]] if turn else target
    if mode == "stretch":
        scale = along_mesh / extent
    else:
        scale = np.full(3, float(np.min(along_mesh / extent)))
    yaw = math.pi / 2 if turn else 0.0
    c, s = math.cos(yaw), math.sin(yaw)
    rot = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    pos = -rot @ (scale * (lo + hi) / 2)
    if mode == "uniform":
        pos[2] += -target[2] / 2 + scale[2] * extent[2] / 2
    return Fit(
        (float(scale[0]), float(scale[1]), float(scale[2])),
        yaw,
        (float(pos[0]), float(pos[1]), float(pos[2])),
    )


def default_manifest_path() -> Path | None:
    """fwdata/simple/tray/simready/manifest.json above this file, if the import ran."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "fwdata/simple/tray/simready/manifest.json"
        if candidate.is_file():
            return candidate
    return None


def load_manifest(path: Path | None) -> dict[str, list[VisualAsset]]:
    """Visual assets by role; empty when the manifest is absent."""
    if path is None or not path.is_file():
        return {}
    data = json.loads(path.read_text())
    out: dict[str, list[VisualAsset]] = {}
    for item in data["assets"]:
        texture = item.get("texture")
        out.setdefault(item["role"], []).append(
            VisualAsset(
                role=item["role"],
                asset=item["asset"],
                obj=path.parent / item["obj"],
                texture=path.parent / texture if texture else None,
                rgba=tuple(item["rgba"]),
                bbox_min=tuple(item["bbox_min"]),
                bbox_max=tuple(item["bbox_max"]),
            )
        )
    return out

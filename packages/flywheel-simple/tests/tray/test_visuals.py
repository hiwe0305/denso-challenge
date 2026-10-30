"""Fitting SimReady visual meshes onto the task's collision boxes. Pure logic, workspace CI."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from flywheel_simple.tray.visuals import VisualAsset, fit_box, load_manifest


def corners(lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    return np.array(
        [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    )


def transformed_bounds(
    asset: VisualAsset, size: tuple[float, float, float], mode: str
) -> np.ndarray:
    fit = fit_box(asset, size, mode)
    pts = corners(np.asarray(asset.bbox_min), np.asarray(asset.bbox_max)) * np.asarray(fit.scale)
    c, s = math.cos(fit.yaw), math.sin(fit.yaw)
    rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    world = pts @ rot.T + np.asarray(fit.pos)
    return np.stack([world.min(axis=0), world.max(axis=0)])


def crate() -> VisualAsset:
    # crate_green_a20: long side along x natively, origin at the bottom centre.
    return VisualAsset(
        "tray",
        "crate_green_a20",
        Path("m.obj"),
        None,
        (0.3, 0.6, 0.3, 1.0),
        (-0.306, -0.206, 0.0),
        (0.306, 0.206, 0.090),
    )


def test_stretch_fills_the_box_and_turns_long_side_onto_y() -> None:
    bounds = transformed_bounds(crate(), (0.30, 0.45, 0.06), "stretch")
    np.testing.assert_allclose(bounds[0], [-0.15, -0.225, -0.03], atol=1e-9)
    np.testing.assert_allclose(bounds[1], [0.15, 0.225, 0.03], atol=1e-9)


def test_uniform_keeps_aspect_and_rests_on_the_box_floor() -> None:
    nut = VisualAsset(
        "part",
        "factory_nut_m20_loose",
        Path("n.obj"),
        None,
        (0.7, 0.7, 0.7, 1.0),
        (-0.015, -0.0173, -0.008),
        (0.015, 0.0173, 0.008),
    )
    bounds = transformed_bounds(nut, (0.035, 0.035, 0.03), "uniform")
    extent = bounds[1] - bounds[0]
    assert extent[2] == pytest.approx(0.016 * extent[0] / 0.030, rel=1e-6)  # aspect kept
    assert np.all(extent <= np.array([0.035, 0.035, 0.03]) + 1e-9)
    assert bounds[0][2] == pytest.approx(-0.015)  # sits on the bottom of the part box


def test_load_manifest_resolves_paths(tmp_path: Path) -> None:
    (tmp_path / "crate").mkdir()
    manifest = {
        "source": "nvidia/simready-assets",
        "revision": "abc",
        "license": "CC-BY-4.0",
        "assets": [
            {
                "role": "tray",
                "asset": "crate_green_a20",
                "obj": "crate/mesh.obj",
                "texture": "crate/albedo.png",
                "rgba": [0.3, 0.6, 0.3, 1.0],
                "bbox_min": [-0.306, -0.206, 0.0],
                "bbox_max": [0.306, 0.206, 0.09],
            },
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    loaded = load_manifest(tmp_path / "manifest.json")
    assert loaded["tray"][0].obj == tmp_path / "crate/mesh.obj"
    assert loaded["tray"][0].texture == tmp_path / "crate/albedo.png"


def test_missing_manifest_means_no_visuals(tmp_path: Path) -> None:
    assert load_manifest(tmp_path / "absent.json") == {}

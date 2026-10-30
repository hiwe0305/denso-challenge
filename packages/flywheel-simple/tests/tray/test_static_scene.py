"""Tray MJCF and the static scene in plain MuJoCo (DA-32 AC 3, milestone M0).

Needs `mujoco`; runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
        fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray -m sim -v
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel_simple.tray import TrayConfig

pytestmark = pytest.mark.sim


def body_pos(model: Any, data: Any, name: str) -> np.ndarray:
    import mujoco

    return np.asarray(data.xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)])


def max_penetration(data: Any) -> float:
    dists = [data.contact[i].dist for i in range(data.ncon)]
    return max(0.0, -min(dists)) if dists else 0.0


def write_cube_manifest(root: Path) -> Path:
    """A one-cube OBJ standing in for every SimReady asset."""
    (root / "cube.obj").write_text(
        "v -1 -1 0\nv 1 -1 0\nv 1 1 0\nv -1 1 0\nv -1 -1 1\nv 1 -1 1\nv 1 1 1\nv -1 1 1\n"
        "f 1 3 2\nf 1 4 3\nf 5 6 7\nf 5 7 8\nf 1 2 6\nf 1 6 5\n"
        "f 2 3 7\nf 2 7 6\nf 3 4 8\nf 3 8 7\nf 4 1 5\nf 4 5 8\n"
    )
    cube = {
        "obj": "cube.obj",
        "texture": None,
        "rgba": [0.5, 0.5, 0.5, 1.0],
        "bbox_min": [-1, -1, 0],
        "bbox_max": [1, 1, 1],
    }
    assets = [{"role": r, "asset": f"test_{r}", **cube} for r in ("tray", "table", "part")]
    manifest = {"source": "test", "revision": "0", "license": "none", "assets": assets}
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root / "manifest.json"


def settle(model: Any, data: Any, seconds: float) -> float:
    import mujoco

    worst = 0.0
    for _ in range(int(seconds / model.opt.timestep)):
        mujoco.mj_step(model, data)
        worst = max(worst, max_penetration(data))
    return worst


def test_scene_rests_for_30_seconds() -> None:
    import mujoco
    from flywheel_simple.tray.mjcf import static_scene_spec

    model = static_scene_spec(TrayConfig.load(), visuals={}).compile()
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    tray0 = body_pos(model, data, "tray").copy()
    parts0 = [body_pos(model, data, f"part_{i}").copy() for i in range(6)]
    max_pen = settle(model, data, 30.0)
    assert np.linalg.norm(body_pos(model, data, "tray") - tray0) < 0.005
    for i in range(6):
        assert np.linalg.norm(body_pos(model, data, f"part_{i}")[:2] - parts0[i][:2]) < 0.02
    assert max_pen < 0.002


def test_no_initial_interpenetration() -> None:
    import mujoco
    from flywheel_simple.tray.mjcf import static_scene_spec

    model = static_scene_spec(TrayConfig.load(), visuals={}).compile()
    data = mujoco.MjData(model)
    assert settle(model, data, 0.1) < 0.002


def test_visual_meshes_never_collide_and_scene_still_rests(tmp_path: Path) -> None:
    import mujoco
    from flywheel_simple.tray.mjcf import static_scene_spec
    from flywheel_simple.tray.visuals import load_manifest

    visuals = load_manifest(write_cube_manifest(tmp_path))
    model = static_scene_spec(TrayConfig.load(), visuals=visuals).compile()
    data = mujoco.MjData(model)
    vis = [g for g in range(model.ngeom) if model.geom_dataid[g] >= 0]
    assert len(vis) == 1 + 2 + 6  # tray, two tables, six parts
    assert all(model.geom_contype[g] == 0 and model.geom_conaffinity[g] == 0 for g in vis)
    mujoco.mj_forward(model, data)
    tray0 = body_pos(model, data, "tray").copy()
    assert settle(model, data, 5.0) < 0.002
    assert np.linalg.norm(body_pos(model, data, "tray") - tray0) < 0.005


def test_visuals_hide_the_boxes_they_dress_but_not_handles(tmp_path: Path) -> None:
    import mujoco
    from flywheel_simple.tray.mjcf import HIDDEN_GROUP, static_scene_spec
    from flywheel_simple.tray.visuals import load_manifest

    visuals = load_manifest(write_cube_manifest(tmp_path))
    model = static_scene_spec(TrayConfig.load(), visuals=visuals).compile()

    def group(name: str) -> int:
        return int(model.geom_group[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)])

    assert group("tray_base") == HIDDEN_GROUP
    assert group("table_a_top") == HIDDEN_GROUP
    assert group("tray_handle_left") != HIDDEN_GROUP
    assert group("tray_handle_right") != HIDDEN_GROUP

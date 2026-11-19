"""Scorer versions 1 and 2 on a tray dropped tilted onto table B, in plain MuJoCo (DA-42 5.1).

The scene is the task's own MJCF (tables, tray, parts) without a robot. A synthetic
carry (the conftest episode up to the set-down) latches the first five steps with both
hands on the handles; then the tray is let go 8 cm above the target, tilted 18 degrees
about its long (y) axis, with its parts, and MuJoCo drops it onto table B. Hands are off the
tray from the release on. Needs `mujoco`; runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \\
        fwdata/simple/.venv/bin/python -m pytest \\
        packages/flywheel-simple/tests/tray/test_predicates_sim.py -m sim -v
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytestmark = pytest.mark.sim

DROP_HEIGHT = 0.08  # m above resting on table B
DROP_TILT_DEG = 18.0  # about the tray's long (y) axis: one long side lands first
SETTLE_S = 3.0


def quat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ]
    )


def dropped_scene(tmp_path: Path) -> tuple[Any, Any, Any, Any]:
    """(model, data, cfg, sample): the tray and parts at the target, raised and tilted."""
    import mujoco
    from flywheel_simple.tray import TrayConfig
    from flywheel_simple.tray.mjcf import write_scene_mjcf
    from flywheel_simple.tray.predicates import quat_to_mat
    from flywheel_simple.tray.randomize import sample_episode

    cfg = TrayConfig.load()
    sample = sample_episode(cfg, 0, 0)
    path = write_scene_mjcf(
        cfg,
        tmp_path / "scene.xml",
        tray_pose=sample.target_pose,
        table_gap=sample.table_gap,
        target_pose=sample.target_pose,
    )
    model = mujoco.MjModel.from_xml_path(str(path))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    half = math.radians(DROP_TILT_DEG) / 2
    turn = np.array([math.cos(half), 0.0, math.sin(half), 0.0])
    tray_adr = model.jnt_qposadr[model.joint("tray_joint").id]
    origin = data.qpos[tray_adr : tray_adr + 3].copy()
    new_origin = origin + [0.0, 0.0, DROP_HEIGHT]
    rot = quat_to_mat(turn)
    for name in ["tray_joint", *(f"part_{i}_joint" for i in range(cfg.part_count))]:
        adr = model.jnt_qposadr[model.joint(name).id]
        pos, quat = data.qpos[adr : adr + 3].copy(), data.qpos[adr + 3 : adr + 7].copy()
        data.qpos[adr : adr + 3] = new_origin + rot @ (pos - origin)
        data.qpos[adr + 3 : adr + 7] = quat_mul(turn, quat)
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)
    return model, data, cfg, sample


def scene_state(model: Any, data: Any, t0: float, base_x: float, cfg: Any) -> Any:
    """TrayState of the robot-less scene: no hand contact, palms far, robot standing."""
    from flywheel_simple.tray.predicates import TrayState

    tray_id = model.body("tray").id
    on_table = "none"
    for i in range(data.ncon):
        c = data.contact[i]
        for mine, other in ((c.geom1, c.geom2), (c.geom2, c.geom1)):
            other_body = model.body(model.geom_bodyid[other]).name
            if model.geom_bodyid[mine] == tray_id and other_body in ("table_a", "table_b"):
                on_table = "A" if other_body == "table_a" else "B"
    tray_pos = np.asarray(data.body("tray").xpos).copy()
    far = tray_pos + [1.0, 0.0, 0.0]
    return TrayState(
        t=t0 + float(data.time),
        tray_pos=tray_pos,
        tray_quat=np.asarray(data.body("tray").xquat).copy(),
        part_pos=np.array([data.body(f"part_{i}").xpos for i in range(cfg.part_count)]),
        hand_contacts=(False, False),
        tray_on_table=on_table,  # type: ignore[arg-type]
        base_xy=np.array([base_x, 0.0]),
        pelvis_height=0.75,
        left_palm=far,
        right_palm=far,
    )


def carry_then_drop(
    full_episode: Callable[[], Iterator[Any]], tmp_path: Path
) -> tuple[list[Any], list[Any]]:
    """(synthetic carry states, physics states of the drop), in one time line."""
    import mujoco

    carry = []
    for s in full_episode():
        if s.tray_on_table == "B":
            break
        carry.append(s)
    model, data, cfg, _ = dropped_scene(tmp_path)
    t0, base_x = carry[-1].t + 0.02, float(carry[-1].base_xy[0])
    per_cycle = round(0.02 / model.opt.timestep)
    drop = []
    for _ in range(round(SETTLE_S / 0.02)):
        drop.append(scene_state(model, data, t0, base_x, cfg))
        for _ in range(per_cycle):
            mujoco.mj_step(model, data)
    return carry, drop


def run_version(version: int, states: list[Any]) -> tuple[Any, Any]:
    from flywheel_simple.tray import TrayConfig
    from flywheel_simple.tray.predicates import StepTracker
    from flywheel_simple.tray.randomize import sample_episode

    cfg = TrayConfig.load()
    tracker = StepTracker(cfg, sample_episode(cfg, 0, 0), version=version)
    report = None
    for s in states:
        report = tracker.update(s)
    return report, tracker.outcome_fields()


def test_the_dropped_tray_falls_tilted_and_settles_flat_on_table_b(
    full_episode: Callable[[], Iterator[Any]], tmp_path: Path
) -> None:
    from flywheel_simple.tray.predicates import quat_to_mat

    _, drop = carry_then_drop(full_episode, tmp_path)
    tilt = [math.degrees(math.acos(min(1.0, quat_to_mat(s.tray_quat)[2, 2]))) for s in drop]
    assert drop[0].tray_on_table == "none" and tilt[0] > 15.0
    assert drop[-1].tray_on_table == "B" and tilt[-1] < 1.0


def test_version_1_labels_the_drop_tilt_version_2_does_not(
    full_episode: Callable[[], Iterator[Any]], tmp_path: Path
) -> None:
    carry, drop = carry_then_drop(full_episode, tmp_path)
    v1, f1 = run_version(1, carry + drop)
    v2, f2 = run_version(2, carry + drop)
    assert v1.failure == "L-TRAY-TILT" and not v1.success
    assert f1["failure_t"] == pytest.approx(drop[0].t)
    assert f1["at_failure"]["hand_contacts"] == {"left": False, "right": False}
    assert f1["at_failure"]["tray_on_table"] == "none"
    assert v2.failure != "L-TRAY-TILT"
    # the tray ends flat in the target with its parts: version 2 scores the success
    assert v2.success and v2.failure is None, f2
    assert f2["step_latch_t"][:5] == f1["step_latch_t"][:5]


def test_a_carried_tray_tipped_with_both_hands_is_tilt_in_both_versions(
    full_episode: Callable[[], Iterator[Any]], tmp_path: Path
) -> None:
    """The first physics state again, but still held by both hands: a real carry tilt."""
    carry, drop = carry_then_drop(full_episode, tmp_path)
    held = replace(drop[0], hand_contacts=(True, True))
    for version in (1, 2):
        report, _ = run_version(version, [*carry, held])
        assert report.failure == "L-TRAY-TILT"

"""The locating jig in MuJoCo (DA-41 AC 3, 5): static, colliding, centres a tray lowered off target.

Plain MuJoCo, no robot. Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m pytest packages/flywheel-simple/tests/tray/test_jig_sim.py -m sim -v
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest
from flywheel_simple.tray import TrayConfig
from flywheel_simple.tray.geometry import Pose2D

pytestmark = pytest.mark.sim

CASES = [(0, 0), (1, 1279), (2, 125195), (2, 1_000_103)]
SETTLE_S = 3.0


def _scene(level: int, seed: int, tray_on_target: Pose2D | None = None, z: float = 0.0) -> Any:
    """Compiled jig scene of (level, seed), plain boxes; with `tray_on_target`, the tray
    starts on table B at that pose, `z` above the table top."""
    import mujoco
    from flywheel_simple.tray import mjcf
    from flywheel_simple.tray.jig import JigConfig, jig_scene_spec, sample_jig_episode

    cfg, jig = TrayConfig.load(), JigConfig.load()
    s = sample_jig_episode(cfg, jig, level, seed)
    spec = jig_scene_spec(
        cfg, jig, tray_pose=s.tray_pose, visuals={}, table_gap=s.table_gap,
        target_pose=s.target_pose,
    )
    model = spec.compile()
    data = mujoco.MjData(model)
    if tray_on_target is not None:
        _move_tray(model, data, cfg, tray_on_target, cfg.table_height + mjcf.SPAWN_GAP + z)
    mujoco.mj_forward(model, data)
    return model, data, s


def _move_tray(model: Any, data: Any, cfg: TrayConfig, pose: Pose2D, z: float) -> None:
    """Put the tray and its parts at `pose`, underside at `z`."""
    from flywheel_simple.tray import mjcf
    from flywheel_simple.tray.geometry import scene_geometry

    quat = [math.cos(pose.yaw / 2), 0.0, 0.0, math.sin(pose.yaw / 2)]
    adr = model.jnt_qposadr[model.joint("tray_joint").id]
    data.qpos[adr : adr + 7] = [pose.x, pose.y, z, *quat]
    c, s = math.cos(pose.yaw), math.sin(pose.yaw)
    part_z = z + cfg.tray_floor + mjcf.SPAWN_GAP + cfg.part_height / 2
    for i, (x, y) in enumerate(scene_geometry(cfg).compartment_centers):
        adr = model.jnt_qposadr[model.joint(f"part_{i}_joint").id]
        data.qpos[adr : adr + 7] = [pose.x + c * x - s * y, pose.y + s * x + c * y, part_z, *quat]


def _yaw(quat: np.ndarray) -> float:
    w, x, y, z = quat
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def _run(model: Any, data: Any, seconds: float) -> None:
    import mujoco

    for _ in range(round(seconds / model.opt.timestep)):
        mujoco.mj_step(model, data)


def _jig_geoms(model: Any) -> list[int]:
    return [g for g in range(model.ngeom) if model.geom(g).name.startswith("jig_")]


@pytest.mark.parametrize(("level", "seed"), CASES)
def test_jig_geoms_belong_to_table_b_at_the_target(level: int, seed: int) -> None:
    from flywheel_simple.tray.jig import JIG_PRIORITY, JigConfig, guide_boxes

    model, data, s = _scene(level, seed)
    cfg, jig = TrayConfig.load(), JigConfig.load()
    geoms = _jig_geoms(model)
    assert len(geoms) == len(guide_boxes(cfg, jig)) + 1  # guide arms and the pad
    table_b = model.body("table_b").id
    t = s.target_pose
    c, sn = math.cos(t.yaw), math.sin(t.yaw)
    for g in geoms:
        # On table B's body: the step tracker reads contacts with it as "on B".
        assert model.geom_bodyid[g] == table_b
        assert model.geom_contype[g] and model.geom_conaffinity[g]
        assert model.geom_priority[g] == JIG_PRIORITY
        assert model.geom_friction[g][0] == pytest.approx(jig.friction)
    for box in guide_boxes(cfg, jig):
        x, y, z = box.pos
        want = [t.x + c * x - sn * y, t.y + sn * x + c * y, cfg.table_height + z]
        assert data.geom(box.name).xpos == pytest.approx(want, abs=1e-6)
        geom = model.geom(box.name)
        assert geom.rgba[3] == 1.0 and model.geom_group[geom.id] == 0  # head camera draws it
    pad = data.geom("jig_pad")
    assert pad.xpos[:2] == pytest.approx([t.x, t.y], abs=1e-6)
    assert model.geom("jig_pad").rgba[3] == 0.0  # the zone under it stays visible
    # No body, joint or mass added: the moving bodies keep their indices and inertia.
    assert [model.body(i).name for i in range(model.nbody)][-1] == "target_zone"
    assert model.nq == 7 * 7 and model.nv == 6 * 7


@pytest.mark.parametrize(("level", "seed"), CASES)
def test_a_tray_resting_on_target_never_touches_a_guide_and_stays_put(
    level: int, seed: int
) -> None:
    import mujoco
    from flywheel_simple.tray.jig import JigConfig

    cfg, jig = TrayConfig.load(), JigConfig.load()
    model, data, s = _scene(level, seed)
    _move_tray(model, data, cfg, s.target_pose, cfg.table_height + jig.pad_thickness)
    mujoco.mj_forward(model, data)
    guides = {g for g in _jig_geoms(model) if model.geom(g).name != "jig_pad"}
    tray = model.body("tray").id
    start = data.body("tray").xpos.copy()
    for _ in range(round(SETTLE_S / model.opt.timestep)):
        mujoco.mj_step(model, data)
        for i in range(data.ncon):
            con = data.contact[i]
            pair = {con.geom1, con.geom2}
            touches_tray = tray in {model.geom_bodyid[con.geom1], model.geom_bodyid[con.geom2]}
            assert not (touches_tray and pair & guides), "a guide touches the tray on target"
    moved = data.body("tray").xpos - start
    assert np.linalg.norm(moved[:2]) < 0.001
    assert abs(_yaw(data.body("tray").xquat) - s.target_pose.yaw) < 1e-3


# Held lowering as the planner does it: a soft weld to a mocap carrier lowers the tray
# at lower_speed from above the guides and lets go at lower_tray_clear. Offsets inside the
# envelope measured by scripts/g0/tray/jig_capture.py (docs/g0/tray/jig.md): towards the
# closed sides (not +x, the robot's side, which is open) up to 2 cm without yaw, 1 cm at
# 2 degrees. Since jig2 the near end arms are low (the wrists pass over them), which
# leads less in: at 4 degrees, 1.5 cm towards +y ends propped on a guide; the planner
# places within about 1 cm and 2 degrees (DA-41 task 6). (radius m, direction deg, yaw deg)
CLOSED = (90, 135, 180, 225, 270)
LOWERED = [(r, a, 0.0) for r in (0.01, 0.02) for a in CLOSED] + [(0.01, a, 2.0) for a in CLOSED]
WELD_SOLREF = [0.05, 1.0]
ENDS_WITHIN_M = 0.02  # the scorer allows 5 cm and 10 degrees


@pytest.mark.parametrize(("radius", "direction", "dyaw"), LOWERED)
def test_a_tray_lowered_off_target_ends_flat_inside_the_jig(
    radius: float, direction: float, dyaw: float
) -> None:
    import mujoco
    from flywheel_simple.tray.jig import JigConfig, jig_scene_spec, sample_jig_episode
    from flywheel_simple.tray.planner import PlannerConfig

    cfg, jig, planner = TrayConfig.load(), JigConfig.load(), PlannerConfig.load()
    s = sample_jig_episode(cfg, jig, 1, 1279)
    spec = jig_scene_spec(cfg, jig, tray_pose=s.tray_pose, visuals={}, table_gap=s.table_gap,
                          target_pose=s.target_pose)
    tray_spec = spec.body("tray")
    spec.worldbody.add_body(name="carrier", mocap=True, pos=list(tray_spec.pos),
                            quat=list(tray_spec.quat))
    spec.add_equality(type=mujoco.mjtEq.mjEQ_WELD, name1="carrier", name2="tray",
                      objtype=mujoco.mjtObj.mjOBJ_BODY, solref=WELD_SOLREF)
    model = spec.compile()
    data = mujoco.MjData(model)
    t = s.target_pose
    a = math.radians(direction)
    dx, dy = radius * math.cos(a), radius * math.sin(a)
    c, sn = math.cos(t.yaw), math.sin(t.yaw)
    pose = Pose2D(t.x + c * dx - sn * dy, t.y + sn * dx + c * dy, t.yaw + math.radians(dyaw))
    z = cfg.table_height + jig.height + 0.02
    _move_tray(model, data, cfg, pose, z)
    data.mocap_pos[0] = [pose.x, pose.y, z]
    data.mocap_quat[0] = [math.cos(pose.yaw / 2), 0.0, 0.0, math.sin(pose.yaw / 2)]
    mujoco.mj_forward(model, data)
    bottom = cfg.table_height + planner.lower_tray_clear
    step = planner.lower_speed * model.opt.timestep
    while data.mocap_pos[0][2] > bottom:
        data.mocap_pos[0][2] = max(bottom, data.mocap_pos[0][2] - step)
        mujoco.mj_step(model, data)
    data.eq_active[0] = 0
    _run(model, data, SETTLE_S)
    tray = data.body("tray")
    err = math.hypot(tray.xpos[0] - t.x, tray.xpos[1] - t.y)
    yaw_err = abs(math.degrees(math.remainder(_yaw(tray.xquat) - t.yaw, math.pi)))
    tilt = math.degrees(math.acos(min(1.0, float(data.xmat[tray.id][8]))))
    height = tray.xpos[2] - cfg.table_height
    assert err <= ENDS_WITHIN_M, (err, yaw_err, tilt, height)
    flat = yaw_err <= 3.0 and tilt <= 2.0 and height < jig.pad_thickness + 0.003
    assert flat, (err, yaw_err, tilt, height)
    for i in range(cfg.part_count):
        assert data.body(f"part_{i}").xpos[2] > cfg.table_height  # no part fell out

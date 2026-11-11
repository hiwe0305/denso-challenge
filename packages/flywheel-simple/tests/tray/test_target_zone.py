"""The target zone drawn on table B: render-only, at the episode's target pose, physics unchanged.

The planner and the scorer always used the target pose; until zone1 the policy's
camera never saw it (docs/g0/tray/target-zone.md). Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m pytest packages/flywheel-simple/tests/tray/test_target_zone.py -m sim -v
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest
from flywheel_simple.tray import TrayConfig

pytestmark = pytest.mark.sim

ZONE_GEOMS = ("target_zone", "target_zone_tab_left", "target_zone_tab_right")
CASES = [(0, 0), (1, 1000), (1, 1279), (2, 125195), (2, 1_000_103)]


def _model(cfg: TrayConfig, level: int, seed: int, zone: bool, monkeypatch: Any) -> Any:
    from flywheel_simple.tray import mjcf
    from flywheel_simple.tray.randomize import sample_episode

    if not zone:
        monkeypatch.setattr(mjcf, "add_target_zone", lambda *a, **k: None)
    s = sample_episode(cfg, level, seed)
    spec = mjcf.task_scene_spec(
        cfg, tray_pose=s.tray_pose, table_gap=s.table_gap, target_pose=s.target_pose
    )
    monkeypatch.undo()
    return spec.compile()


def _yaw(quat: np.ndarray) -> float:
    w, x, y, z = quat
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


@pytest.mark.parametrize(("level", "seed"), CASES)
def test_zone_lies_on_table_b_at_the_episode_target_pose(
    level: int, seed: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mujoco
    from flywheel_simple.tray.randomize import sample_episode

    cfg = TrayConfig.load()
    model = _model(cfg, level, seed, True, monkeypatch)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    target = sample_episode(cfg, level, seed).target_pose
    zone = data.body("target_zone")
    assert zone.xpos[:2] == pytest.approx([target.x, target.y], abs=1e-9)
    assert zone.xpos[2] == pytest.approx(cfg.table_height, abs=1e-9)
    assert _yaw(zone.xquat) == pytest.approx(target.yaw, abs=1e-9)
    # The zone is the tray footprint, its long side along the tray's (y).
    size = model.geom("target_zone").size
    assert 2 * size[:2] == pytest.approx([cfg.tray_width, cfg.tray_length])
    # It lies on the table top, 1-2 mm thick, wholly inside table B.
    assert 0.001 <= 2 * size[2] <= 0.002
    signs = np.array([[1, 1], [1, -1], [-1, -1], [-1, 1]])
    corners = []
    for g in ZONE_GEOMS:
        rot = data.geom(g).xmat.reshape(3, 3)[:2, :2]
        corners.append(data.geom(g).xpos[:2] + (signs * model.geom(g).size[:2]) @ rot.T)
    table_b = data.body("table_b").xpos[:2]
    half = [cfg.table_depth / 2, cfg.table_length / 2]
    assert np.all(np.abs(np.concatenate(corners) - table_b) <= half)


def test_zone_geoms_never_collide_and_weigh_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    import mujoco
    from flywheel_simple.tray.mjcf import VISUAL_GROUP

    cfg = TrayConfig.load()
    model = _model(cfg, 1, 1000, True, monkeypatch)
    plain = _model(cfg, 1, 1000, False, monkeypatch)
    for name in ZONE_GEOMS:
        g = model.geom(name)
        assert (int(g.contype[0]), int(g.conaffinity[0])) == (0, 0), name
        assert int(g.group[0]) == VISUAL_GROUP
    body = model.body("target_zone")
    assert float(body.mass[0]) == 0.0 and int(body.jntnum[0]) == 0  # static, massless
    assert model.nq == plain.nq and model.nv == plain.nv
    assert mujoco.mj_getTotalmass(model) == mujoco.mj_getTotalmass(plain)
    # Every other body keeps its index, so recorded body arrays line up.
    names = [model.body(i).name for i in range(model.nbody)]
    assert names[: plain.nbody] == [plain.body(i).name for i in range(plain.nbody)]
    assert names[plain.nbody :] == ["target_zone"]


@pytest.mark.parametrize("on_zone", [False, True])
def test_tray_drops_the_same_with_and_without_the_zone(
    on_zone: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bit-identical qpos and qvel over 2 s; `on_zone` drops the tray onto the zone itself."""
    import mujoco
    from flywheel_simple.tray import mjcf
    from flywheel_simple.tray.randomize import sample_episode

    cfg = TrayConfig.load()
    s = sample_episode(cfg, 1, 1279)
    tray = s.target_pose if on_zone else s.tray_pose
    runs = []
    for zone in (True, False):
        if not zone:
            monkeypatch.setattr(mjcf, "add_target_zone", lambda *a, **k: None)
        spec = mjcf.task_scene_spec(
            cfg, tray_pose=tray, table_gap=s.table_gap, target_pose=s.target_pose
        )
        monkeypatch.undo()
        spec.worldbody.add_geom(name="floor", type=mujoco.mjtGeom.mjGEOM_PLANE, size=[5, 5, 0.1])
        model = spec.compile()
        data = mujoco.MjData(model)
        data.qpos[2] += 0.02  # drop the tray and its parts 2 cm
        data.qpos[9::7] += 0.02
        traj = []
        for _ in range(400):
            mujoco.mj_step(model, data)
            traj.append(np.concatenate([data.qpos, data.qvel]))
        runs.append(np.array(traj))
    assert np.array_equal(runs[0], runs[1])



@pytest.fixture(scope="module")
def env() -> Iterator[Any]:
    from flywheel_simple.tray.simple_task import make_env

    e = make_env(seed=0)
    yield e
    e.close()


def _episode(env: Any, level: int, seed: int) -> tuple[Any, np.ndarray]:
    from flywheel_simple.tray.agent import TrayAgent, run_episode
    from flywheel_simple.tray.planner import PlannerConfig

    sim = env.unwrapped
    states: list[np.ndarray] = []

    def on_step(obs: Any, info: Any, action: Any) -> None:
        states.append(np.concatenate([sim.mjData.qpos, sim.mjData.qvel, sim.mjData.ctrl]))

    result = run_episode(env, TrayAgent(env, PlannerConfig.load()), seed, level, on_step=on_step)
    return result, np.array(states)


def test_env_has_the_zone_at_the_target_pose_and_the_episode_is_unchanged(
    env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One planner episode through SIMPLE with and without the zone: the same, number for number.

    Level 1 seed 1279 is a train episode of release tray_s1_f9433b028c52 (planner-5).
    """
    from flywheel_simple.tray import mjcf

    with_zone, a = _episode(env, 1, 1279)
    sim = env.unwrapped
    target = sim.task.target_pose
    zone = sim.mjData.body("target_zone")
    # The scene reaches SIMPLE as MJCF text, which keeps 6 significant digits (the
    # tray's pose too): micrometres off, not more.
    assert zone.xpos[:2] == pytest.approx([target.x, target.y], abs=1e-5)
    assert _yaw(zone.xquat) == pytest.approx(target.yaw, abs=1e-5)

    monkeypatch.setattr(mjcf, "add_target_zone", lambda *a, **k: None)
    without, b = _episode(env, 1, 1279)
    with pytest.raises(KeyError):
        sim.mjData.body("target_zone")
    assert (with_zone.success, with_zone.failure, with_zone.phases) == (
        without.success, without.failure, without.phases
    )
    assert a.shape == b.shape and np.array_equal(a, b)

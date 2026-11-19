"""Fixed target and locating jig on table B (DA-41 AC 1-3). Pure logic, workspace CI."""

from __future__ import annotations

import dataclasses
import hashlib
import math
from pathlib import Path

import numpy as np
import pytest
from flywheel_simple.tray import TrayConfig
from flywheel_simple.tray.geometry import scene_geometry_with_gap
from flywheel_simple.tray.jig import (
    JigConfig,
    guide_boxes,
    jig_footprint,
    jig_on_table,
    jig_target_pose,
    rotation_quat,
    sample_jig_episode,
    slot_offsets,
)
from flywheel_simple.tray.randomize import GAP_RANGE, sample_episode

REPO = Path(__file__).resolve().parents[4]
# sha256 of the files the frozen DA-34 run plans pin (configs/runplans/tray/
# he-tray-pair60k.yaml pinned_files): DA-41 adds beside them and must not change them.
PINNED = {
    "configs/sim/tray.yaml": "89ad4e8d381005cf7b642cc17b323f3f2c13cf39dc7aefe98e9843f2d5efc245",
    "packages/flywheel-simple/src/flywheel_simple/tray/randomize.py":
        "9927c81cdd84742f772313180100c27cdb565e5f96c59e03ec634294d27bae37",
    "packages/flywheel-simple/src/flywheel_simple/tray/mjcf.py":
        "3bfabf24566c4111cd78e626e567585b2585a770fea7c82807fbd3204150f6e6",
    "packages/flywheel-simple/src/flywheel_simple/tray/simple_task.py":
        "4d63f0b77a448baba265dae7922c97736f0c42407b6b88861db14dee88b35531",
    "packages/flywheel-simple/src/flywheel_simple/tray/config.py":
        "9f9d0ddd38014b2fa804b48940073c351926b40e4c6148bec18705e2319d226a",
    "packages/flywheel-simple/src/flywheel_simple/tray/geometry.py":
        "abda4691c69f63cd7fffc1f2fb3d53a706e7206d7282155c131af9d1c82c10a8",
}


def cfgs() -> tuple[TrayConfig, JigConfig]:
    return TrayConfig.load(), JigConfig.load()


@pytest.mark.parametrize("rel", sorted(PINNED))
def test_files_pinned_by_frozen_run_plans_are_unchanged(rel: str) -> None:
    assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == PINNED[rel]


def test_config_loads_and_fits_the_tray() -> None:
    cfg, jig = cfgs()
    assert jig.check(cfg) == []
    assert jig.slots == 1  # discrete positions are off by default
    rise = jig.height - jig.wall_height
    assert jig.lead_in == pytest.approx(jig.clearance + rise * math.tan(jig.chamfer))
    # The wall boxes the tray in before the planner lets go of it (lower_tray_clear).
    from flywheel_simple.tray.planner import PlannerConfig

    assert jig.wall_height >= PlannerConfig.load().lower_tray_clear


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"slots": 4}, "slots"),
        ({"chamfer_deg": 70.0}, "chamfer_deg"),
        ({"end_arm": 0.12}, "handles"),
        ({"height": 0.08}, "reaches the handles"),
        ({"side_arm": 0.3}, "side_arm"),
        ({"clearance": 0.0}, "positive"),
        ({"wall_height": 0.07}, "wall_height"),
        ({"near_side_arm": 0.5}, "near_side_arm"),
        ({"near_end_arm": 0.05}, "near_end_arm"),
    ],
)
def test_check_refuses_jigs_that_do_not_fit(change: dict[str, float], reason: str) -> None:
    cfg, jig = cfgs()
    problems = dataclasses.replace(jig, **change).check(cfg)  # type: ignore[arg-type]
    assert any(reason in p for p in problems), problems


@pytest.mark.parametrize("level", [0, 1, 2])
def test_target_is_fixed_to_table_b_and_the_rest_of_the_episode_is_kept(level: int) -> None:
    cfg, jig = cfgs()
    for seed in range(200):
        old, new = sample_episode(cfg, level, seed), sample_jig_episode(cfg, jig, level, seed)
        assert dataclasses.replace(new, target_pose=old.target_pose) == old
        geo = scene_geometry_with_gap(cfg, new.table_gap)
        assert new.target_pose == geo.target_pose
        # Fixed relative to table B: its offset from table B's centre never changes.
        offset = np.array([new.target_pose.x, new.target_pose.y]) - geo.table_b_center
        assert offset == pytest.approx([cfg.table_depth / 2 - cfg.tray_edge_offset, 0.0])


def test_old_episodes_keep_their_jittered_target() -> None:
    # Eval runs before DA-41 read the target with sample_episode; it must not move.
    cfg, _ = cfgs()
    t = sample_episode(cfg, 1, 1279).target_pose
    assert (t.x, t.y, t.yaw) == pytest.approx((-1.1323919401903382, 0.04733055438980063,
                                               0.0636266857695682))


@pytest.mark.parametrize("slots", [2, 3])
def test_slots_spread_seeds_over_discrete_positions_and_keep_the_stream(slots: int) -> None:
    cfg, jig = cfgs()
    jig = dataclasses.replace(jig, slots=slots)
    assert jig.check(cfg) == []
    ys = set()
    for seed in range(300):
        old, new = sample_episode(cfg, 2, seed), sample_jig_episode(cfg, jig, 2, seed)
        assert dataclasses.replace(new, target_pose=old.target_pose) == old
        base = scene_geometry_with_gap(cfg, new.table_gap).target_pose
        assert (new.target_pose.x, new.target_pose.yaw) == (base.x, base.yaw)
        ys.add(round(new.target_pose.y - base.y, 9))
    assert ys == {round(dy, 9) for dy in slot_offsets(jig)}
    assert jig_target_pose(cfg, jig, cfg.corridor, 5) == jig_target_pose(cfg, jig, cfg.corridor, 5)


@pytest.mark.parametrize("slots", [1, 2, 3])
@pytest.mark.parametrize("gap", [GAP_RANGE[0], 1.8, GAP_RANGE[1]])
def test_every_slot_lies_on_table_b(slots: int, gap: float) -> None:
    cfg, jig = cfgs()
    assert jig_on_table(cfg, dataclasses.replace(jig, slots=slots), gap)


def test_guides_are_a_stop_wall_then_a_chamfer_leaning_out() -> None:
    cfg, jig = cfgs()
    hx, hy = cfg.tray_width / 2, cfg.tray_length / 2
    boxes = guide_boxes(cfg, jig)
    # Far side: two long-side and two end arms; robot side: end arms only by default.
    arms = 4 + 2 * (jig.near_side_arm > 0) + 2 * (jig.near_end_arm > 0)
    assert len(boxes) == 2 * arms  # each arm: wall and chamfer
    assert not jig.near_side_arm and not any(
        "_side" in b.name and b.pos[0] > 0 for b in boxes
    )  # robot-side long side left open
    for box in boxes:
        pts = box.corners()
        side = "_side" in box.name
        u = np.abs(pts[:, 0]) - hx if side else np.abs(pts[:, 1]) - hy  # outward of the tray
        bottom, top = float(np.min(pts[:, 2])), float(np.max(pts[:, 2]))
        innermost = float(np.min(u))
        assert innermost == pytest.approx(jig.clearance, abs=1e-9), box.name
        if box.name.endswith("_wall"):
            # Vertical inner face at the clearance, table top to wall_height.
            assert (bottom, top) == pytest.approx((0.0, jig.wall_height), abs=1e-9)
            inner = pts[np.isclose(u, innermost)]
            assert sorted(inner[:, 2]) == pytest.approx([0, 0, jig.wall_height, jig.wall_height])
        else:
            # Inner face from the wall top at the clearance out to lead_in at the top.
            assert top == pytest.approx(jig.height, abs=1e-9)
            assert pts[np.argmin(u), 2] == pytest.approx(jig.wall_height, abs=1e-9)
            inner_top = float(np.min(u[np.isclose(pts[:, 2], top)]))
            assert inner_top == pytest.approx(jig.lead_in, abs=1e-9)


def test_guides_leave_the_footprint_and_the_handles_free() -> None:
    cfg, jig = cfgs()
    hx, hy = cfg.tray_width / 2, cfg.tray_length / 2
    for box in guide_boxes(cfg, jig):
        pts = box.corners()
        above = pts[pts[:, 2] >= 0]
        outside = (np.abs(above[:, 0]) >= hx + jig.clearance - 1e-9) | (
            np.abs(above[:, 1]) >= hy + jig.clearance - 1e-9
        )
        assert outside.all(), box.name
        assert np.abs(pts[:, 0]).min() >= cfg.handle_length / 2 + jig.handle_gap - 1e-9
    width, length = jig_footprint(cfg, jig)
    assert width < cfg.table_depth and length < cfg.table_length


def test_rotation_quat_round_trips() -> None:
    cfg, jig = cfgs()
    for box in guide_boxes(cfg, jig):
        w, x, y, z = rotation_quat(box.rot)
        rot = np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ])
        assert rot == pytest.approx(box.rot, abs=1e-12)
        assert np.linalg.det(box.rot) == pytest.approx(1.0)


def test_jig_scenes_get_their_own_visuals_revision(tmp_path: Path) -> None:
    from flywheel_simple.tray.jig import JIG_REVISION
    from flywheel_simple.tray.mjcf import TARGET_ZONE_REVISION
    from flywheel_simple.tray.recorder import visuals_revision

    zone = f"none+{TARGET_ZONE_REVISION}"
    assert visuals_revision(None) == zone  # the scene without the jig keeps its revision
    assert visuals_revision(None, jig=True) == f"{zone}+{JIG_REVISION}"
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"revision": "abc123", "assets": []}')
    assert visuals_revision(manifest, jig=True) == f"abc123+{TARGET_ZONE_REVISION}+{JIG_REVISION}"


def test_generate_refuses_to_mix_jig_and_zone1_episodes_in_one_batch(tmp_path: Path) -> None:
    import json

    from flywheel_simple.tray.generate import LOG_NAME, check_visuals_revision
    from flywheel_simple.tray.recorder import visuals_revision

    shard = tmp_path / "shard-0"
    shard.mkdir()
    row = {"seed": 1, "visuals_revision": visuals_revision(None)}
    (shard / LOG_NAME).write_text(json.dumps(row) + "\n")
    check_visuals_revision(tmp_path, visuals_revision(None))
    with pytest.raises(RuntimeError, match="generate into a new --out"):
        check_visuals_revision(tmp_path, visuals_revision(None, jig=True))


def test_generate_refuses_an_unknown_scene_before_loading_anything(tmp_path: Path) -> None:
    from flywheel_simple.tray.generate import SCENES, generate

    assert SCENES == ("zone1", "jig")
    with pytest.raises(ValueError, match="scene must be one of"):
        generate(tmp_path, n_attempts=1, level=1, seed_start=0, scene="jigs")


def test_generate_on_the_jig_scene_refuses_a_zone1_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from flywheel_simple.tray import generate as gen
    from flywheel_simple.tray.planner import PlannerConfig
    from flywheel_simple.tray.recorder import planner_version, visuals_revision

    monkeypatch.setattr(gen, "default_manifest_path", lambda: None)
    shard = tmp_path / "shard-0"
    shard.mkdir()
    row = {
        "seed": 1,
        "planner_version": planner_version(PlannerConfig.load()),
        "visuals_revision": visuals_revision(None),
    }
    (shard / gen.LOG_NAME).write_text(json.dumps(row) + "\n")
    with pytest.raises(RuntimeError, match=r"\+jig1"):
        gen.generate(tmp_path, n_attempts=1, level=1, seed_start=0, allow_plain=True, scene="jig")

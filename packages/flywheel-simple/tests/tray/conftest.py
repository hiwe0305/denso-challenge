"""Synthetic TrayState sequences for the step-predicate tests; no simulator."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import replace
from typing import Any

import numpy as np
import pytest

DT = 0.02


def _cfg() -> Any:
    from flywheel_simple.tray import TrayConfig

    return TrayConfig.load()


def _geo() -> Any:
    from flywheel_simple.tray import scene_geometry

    return scene_geometry(_cfg())


def _parts_at(tray_pos: np.ndarray) -> np.ndarray:
    """Parts in the compartments of a level, unturned tray whose underside is at tray_pos."""
    cfg = _cfg()
    xy = _geo().compartment_centers + tray_pos[:2]
    z = tray_pos[2] + cfg.tray_floor + cfg.part_height / 2
    return np.c_[xy, np.full(len(xy), z)]


def state(
    t: float,
    tray_pos: np.ndarray,
    on_table: str,
    contacts: tuple[bool, bool],
    base_x: float,
    tray_quat: np.ndarray | None = None,
    parts: np.ndarray | None = None,
    pelvis: float = 0.75,
) -> Any:
    from flywheel_simple.tray.predicates import TrayState

    handles = _handles(tray_pos)
    return TrayState(
        t=t,
        tray_pos=np.asarray(tray_pos, float),
        tray_quat=np.array([1.0, 0, 0, 0]) if tray_quat is None else tray_quat,
        part_pos=_parts_at(tray_pos) if parts is None else parts,
        hand_contacts=contacts,
        tray_on_table=on_table,
        base_xy=np.array([base_x, 0.0]),
        pelvis_height=pelvis,
        left_palm=handles[0] if any(contacts) else handles[0] + [-0.4, 0, -0.2],
        right_palm=handles[1] if any(contacts) else handles[1] + [-0.4, 0, -0.2],
    )


def _handles(tray_pos: np.ndarray) -> np.ndarray:
    cfg = _cfg()
    y = cfg.tray_length / 2 + cfg.handle_depth / 2
    z = tray_pos[2] + cfg.tray_height - cfg.handle_thickness / 2
    return np.array([[tray_pos[0], y, z], [tray_pos[0], -y, z]])


def _on_a() -> np.ndarray:
    pose = _geo().tray_pose
    return np.array([pose.x, pose.y, _cfg().table_height])


def _at_target(offset_xy: tuple[float, float] = (0.0, 0.0)) -> np.ndarray:
    pose = _geo().target_pose
    return np.array([pose.x + offset_xy[0], pose.y + offset_xy[1], _cfg().table_height])


@pytest.fixture
def make_tracker() -> Callable[[], Any]:
    from flywheel_simple.tray.predicates import StepTracker
    from flywheel_simple.tray.randomize import sample_episode

    def build() -> Any:
        cfg = _cfg()
        return StepTracker(cfg, sample_episode(cfg, 0, 0))

    return build


@pytest.fixture
def idle_state() -> Callable[..., Any]:
    def build(t: float = 0.0) -> Any:
        return state(t, _on_a(), "A", (False, False), base_x=_geo().robot_spawn.x)

    return build


@pytest.fixture
def placed_state_sequence() -> Callable[..., Iterator[Any]]:
    """Tray resting on table B after release, 3 s; optional bounce and offset."""

    def build(
        bounce_at: float | None = None, offset_xy: tuple[float, float] = (0.0, 0.0)
    ) -> Iterator[Any]:
        base_x = _geo().table_b_center[0] + 0.8
        for k in range(int(3.0 / DT)):
            t = k * DT
            pos, on_table = _at_target(offset_xy), "B"
            if bounce_at is not None and bounce_at <= t < bounce_at + 0.1:
                pos, on_table = pos + [0, 0, 0.01], "none"
            yield state(t, pos, on_table, (False, False), base_x)

    return build


@pytest.fixture
def carry_sequence() -> Callable[..., Iterator[Any]]:
    """Tray lifted 0.1 m in both hands, carried from table A towards B over 5 s."""

    def build(
        drop_part_at: float | None = None, release_left_at: float | None = None
    ) -> Iterator[Any]:
        geo = _geo()
        start, end = geo.robot_spawn.x + 0.3, geo.table_b_center[0] + 0.8
        for k in range(int(5.0 / DT)):
            t = k * DT
            base_x = start + (end - start) * t / 5.0
            pos = np.array([base_x + 0.45, 0.0, _cfg().table_height + 0.1])
            parts = _parts_at(pos)
            if drop_part_at is not None and t >= drop_part_at:
                parts[0] = [base_x + 0.45, 0.6, 0.02]  # on the floor beside the robot
            contacts = (release_left_at is None or t < release_left_at, True)
            yield state(t, pos, "none", contacts, base_x, parts=parts)

    return build


@pytest.fixture
def full_episode() -> Callable[[], Iterator[Any]]:
    """Approach, grasp, lift, carry, reach B, place, release: a successful episode."""

    def build() -> Iterator[Any]:
        geo, cfg = _geo(), _cfg()
        t = 0.0

        def tick() -> float:
            nonlocal t
            t += DT
            return t

        a_front = geo.table_a_center[0] - cfg.table_depth / 2 - 0.3
        b_front = geo.table_b_center[0] + cfg.table_depth / 2 + 0.3
        for _ in range(25):  # approach: walk to table A, hands on handles at the end
            yield state(tick(), _on_a(), "A", (False, False), base_x=a_front)
        yield replace(state(tick(), _on_a(), "A", (True, True), base_x=a_front))
        lifted = _on_a() + [0, 0, 0.1]
        for _ in range(10):
            yield state(tick(), lifted, "none", (True, True), base_x=a_front)
        for k in range(50):  # carry to table B
            x = a_front + (b_front - a_front) * k / 49
            pos = np.array([x - 0.45 if x < 0 else x + 0.45, 0.0, lifted[2]])
            yield state(tick(), pos, "none", (True, True), base_x=x)
        placed = _at_target()
        for _ in range(10):
            yield state(tick(), placed, "B", (True, True), base_x=b_front)
        for _ in range(int(1.5 / DT)):
            yield state(tick(), placed, "B", (False, False), base_x=b_front)

    return build

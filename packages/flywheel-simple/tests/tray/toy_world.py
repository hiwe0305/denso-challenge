"""Toy world for the tray planner tests; no simulator.

The base follows `nav` as decoupled WBC does (vx, vy in the base frame; with a
turn flag >= 0.1 the yaw goes to `heading` at (error / 0.5) rad/s, at most
1 rad/s). Palms sit at the commanded wrists plus the palm offset, optionally
sagging. A hand grips its handle when closed past half with the palm within
CONTACT_R of its squeezed grasp point (`grasp_palms_world`). A squeeze holds
while the hands stay no further apart than when they gripped (plus SLACK), so
spreading them releases it as opening does; while both grip, the tray moves
rigidly with the palms. Released over a table, the tray rests on it; elsewhere it falls to the
floor. DA-32's StepTracker scores every step. The arms start hanging at rest
(`start_wrists`), where the planner's first targets start from.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from flywheel_simple.tray.config import TrayConfig
from flywheel_simple.tray.geometry import Pose2D, scene_geometry_with_gap
from flywheel_simple.tray.planner import (
    Phase,
    PlannerCommand,
    PlannerConfig,
    TrayPlanner,
    base_transform,
    grasp_palms_world,
)
from flywheel_simple.tray.predicates import StepReport, StepTracker, TrayState
from flywheel_simple.tray.randomize import sample_episode

DT = 0.02
PELVIS_Z = 0.75
CONTACT_R = 0.03
SLACK = 0.02
LINGER_S = 2.0  # keep stepping after DONE or ABORT so success can register


@dataclass(frozen=True)
class Record:
    cmd: PlannerCommand
    state: TrayState
    base: Pose2D
    report: StepReport


class ToyWorld:
    def __init__(
        self,
        level: int = 0,
        seed: int = 0,
        palm_sag: float = 0.0,
        vy_scale: float = 1.0,
        planner_cfg: PlannerConfig | None = None,
    ) -> None:
        self.cfg = TrayConfig.load()
        self.planner_cfg = planner_cfg or PlannerConfig.load()
        self.vy_scale = vy_scale  # 0 blocks sideways steps, leaving a lateral error
        self.sample = sample_episode(self.cfg, level, seed)
        self.geo = scene_geometry_with_gap(self.cfg, self.sample.table_gap)
        spawn = self.sample.robot_spawn
        self.base = Pose2D(spawn.x, spawn.y, spawn.yaw)
        tray = self.sample.tray_pose
        self.tray_pos = np.array([tray.x, tray.y, self.cfg.table_height])
        self.tray_yaw = tray.yaw
        self.palm_sag = palm_sag
        # The arms hang at rest, wrists unrotated in the base frame; the planner starts there.
        offsets = self.planner_cfg.palm_offsets
        self.start_wrists = []
        for k, side in enumerate((1, -1)):
            wrist = np.eye(4)
            wrist[:3, 3] = np.array([0.2, side * 0.2, -0.1]) - offsets[k]
            self.start_wrists.append(wrist)
        rest = base_transform(self.base, PELVIS_Z)
        self.palms = [(rest @ w @ np.r_[o, 1.0])[:3] for w, o in zip(self.start_wrists, offsets)]
        self.contacts = (False, False)
        self.grip: tuple[float, np.ndarray] | None = None  # tray yaw - base yaw, tray - palm mid
        self.grip_width = 0.0
        self.blocked = False
        self.drop_left_in: Phase | None = None
        self.left_dropped = False
        self.t = 0.0

    @property
    def tray_pose(self) -> Pose2D:
        return Pose2D(float(self.tray_pos[0]), float(self.tray_pos[1]), self.tray_yaw)

    def block_base(self) -> None:
        self.blocked = True

    def drop_left_contact_at(self, phase: Phase) -> None:
        self.drop_left_in = phase

    def run(self, max_s: float = 150.0) -> list[Record]:
        planner = TrayPlanner(self.planner_cfg, self.cfg, self.sample)
        planner.start(self.start_wrists[0], self.start_wrists[1])
        tracker = StepTracker(self.cfg, self.sample)
        state = self._state()
        report = tracker.update(state)
        records: list[Record] = []
        linger = 0.0
        while self.t < max_s and linger < LINGER_S:
            base = self.base
            cmd = planner.step(state, base, report)
            self._apply(cmd)
            state = self._state()
            report = tracker.update(state)
            records.append(Record(cmd, state, base, report))
            if cmd.phase in (Phase.DONE, Phase.ABORT):
                linger += DT
        return records

    def _apply(self, cmd: PlannerCommand) -> None:
        self.t += DT
        vx, vy, vyaw = cmd.nav
        yaw = self.base.yaw
        if abs(vyaw) >= 0.1:
            error = math.atan2(math.sin(cmd.heading - yaw), math.cos(cmd.heading - yaw))
            yaw += float(np.clip(error / 0.5, -1.0, 1.0)) * DT
        x, y = self.base.x, self.base.y
        if not self.blocked:
            c, s = math.cos(self.base.yaw), math.sin(self.base.yaw)
            vy *= self.vy_scale
            x += (c * vx - s * vy) * DT
            y += (s * vx + c * vy) * DT
        self.base = Pose2D(x, y, math.atan2(math.sin(yaw), math.cos(yaw)))

        world = base_transform(self.base, PELVIS_Z)
        offsets = self.planner_cfg.palm_offsets
        for k, (wrist, off) in enumerate(zip((cmd.left_wrist, cmd.right_wrist), offsets)):
            palm = (world @ wrist @ np.r_[off, 1.0])[:3]
            self.palms[k] = palm - np.array([0.0, 0.0, self.palm_sag])

        if self.drop_left_in is not None and cmd.phase == self.drop_left_in:
            self.left_dropped = True
        squeeze = -self.planner_cfg.squeeze  # the planner presses this far inside
        grasp = grasp_palms_world(self.planner_cfg, self.cfg, self.tray_pos, self.tray_yaw, squeeze)
        width = float(np.linalg.norm(self.palms[0] - self.palms[1]))
        gripping = []
        for k in range(2):
            closed = cmd.hand_closure[k] >= 0.5
            if self.grip is None:
                held = np.linalg.norm(self.palms[k] - grasp[k]) <= CONTACT_R
            else:
                held = width <= self.grip_width + SLACK
            gripping.append(closed and bool(held))
        if self.left_dropped:
            gripping[0] = False
        self.contacts = (gripping[0], gripping[1])

        mid = (self.palms[0] + self.palms[1]) / 2
        if self.grip is None and all(gripping):
            self.grip = (self.tray_yaw - self.base.yaw, self.tray_pos - mid)
            self.grip_width = width
        if self.grip is not None and (gripping[1] or all(gripping)):
            rel_yaw, offset = self.grip
            turn = self.base.yaw + rel_yaw - self.tray_yaw
            c, s = math.cos(turn), math.sin(turn)
            offset = np.array(
                [c * offset[0] - s * offset[1], s * offset[0] + c * offset[1], offset[2]]
            )
            self.grip = (rel_yaw, offset)
            self.tray_yaw = self.base.yaw + rel_yaw
            self.tray_pos = mid + offset
            if self._over_table() is not None:
                self.tray_pos[2] = max(self.tray_pos[2], self.cfg.table_height)
        elif self.grip is not None:
            self.grip = None
            self.tray_pos[2] = self.cfg.table_height if self._over_table() else 0.0

    def _over_table(self) -> str | None:
        half = np.array([self.cfg.table_depth, self.cfg.table_length]) / 2
        for name, centre in (("A", self.geo.table_a_center), ("B", self.geo.table_b_center)):
            if np.all(np.abs(self.tray_pos[:2] - centre) <= half):
                return name
        return None

    def _state(self) -> TrayState:
        cfg = self.cfg
        c, s = math.cos(self.tray_yaw), math.sin(self.tray_yaw)
        rot = np.array([[c, -s], [s, c]])
        parts_xy = self.geo.compartment_centers @ rot.T + self.tray_pos[:2]
        z = self.tray_pos[2] + cfg.tray_floor + cfg.part_height / 2
        parts = np.c_[parts_xy, np.full(len(parts_xy), z)]
        table = self._over_table()
        on_table: Any = table if table and self.tray_pos[2] <= cfg.table_height + 1e-6 else "none"
        return TrayState(
            t=self.t,
            tray_pos=self.tray_pos.copy(),
            tray_quat=np.array(
                [math.cos(self.tray_yaw / 2), 0.0, 0.0, math.sin(self.tray_yaw / 2)]
            ),
            part_pos=parts,
            hand_contacts=self.contacts,
            tray_on_table=on_table,
            base_xy=np.array([self.base.x, self.base.y]),
            pelvis_height=PELVIS_Z,
            left_palm=self.palms[0].copy(),
            right_palm=self.palms[1].copy(),
        )

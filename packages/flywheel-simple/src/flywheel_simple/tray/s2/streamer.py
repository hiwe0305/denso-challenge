"""The S2 replay operator as a PICO streamer in SIMPLE's teleop pipeline (DA-35 tasks 9-11).

Plugs into `StreamerDecoupledAgent` where the headset would be, like the
virtual operator. Each attempt of a session is one S2 job: a parent demo, the
condition (level, seed) the env resets to, and a generation seed. Parents are
read from their batch directory (generate_parents.py) and cut once per process.

Mode `exact` plays the parent's frames as recorded (task 9); mode `variant`
moves them onto the job's condition (flywheel_simple.tray.s2.variant) and
replays them closed loop on the measured pelvis pose (task 10).

Only runs in the SIMPLE venv.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

import numpy as np

from flywheel_simple.tray.pico.agent import calibration_of, pico_output
from flywheel_simple.tray.pico.conditions import Condition
from flywheel_simple.tray.pico.operator import OperatorConfig, PicoSignal
from flywheel_simple.tray.pico.virtual import YawStick
from flywheel_simple.tray.randomize import sample_episode
from flywheel_simple.tray.s2.config import S2Config, segment_with
from flywheel_simple.tray.s2.jobs import S2Job
from flywheel_simple.tray.s2.parents import ParentDemo, load_palms, load_parent, parent_dataset
from flywheel_simple.tray.s2.replay import ReplayOperator, ReplayPlan
from flywheel_simple.tray.s2.segments import Segmentation
from flywheel_simple.tray.s2.variant import (
    VariantPlan,
    condition_distance,
    plan_variant,
    stitch_for,
)

Mode = Literal["exact", "variant"]

GENERATOR_VERSION = "da35-s2-1"


def generator_version(s2_cfg: S2Config, op_cfg: OperatorConfig) -> str:
    """GENERATOR_VERSION plus a hash of the S2 and operator settings."""
    values = {"s2": asdict(s2_cfg), "operator": asdict(op_cfg)}
    digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:8]
    return f"{GENERATOR_VERSION}+cfg.{digest}"


class ParentStore:
    """Parents of one batch by id (`<batch>/<shard>/<episode_index>`), loaded and cut once."""

    def __init__(self, batch: Path, cfg: S2Config) -> None:
        self.batch = batch
        self.cfg = cfg
        self._cache: dict[str, tuple[ParentDemo, Segmentation]] = {}
        self._palms = load_palms(batch)

    def get(self, parent_id: str) -> tuple[ParentDemo, Segmentation]:
        if parent_id not in self._cache:
            batch, shard, index = parent_id.split("/")
            if batch != self.batch.name:
                raise KeyError(f"{parent_id} is not in batch {self.batch}")
            demo = load_parent(parent_dataset(self.batch, shard), int(index), parent_id)
            if parent_id in self._palms:
                demo = dataclasses.replace(demo, palms=self._palms[parent_id])
            cut = segment_with(demo, self.cfg)
            self._cache[parent_id] = (demo, cut)
        return self._cache[parent_id]


class S2Streamer:
    """Replays the current job's parent; `begin_attempt` names the job before each reset."""

    def __init__(
        self,
        env: Any,
        parents: ParentStore,
        op_cfg: OperatorConfig,
        s2_cfg: S2Config,
        mode: Mode = "variant",
    ) -> None:
        self.env = env
        self.parents = parents
        self.op_cfg = op_cfg
        self.s2_cfg = s2_cfg
        self.mode = mode
        self.version = generator_version(s2_cfg, op_cfg)
        self.operator = ReplayOperator(op_cfg.ctrl0(), op_cfg.done_wait_s, cfg=s2_cfg)
        self.plan: ReplayPlan | VariantPlan | None = None
        self.distance: dict[str, float] = {}
        self._job: S2Job | None = None
        self._pre: Any = None
        self._last: tuple[float, PicoSignal] | None = None

    def bind(self, pre_processor: Any) -> None:
        self._pre = pre_processor

    def begin_attempt(self, condition: Condition, attempt: int) -> None:
        if not isinstance(condition, S2Job):
            raise TypeError(f"S2 sessions run S2Job conditions, got {condition!r}")
        self._job = condition

    def reset_status(self) -> None:
        """New episode (SIMPLE's teleop reset): the plan of the current job."""
        task = self.env.unwrapped.task
        if self._job is not None and getattr(task, "sample", None) is not None:
            demo, cut = self.parents.get(self._job.parent_id)
            parent_sample = sample_episode(task.cfg, demo.level, demo.seed)
            self.distance = condition_distance(parent_sample, task.sample)
            if self.mode == "exact":
                self.plan = ReplayPlan(demo, cut)
                self.operator.reset(self.plan)
            else:
                cfg = self.s2_cfg
                stitch = stitch_for(self._job.gen_seed, cfg.stitch_min_s, cfg.stitch_max_s)
                self.plan = plan_variant(demo, cut, parent_sample, task.sample, stitch)
                style = demo.meta.get("style") or {}
                accel = float(style.get("joystick_accel", self.op_cfg.joystick_accel))
                turn = float(style.get("turn_rate", self.op_cfg.turn_rate))
                self.operator.reset(self.plan, joystick_accel=accel, yaw=self._yaw_stick(turn))
        self._last = None

    def _yaw_stick(self, rate_max: float) -> YawStick:
        """The right stick at a gate: the virtual operator's steering at the parent's turn
        rate, pushed only past the gate's yaw tolerance. Every push raises the turn flag,
        and with it the walking policy: the body steps in place and sways."""
        cfg, tol = self.op_cfg, float(np.radians(self.s2_cfg.gate_yaw_tol_deg))
        return YawStick(
            self.operator.dt,
            rate_max=rate_max,
            gain=cfg.yaw_gain,
            rate_min=cfg.yaw_rate_min,
            engage=tol,
            release=tol / 3,
            lead=cfg.yaw_lead,
        )

    def start_streaming(self) -> None:
        pass

    def stop_streaming(self) -> None:
        pass

    @property
    def wants_reset(self) -> bool:
        return self._last is not None and self._last[1].reset

    def episode_meta(self) -> dict[str, Any]:
        """The flywheel block's source fields for this episode (DA-35 AC 6)."""
        assert self._job is not None
        demo, _ = self.parents.get(self._job.parent_id)
        return {
            "source_kind": "synthetic",
            "synthetic_tier": "S2",
            "action_quality": "planned",
            "generator_version": self.version,
            "parent_episode": self._job.parent_id,
            "parent_level": demo.level,
            "parent_seed": demo.seed,
            "parent_source_detail": demo.meta.get("source_detail"),
            "parent_style_seed": demo.meta.get("style_seed"),
            "parent_operator_version": demo.meta.get("operator_version"),
            "gen_seed": self._job.gen_seed,
            "s2_mode": self.mode,
            "transform": self.plan.meta() if isinstance(self.plan, VariantPlan) else None,
            "condition_distance": self.distance,
            "gate_waits": [list(g) for g in self.operator.gate_waits],
            **self._corrections(),
        }

    def _corrections(self) -> dict[str, Any]:
        """What the closed-loop replay corrected: placing hands, palms (task 10)."""
        op = self.operator
        return {
            "place_fix": None if op.place_fix is None else op.place_fix.as_dict(),
            "palm_correction_m": [round(float(np.linalg.norm(c)), 4) for c in op.palm_correction],
            "palm_error_max_m": round(op.palm_error_max, 4),
        }

    def attempt_notes(self) -> dict[str, Any]:
        """Job and the operator's segment timeline, for attempts.jsonl."""
        job = self._job
        return {
            "parent_episode": None if job is None else job.parent_id,
            "gen_seed": None if job is None else job.gen_seed,
            "generator_version": self.version,
            "s2_mode": self.mode,
            "condition_distance": self.distance,
            "gate_waits": [list(g) for g in self.operator.gate_waits],
            **self._corrections(),
            "timeline": [list(entry) for entry in self.operator.timeline],
            "frames_played": self.operator.ref,
        }

    def signal(self) -> PicoSignal:
        from flywheel_simple.tray.simple_task import tray_state  # SIMPLE venv

        """This step's signal; a second read at the same sim time repeats the first
        without the activation edge (TeleopPolicy reads twice when activating)."""
        data = self.env.unwrapped.mjData
        t = float(data.time)
        if self._last is not None and self._last[0] == t:
            return dataclasses.replace(self._last[1], activate=False)
        pelvis = data.body("pelvis")
        base = np.concatenate([pelvis.xpos, pelvis.xquat]).astype(np.float64)
        state = tray_state(self.env.unwrapped.mjModel, data)
        tray = np.concatenate([state.tray_pos, state.tray_quat]).astype(np.float64)
        calibration = None if self._last is None else calibration_of(self._pre)
        palms = (state.left_palm.copy(), state.right_palm.copy())
        signal = self.operator.step(t, calibration, base, tray, palms)
        self._last = (t, signal)
        return signal

    def get(self) -> Any:
        return pico_output(self.signal(), self.op_cfg.grasp_name, source="s2")

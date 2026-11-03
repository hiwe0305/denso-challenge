"""The S2 replay operator as a PICO streamer in SIMPLE's teleop pipeline (DA-35 tasks 9-11).

Plugs into `StreamerDecoupledAgent` where the headset would be, like the
virtual operator. Each attempt of a session is one S2 job: a parent demo, the
condition (level, seed) the env resets to, and a generation seed. Parents are
read from their batch directory (generate_parents.py) and cut once per process.

Only runs in the SIMPLE venv.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from flywheel_simple.tray.pico.agent import calibration_of, pico_output
from flywheel_simple.tray.pico.conditions import Condition
from flywheel_simple.tray.pico.operator import OperatorConfig, PicoSignal
from flywheel_simple.tray.s2.config import S2Config
from flywheel_simple.tray.s2.jobs import S2Job
from flywheel_simple.tray.s2.parents import ParentDemo, load_parent, parent_dataset
from flywheel_simple.tray.s2.replay import ReplayOperator, ReplayPlan
from flywheel_simple.tray.s2.segments import Segmentation, segment

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

    def get(self, parent_id: str) -> tuple[ParentDemo, Segmentation]:
        if parent_id not in self._cache:
            batch, shard, index = parent_id.split("/")
            if batch != self.batch.name:
                raise KeyError(f"{parent_id} is not in batch {self.batch}")
            demo = load_parent(parent_dataset(self.batch, shard), int(index), parent_id)
            cut = segment(demo, hold_s=self.cfg.hold_s, walk_min_s=self.cfg.walk_min_s)
            self._cache[parent_id] = (demo, cut)
        return self._cache[parent_id]


class S2Streamer:
    """Replays the current job's parent; `begin_attempt` names the job before each reset."""

    def __init__(
        self, env: Any, parents: ParentStore, op_cfg: OperatorConfig, s2_cfg: S2Config
    ) -> None:
        self.env = env
        self.parents = parents
        self.op_cfg = op_cfg
        self.version = generator_version(s2_cfg, op_cfg)
        self.operator = ReplayOperator(op_cfg.ctrl0(), op_cfg.done_wait_s)
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
        if self._job is not None:
            demo, cut = self.parents.get(self._job.parent_id)
            self.operator.reset(ReplayPlan(demo, cut))
        self._last = None

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
            "s2_mode": "exact",
        }

    def attempt_notes(self) -> dict[str, Any]:
        """Job and the operator's segment timeline, for attempts.jsonl."""
        job = self._job
        return {
            "parent_episode": None if job is None else job.parent_id,
            "gen_seed": None if job is None else job.gen_seed,
            "generator_version": self.version,
            "s2_mode": "exact",
            "timeline": [list(entry) for entry in self.operator.timeline],
            "frames_played": self.operator.ref,
        }

    def signal(self) -> PicoSignal:
        """This step's signal; a second read at the same sim time repeats the first
        without the activation edge (TeleopPolicy reads twice when activating)."""
        t = float(self.env.unwrapped.mjData.time)
        if self._last is not None and self._last[0] == t:
            return dataclasses.replace(self._last[1], activate=False)
        signal = self.operator.step(t, None if self._last is None else calibration_of(self._pre))
        self._last = (t, signal)
        return signal

    def get(self) -> Any:
        return pico_output(self.signal(), self.op_cfg.grasp_name, source="s2")

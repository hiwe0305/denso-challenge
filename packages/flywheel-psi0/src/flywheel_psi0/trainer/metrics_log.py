"""Turn what Psi0 hands `Trainer.log()` into `metrics.jsonl` lines (DA-19 AC 3).

Psi0 logs only through `accelerator.log(metrics, step=global_step)`, once per
optimiser step with `train/*` keys and once per evaluation with `eval/*` keys
(docs/g0/psi0-logging.md). `MetricsLog.log` takes the same dict and step and
appends one `TrainingMetric` line per split it finds, adding what Psi0 lacks:
the job identity, wall time, VRAM, throughput, and recomputed statistics:

* train line, every step: the train loss split by group and chunk position
  (`LossBreakdown`); at validation steps also the per-dimension statistics of
  actions sampled on that step's train batch (`train_stats`);
* val line: all of them from the evaluation's own predictions (`val_stats`).

The file is append-only: a resumed job opens it again with `attempt` raised by
one, and the evaluation lane keeps the highest attempt for each `(split, step)`.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from flywheel.contracts.training import TrainingMetric

from flywheel_psi0.trainer.val_stats import LossBreakdown, ValStats


@dataclass(frozen=True)
class JobIdentity:
    """Who a `metrics.jsonl` belongs to; constant for every line of one job."""

    run_plan_id: str
    job_id: str
    checkpoint_id: str
    release_id: str
    attempt: int
    vlm_frozen: bool


def _loss(value: float) -> float | str:
    """A finite loss as-is, otherwise the JSON string the contract asks for."""
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    return value


def _optional(metrics: Mapping[str, float], key: str) -> float | None:
    value = metrics.get(key)
    return None if value is None or not math.isfinite(value) else float(value)


class MetricsLog:
    """Appends `TrainingMetric` lines for one attempt of one train job."""

    def __init__(
        self,
        path: Path,
        identity: JobIdentity,
        val_stats: ValStats | None = None,
        train_loss: LossBreakdown | None = None,
        train_stats: ValStats | None = None,
        global_batch_size: int | None = None,
        vram_gb: Callable[[], float | None] = lambda: None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.path = path
        self.identity = identity
        self.val_stats = val_stats
        self.train_loss = train_loss
        self.train_stats = train_stats
        self._global_batch_size = global_batch_size
        self._vram_gb = vram_gb
        self._clock = clock
        self._start = clock()
        self._last_train_time: float | None = None
        self._lr = 0.0
        self._epoch = 0
        path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, metrics: Mapping[str, float], step: int) -> list[TrainingMetric]:
        """Append the lines for one `accelerator.log` call; returns what was written."""
        now = self._clock()
        records = []
        if "train/loss" in metrics:
            records.append(self._train(metrics, step, now))
        if "eval/loss" in metrics:
            records.append(self._val(metrics, step, now))
            # The next step's interval includes the whole evaluation, not training.
            self._last_train_time = None
        if records:
            with self.path.open("a", encoding="utf-8") as stream:
                for record in records:
                    stream.write(record.model_dump_json() + "\n")
        return records

    def _common(self, step: int, now: float) -> dict[str, object]:
        return {
            **vars(self.identity),
            "step": step,
            "epoch": self._epoch,
            "lr": self._lr,
            "vram_gb": self._vram_gb(),
            "wall_time_s": now - self._start,
        }

    def _train(self, metrics: Mapping[str, float], step: int, now: float) -> TrainingMetric:
        # Stage 3 and 2 log `lr_act`; stage 1 logs `lr`.
        lr = metrics.get("train/lr_act", metrics.get("train/lr"))
        if lr is not None:
            self._lr = float(lr)
        if "train/epoch" in metrics:
            self._epoch = int(metrics["train/epoch"])
        throughput = None
        if self._global_batch_size and self._last_train_time is not None:
            elapsed = now - self._last_train_time
            throughput = self._global_batch_size / elapsed if elapsed > 0 else None
        self._last_train_time = now
        loss_split = self.train_loss.summary() if self.train_loss is not None else {}
        sampled = self.train_stats.summary(errors=False) if self.train_stats is not None else {}
        return TrainingMetric.model_validate(
            {
                **self._common(step, now),
                **loss_split,
                **sampled,
                "split": "train",
                "loss": _loss(float(metrics["train/loss"])),
                "grad_norm_vlm": _optional(metrics, "train/grad_norm_vlm"),
                "grad_norm_action": _optional(metrics, "train/grad_norm_act"),
                "throughput": throughput,
            }
        )

    def _val(self, metrics: Mapping[str, float], step: int, now: float) -> TrainingMetric:
        stats = self.val_stats.summary() if self.val_stats is not None else {}
        return TrainingMetric.model_validate(
            {
                **self._common(step, now),
                "split": "val",
                "loss": _loss(float(metrics["eval/loss"])),
                **stats,
            }
        )

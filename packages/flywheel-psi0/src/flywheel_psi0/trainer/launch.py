"""Run the author's `scripts/train.py` with `metrics.jsonl` hooks, without editing Psi0.

`Psi0Trainer` starts this module under `torchrun` in Psi0's own environment, from the
Psi0 repo root (the author's paths are relative to it):

    torchrun --nproc_per_node=N -m flywheel_psi0.trainer.launch <launch.json>

It wraps methods of the stage's trainer class, then executes `scripts/train.py` as
`__main__` with the recipe's argv (docs/g0/psi0-logging.md):

* `log` - every `train/*` and `eval/*` dict goes to `MetricsLog`; at a validation
  step it first samples actions on that step's train batch, for the train line;
* `inference` - each val batch's predictions and targets go to the val `ValStats`,
  the sampled train batch's to the train one;
* `training_step` - keeps the batch, and switches on `LossTap`, which stands in for
  `torch.nn.functional` in the trainer's module and hands the per-element train
  loss to `LossBreakdown`;
* `clip_grad_norms` - with a frozen VLM Psi0 reports no VLM gradient norm, so it is
  measured here, after `backward` and before `zero_grad`, for DA-08 T8a.

`save_checkpoint` is wrapped too, to report where the run wrote its checkpoints.
Only rank 0 records anything; torch is imported lazily so this module also imports
on a CPU-only machine without Psi0.
"""

from __future__ import annotations

import contextlib
import functools
import importlib
import json
import math
import os
import runpy
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.contracts.artifacts import ActionLayout
from flywheel.contracts.v0 import InfraStatus
from pydantic import BaseModel, ConfigDict

from flywheel_psi0.trainer.metrics_log import JobIdentity, MetricsLog
from flywheel_psi0.trainer.val_stats import LossBreakdown, ValStats

VLM_GROUPS = ("lang_backbone", "vision_tower", "mm_projector")


class LaunchSpec(BaseModel):
    """Everything the launcher needs, written by `Psi0Trainer` as JSON."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    psi0_root: str
    trainer_module: str
    argv: list[str]
    metrics_path: str
    result_path: str
    identity: dict[str, Any]
    layout: ActionLayout
    hand_open_pose: list[float] | None = None
    global_batch_size: int | None = None
    rtc_prefix: int = 0


class LaunchResult(BaseModel):
    """What rank 0 reports back: where the run went and how it ended."""

    project_dir: str | None = None
    checkpoint_dir: str | None = None
    checkpoint_step: int | None = None
    status: InfraStatus = "ok"
    error: str | None = None


def _is_rank_zero() -> bool:
    return os.environ.get("RANK", "0") == "0"


def _trainer_class(module: str) -> type:
    """`psi.trainers.<module>.<Module>Trainer`, as `Trainer.instantiate` resolves it."""
    pascal = "".join(part.capitalize() for part in module.split("_"))
    return getattr(importlib.import_module(f"psi.trainers.{module}"), f"{pascal}Trainer")  # type: ignore[no-any-return]


def _floats(metrics: dict[str, Any]) -> dict[str, float]:
    """Psi0's dict as plain floats; `None` (e.g. no grad norm under deepspeed) is dropped."""
    return {
        key: float(value.item() if hasattr(value, "item") else value)
        for key, value in metrics.items()
        if value is not None
    }


def _numpy(tensor: Any) -> Any:
    return tensor.detach().float().cpu().numpy()


def _torch() -> Any | None:
    try:
        return importlib.import_module("torch")
    except ImportError:
        return None


def _vram_gb() -> float | None:
    torch = _torch()
    if torch is None or not torch.cuda.is_available():
        return None
    return float(torch.cuda.max_memory_allocated()) / 1e9


@dataclass
class Sinks:
    """Where each hook sends what it sees."""

    log: MetricsLog
    val: ValStats
    train_sampled: ValStats
    train_loss: LossBreakdown


class LossTap:
    """Stands in for `torch.nn.functional` in a Psi0 trainer module.

    Everything is passed through; while `active` (inside `training_step`), the
    result of `mse_loss(..., reduction="none")` - Psi0's per-element loss before it
    masks and sums it - also goes to `sink`. `evaluate()` computes the val loss with
    the same function, outside `training_step`, so it is not recorded.
    """

    def __init__(self, functional: Any, sink: Callable[[Any], None]) -> None:
        self._functional = functional
        self._sink = sink
        self.active = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._functional, name)

    def mse_loss(self, input: Any, target: Any, *args: Any, **kwargs: Any) -> Any:
        loss = self._functional.mse_loss(input, target, *args, **kwargs)
        if self.active and kwargs.get("reduction") == "none":
            self._sink(loss)
        return loss


def _is_validation_step(trainer: Any) -> bool:
    every = int(trainer.cfg.train.validation_steps)
    return every > 0 and int(trainer.global_step) % every == 0


def _sample_train_batch(trainer: Any) -> None:
    """Sample actions on the step's train batch, as `evaluate()` does on val batches.

    Only under ddp or one process: rank 0 runs the unwrapped model alone, which
    under fsdp or deepspeed would wait on the other ranks.
    """
    batch = getattr(trainer, "_flywheel_batch", None)
    if batch is None or trainer.cfg.train.data_parallel != "ddp":
        return
    torch = _torch()
    context: Any = contextlib.nullcontext()
    if torch is not None and torch.cuda.is_available():
        context = torch.autocast(device_type="cuda", dtype=trainer.dtype)
    trainer.set_eval()
    trainer._flywheel_sampling_train = True
    try:
        with context:
            trainer.inference(trainer.unwrap_model(), batch)
    finally:
        trainer._flywheel_sampling_train = False
        trainer.set_train()


def _vlm_grad_norm(trainer: Any) -> float:
    """Norm over the gradients of every non-action-header parameter (0 when frozen)."""
    total = 0.0
    for name, param in trainer.model.named_parameters():
        if "action_header." in name or param.grad is None:
            continue
        total += float(param.grad.detach().float().norm()) ** 2
    return math.sqrt(total)


def install_hooks(cls: type, sinks: Sinks, result: LaunchResult, result_path: Path) -> None:
    """Wrap `cls`'s methods in place; subclasses and instances pick the wrappers up."""
    original_log: Callable[..., Any] = cls.log  # type: ignore[attr-defined]
    original_step: Callable[..., Any] = cls.training_step  # type: ignore[attr-defined]
    original_inference: Callable[..., Any] = cls.inference  # type: ignore[attr-defined]
    original_clip: Callable[..., Any] | None = getattr(cls, "clip_grad_norms", None)
    original_save: Callable[..., Any] = cls.save_checkpoint  # type: ignore[attr-defined]

    @functools.wraps(original_log)
    def logged(self: Any, metrics: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        returned = original_log(self, metrics, *args, **kwargs)
        if _is_rank_zero():
            values = _floats(metrics)
            if "train/loss" in values and _is_validation_step(self):
                _sample_train_batch(self)
            measured = getattr(self, "_flywheel_grad_norm_vlm", None)
            if (
                "train/loss" in values
                and "train/grad_norm_vlm" not in values
                and measured is not None
            ):
                values["train/grad_norm_vlm"] = measured
            sinks.log.log(values, step=int(self.global_step))
        return returned

    def record_loss(loss: Any) -> None:
        if _is_rank_zero():
            sinks.train_loss.add(_numpy(loss))

    # The trainer module's own `F` (`import torch.nn.functional as F`), if it has one.
    module: Any = sys.modules[cls.__module__]
    tap: LossTap | None = None
    if hasattr(module, "F"):
        tap = LossTap(module.F, record_loss)
        module.F = tap

    @functools.wraps(original_step)
    def stepped(self: Any, batch: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_rank_zero():
            self._flywheel_batch = batch
        if tap is None:
            return original_step(self, batch, *args, **kwargs)
        tap.active = True
        try:
            return original_step(self, batch, *args, **kwargs)
        finally:
            tap.active = False

    @functools.wraps(original_inference)
    def inferred(
        self: Any, eval_model: Any, batch: dict[str, Any], *args: Any, **kwargs: Any
    ) -> Any:
        predicted = original_inference(self, eval_model, batch, *args, **kwargs)
        if _is_rank_zero():
            chunk = predicted.shape[1]
            sampled = (
                sinks.train_sampled
                if getattr(self, "_flywheel_sampling_train", False)
                else sinks.val
            )
            sampled.add(_numpy(predicted), _numpy(batch["actions"][:, :chunk]))
        return predicted

    @functools.wraps(original_save)
    def saved(self: Any, global_step: int, *args: Any, **kwargs: Any) -> Any:
        path = original_save(self, global_step, *args, **kwargs)
        if _is_rank_zero():
            result.project_dir = str(self.project_dir)
            result.checkpoint_dir = None if path is None else str(path)
            result.checkpoint_step = int(global_step)
            result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return path

    cls.log = logged  # type: ignore[attr-defined]
    cls.training_step = stepped  # type: ignore[attr-defined]
    cls.inference = inferred  # type: ignore[attr-defined]
    cls.save_checkpoint = saved  # type: ignore[attr-defined]

    if original_clip is not None:
        clip: Callable[..., Any] = original_clip

        @functools.wraps(clip)
        def clipped(self: Any, *args: Any, **kwargs: Any) -> Any:
            norms = clip(self, *args, **kwargs)
            if _is_rank_zero() and not any(group in norms for group in VLM_GROUPS):
                self._flywheel_grad_norm_vlm = _vlm_grad_norm(self)
            return norms

        cls.clip_grad_norms = clipped  # type: ignore[attr-defined]


def _status(error: BaseException) -> InfraStatus:
    return "out_of_memory" if type(error).__name__ == "OutOfMemoryError" else "policy_error"


def run(spec: LaunchSpec) -> None:
    root = Path(spec.psi0_root)
    result_path = Path(spec.result_path)
    result = LaunchResult()
    identity = JobIdentity(**spec.identity)
    hand = None if spec.hand_open_pose is None else np.asarray(spec.hand_open_pose)
    val = ValStats(spec.layout, hand_open_pose=hand)
    train_sampled = ValStats(spec.layout, hand_open_pose=hand)
    train_loss = LossBreakdown(spec.layout, rtc_prefix=spec.rtc_prefix)
    log = MetricsLog(
        Path(spec.metrics_path),
        identity,
        val_stats=val,
        train_loss=train_loss,
        train_stats=train_sampled,
        global_batch_size=spec.global_batch_size,
        vram_gb=_vram_gb,
    )
    sinks = Sinks(log=log, val=val, train_sampled=train_sampled, train_loss=train_loss)
    install_hooks(_trainer_class(spec.trainer_module), sinks, result, result_path)

    train_py = root / "scripts" / "train.py"
    sys.argv = [str(train_py), *spec.argv]
    try:
        runpy.run_path(str(train_py), run_name="__main__")
    except BaseException as error:
        if _is_rank_zero():
            result.status, result.error = _status(error), f"{type(error).__name__}: {error}"
            result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        raise
    if _is_rank_zero():
        result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    (spec_path,) = sys.argv[1:] if argv is None else argv
    spec = LaunchSpec.model_validate(json.loads(Path(spec_path).read_text(encoding="utf-8")))
    os.chdir(spec.psi0_root)
    run(spec)


if __name__ == "__main__":
    main()

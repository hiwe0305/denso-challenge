"""Run the author's `scripts/train.py` with `metrics.jsonl` hooks, without editing Psi0.

`Psi0Trainer` starts this module under `torchrun` in Psi0's own environment, from the
Psi0 repo root (the author's paths are relative to it):

    torchrun --nproc_per_node=N -m flywheel_psi0.trainer.launch <launch.json>

It wraps three methods of the stage's trainer class, then executes `scripts/train.py`
as `__main__` with the recipe's argv (docs/g0/psi0-logging.md):

* `log` - every `train/*` and `eval/*` dict goes to `MetricsLog`;
* `inference` - each val batch's predictions and targets go to `ValStats`;
* `clip_grad_norms` - with a frozen VLM Psi0 reports no VLM gradient norm, so it is
  measured here, after `backward` and before `zero_grad`, for DA-08 T8a.

`save_checkpoint` is wrapped too, to report where the run wrote its checkpoints.
Only rank 0 records anything; torch is imported lazily so this module also imports
on a CPU-only machine without Psi0.
"""

from __future__ import annotations

import functools
import importlib
import json
import math
import os
import runpy
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.contracts.artifacts import ActionLayout
from flywheel.contracts.v0 import InfraStatus
from pydantic import BaseModel, ConfigDict

from flywheel_psi0.trainer.metrics_log import JobIdentity, MetricsLog
from flywheel_psi0.trainer.val_stats import ValStats

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


def _vram_gb() -> float | None:
    try:
        torch = importlib.import_module("torch")
    except ImportError:
        return None
    if not torch.cuda.is_available():
        return None
    return float(torch.cuda.max_memory_allocated()) / 1e9


def _vlm_grad_norm(trainer: Any) -> float:
    """Norm over the gradients of every non-action-header parameter (0 when frozen)."""
    total = 0.0
    for name, param in trainer.model.named_parameters():
        if "action_header." in name or param.grad is None:
            continue
        total += float(param.grad.detach().float().norm()) ** 2
    return math.sqrt(total)


def install_hooks(
    cls: type, log: MetricsLog, stats: ValStats, result: LaunchResult, result_path: Path
) -> None:
    """Wrap `cls`'s methods in place; subclasses and instances pick the wrappers up."""
    original_log: Callable[..., Any] = cls.log  # type: ignore[attr-defined]
    original_inference: Callable[..., Any] = cls.inference  # type: ignore[attr-defined]
    original_clip: Callable[..., Any] | None = getattr(cls, "clip_grad_norms", None)
    original_save: Callable[..., Any] = cls.save_checkpoint  # type: ignore[attr-defined]

    @functools.wraps(original_log)
    def logged(self: Any, metrics: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        returned = original_log(self, metrics, *args, **kwargs)
        if _is_rank_zero():
            values = _floats(metrics)
            measured = getattr(self, "_flywheel_grad_norm_vlm", None)
            if (
                "train/loss" in values
                and "train/grad_norm_vlm" not in values
                and measured is not None
            ):
                values["train/grad_norm_vlm"] = measured
            log.log(values, step=int(self.global_step))
        return returned

    @functools.wraps(original_inference)
    def inferred(
        self: Any, eval_model: Any, batch: dict[str, Any], *args: Any, **kwargs: Any
    ) -> Any:
        predicted = original_inference(self, eval_model, batch, *args, **kwargs)
        if _is_rank_zero():
            chunk = predicted.shape[1]
            stats.add(_numpy(predicted), _numpy(batch["actions"][:, :chunk]))
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
    stats = ValStats(
        spec.layout,
        hand_open_pose=None if spec.hand_open_pose is None else np.asarray(spec.hand_open_pose),
    )
    log = MetricsLog(
        Path(spec.metrics_path),
        identity,
        val_stats=stats,
        global_batch_size=spec.global_batch_size,
        vram_gb=_vram_gb,
    )
    install_hooks(_trainer_class(spec.trainer_module), log, stats, result, result_path)

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

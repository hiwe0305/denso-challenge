"""Run Psi0's stage 1 (`PretrainTrainer`) with `metrics.jsonl` hooks (DA-30 task 1).

The stage 3 launcher (`flywheel_psi0.trainer.launch`) also wraps `inference` and taps
`F.mse_loss`, which `PretrainTrainer` does not have: stage 1 trains next-token
cross-entropy on FAST action tokens and has no sampled actions to compare. This
launcher keeps the parts that apply - `LaunchSpec`, `LaunchResult`, `MetricsLog` -
and wraps only `log` and `save_checkpoint`:

    torchrun --nproc_per_node=N -m flywheel_psi0.stage1.launch <launch.json>

Before the run it applies `restore_shuffle` (`flywheel_psi0.stage1.patches`): without
it, stage 1 at the pin stops with `UnboundLocalError` before its first step.
"""

from __future__ import annotations

import functools
import json
import os
import runpy
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from flywheel_psi0.stage1.patches import restore_shuffle
from flywheel_psi0.trainer.launch import (
    LaunchResult,
    LaunchSpec,
    _floats,
    _is_rank_zero,
    _status,
    _trainer_class,
    _vram_gb,
)
from flywheel_psi0.trainer.metrics_log import JobIdentity, MetricsLog


def install_hooks(cls: type, log: MetricsLog, result: LaunchResult, result_path: Path) -> None:
    """Wrap `log` and `save_checkpoint` of `cls` in place."""
    original_log: Callable[..., Any] = cls.log  # type: ignore[attr-defined]
    original_save: Callable[..., Any] = cls.save_checkpoint  # type: ignore[attr-defined]

    @functools.wraps(original_log)
    def logged(self: Any, metrics: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        # PretrainTrainer.log adds train/grad_norm_vlm to `metrics` in place.
        returned = original_log(self, metrics, *args, **kwargs)
        if _is_rank_zero():
            log.log(_floats(metrics), step=int(self.global_step))
        return returned

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
    cls.save_checkpoint = saved  # type: ignore[attr-defined]


def run(spec: LaunchSpec) -> None:
    root = Path(spec.psi0_root)
    result_path = Path(spec.result_path)
    result = LaunchResult()
    log = MetricsLog(
        Path(spec.metrics_path),
        JobIdentity(**spec.identity),
        global_batch_size=spec.global_batch_size,
        vram_gb=_vram_gb,
    )
    cls = _trainer_class(spec.trainer_module)
    if restore_shuffle(cls) and _is_rank_zero():
        print(f"flywheel: {cls.__name__}.create_dataloaders shuffle=True restored", flush=True)
    install_hooks(cls, log, result, result_path)

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

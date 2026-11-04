"""Try the stage 1 DeepSpeed path on a tiny model before the real one loads (DA-30).

Run 1 (4/11/2026) spent ten minutes of setup and a model load before
`accelerator.prepare` refused the DeepSpeed config. `setup` now runs this first, in
Psi0's environment, on the plan's config:

    torchrun --nproc_per_node=1 -m flywheel_psi0.stage1.preflight <deepspeed.json> \\
        --lr 1e-4 --betas 0.9 0.999 --eps 1e-8 --weight-decay 0.0 \\
        --micro-batch 16 --accumulation 2 --precision bf16 --total-steps 200

It builds DeepSpeed's CPU Adam (a JIT build on first use), then builds the
Accelerator, `DummyOptim` and `DummyScheduler` as Psi0's `scripts/train.py` and
`PretrainTrainer` do, prepares a two-group model (the second group at its own lr, as
Psi0's vision tower) and takes optimizer steps. It fails when the config does not
prepare, or when a group is at another lr than its own after `prepare` or the steps.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import time
from types import SimpleNamespace
from typing import Any

HIDDEN = 64  # accelerate sizes ZeRO-3's "auto" buckets from model.config.hidden_size
GROUP_LR_RATIO = 0.1  # the second group's lr, as Psi0's vision tower: 1e-5 against 1e-4


def _tiny_model(torch: Any) -> Any:
    class Tiny(torch.nn.Module):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__()
            self.config = SimpleNamespace(hidden_size=HIDDEN)
            self.body = torch.nn.Linear(HIDDEN, HIDDEN, bias=False)
            self.head = torch.nn.Linear(HIDDEN, 1, bias=False)

        def forward(self, x: Any) -> Any:
            return self.head(torch.relu(self.body(x)))

    return Tiny()


def _check_lrs(optimizer: Any, want: list[float], when: str) -> list[float]:
    lrs = [float(group["lr"]) for group in optimizer.param_groups]
    if len(lrs) != len(want) or not all(map(math.isclose, lrs, want)):
        raise SystemExit(f"preflight: group lrs {lrs} {when}, want {want}")
    return lrs


def run(args: argparse.Namespace) -> dict[str, Any]:
    torch = importlib.import_module("torch")
    accelerate = importlib.import_module("accelerate")
    utils = importlib.import_module("accelerate.utils")

    start = time.monotonic()
    adam = importlib.import_module("deepspeed.ops.adam")
    adam.DeepSpeedCPUAdam([torch.nn.Parameter(torch.zeros(1))])
    cpu_adam_seconds = time.monotonic() - start

    start = time.monotonic()
    plugin = utils.DeepSpeedPlugin(zero_stage=3, hf_ds_config=args.config)
    accelerator = accelerate.Accelerator(
        gradient_accumulation_steps=args.accumulation,
        mixed_precision=args.precision,
        deepspeed_plugin=plugin,
    )
    accelerator.deepspeed_plugin.deepspeed_config["train_micro_batch_size_per_gpu"] = (
        args.micro_batch
    )
    model = _tiny_model(torch)
    group_lr = args.lr * GROUP_LR_RATIO
    groups = [
        {"params": [model.body.weight], "weight_decay": args.weight_decay},
        {"params": [model.head.weight], "weight_decay": args.weight_decay, "lr": group_lr},
    ]
    optimizer = utils.DummyOptim(
        groups,
        lr=args.lr,
        betas=tuple(args.betas),
        weight_decay=args.weight_decay,
        eps=args.eps,
    )
    scheduler = utils.DummyScheduler(
        optimizer, total_num_steps=args.total_steps, warmup_num_steps=0
    )
    model, optimizer, scheduler = accelerator.prepare(model, optimizer, scheduler)
    want = [args.lr, group_lr]
    _check_lrs(optimizer, want, "after prepare")
    dtype = {"bf16": torch.bfloat16, "fp16": torch.float16}.get(args.precision, torch.float32)
    for _ in range(2 * args.accumulation):
        with accelerator.accumulate(model):
            x = torch.randn(args.micro_batch, HIDDEN, device=accelerator.device, dtype=dtype)
            loss = model(x).float().pow(2).mean()
            accelerator.backward(loss)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
    lrs = _check_lrs(optimizer, want, "after two steps")
    return {
        "cpu_adam_seconds": round(cpu_adam_seconds, 1),
        "prepare_and_steps_seconds": round(time.monotonic() - start, 1),
        "optimizer": type(getattr(optimizer, "optimizer", optimizer)).__name__,
        "group_lrs": lrs,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("config", help="the DeepSpeed config the run will use")
    parser.add_argument("--lr", type=float, required=True)
    parser.add_argument("--betas", type=float, nargs=2, required=True)
    parser.add_argument("--eps", type=float, required=True)
    parser.add_argument("--weight-decay", type=float, required=True)
    parser.add_argument("--micro-batch", type=int, required=True)
    parser.add_argument("--accumulation", type=int, required=True)
    parser.add_argument("--precision", required=True)
    parser.add_argument("--total-steps", type=int, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    print("preflight:", json.dumps(run(parse_args(argv))), flush=True)


if __name__ == "__main__":
    main()

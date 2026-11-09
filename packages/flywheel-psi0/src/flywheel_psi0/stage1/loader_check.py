"""Psi0's own stage 1 data path on CPU, without the model: does the export load?

Run in Psi0's environment from the Psi0 repo root, on the `launch.json` that
`Stage1Trainer` writes for a job, so it parses exactly the argv the run gets:

    python -m flywheel_psi0.stage1.loader_check <launch.json> --batches 2

It parses the argv with the config module and tyro as `scripts/train.py` does, builds
`PretrainTrainer` on CPU, loads only the parent's processor (tokenizer and image
preprocessor, not the weights), calls the trainer's own `create_datasets` (EgoDex
loader, transforms, FAST tokenizer) and `create_dataloaders` (with `restore_shuffle`),
and draws a few collated batches. It prints one JSON report: batch shapes, action
tokens per sample, decode errors, seconds per batch; it exits 1 when a batch has no
action token, a NaN, or an unexpected shape. For the DA-18 export (AC 2 of DA-18
uses Psi0's loader the same way) and as a gate before a GPU job.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from flywheel_psi0.stage1.patches import restore_shuffle


def build_trainer(argv: list[str]) -> Any:
    tyro = importlib.import_module("tyro")
    module = importlib.import_module(f"psi.config.train.{argv[0]}")
    config = tyro.cli(
        module.DynamicLaunchConfig, config=(tyro.conf.ConsolidateSubcommandArgs,), args=argv[1:]
    )
    trainers = importlib.import_module("psi.trainers.pretrain")
    trainer = trainers.PretrainTrainer(config, "cpu")
    transformers = importlib.import_module("transformers")
    trainer.vlm_processor = transformers.AutoProcessor.from_pretrained(
        config.model.model_name_or_path
    )
    trainer.tokenizer = trainer.vlm_processor.tokenizer
    trainer.im_end_token_id = trainer.tokenizer.convert_tokens_to_ids("<|im_end|>")
    return trainer


PAD_DIMS = frozenset((6, 7, 8, 30, 31, 32))  # zero in the 48-d EgoDex action, never normalized
CLIP_EDGE = 0.999


def action_clip_summary(rows: list[list[float]]) -> dict[str, Any]:
    """How much of the normalized actions sits on Psi0's [-1, 1] clip.

    `raw_actions` in a collated batch is the action after `bounds_q99` normalization
    and `np.clip(actions, -1, 1)` (`config/transform.py:682-685` at the pin). On data
    the stats fit, about 2% of the values of a dim lie past q01..q99; a large share
    means the stats do not fit the data and the FAST tokens see mostly the clip.
    """
    live = [[x for d, x in enumerate(row) if d not in PAD_DIMS] for row in rows]
    values = [abs(x) >= CLIP_EDGE for row in live for x in row]
    return {
        "samples": len(rows),
        "clipped_value_share": round(sum(values) / len(values), 3) if values else None,
        "samples_with_a_clipped_dim": (
            round(sum(any(abs(x) >= CLIP_EDGE for x in row) for row in live) / len(live), 3)
            if live
            else None
        ),
    }


def check_batches(trainer: Any, batches: int, workers: int | None = None) -> dict[str, Any]:
    torch = importlib.import_module("torch")
    if workers is not None:
        # create_dataloaders reads an optional `num_workers` (12 when absent) that the
        # EgoDex config does not declare; set it around pydantic's validation.
        object.__setattr__(trainer.data_cfg, "num_workers", workers)
    train_dataset, val_dataset = trainer.create_datasets()
    report: dict[str, Any] = {"train_samples": len(train_dataset)}
    try:  # the pin as it is, to record whether the patch is still needed
        trainer.create_dataloaders(train_dataset, val_dataset)
        report["unpatched"] = "ok"
    except UnboundLocalError as error:
        report["unpatched"] = f"UnboundLocalError: {error}"
    report["shuffle_patched"] = restore_shuffle(type(trainer))
    trainer.create_dataloaders(train_dataset, val_dataset)
    tokenizer = trainer.action_tokenizer
    begin, bins = tokenizer.action_token_begin_idx, tokenizer.n_bins
    problems: list[str] = []
    seen: list[dict[str, Any]] = []
    rows: list[list[float]] = []
    one_token = 0
    start = time.monotonic()
    for index, batch in enumerate(trainer.train_dataloader):
        if index >= batches:
            break
        labels = batch["labels"]
        is_action = (labels >= begin) & (labels < begin + bins)
        per_sample = is_action.sum(dim=1).tolist()
        raw = batch.get("raw_actions")
        seen.append(
            {
                "seconds": round(time.monotonic() - start, 2),
                "input_ids": list(batch["input_ids"].shape),
                "pixel_values": list(batch["pixel_values"].shape),
                "image_grid_thw": batch["image_grid_thw"][0].tolist(),
                "action_tokens_per_sample": [min(per_sample), max(per_sample)],
                "raw_action_shape": list(raw[0].shape) if raw is not None else None,
            }
        )
        one_token += sum(n == 1 for n in per_sample)
        if raw is not None:
            rows += [torch.as_tensor(r).float().reshape(-1).tolist() for r in raw]
        if min(per_sample) == 0:
            problems.append(f"batch {index}: a sample has no FAST action token")
        if torch.isnan(batch["pixel_values"].float()).any():
            problems.append(f"batch {index}: NaN in pixel_values")
        if raw is not None and any(torch.isnan(torch.as_tensor(r)).any() for r in raw):
            problems.append(f"batch {index}: NaN in raw_actions")
        if batch["input_ids"].shape[0] != trainer.train_cfg.train_batch_size:
            problems.append(f"batch {index}: {batch['input_ids'].shape[0]} samples")
        start = time.monotonic()
    # A 1-token sample is usually a zero delta: near a clip's end Psi0 repeats the last
    # frame index instead of the one `upsample_rate` ahead (`egodex_dataset.py:470-506`).
    report |= {
        "batches": seen,
        "actions": action_clip_summary(rows) | {"one_token_samples": one_token},
        "problems": problems,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("launch", type=Path, help="launch.json written by Stage1Trainer")
    parser.add_argument("--batches", type=int, default=2)
    parser.add_argument("--workers", type=int, help="dataloader workers (the run uses 12)")
    args = parser.parse_args(argv)
    launch = json.loads(args.launch.read_text(encoding="utf-8"))
    os.chdir(launch["psi0_root"])
    report = check_batches(build_trainer(launch["argv"]), args.batches, args.workers)
    print(json.dumps(report, indent=1))
    return 1 if report["problems"] or not report["batches"] else 0


if __name__ == "__main__":
    sys.exit(main())

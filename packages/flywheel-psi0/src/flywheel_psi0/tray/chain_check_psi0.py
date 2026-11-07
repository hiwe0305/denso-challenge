"""Psi0 side of the train/serve chain check of checkpoint C (DA-34 task 3.7, tray.md 15).

Runs in the Psi0 environment (container of `docker/psi0/compose.yaml`, working dir the Psi0
checkout, as `scripts/g0/serve_psi0.sh` runs the server), imports `psi` and `torch` lazily:

    stats       B1 of tray.md 15.3: build the launch config as `Server.__init__` of
                `psi.deploy.serve_psi0_simple` does (argv.txt + run_config.json), and compare the
                action/state bounds it ends up with against a stats_psi0.json; report where
                `stat_path` resolves at serve time. No GPU.
    train-path  the train path of A (tray.md 15.2): the dataset of C's launch config, split
                `val` (`no_aug`), on a local copy of set C, and `Psi0Model.predict_action` with
                the frame's noise seed, as the server seeds it (`serve_psi0_seeded`). Writes
                the denormalized chunk per frame, the server's units.

The CPU side (frame list, serve path, readings) is `flywheel_psi0.tray.chain_check`.
Psi0's source is not edited.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

QWEN3VL_VARIANT = "Qwen/Qwen3-VL-2B-Instruct"  # psi.models.psi0.QWEN3VL_VARIANT at cda3fdf


def load_launch(run_dir: Path) -> Any:
    """LaunchConfig of a run dir, built as `serve_psi0_simple.Server.__init__` builds it."""
    from psi.utils import (  # type: ignore[import-not-found]
        apply_legacy_model_config_defaults,
        parse_args_to_tyro_config,
    )

    config = parse_args_to_tyro_config(run_dir / "argv.txt")
    conf = apply_legacy_model_config_defaults(json.loads((run_dir / "run_config.json").read_text()))
    return config.model_validate(conf)


def max_diff(served: Any, reference: list[float]) -> float:
    """Largest |served - reference| over the reference dims; served may be padded longer."""
    if served is None:
        return float("inf")
    pairs = list(zip(served, reference, strict=False))
    if len(pairs) != len(reference):
        return float("inf")
    return max(abs(float(a) - float(b)) for a, b in pairs)


def _cmd_stats(args: argparse.Namespace) -> int:
    from psi.utils import resolve_path

    launch = load_launch(args.run_dir)
    field = launch.data.transform.field
    stats = json.loads(args.stats.read_text())
    try:
        resolved: Path | None = Path(resolve_path(field.stat_path))
    except Exception:  # noqa: BLE001  resolve_path raises when nothing matches
        resolved = None
    found = resolved is not None and resolved.exists()
    pad = list(getattr(field, "state_min", []) or [])[len(stats["states"]["min"]) :]
    report = {
        "stat_path": field.stat_path,
        "normalize_state": bool(field.normalize_state),
        "action_norm_type": field.action_norm_type,
        "resolved_at_serve": str(resolved) if found else None,
        "resolved_sha256": hashlib.sha256(resolved.read_bytes()).hexdigest()
        if found and resolved
        else None,
        "reference": str(args.stats),
        "reference_sha256": hashlib.sha256(args.stats.read_bytes()).hexdigest(),
        "max_diff": {
            "action_min": max_diff(field.action_min, stats["action"]["min"]),
            "action_max": max_diff(field.action_max, stats["action"]["max"]),
            "state_min": max_diff(field.state_min, stats["states"]["min"]),
            "state_max": max_diff(field.state_max, stats["states"]["max"]),
        },
        "state_dims_reference": len(stats["states"]["min"]),
        "state_dims_served": len(field.state_min or []),
        "state_padding_max_abs": max((abs(float(x)) for x in pad), default=0.0),
    }
    same_file = not found or report["resolved_sha256"] == report["reference_sha256"]
    report["b1"] = (
        "match" if same_file and all(v == 0.0 for v in report["max_diff"].values()) else "differs"
    )
    text = json.dumps(report, indent=1)
    if args.json:
        args.json.write_text(text + "\n")
    print(text)
    return 0


def _cmd_train_path(args: argparse.Namespace) -> int:
    import numpy as np
    import torch  # type: ignore[import-not-found]
    from psi.models.psi0 import Psi0Model  # type: ignore[import-not-found]
    from transformers import AutoProcessor  # type: ignore[import-not-found]

    launch = load_launch(args.run_dir)
    data_cfg = launch.data.model_copy(deep=True)
    data_cfg.root_dir = str(args.root_dir)  # the run's Colab path -> the local copy of set C
    processor = AutoProcessor.from_pretrained(QWEN3VL_VARIANT)
    dataset = data_cfg(split="val", transform_kwargs={"vlm_processor": processor, "no_aug": True})
    field = launch.data.transform.field
    model = Psi0Model.from_pretrained(args.run_dir, args.ckpt_step, launch, device=args.device)
    model.to(args.device)
    model.eval()
    da = int(launch.model.action_dim)

    frames = [json.loads(line) for line in args.frames.read_text().splitlines() if line.strip()]
    done: set[int] = set()
    if args.out.exists():
        done = {
            int(json.loads(line)["index"]) for line in args.out.read_text().splitlines() if line
        }
    t0 = time.monotonic()
    with args.out.open("a", encoding="utf-8") as out:
        for n, f in enumerate(frames):
            index = int(f["index"])
            if index in done:
                continue
            item = dataset[index]
            states = torch.as_tensor(np.asarray(item["states"], dtype=np.float32)).to(args.device)
            seed = int(f["noise_seed"])
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            raw = model.predict_action(
                observations=[list(item["observations"])],
                states=states.unsqueeze(0),
                instructions=[item["instruction"]],
                num_inference_steps=args.steps,
                traj2ds=None,
            )
            raw = raw.reshape(-1, da).float().detach().cpu().numpy()
            action = np.asarray(field.denormalize(raw))
            row = {
                "index": index,
                "action": action.tolist(),
                "instruction": item["instruction"],
                "image_size": list(item["observations"][0].size),
            }
            out.write(json.dumps(row) + "\n")
            out.flush()
            if n % 50 == 0:
                print(f"{n}/{len(frames)} frames, {time.monotonic() - t0:.0f} s", flush=True)
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("stats")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--stats", type=Path, required=True, help="stats_psi0.json of set C")
    p.add_argument("--json", type=Path)
    p.set_defaults(fn=_cmd_stats)

    p = sub.add_parser("train-path")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--ckpt-step", type=int, default=40000)
    p.add_argument("--root-dir", type=Path, required=True, help="dir holding the repo id of C")
    p.add_argument("--frames", type=Path, required=True)
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--steps", type=int, default=10, help="= the server's num_inference_steps")
    p.add_argument("--out", type=Path, required=True, help="jsonl, appended (resumable)")
    p.set_defaults(fn=_cmd_train_path)

    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())

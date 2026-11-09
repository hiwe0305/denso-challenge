"""The stage 1 VLM in the layout stage 3 loads (DA-30 task 2, design 28/10 Q-28C).

At Psi0 `cda3fdf`, `PretrainTrainer.save_checkpoint` (`trainers/pretrain.py:441-447`)
writes `accelerator.save_model(self.model, ckpt_dir)`: the Qwen3-VL weights as one
`model.safetensors` (bf16, gathered by ZeRO-3 since the plan's DeepSpeed config sets
`gather_16bit_weights_on_model_save`), then DeepSpeed's full training state beside it
(`trainer.py:428-463`). It writes no `config.json` and no processor files. Stage 3's
`FinetuneTrainer.init_qwen3vl_models` (`trainers/finetune.py:266-288`) loads both the
model and the processor from `model.model_name_or_path` alone, so a stage 1 checkpoint
directory as saved cannot be that path.

`package` builds the directory stage 3 can take: the trained `model.safetensors` and
every other file of the parent's directory (`config.json`, `generation_config.json`,
tokenizer and processor files), which stage 1 does not change: the vocabulary was
resized when the parent was trained (`pretrain.py:63-72` resizes to
len(tokenizer) + 2048 FAST bins, padded to 192, and the parent's config already has
that size), and the processor is read, never written. It checks the trained file's
safetensors header against the parent's (same tensor names, shapes and dtypes) and
writes `vlm.json` with every file's sha256.

`package` is standard library only (`persist` runs it in the VM's python);
`load_check` needs Psi0's environment:

    .venv-psi/bin/python -m flywheel_psi0.stage1.vlm_checkpoint load-check <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import shutil
import struct
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

WEIGHTS = "model.safetensors"
MANIFEST = "vlm.json"
FORMAT = "psi0-stage1-vlm"
_CHUNK = 1 << 22


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def safetensors_header(path: Path) -> dict[str, tuple[str, tuple[int, ...]]]:
    """`{tensor name: (dtype, shape)}` from a safetensors file's JSON header."""
    with path.open("rb") as f:
        (length,) = struct.unpack("<Q", f.read(8))
        header: dict[str, Any] = json.loads(f.read(length))
    return {
        name: (str(entry["dtype"]), tuple(int(n) for n in entry["shape"]))
        for name, entry in header.items()
        if name != "__metadata__"
    }


def header_problems(
    trained: Mapping[str, tuple[str, tuple[int, ...]]],
    parent: Mapping[str, tuple[str, tuple[int, ...]]],
) -> list[str]:
    """Why `trained` would not load where `parent` does; empty when the headers agree."""
    problems = []
    missing, extra = sorted(set(parent) - set(trained)), sorted(set(trained) - set(parent))
    if missing:
        problems.append(f"{len(missing)} tensor(s) of the parent missing, e.g. {missing[:3]}")
    if extra:
        problems.append(f"{len(extra)} tensor(s) not in the parent, e.g. {extra[:3]}")
    changed = sorted(n for n in set(parent) & set(trained) if parent[n] != trained[n])
    problems += [f"{n}: {trained[n]}, the parent has {parent[n]}" for n in changed[:5]]
    if len(changed) > 5:
        problems.append(f"... {len(changed) - 5} more tensor(s) differ")
    return problems


def package(
    checkpoint_dir: Path, parent_dir: Path, out: Path, identity: Mapping[str, Any]
) -> dict[str, Any]:
    """Write the stage 3 loadable VLM of `checkpoint_dir` at `out`; returns `vlm.json`.

    A second call for the same weights only rewrites `vlm.json` (persist may run at
    the watcher's soft cap and again by hand).
    """
    trained = checkpoint_dir / WEIGHTS
    if not trained.is_file():
        raise FileNotFoundError(f"{trained}: no weights (did the run reach a checkpoint?)")
    weights_sha256 = sha256(trained)
    problems = header_problems(
        safetensors_header(trained), safetensors_header(parent_dir / WEIGHTS)
    )
    out.mkdir(parents=True, exist_ok=True)
    previous = out / MANIFEST
    kept = (
        previous.is_file()
        and json.loads(previous.read_text(encoding="utf-8")).get("weights_sha256") == weights_sha256
        and (out / WEIGHTS).is_file()
        and (out / WEIGHTS).stat().st_size == trained.stat().st_size
    )
    files: dict[str, str] = {}
    for source in sorted(p for p in parent_dir.iterdir() if p.is_file()):
        if source.name == WEIGHTS or source.suffix == ".safetensors":
            continue
        shutil.copyfile(source, out / source.name)
        files[source.name] = sha256(source)
    if not kept:
        partial = out / f"{WEIGHTS}.part"
        shutil.copyfile(trained, partial)
        partial.replace(out / WEIGHTS)
    files[WEIGHTS] = weights_sha256
    manifest = {
        "format": FORMAT,
        **identity,
        "checkpoint_dir": str(checkpoint_dir),
        "weights_sha256": weights_sha256,
        "weights_bytes": trained.stat().st_size,
        "files": files,
        "header_problems": problems,
        "loadable_as_model_name_or_path": not problems,
    }
    previous.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


FAST_BINS = 2048  # the recipe's `model.action_tokenizer.bins`


def load_check(path: Path) -> dict[str, Any]:
    """Load `path` as stage 3 does and report what would go wrong; run in Psi0's env.

    `FinetuneTrainer.init_qwen3vl_models` calls `from_pretrained` on the directory and
    `AutoProcessor.from_pretrained` on it. This does the same on CPU (sdpa instead of
    flash attention: the attention kernel does not change what is loaded), asks
    transformers which keys it missed, and checks that the input embeddings hold the
    file's values (not a fresh init), that `lm_head` is tied to them, that the FAST
    bins fit the vocabulary, and that the weights' sha256 is the one in `vlm.json`.
    """
    torch = importlib.import_module("torch")
    transformers = importlib.import_module("transformers")
    safe_open = importlib.import_module("safetensors").safe_open

    start = time.monotonic()
    manifest = json.loads((path / MANIFEST).read_text(encoding="utf-8"))
    problems: list[str] = []
    if sha256(path / WEIGHTS) != manifest["weights_sha256"]:
        problems.append(f"{path / WEIGHTS} sha256 differs from {MANIFEST}")
    model, info = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
        str(path), dtype=torch.bfloat16, attn_implementation="sdpa", output_loading_info=True
    )
    processor = transformers.AutoProcessor.from_pretrained(str(path))
    for kind in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs"):
        if info.get(kind):
            problems.append(f"{kind}: {list(info[kind])[:3]}")
    embed = model.get_input_embeddings().weight
    with safe_open(str(path / WEIGHTS), framework="pt") as f:
        key = next(k for k in f.keys() if k.endswith("embed_tokens.weight"))
        if not torch.equal(embed.detach(), f.get_tensor(key).to(embed.dtype)):
            problems.append(f"loaded input embeddings differ from {key} in the file")
    if model.lm_head.weight.data_ptr() != embed.data_ptr():
        problems.append("lm_head is not tied to the input embeddings")
    vocab, tokens = int(embed.shape[0]), len(processor.tokenizer)
    if tokens + FAST_BINS > vocab:
        problems.append(f"{tokens} tokens + {FAST_BINS} FAST bins exceed the vocabulary {vocab}")
    return {
        "seconds": round(time.monotonic() - start, 1),
        "vocab": vocab,
        "tokenizer": tokens,
        "parameters": sum(p.numel() for p in model.parameters()),
        "problems": problems,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("command", choices=["load-check"])
    parser.add_argument("path", type=Path, help="a directory `package` wrote")
    args = parser.parse_args(argv)
    result = load_check(args.path)
    print("load-check:", json.dumps(result), flush=True)
    return 1 if result["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())

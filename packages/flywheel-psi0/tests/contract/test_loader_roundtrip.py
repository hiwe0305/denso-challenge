"""Point 7 of the design 6.4 checklist: Psi0's own loader reads a saved batch back (DA-02 AC 2).

Runs in the Psi0 environment only (the image pinned in docker/psi0/compose.yaml, with
lerobot songlin/lerobot@09929d8, CODEBASE_VERSION "v2.1", and psi from the Psi0
checkout at cda3fdf); without `psi` and `lerobot` the module is skipped, so the lane
CI stays green. Set:

    FW_PSI0_ROUNDTRIP_DATASET    root of a LeRobot v2.1 dataset in Psi0's layout
    FW_PSI0_ROUNDTRIP_REFERENCE  the saved batch (.npz) for that dataset; its sha256
                                 must be one of REFERENCES (large, kept outside git)
    FW_PSI0_SRC                  the Psi0 checkout psi is imported from (pin check)
    FW_PSI0_ROUNDTRIP_WRITE=1    write the reference instead of reading it, once

The batch is what Psi0 stage 3 feeds its model transform: `LeRobotDatasetWrapper`
(lerobot dataset, `SimpleRepackTransform.delta_timestamps`, pyav) at the indices of
`sample_indices`, then `SimpleRepackTransform` and `ActionStateTransform` with the
arguments of configs/models/psi0-stage3.yaml (stats_psi0.json, bounds, normalized
states, pad 36), no augmentation. The model transform (resize, VLM tokens) is left
out: it needs the VLM processor files and adds no dataset-dependent step.

Two comparisons. Against the parquet, read with pyarrow, which holds whatever the
loader does: states, the 30-step action chunk with its padding past the episode end,
the task sentence, and constant dims (max = min in the stats) passed through raw by
the normalizer (design 6.4 point 6). Against the saved batch, value by value
(`np.array_equal`), which holds the whole pipeline still: stats, normalization, video
decoding.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

psi_transform = pytest.importorskip("psi.config.transform")
lerobot_dataset = pytest.importorskip("lerobot.datasets.lerobot_dataset")
pq = pytest.importorskip("pyarrow.parquet")
yaml = pytest.importorskip("yaml")

from psi.data.lerobot.lerobot_ext import LeRobotDatasetWrapper  # noqa: E402

PSI0_COMMIT = "cda3fdfafe47cb6fa75400d013de1bd36e3cea05"
LEROBOT_COMMIT = "09929d8057b044b53aecaf5c6d7eb71f99e8beb9"
STAGE3 = Path(__file__).resolve().parents[4] / "configs" / "models" / "psi0-stage3.yaml"
IMAGE_KEY = "observation.images.egocentric"
# sha256 of the saved batches, by file name; written on rtx3060 4/11/2026 (docs/g0/export-v21.md).
REFERENCES = {
    "tray_s1_0d84cc87b1e5.npz": "7aab984b6ab6118a7993edac93e463253f6c3d352561d7cd81c4998206857e10",
    "psi-data-e78fb93-two-table.npz":
        "f6719f08fbfc8c8cb7c12a42dca733302b794db6c484b5d6645e6eae29d04840",
}

DATASET = Path(os.environ.get("FW_PSI0_ROUNDTRIP_DATASET", "/nonexistent"))
REFERENCE = Path(os.environ.get("FW_PSI0_ROUNDTRIP_REFERENCE", "/nonexistent.npz"))
WRITE = os.environ.get("FW_PSI0_ROUNDTRIP_WRITE") == "1"

pytestmark = pytest.mark.skipif(
    not (DATASET / "meta" / "info.json").is_file(), reason="FW_PSI0_ROUNDTRIP_DATASET not set"
)


def stage3_kwargs(group: str) -> dict[str, Any]:
    """`data.transform.<group>.*` args of the stage-3 recipe as pydantic field values."""
    args = yaml.safe_load(STAGE3.read_text())["args"]
    prefix = f"data.transform.{group}."
    kwargs: dict[str, Any] = {}
    for key, value in args.items():
        if not key.startswith(prefix):
            continue
        name = key[len(prefix):].replace("-", "_")
        if name.startswith("no_") and value is True:  # tyro's --no-<flag>
            name, value = name[3:], False
        kwargs[name] = value
    return kwargs


def episode_lengths(root: Path) -> list[int]:
    rows = [json.loads(x) for x in (root / "meta/episodes.jsonl").read_text().splitlines() if x]
    return [int(r["length"]) for r in sorted(rows, key=lambda r: int(r["episode_index"]))]


def sample_indices(root: Path) -> list[int]:
    """First frame, the end of episode 0 (chunk padded), the start of episode 1, the
    middle of the last episode and the last frame: the places an index error shows."""
    lengths = episode_lengths(root)
    starts = np.cumsum([0, *lengths])
    last = len(lengths) - 1
    picks = [0, lengths[0] - 1, int(starts[1]), int(starts[last] + lengths[last] // 2),
             int(starts[-1] - 1)]
    return sorted(set(picks))


def load_batch(root: Path) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    """The batch as Psi0 builds it, and the raw lerobot items it came from."""
    repack = psi_transform.SimpleRepackTransform(**stage3_kwargs("repack"))
    field_args = stage3_kwargs("field")
    field_args["stat_path"] = str(root / field_args["stat_path"])
    field = psi_transform.ActionStateTransform(**field_args)
    cfg = SimpleNamespace(
        train_repo_ids=[root.name], val_repo_ids=[root.name], root_dir=str(root.parent),
        transform=SimpleNamespace(repack=repack),
    )
    loader = LeRobotDatasetWrapper(cfg, split="train")  # type: ignore[arg-type]
    raws, samples = [], []
    for idx in sample_indices(root):
        raw = loader[idx]
        raws.append(raw)
        samples.append(field(repack(dict(raw), no_aug=True), no_aug=True))
    batch = {
        "index": np.asarray(sample_indices(root), dtype=np.int64),
        "image": np.stack([np.asarray(s["observations"][0]) for s in samples]),
        "states": np.stack([s["states"] for s in samples]),
        "actions": np.stack([s["actions"] for s in samples]),
        "raw_actions": np.stack([s["raw_actions"] for s in samples]),
        "actions_mask": np.stack([s["actions_mask"] for s in samples]),
        "instruction": np.asarray([s["instruction"] for s in samples]),
    }
    return batch, raws


def parquet_rows(root: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """states, action and episode_index of every row, in dataset order, read with pyarrow."""
    info = json.loads((root / "meta/info.json").read_text())
    states, action, episode = [], [], []
    for index in range(len(episode_lengths(root))):
        chunk = index // int(info["chunks_size"])
        path = root / info["data_path"].format(episode_chunk=chunk, episode_index=index)
        table = pq.read_table(path, columns=["states", "action"])
        states.append(np.asarray(table.column("states").to_pylist(), dtype=np.float32))
        action.append(np.asarray(table.column("action").to_pylist(), dtype=np.float32))
        episode.append(np.full(table.num_rows, index))
    return np.concatenate(states), np.concatenate(action), np.concatenate(episode)


def git_head(checkout: Path) -> str:
    """The commit HEAD of a git checkout points to, read from .git (no git in the image)."""
    git = checkout / ".git"
    if not git.is_dir():
        return ""
    head = (git / "HEAD").read_text().strip()
    if not head.startswith("ref: "):
        return head
    ref = head[len("ref: "):]
    if (git / ref).is_file():
        return (git / ref).read_text().strip()
    packed_refs = git / "packed-refs"
    packed = packed_refs.read_text().splitlines() if packed_refs.is_file() else []
    return next((line.split()[0] for line in packed if line.endswith(f" {ref}")), "")


def test_the_pins_are_the_ones_stage_3_trains_with() -> None:
    from importlib.metadata import distribution

    assert lerobot_dataset.CODEBASE_VERSION == "v2.1"
    direct = json.loads(distribution("lerobot").read_text("direct_url.json") or "{}")
    assert direct.get("vcs_info", {}).get("commit_id") == LEROBOT_COMMIT
    src = Path(os.environ.get("FW_PSI0_SRC", "/nonexistent"))
    assert git_head(src) == PSI0_COMMIT, f"Psi0 checkout {src} at {git_head(src)!r}"
    imported = Path(psi_transform.__file__)
    pinned = src / "src" / "psi" / "config" / "transform.py"
    assert imported.read_bytes() == pinned.read_bytes(), f"psi imported from {imported}"


def test_the_loader_reads_what_the_export_wrote() -> None:
    batch, raws = load_batch(DATASET)
    states, action, episode = parquet_rows(DATASET)
    tasks = [json.loads(x) for x in (DATASET / "meta/tasks.jsonl").read_text().splitlines() if x]
    chunk = batch["actions"].shape[1]
    for k, idx in enumerate(batch["index"]):
        raw = raws[k]
        assert np.array_equal(raw["states"].numpy().reshape(-1), states[idx])
        rows = np.arange(idx, idx + chunk)
        inside = rows < len(episode)
        inside[inside] = episode[rows[inside]] == episode[idx]
        last = rows[inside][-1]
        want = action[np.where(inside, rows, last)]
        assert np.array_equal(raw["action"].numpy(), want)
        assert np.array_equal(raw["action_is_pad"].numpy(), ~inside)
        assert raw["task"] in {t["task"] for t in tasks}
        assert batch["instruction"][k] == raw["task"].lower()
        assert batch["image"][k].shape == (*raw[IMAGE_KEY].shape[1:], 3)
    stats = json.loads((DATASET / "meta/stats_psi0.json").read_text())["action"]
    low, high = np.asarray(stats["min"]), np.asarray(stats["max"])
    constant = np.abs(high - low) < 1e-4 * (np.abs(high) + np.abs(low) + 1e-8)
    assert np.array_equal(
        batch["actions"][..., constant], np.clip(batch["raw_actions"][..., constant], -1, 1)
    )


def test_the_batch_equals_the_saved_reference() -> None:
    batch, _ = load_batch(DATASET)
    if WRITE:
        REFERENCE.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(REFERENCE, **batch)
        digest = hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
        pytest.skip(f"wrote {REFERENCE} sha256 {digest}; record it in REFERENCES")
    digest = hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
    assert REFERENCES.get(REFERENCE.name) == digest, f"{REFERENCE} is not a recorded batch"
    saved = np.load(REFERENCE)
    assert sorted(saved.files) == sorted(batch)
    for key in batch:
        assert saved[key].dtype == batch[key].dtype, key
        assert np.array_equal(saved[key], batch[key]), key

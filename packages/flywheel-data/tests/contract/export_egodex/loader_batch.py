"""One loader batch as plain JSON, and how two of them are compared (DA-18 AC 2).

Shared by the fake loader (CI) and `psi0_loader_probe.py` (Psi0's own loader, in
Psi0's environment), so it imports numpy and the standard library only.

A batch maps each sample's path under the export root (`part1/<task>/<i>.hdf5`) to
what the loader returned for it, plus the action after the `bounds_q99` field
transform. Each sample is drawn right after `random.seed(f"{seed}:{path}")`, so both
loaders draw the same `index` whatever order their directory scan gave.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

import numpy as np

SEED = 7
# Tolerances of `compare`, each with its reason:
# - actions: rotation deltas come from scipy (Psi0) or a closed form (fake), both in
#   float32 rotations, about 1e-7 apart;
# - normalized: divided by q99 - q01 (about 1e-2 for a 3-frame xyz delta), clipped;
# - image: the two decoders (torchcodec in Psi0, OpenCV in the fake) agree on mp4v
#   to well under one grey level on average.
ATOL = {"states": 0.0, "actions": 1e-5, "actions_normalized": 1e-3, "image_mean_rgb": 1.0}


def seeded(path: str, seed: int = SEED) -> None:
    random.seed(f"{seed}:{path}")


def record(item: dict[str, Any], normalized: Any) -> dict[str, Any]:
    image = np.asarray(item["current_images"][0])
    return {
        "task": item["task"],
        "instruction": item["instruction"],
        "total_frames": int(item["file_info"]["total_frames"]),
        "selected_index": int(item["file_info"]["selected_index"]),
        "action_indices": [int(i) for i in item["file_info"]["action_indices"]],
        "states": np.asarray(item["states"], np.float64).tolist(),
        "actions": np.asarray(item["actions"], np.float64).tolist(),
        "actions_normalized": np.asarray(normalized, np.float64).tolist(),
        "image_shape": list(image.shape),
        "image_mean_rgb": image.reshape(-1, 3).mean(axis=0).tolist(),
    }


def draw(
    paths: list[str], get: Callable[[str], dict[str, Any]], seed: int = SEED
) -> dict[str, Any]:
    batch = {}
    for path in sorted(paths):
        seeded(path, seed)
        batch[path] = get(path)
    return batch


def compare(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """Every difference between two batches, value by value; empty when they agree."""
    problems = []
    if sorted(expected) != sorted(actual):
        return [f"samples differ: {sorted(expected)} vs {sorted(actual)}"]
    for path in sorted(expected):
        want, got = expected[path], actual[path]
        for key in sorted(set(want) | set(got)):
            a, b = want.get(key), got.get(key)
            if key in ATOL:
                same = np.shape(a) == np.shape(b) and np.allclose(a, b, rtol=0, atol=ATOL[key])
                if not same:
                    gap = np.abs(np.subtract(a, b)).max() if np.shape(a) == np.shape(b) else "shape"
                    problems.append(f"{path} {key}: max |diff| {gap} > {ATOL[key]}")
            elif a != b:
                problems.append(f"{path} {key}: {a!r} != {b!r}")
    return problems

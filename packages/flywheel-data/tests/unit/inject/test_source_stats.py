"""Recompute psi-data's shipped stats from its own parquet (DA-27 9.7, test a).

Runs where the pinned package is unpacked; set DA27_PSI_DATA to its root, e.g.
rtx3060:~/denso-da27/fwdata/psi-data/e78fb93/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.
SIMPLE accumulates `states` in float64 and `action` (float32 in its export) in float32.
`compute_stats` accumulates every column in float64, so it reproduces the shipped stats
to float32 rounding (atol 1e-6) for every column but `action`, which matches SIMPLE's
float32 recipe (`stats_block` on the float32 action) instead. Measured 25/11/2026 on
e78fb93: float64 `action` mean and std differ from the shipped ones by up to 3.63e-4
over the dataset and 1.1e-5 per episode (up to 1248 frames); float64 `states` by 1.2e-7.
The 3.63e-4 gap on `states` that this test pinned before was the lane's own float32
accumulation, not a finding on the source.
"""

import json
import os
from pathlib import Path

import numpy as np
import pytest
from flywheel.data.ingest.lerobot import iter_episodes
from flywheel.data.inject.stats import compute_stats, stats_block

ROOT = Path(os.environ.get("DA27_PSI_DATA", "/nonexistent"))
ATOL = 1e-6

pytestmark = pytest.mark.skipif(
    not (ROOT / "meta" / "episodes_stats.jsonl").is_file(), reason="DA27_PSI_DATA not set"
)


def _close(a: object, b: object, atol: float) -> bool:
    return bool(np.allclose(np.asarray(a, dtype=float), np.asarray(b, dtype=float), atol=atol))


def test_recompute_reproduces_the_shipped_stats_in_simple_precision() -> None:
    episodes, dataset = compute_stats(ROOT)
    actions = {f.episode_index: f.action for f in iter_episodes(ROOT)}
    shipped = [json.loads(x) for x in (ROOT / "meta/episodes_stats.jsonl").read_text().splitlines()]
    assert [r["episode_index"] for r in episodes] == [r["episode_index"] for r in shipped]
    for mine, theirs in zip(episodes, shipped, strict=True):
        index = mine["episode_index"]
        simple = {**stats_block(actions[index]), "count": mine["stats"]["action"]["count"]}
        for feature, block in theirs["stats"].items():
            recomputed = simple if feature == "action" else mine["stats"][feature]
            for key, value in block.items():
                assert _close(recomputed[key], value, ATOL), (index, feature, key)
    stats = json.loads((ROOT / "meta/stats.json").read_text())
    assert json.loads((ROOT / "meta/stats_psi0.json").read_text()) == stats
    dataset["action"] = stats_block(np.concatenate(list(actions.values()), axis=0))
    for feature, block in stats.items():
        for key, value in block.items():
            assert _close(dataset[feature][key], value, ATOL), (feature, key)

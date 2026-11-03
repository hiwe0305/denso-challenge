"""Recompute psi-data's shipped stats from its own parquet (DA-27 9.7, test a).

Runs where the pinned package is unpacked; set DA27_PSI_DATA to its root, e.g.
rtx3060:~/denso-da27/fwdata/psi-data/e78fb93/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.
Measured 4/11/2026 on e78fb93: per-episode stats and every dataset column but
`states` match to float32 rounding (atol 1e-6); `states` mean and std are off by up
to 3.7e-4, so the authors' stats.json for `states` is not computed on the shipped
data. That gap is a D4 finding on the source and is pinned here so it cannot grow.
"""

import json
import os
from pathlib import Path

import numpy as np
import pytest
from flywheel.data.inject.stats import compute_stats

ROOT = Path(os.environ.get("DA27_PSI_DATA", "/nonexistent"))
ATOL = 1e-6
STATES_GAP = 4e-4  # measured max |shipped - recomputed| of states mean and std: 3.63e-4

pytestmark = pytest.mark.skipif(
    not (ROOT / "meta" / "episodes_stats.jsonl").is_file(), reason="DA27_PSI_DATA not set"
)


def _close(a: object, b: object, atol: float) -> bool:
    return bool(np.allclose(np.asarray(a, dtype=float), np.asarray(b, dtype=float), atol=atol))


def test_recompute_reproduces_the_shipped_stats_but_states() -> None:
    episodes, dataset = compute_stats(ROOT)
    shipped = [json.loads(x) for x in (ROOT / "meta/episodes_stats.jsonl").read_text().splitlines()]
    assert [r["episode_index"] for r in episodes] == [r["episode_index"] for r in shipped]
    for mine, theirs in zip(episodes, shipped, strict=True):
        for feature, block in theirs["stats"].items():
            for key, value in block.items():
                assert _close(mine["stats"][feature][key], value, ATOL), (
                    mine["episode_index"],
                    feature,
                    key,
                )
    stats = json.loads((ROOT / "meta/stats.json").read_text())
    assert json.loads((ROOT / "meta/stats_psi0.json").read_text()) == stats
    for feature, block in stats.items():
        for key, value in block.items():
            atol = STATES_GAP if feature == "states" and key in ("mean", "std") else ATOL
            assert _close(dataset[feature][key], value, atol), (feature, key)

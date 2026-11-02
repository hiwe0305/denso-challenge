"""The tray task's seed ranges are the shared SplitPlan in configs/splits/default.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from flywheel_simple.tray.randomize import SEED_RANGES

SPLIT_PLAN = Path(__file__).resolve().parents[4] / "configs" / "splits" / "default.yaml"


def test_seed_ranges_match_shared_split_plan() -> None:
    plan = yaml.safe_load(SPLIT_PLAN.read_text())
    shared = {name: range(r["start"], r["stop"]) for name, r in plan["seed_ranges"].items()}
    assert shared == SEED_RANGES

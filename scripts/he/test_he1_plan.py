"""Checks of the HE-1 RunPlan (DA-26 AC 1). Run: uv run pytest scripts/he -q"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from he1_plan import (
    REPO,
    He1RunPlan,
    check,
    check_lock,
    demo_sets_from_plan,
    freeze,
    open_items,
)

PLAN = REPO / "configs/runplans/he/he-1.yaml"


@pytest.fixture
def plan() -> He1RunPlan:
    return He1RunPlan.load(PLAN)


def test_plan_holds(plan: He1RunPlan) -> None:
    assert check(plan) == []
    assert check_lock(plan, PLAN) == []


def test_sets_are_nested_and_skip_the_eval_episodes(plan: He1RunPlan) -> None:
    sets = demo_sets_from_plan(plan).sets
    n10, n20, n40, n80 = (set(sets[k].seeds) for k in ("N10", "N20", "N40", "N80"))
    assert n10 < n20 < n40 < n80
    assert not n80 & set(range(10))


def test_preliminary_points_are_the_four_of_ac6(plan: He1RunPlan) -> None:
    prelim = {(p.variant, p.demo_set, p.seed) for p in plan.points if p.phase == "preliminary"}
    assert prelim == {(v, n, 0) for v in ("V-EGO", "V-NOEGO") for n in ("N20", "N80")}


def test_main_eval_is_30_dev_seeds_at_three_levels(plan: He1RunPlan) -> None:
    conditions = plan.eval_conditions()
    assert len(conditions) == 90
    assert all(1_000_000 <= seed < 1_001_000 for _, seed in conditions)
    raw = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    raw["eval"]["main"]["seeds"] = {"start": 0, "stop": 30}
    assert any("dev range" in p for p in check(He1RunPlan.model_validate(raw)))


def test_check_catches_a_changed_pin(plan: He1RunPlan) -> None:
    raw = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    raw["demo_sets"]["hashes"]["N20"] = "0" * 64
    assert any("N20" in p for p in check(He1RunPlan.model_validate(raw)))
    raw = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    raw["demo_sets"]["exclude"] = []
    assert check(He1RunPlan.model_validate(raw))
    raw = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    raw["recipe"]["overrides"]["train.max_training_steps"] = 20000
    assert any("changes training" in p for p in check(He1RunPlan.model_validate(raw)))


def test_freeze_writes_lock_and_decision_then_detects_drift(tmp_path: Path) -> None:
    for rel in (
        "configs/runplans/he/he-1.yaml",
        "configs/runplans/he/demo_sets.json",
        "configs/models/psi0-stage3.yaml",
        "docs/he/he-1.md",
        "configs/splits/default.yaml",
        "scripts/he/dev_eval_set.py",
    ):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, tmp_path / rel)
    plan_path = tmp_path / "configs/runplans/he/he-1.yaml"
    raw = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    if open_items(He1RunPlan.model_validate(raw)):
        with pytest.raises(ValueError, match="awaits|pending"):
            freeze(plan_path, "tester", "test", repo=tmp_path)
        raw["eval"].update(sim_mode="mujoco_isaac", clock="sim", awaiting=None)
        plan_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    lock, decision = freeze(plan_path, "tester", "test", repo=tmp_path)
    plan = He1RunPlan.load(plan_path)
    assert check_lock(plan, plan_path) == []
    signed = json.loads(decision.read_text(encoding="utf-8"))
    assert signed["kind"] == "plan_review"
    assert signed["subject_id"] == json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"]
    with pytest.raises(ValueError, match="exists"):
        freeze(plan_path, "tester", "again", repo=tmp_path)
    raw = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    raw["stats"]["seed"] = 1
    plan_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    assert check_lock(He1RunPlan.load(plan_path), plan_path)

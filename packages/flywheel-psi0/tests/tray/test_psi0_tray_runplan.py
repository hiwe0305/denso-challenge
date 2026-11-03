"""RunPlans of the tray experiment against the files they name, on CPU (DA-34 AC 1, AC 6)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from flywheel_psi0.trainer.recipe import Psi0Recipe
from flywheel_psi0.tray.runplan import (
    TrayRoundPlan,
    TrayRunPlan,
    check,
    check_round,
    freeze,
    lock_path,
    recipe_sha256,
    run_plan_id,
)

REPO = Path(__file__).resolve().parents[4]
PLANS = REPO / "configs" / "runplans" / "tray"
PLAN = PLANS / "he-tray.yaml"
ROUND = PLANS / "round-tray-cplus.yaml"


@pytest.fixture
def plan() -> TrayRunPlan:
    return TrayRunPlan.load(PLAN)


def _repo_copy(tmp_path: Path) -> Path:
    """The files `check` reads, copied so a test can break one."""
    for rel in [
        "configs/models/psi0-stage3.yaml",
        "configs/splits/default.yaml",
        "configs/runplans/tray/demo_sets.json",
        "configs/runplans/tray/he-tray.yaml",
    ]:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, tmp_path / rel)
    return tmp_path


def test_plan_matches_the_files_it_names(plan: TrayRunPlan) -> None:
    assert check(plan) == []


def test_three_branches_as_ac1(plan: TrayRunPlan) -> None:
    assert set(plan.branches) == {"A", "C", "C_NOEGO"}
    a, c, noego = (plan.branches[k] for k in ("A", "C", "C_NOEGO"))
    assert c.demo_set == noego.demo_set != a.demo_set
    assert a.parent == c.parent != noego.parent
    assert plan.parents[noego.parent].vlm.path.startswith("psi0/pre.abl.only.he")


def test_eval_conditions_are_90_dev_conditions(plan: TrayRunPlan) -> None:
    conditions = plan.eval_conditions()
    assert len(conditions) == len(set(conditions)) == 90
    assert {level for level, _ in conditions} == {0, 1, 2}
    assert all(1_000_000 <= seed < 1_001_000 for _, seed in conditions)


def test_branches_cannot_carry_their_own_recipe() -> None:
    raw = yaml.safe_load(PLAN.read_text())
    raw["branches"]["C"]["recipe"] = {"train.max_training_steps": 20000}
    with pytest.raises(ValueError, match="recipe"):
        TrayRunPlan.model_validate(raw)


def test_run_plan_id_is_stable_and_content_defined(plan: TrayRunPlan) -> None:
    assert run_plan_id(plan) == run_plan_id(TrayRunPlan.load(PLAN))
    other = plan.model_copy(update={"train_seeds": [1]})
    assert run_plan_id(other) != run_plan_id(plan)
    assert run_plan_id(plan).startswith("rp_") and len(run_plan_id(plan)) == 15


def test_recipe_hash_ignores_the_step_time_estimate() -> None:
    recipe = Psi0Recipe.load(REPO / "configs/models/psi0-stage3.yaml")
    estimate = recipe.estimate.model_copy(update={"seconds_per_step": 0.25})
    assert recipe_sha256(recipe.model_copy(update={"estimate": estimate})) == recipe_sha256(recipe)
    assert recipe_sha256(recipe.with_overrides({"train.max_training_steps": 1})) != recipe_sha256(
        recipe
    )


def test_check_catches_a_changed_recipe(tmp_path: Path, plan: TrayRunPlan) -> None:
    repo = _repo_copy(tmp_path)
    recipe = repo / "configs/models/psi0-stage3.yaml"
    recipe.write_text(
        recipe.read_text().replace("max_training_steps: 40000", "max_training_steps: 20000")
    )
    assert any("hashes to" in p for p in check(plan, repo))


def test_check_catches_a_changed_demo_set(tmp_path: Path, plan: TrayRunPlan) -> None:
    repo = _repo_copy(tmp_path)
    sets = repo / "configs/runplans/tray/demo_sets.json"
    text = sets.read_text()
    c_hash = plan.demo_sets.hashes["C"]
    sets.write_text(text.replace(c_hash, "0" * 64))
    assert any(p.startswith("demo set C") for p in check(plan, repo))


def test_check_catches_eval_seeds_outside_dev() -> None:
    raw = yaml.safe_load(PLAN.read_text())
    raw["eval"]["condition_seeds"] = {"start": 2_000_000, "stop": 2_000_030}
    assert any("leave the dev range" in p for p in check(TrayRunPlan.model_validate(raw)))


def test_check_catches_unknown_parent_and_branch(plan: TrayRunPlan) -> None:
    branches = dict(plan.branches)
    branches["X"] = branches["C"].model_copy(update={"parent": "psi0-unknown"})
    bad = plan.model_copy(update={"branches": branches})
    assert any("psi0-unknown is not pinned" in p for p in check(bad))


def test_cplus_slot_is_a_draft_on_branch_c() -> None:
    round_plan = TrayRoundPlan.load(ROUND)
    assert round_plan.status == "draft" and round_plan.base_branch == "C"
    assert round_plan.targets.n_add == 40 and round_plan.targets.seeds == []
    problems = check_round(round_plan)
    assert problems in ([], [f"{round_plan.inherits} is not frozen"])
    frozen = round_plan.model_copy(update={"status": "frozen"})
    assert any("n_add targeted seeds" in p for p in check_round(frozen))


def test_plan_is_unchanged_since_it_was_frozen(plan: TrayRunPlan) -> None:
    # Reading rules and branches are fixed before the first job (design 6.4). Changing
    # the plan means a new RunPlan and a Decision, not an edit of this one.
    lock = json.loads(lock_path(PLAN).read_text())
    assert lock["plan"] == plan.model_dump(mode="json")
    assert lock["run_plan_id"] == run_plan_id(plan)
    assert (REPO / plan.interpretation.doc).is_file()


def test_freeze_refuses_without_the_reading_rules(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    with pytest.raises(ValueError, match="reading rules"):
        freeze(repo / "configs/runplans/tray/he-tray.yaml", repo)

"""RunPlans of the tray experiment against the files they name, on CPU (DA-34 AC 1, AC 6)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml
from flywheel_psi0.trainer.recipe import Psi0Recipe
from flywheel_psi0.tray.demo_sets import (
    EXPORT_META,
    MANIFEST,
    DemoSets,
    QaPin,
    ReleaseEpisode,
    canonical_sha256,
    nested_sets,
)
from flywheel_psi0.tray.runplan import (
    QaRef,
    TrayRoundPlan,
    TrayRunPlan,
    check,
    check_release,
    check_round,
    freeze,
    lock_path,
    main,
    plan_json,
    recipe_sha256,
    rules_block,
    run_plan_id,
)

REPO = Path(__file__).resolve().parents[4]
PLANS = REPO / "configs" / "runplans" / "tray"
PLAN = PLANS / "he-tray.yaml"
PLAN_V2 = PLANS / "he-tray-v2.yaml"
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
        "configs/runplans/tray/demo_sets-v2.json",
        "configs/runplans/tray/quality-s1-pool-1104.jsonl",
        "configs/runplans/tray/he-tray-v2.yaml",
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


def test_plan_validates_every_2000_steps_on_all_branches(plan: TrayRunPlan) -> None:
    # PO decision 4/11/2026 (docs/g0/psi0-finetune-cost.md 4.1 on S1-04): val every
    # 2000 steps instead of 500, as a plan-level override so the three branches share it.
    assert plan.recipe.overrides == {"train.validation_steps": 2000}
    assert check(plan) == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"train.max_training_steps": 1000}, "changes training"),
        ({"train.learning_rate": 5e-5}, "changes training"),
        ({"train.validation_steps": 0}, "positive step count"),
        ({"train.validation_steps": "2000"}, "positive step count"),
    ],
)
def test_check_rejects_overrides_that_change_training(
    plan: TrayRunPlan, overrides: dict[str, object], message: str
) -> None:
    raw = plan_json(plan)
    raw["recipe"]["overrides"] = overrides
    assert any(message in p for p in check(TrayRunPlan.model_validate(raw)))


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
    assert round_plan.inherits == "configs/runplans/tray/he-tray-v2.yaml"
    assert round_plan.targets.n_add == 160 and round_plan.targets.seeds == []
    assert check_round(round_plan) == []
    # C+ has no recipe of its own: it trains with the frozen plan's, override included.
    inherited = TrayRunPlan.load(REPO / round_plan.inherits)
    assert inherited.recipe.overrides == {"train.validation_steps": 2000}
    frozen = round_plan.model_copy(update={"status": "frozen"})
    assert any("n_add targeted seeds" in p for p in check_round(frozen))


def test_plan_is_unchanged_since_it_was_frozen(plan: TrayRunPlan) -> None:
    # Reading rules and branches are fixed before the first job (design 6.4). Changing
    # the plan means a new RunPlan and a Decision, not an edit of this one.
    lock = json.loads(lock_path(PLAN).read_text())
    assert lock["plan"] == plan_json(plan)
    assert lock["run_plan_id"] == run_plan_id(plan)
    assert (REPO / plan.interpretation.doc).is_file()


def test_round_refuses_a_plan_edited_after_its_lock(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    shutil.copy(ROUND, repo / "configs/runplans/tray/round-tray-cplus.yaml")
    shutil.copy(lock_path(PLAN_V2), lock_path(repo / "configs/runplans/tray/he-tray-v2.yaml"))
    plan_file = repo / "configs/runplans/tray/he-tray-v2.yaml"
    plan_file.write_text(plan_file.read_text().replace("resamples: 10000", "resamples: 20000"))
    round_plan = TrayRoundPlan.load(repo / "configs/runplans/tray/round-tray-cplus.yaml")
    assert any("changed since it was frozen" in p for p in check_round(round_plan, repo))


def test_v1_is_superseded_without_changing_its_id(plan: TrayRunPlan) -> None:
    assert plan.superseded_by == "configs/runplans/tray/he-tray-v2.yaml"
    assert run_plan_id(plan) == run_plan_id(plan.model_copy(update={"superseded_by": None}))
    assert run_plan_id(plan) == json.loads(lock_path(PLAN).read_text())["run_plan_id"]


def test_cli_refuses_to_pass_a_superseded_plan(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(PLAN)]) == 1
    assert "SUPERSEDED by configs/runplans/tray/he-tray-v2.yaml" in capsys.readouterr().err


def test_cli_checks_a_round_plan(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(ROUND)]) == 0
    assert "round draft, branch C_PLUS" in capsys.readouterr().out


def test_freeze_refuses_a_superseded_plan(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    (repo / "docs/he").mkdir(parents=True)
    (repo / "docs/he/tray.md").write_text("rules")
    with pytest.raises(ValueError, match="superseded by"):
        freeze(repo / "configs/runplans/tray/he-tray.yaml", repo)


def test_freeze_refuses_without_the_reading_rules(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    with pytest.raises(ValueError, match="reading rules"):
        freeze(repo / "configs/runplans/tray/he-tray.yaml", repo)


def _v2_eval(raw: dict) -> dict:
    """v1's plan with the eval of the 4/11/2026 decision (docs/he/tray.md 8.2)."""
    for key in ("levels", "condition_seeds", "rollout_replicates"):
        raw["eval"].pop(key)
    raw["eval"].update(
        clock="sim",
        policy_noise="per_episode_condition_seed",
        by_level=[
            {
                "level": 0,
                "seeds": {"start": 1_000_100, "stop": 1_000_130},
                "unit": "replicate",
                "headline": False,
            },
            {
                "level": 1,
                "seeds": {"start": 1_000_100, "stop": 1_000_220},
                "unit": "condition",
                "headline": True,
            },
            {
                "level": 2,
                "seeds": {"start": 1_000_100, "stop": 1_000_220},
                "unit": "condition",
                "headline": True,
            },
        ],
    )
    return raw


def test_v2_eval_is_30_replicates_and_240_headline_scenes() -> None:
    plan = TrayRunPlan.model_validate(_v2_eval(yaml.safe_load(PLAN.read_text())))
    conditions = plan.eval_conditions()
    assert len(conditions) == len(set(conditions)) == 270
    assert sum(level == 0 for level, _ in conditions) == 30
    assert len(plan.headline_conditions()) == 240
    assert not any(p for p in check(plan) if "dev range" in p)


def test_level_0_cannot_count_as_scenes() -> None:
    raw = _v2_eval(yaml.safe_load(PLAN.read_text()))
    raw["eval"]["by_level"][0].update(unit="condition", headline=True)
    with pytest.raises(ValueError, match="level 0 has one scene"):
        TrayRunPlan.model_validate(raw)


def test_v2_eval_needs_the_clock_and_the_noise_seeding() -> None:
    raw = _v2_eval(yaml.safe_load(PLAN.read_text()))
    del raw["eval"]["policy_noise"]
    with pytest.raises(ValueError, match="clock and policy_noise"):
        TrayRunPlan.model_validate(raw)


def test_eval_takes_one_shape_not_both() -> None:
    raw = _v2_eval(yaml.safe_load(PLAN.read_text()))
    raw["eval"]["condition_seeds"] = {"start": 1_000_100, "stop": 1_000_130}
    with pytest.raises(ValueError, match="either by_level or"):
        TrayRunPlan.model_validate(raw)


def test_check_catches_level_seeds_outside_dev() -> None:
    raw = _v2_eval(yaml.safe_load(PLAN.read_text()))
    raw["eval"]["by_level"][2]["seeds"] = {"start": 2_000_000, "stop": 2_000_120}
    assert any("level 2" in p and "dev range" in p for p in check(TrayRunPlan.model_validate(raw)))


TIER_2 = {
    "ceiling_cu": 36,
    "cap_cu_per_run": 18,
    "runs": ["A", "C", "C_NOEGO"],
    "round_runs": [],
    "watcher": "stop the run when its Colab session has used cap_cu_per_run",
}


def test_budget_holds_when_every_run_fits_under_the_ceiling() -> None:
    raw = yaml.safe_load(PLAN.read_text())
    raw["budget"] = dict(TIER_2, ceiling_cu=54)
    assert not any("budget" in p for p in check(TrayRunPlan.model_validate(raw)))


def test_budget_refuses_caps_over_the_ceiling() -> None:
    raw = yaml.safe_load(PLAN.read_text())
    raw["budget"] = TIER_2  # 3 runs x 18 CU = 54 > 36
    assert any("54 CU over the ceiling of 36" in p for p in check(TrayRunPlan.model_validate(raw)))


def test_budget_must_cover_every_branch() -> None:
    raw = yaml.safe_load(PLAN.read_text())
    raw["budget"] = dict(TIER_2, runs=["C"])
    problems = check(TrayRunPlan.model_validate(raw))
    assert any("branch A has no run in the budget" in p for p in problems)


def test_budget_refuses_a_run_of_no_branch() -> None:
    raw = yaml.safe_load(PLAN.read_text())
    raw["budget"] = dict(TIER_2, ceiling_cu=72, runs=["A", "C", "C_NOEGO", "C_PLSU"])
    problems = check(TrayRunPlan.model_validate(raw))
    assert any("run C_PLSU is not a branch of this plan" in p for p in problems)


def test_budget_round_runs_count_and_must_not_be_branches() -> None:
    raw = yaml.safe_load(PLAN.read_text())
    raw["budget"] = dict(TIER_2, ceiling_cu=54, round_runs=["C"])  # 4 runs x 18 = 72
    problems = check(TrayRunPlan.model_validate(raw))
    assert any("72 CU over the ceiling of 54" in p for p in problems)
    assert any("round run C is a branch of this plan" in p for p in problems)


def test_round_needs_a_run_in_the_parents_budget(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    plan_file = repo / "configs/runplans/tray/he-tray-v2.yaml"
    raw = yaml.safe_load(plan_file.read_text())
    raw["budget"]["round_runs"] = []  # no C_PLUS
    plan_file.write_text(yaml.safe_dump(raw))
    shutil.copy(ROUND, repo / "configs/runplans/tray/round-tray-cplus.yaml")
    round_plan = TrayRoundPlan.load(repo / "configs/runplans/tray/round-tray-cplus.yaml")
    assert any("C_PLUS has no round run in the budget" in p for p in check_round(round_plan, repo))


QA_PIN = {"reports_sha256": "a" * 64, "threshold_version": "qa-1@fb6ddaf9f48c"}


def _with_qa_sets(tmp_path: Path) -> Path:
    """A repo copy whose demo-set file says its sets left out DA-03 rejects."""
    repo = _repo_copy(tmp_path)
    sets_file = repo / "configs/runplans/tray/demo_sets.json"
    sets = DemoSets.model_validate_json(sets_file.read_text())
    qa = QaPin(**QA_PIN, excluded=[])
    sets_file.write_text(sets.model_copy(update={"qa": qa}).model_dump_json(indent=1))
    return repo


def test_check_needs_the_qa_pin_of_sets_cut_after_qa(tmp_path: Path, plan: TrayRunPlan) -> None:
    repo = _with_qa_sets(tmp_path)
    assert any("DA-03 QA" in p for p in check(plan, repo))
    pins = plan.demo_sets.model_copy(update={"qa": QaRef(**QA_PIN)})
    assert check(plan.model_copy(update={"demo_sets": pins}), repo) == []


def test_check_catches_other_qa_reports(tmp_path: Path, plan: TrayRunPlan) -> None:
    repo = _with_qa_sets(tmp_path)
    pins = plan.demo_sets.model_copy(update={"qa": QaRef(**dict(QA_PIN, reports_sha256="b" * 64))})
    problems = check(plan.model_copy(update={"demo_sets": pins}), repo)
    assert any("other DA-03 QA reports" in p for p in problems)


# Version 2, frozen on the planner-5 release (docs/he/tray.md sections 7-10).
DA03_REJECTS = {1072, 1097, 1153, 1166, 1358, 1372, 1431}  # tray.md section 10


@pytest.fixture
def plan_v2() -> TrayRunPlan:
    return TrayRunPlan.load(PLAN_V2)


def test_v2_matches_the_files_it_names(plan_v2: TrayRunPlan) -> None:
    assert check(plan_v2) == []
    assert main(["check", str(PLAN_V2)]) == 0


def test_v2_is_unchanged_since_it_was_frozen(plan_v2: TrayRunPlan) -> None:
    lock = json.loads(lock_path(PLAN_V2).read_text())
    assert lock["plan"] == plan_json(plan_v2)
    assert lock["run_plan_id"] == run_plan_id(plan_v2)
    assert plan_v2.superseded_by is None


def test_v2_replaces_v1_by_its_frozen_id(plan_v2: TrayRunPlan, plan: TrayRunPlan) -> None:
    assert plan_v2.supersedes == json.loads(lock_path(PLAN).read_text())["run_plan_id"]
    assert plan.superseded_by == str(PLAN_V2.relative_to(REPO))


def test_v2_is_tier_2(plan_v2: TrayRunPlan) -> None:
    # Hiếu, 4/11/2026: train only C here and C+ in the round, 18 CU each under 36.
    assert set(plan_v2.branches) == {"C"} and set(plan_v2.parents) == {"psi0-baseline-egodex-he"}
    budget = plan_v2.budget
    assert budget is not None
    assert (budget.ceiling_cu, budget.cap_cu_per_run) == (36, 18)
    assert (budget.runs, budget.round_runs) == (["C"], ["C_PLUS"])
    assert "scripts/colab/cu_watch.py" in budget.watcher
    assert (REPO / "scripts/colab/cu_watch.py").is_file()
    assert plan_v2.recipe.overrides == {"train.validation_steps": 2000}


def test_v2_eval_is_the_decision_of_4_11(plan_v2: TrayRunPlan) -> None:
    assert (plan_v2.eval.clock, plan_v2.eval.policy_noise) == ("sim", "per_episode_condition_seed")
    assert len(plan_v2.eval_conditions()) == 270
    assert len(plan_v2.headline_conditions()) == 240


def test_v2_sets_leave_out_the_da03_rejects(plan_v2: TrayRunPlan) -> None:
    sets = DemoSets.model_validate_json((REPO / plan_v2.demo_sets.file).read_text())
    assert sets.qa is not None and sets.quality is not None
    assert {e.seed for e in sets.qa.excluded} == DA03_REJECTS
    assert {e.decision for e in sets.qa.excluded} == {"reject"}
    assert sets.quality.kept == 429
    assert {k: v.n for k, v in sets.sets.items()} == {"N40": 40, "N80": 80, "C": 160, "A": 320}
    assert not DA03_REJECTS & set(sets.sets["A"].seeds)


# Review of #116: what `check` recomputes instead of trusting the files.
SETS_V2 = "configs/runplans/tray/demo_sets-v2.json"


def test_check_recomputes_set_hashes_from_the_seeds(tmp_path: Path, plan_v2: TrayRunPlan) -> None:
    # One seed of C swapped for one outside A, every hash in the file kept.
    repo = _repo_copy(tmp_path)
    raw = json.loads((repo / SETS_V2).read_text())
    seeds = raw["sets"]["C"]["seeds"]
    outside = next(s for s in range(seeds[0] - 1, 0, -1) if s not in raw["sets"]["A"]["seeds"])
    raw["sets"]["C"]["seeds"] = sorted([outside, *seeds[1:]])
    (repo / SETS_V2).write_text(json.dumps(raw))
    unpinned = plan_v2.demo_sets.model_copy(update={"file_sha256": None})
    problems = check(plan_v2.model_copy(update={"demo_sets": unpinned}), repo)
    assert any(p.startswith("demo set C: its seeds hash to") for p in problems)


def test_check_pins_the_demo_set_file(tmp_path: Path, plan_v2: TrayRunPlan) -> None:
    # Episode indices are not in any set hash; the file hash covers them.
    repo = _repo_copy(tmp_path)
    assert not any("demo-set file" in p for p in check(plan_v2, repo))
    raw = json.loads((repo / SETS_V2).read_text())
    raw["sets"]["C"]["episode_indices"][0] += 1
    (repo / SETS_V2).write_text(json.dumps(raw, indent=1))
    assert any("not the demo-set file the plan pins" in p for p in check(plan_v2, repo))


def _with_doc(tmp_path: Path) -> Path:
    repo = _repo_copy(tmp_path)
    (repo / "docs/he").mkdir(parents=True)
    shutil.copy(REPO / "docs/he/tray.md", repo / "docs/he/tray.md")
    return repo


def test_one_edited_character_of_the_rules_fails(tmp_path: Path, plan_v2: TrayRunPlan) -> None:
    repo = _with_doc(tmp_path)
    assert not any("reading rules" in p for p in check(plan_v2, repo))
    doc = repo / "docs/he/tray.md"
    text = doc.read_text()
    block = rules_block(text)
    i = block.index("p_C < 10%")
    doc.write_text(text.replace(block, block[:i] + "p_C < 20%" + block[i + 9 :]))
    assert any("reading rules in docs/he/tray.md changed" in p for p in check(plan_v2, repo))


def test_the_label_outside_the_rules_block_may_change(tmp_path: Path, plan_v2: TrayRunPlan) -> None:
    repo = _with_doc(tmp_path)
    doc = repo / "docs/he/tray.md"
    doc.write_text(doc.read_text().replace("[Đã chốt 5/11/2026, Hiếu]", "[Đề xuất]", 1))
    assert not any("reading rules" in p for p in check(plan_v2, repo))


def test_rules_need_one_pair_of_markers() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        rules_block("no markers")
    with pytest.raises(ValueError, match="comes before"):
        rules_block("<!-- /tier2-rules --> x <!-- tier2-rules -->")


def test_v2_pins_the_eval_config_split_and_tray_sources(plan_v2: TrayRunPlan) -> None:
    pinned = plan_v2.pinned_files
    assert pinned is not None
    assert {plan_v2.task["config"], "configs/splits/default.yaml"} <= set(pinned)
    tray = "packages/flywheel-simple/src/flywheel_simple/tray/"
    for module in ("simple_task", "predicates", "randomize", "mjcf", "run"):
        assert f"{tray}{module}.py" in pinned
    assert plan_v2.interpretation.delta_pp is None  # no HE-T rule reads it in tier 2


def test_check_catches_a_changed_pinned_file(tmp_path: Path, plan_v2: TrayRunPlan) -> None:
    repo = _repo_copy(tmp_path)
    (repo / "configs/sim").mkdir(parents=True)
    (repo / "configs/sim/tray.yaml").write_text("episode_limit_s: 120.0\n")
    problems = check(plan_v2, repo)
    assert "pinned file configs/sim/tray.yaml changed since the plan pinned it" in problems
    unpinned = {
        k: v for k, v in (plan_v2.pinned_files or {}).items() if k != "configs/sim/tray.yaml"
    }
    problems = check(plan_v2.model_copy(update={"pinned_files": unpinned}), repo)
    assert "pinned_files lacks configs/sim/tray.yaml, which the eval reads" in problems


def _fake_release(root: Path, episodes: list[ReleaseEpisode]) -> str:
    """A release directory with the manifest and export meta read_release checks."""
    (root / "meta").mkdir(parents=True)
    (root / EXPORT_META).write_text(json.dumps({"episodes": [e.model_dump() for e in episodes]}))
    meta = root / EXPORT_META
    files = [{"path": EXPORT_META, "sha256": hashlib.sha256(meta.read_bytes()).hexdigest()}]
    release_hash = canonical_sha256(files)
    (root / MANIFEST).write_text(json.dumps({"release_hash": release_hash, "files": files}))
    return release_hash


def test_check_release_ties_indices_to_seeds(tmp_path: Path, plan_v2: TrayRunPlan) -> None:
    # Export order is not seed order, so the sorted index list depends on the pairing.
    episodes = [ReleaseEpisode(episode_index=i, seed=2000 + (i * 7) % 30) for i in range(30)]
    release_hash = _fake_release(tmp_path / "release", episodes)
    sets = nested_sets("tray_fake", release_hash, episodes, {"C": 10, "A": 20})
    repo = tmp_path / "repo"
    (repo / "configs/runplans/tray").mkdir(parents=True)
    (repo / SETS_V2).write_text(sets.model_dump_json())
    release = plan_v2.release.model_copy(update={"release_hash": release_hash})
    plan = plan_v2.model_copy(update={"release": release})
    assert check_release(plan, tmp_path / "release", repo) == []
    swapped = [ReleaseEpisode(episode_index=e.seed % 30, seed=e.seed) for e in episodes]
    other = tmp_path / "other"
    other_plan = plan.model_copy(
        update={
            "release": release.model_copy(update={"release_hash": _fake_release(other, swapped)})
        }
    )
    problems = check_release(other_plan, other, repo)
    assert any("episode_indices are not its seeds'" in p for p in problems)
    assert any("not" in p for p in check_release(plan_v2, tmp_path / "release", repo))

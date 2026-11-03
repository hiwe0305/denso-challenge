"""RunPlans of the tray experiment: schema, checks, id and freeze (DA-34 AC 1, AC 6).

`configs/runplans/tray/he-tray.yaml` holds branches A, C and C-NOEGO of design
28/10/2026 section 6.2 in the shape of 03 section 8.1. The recipe, train seeds
and eval conditions sit once at plan level and a branch can only pick a demo
set and a parent checkpoint, so "same recipe, same steps, same condition seeds"
holds by construction. `check` ties the plan to the files it names: the recipe
hash, the parent paths of the recipe, the demo-set hashes and the dev split.

`run_plan_id` is `rp_` + sha256 of the plan as canonical JSON, cut to 12
characters. `freeze` writes `<plan>.lock.json` beside the plan; a test fails if
the plan changes afterwards, so the interpretation rules and branches fixed
before the first job (design 6.4) cannot drift silently.

`round-tray-cplus.yaml` is the slot for branch C+ of the Failure -> Data round
(section 6.6, task 5): it inherits everything from the frozen plan and stays a
draft until its targeted episodes exist.

    python -m flywheel_psi0.tray.runplan check configs/runplans/tray/he-tray.yaml
    python -m flywheel_psi0.tray.runplan freeze configs/runplans/tray/he-tray.yaml
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from flywheel_psi0.trainer.recipe import Psi0Recipe
from flywheel_psi0.tray.demo_sets import DemoSets, canonical_sha256

REPO = Path(__file__).resolve().parents[5]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Pin(_Frozen):
    repo: str
    commit: str = Field(min_length=40, max_length=40)


class Weights(_Frozen):
    path: str  # inside the psi-model repo
    sha256: str = Field(min_length=64, max_length=64)  # Hugging Face LFS oid at the revision


class Parent(_Frozen):
    vlm: Weights
    action_header: Weights
    clean_for_main_task: bool  # Q0 (03 section 8.3 point 7)
    note: str = ""


class PsiModel(_Frozen):
    repo: str
    revision: str = Field(min_length=40, max_length=40)


class Release(_Frozen):
    id: str
    release_hash: str = Field(min_length=64, max_length=64)
    location: str
    data_class: Literal["public", "internal", "restricted"]


class DemoSetPins(_Frozen):
    file: str  # repo-relative
    salt: str
    hashes: dict[str, str]


class Recipe(_Frozen):
    file: str  # repo-relative
    sha256: str  # recipe_sha256 of that file
    overrides: dict[str, str | int | float | bool] = Field(default_factory=dict)
    nproc_per_node: int = Field(ge=1)
    dataset_stats: Literal["own_train_set"]


class Branch(_Frozen):
    demo_set: str
    parent: str
    role: str


class SeedRange(_Frozen):
    start: int
    stop: int


class Eval(_Frozen):
    cli: Literal["eval-decoupled-wbc"]
    sim_mode: Literal["mujoco"]
    renderer: Literal["mujoco"]
    synchronous: bool
    split: Literal["dev"]
    levels: list[Literal[0, 1, 2]]
    condition_seeds: SeedRange  # the same seeds at every level
    rollout_replicates: int = Field(ge=1)
    episode_limit_s: float = Field(gt=0)


class Stats(_Frozen):
    method: Literal["bootstrap_by_condition"]
    resamples: int = Field(ge=1000)
    seed: int
    ci: float = Field(gt=0, lt=1)


class Comparison(_Frozen):
    a: str
    b: str
    question: str


class Interpretation(_Frozen):
    doc: str  # repo-relative
    delta_pp: float = Field(gt=0)


class TrayRunPlan(_Frozen):
    name: str
    purpose: Literal["branch_train"]
    story: str
    site_id: str
    task: dict[str, str]
    embodiment: str
    code: dict[str, Pin]
    psi_model: PsiModel
    parents: dict[str, Parent]
    release: Release
    demo_sets: DemoSetPins
    recipe: Recipe
    train_seeds: list[int] = Field(min_length=1)
    branches: dict[str, Branch]
    eval: Eval
    metric: dict[str, str]
    stats: Stats
    comparisons: list[Comparison]
    interpretation: Interpretation
    pricebook: str

    @classmethod
    def load(cls, path: Path) -> TrayRunPlan:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def eval_conditions(self) -> list[tuple[int, int]]:
        """(level, seed) of every eval condition; the same list for every branch."""
        seeds = range(self.eval.condition_seeds.start, self.eval.condition_seeds.stop)
        return [(level, seed) for level in self.eval.levels for seed in seeds]


class RoundTargets(_Frozen):
    n_add: int = Field(gt=0)
    from_failures_of: str
    generator: str
    seeds: list[int] = Field(default_factory=list)  # empty until generated (task 5)
    set_hash: str | None = None


class TrayRoundPlan(_Frozen):
    """Branch C+: C's demos plus targeted episodes, everything else as in `inherits`."""

    name: str
    purpose: Literal["round"]
    story: str
    status: Literal["draft", "frozen"]
    inherits: str  # repo-relative path of the frozen branch_train plan
    branch: str
    base_branch: str
    targets: RoundTargets
    max_rounds: Literal[1]

    @classmethod
    def load(cls, path: Path) -> TrayRoundPlan:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def recipe_sha256(recipe: Psi0Recipe) -> str:
    """Hash of what a recipe trains with; the step-time `estimate` is left out."""
    return canonical_sha256(recipe.model_dump(mode="json", exclude={"estimate"}))


def run_plan_id(plan: BaseModel) -> str:
    return "rp_" + canonical_sha256(plan.model_dump(mode="json"))[:12]


def lock_path(plan_path: Path) -> Path:
    return plan_path.with_name(plan_path.name.removesuffix(".yaml") + ".lock.json")


def check(plan: TrayRunPlan, repo: Path = REPO) -> list[str]:
    """Everything wrong between the plan and the files it names; empty when it holds."""
    problems: list[str] = []
    recipe = Psi0Recipe.load(repo / plan.recipe.file)
    if recipe.stage != 3:
        problems.append(f"{plan.recipe.file} is stage {recipe.stage}, not 3")
    if recipe_sha256(recipe) != plan.recipe.sha256:
        problems.append(f"{plan.recipe.file} hashes to {recipe_sha256(recipe)}")
    if plan.recipe.overrides:
        problems.append("recipe.overrides must stay empty: every branch runs the file as is")

    for name, parent in plan.parents.items():
        known = recipe.parents.get(name)
        if known is None:
            problems.append(f"parent {name} is not in {plan.recipe.file}")
            continue
        paired = [
            (parent.vlm.path, known.model_name_or_path),
            (parent.action_header.path, known.pretrained_action_header_path or ""),
        ]
        for hf_path, local in paired:  # a weight file inside the folder the recipe loads
            if Path(hf_path).parent.name != Path(local).name:
                problems.append(f"parent {name}: {hf_path} is not {local} of the recipe")
        if not parent.clean_for_main_task:
            problems.append(f"parent {name} is not clean for the main task (Q0)")

    sets = DemoSets.model_validate_json((repo / plan.demo_sets.file).read_text(encoding="utf-8"))
    if (sets.release_id, sets.release_hash) != (plan.release.id, plan.release.release_hash):
        problems.append(f"{plan.demo_sets.file} is for another release: {sets.release_id}")
    if sets.salt != plan.demo_sets.salt:
        problems.append(f"{plan.demo_sets.file} uses salt {sets.salt!r}")
    for name, pinned in plan.demo_sets.hashes.items():
        got = sets.sets.get(name)
        if got is None or got.set_hash != pinned:
            problems.append(f"demo set {name}: file has {got and got.set_hash}, plan pins {pinned}")
    ordered = sorted(sets.sets.values(), key=lambda s: s.n)
    for small, large in zip(ordered, ordered[1:]):
        if not set(small.seeds) <= set(large.seeds):
            problems.append(f"demo set of {small.n} is not inside the set of {large.n}")

    for name, branch in plan.branches.items():
        if branch.demo_set not in plan.demo_sets.hashes:
            problems.append(f"branch {name}: demo set {branch.demo_set} is not pinned")
        if branch.parent not in plan.parents:
            problems.append(f"branch {name}: parent {branch.parent} is not pinned")
    for comparison in plan.comparisons:
        for side in (comparison.a, comparison.b):
            if side not in plan.branches:
                problems.append(f"comparison names unknown branch {side}")

    split = yaml.safe_load((repo / "configs/splits/default.yaml").read_text(encoding="utf-8"))
    dev = split["seed_ranges"][plan.eval.split]
    seeds = plan.eval.condition_seeds
    if not dev["start"] <= seeds.start < seeds.stop <= dev["stop"]:
        problems.append(
            f"eval seeds [{seeds.start}, {seeds.stop}) leave the {plan.eval.split} range"
        )
    return problems


def check_round(round_plan: TrayRoundPlan, repo: Path = REPO) -> list[str]:
    problems: list[str] = []
    parent = TrayRunPlan.load(repo / round_plan.inherits)
    if round_plan.base_branch not in parent.branches:
        problems.append(f"base branch {round_plan.base_branch} is not in {round_plan.inherits}")
    if round_plan.branch in parent.branches:
        problems.append(f"branch {round_plan.branch} already exists in {round_plan.inherits}")
    if round_plan.targets.from_failures_of != round_plan.base_branch:
        problems.append("targets must come from the failures of the base branch")
    if not lock_path(repo / round_plan.inherits).is_file():
        problems.append(f"{round_plan.inherits} is not frozen")
    targets = round_plan.targets
    if round_plan.status == "frozen" and (
        len(targets.seeds) != targets.n_add or not targets.set_hash
    ):
        problems.append("a frozen round needs its n_add targeted seeds and their set_hash")
    return problems


def freeze(plan_path: Path, repo: Path = REPO) -> Path:
    plan = TrayRunPlan.load(plan_path)
    problems = check(plan, repo)
    if not (repo / plan.interpretation.doc).is_file():
        problems.append(f"{plan.interpretation.doc} is missing: fix the reading rules first")
    if problems:
        raise ValueError("; ".join(problems))
    lock = {
        "run_plan_id": run_plan_id(plan),
        "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "plan": plan.model_dump(mode="json"),
    }
    out = lock_path(plan_path)
    out.write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["check", "freeze"])
    parser.add_argument("plan", type=Path)
    args = parser.parse_args(argv)
    if args.action == "freeze":
        out = freeze(args.plan)
        print(f"wrote {out}: {json.loads(out.read_text())['run_plan_id']}")
        return 0
    plan = TrayRunPlan.load(args.plan)
    problems = check(plan)
    for problem in problems:
        print(problem, file=sys.stderr)
    if not problems:
        print(f"{args.plan}: {run_plan_id(plan)}, {len(plan.eval_conditions())} eval conditions")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

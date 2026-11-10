"""Paired stage 3 plan of the tray experiment: one cut, two VLMs (DA-34 task 6).

Hiếu 11/11/2026 (docs/he/tray.md section 19): after eval C showed the target zone on
table B is not drawn (the planner lines up on a hidden target; the policy sees only the
image), DA-33 draws the zone and regenerates both demo pools (W1) and DA-30 runs stage 1
on the cleaned egocentric export (W2). Then two stage 3 runs train on the same cut ALL
for 60000 steps:

    B_ALL  C's VLM after DA-30's stage 1 (`Stage1Parent`), C's action header
    C_ALL  C's VLM and action header (`Parent`)

The plan is the one place their setup lives. Cut, recipe with its overrides, train
seed, eval and stats sit once at plan level and a branch names only its parent, so
"identical except the VLM" holds by construction; `check` adds that the two parents
share their action header and that the stage 1 VLM started from the other branch's VLM.

The cut joins one part per regenerated pool, as C+ joined C's and the targeted cut
(`cplus_cut`): each part is a demo set of its own release, pinned as the release, the
demo-set file and the set name. Both branches train on the joined cut and its one
`meta/stats_psi0.json` (`cut.stats_sha256`). Until W1 and W2 deliver, the data and
stage 1 pins are null: `check` passes as a draft, `freeze` and `check --launch` refuse
and list what is missing (`pending`).

The recipe overrides may set `train.max_training_steps` (the plan's step count, for
both branches) besides the training-neutral ones of `runplan`. The eval is the eval of
a frozen plan (`eval_of`: same conditions, same stats, same code pins), so the eval set
of that plan pairs the two branches condition by condition.

    python -m flywheel_psi0.tray.pairplan check configs/runplans/tray/he-tray-pair60k.yaml
    python -m flywheel_psi0.tray.pairplan check <plan> --launch
    python -m flywheel_psi0.tray.pairplan freeze <plan>
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
from pydantic import BaseModel, ConfigDict, Field, model_validator

from flywheel_psi0.trainer.recipe import Psi0Recipe
from flywheel_psi0.tray.runplan import (
    REPO,
    TRAINING_NEUTRAL_OVERRIDES,
    Budget,
    DemoSetPins,
    Eval,
    Interpretation,
    Parent,
    Pin,
    PsiModel,
    Recipe,
    Release,
    Stage1Parent,
    Stats,
    TrayRunPlan,
    demo_set_problems,
    file_pin_drift,
    lock_path,
    parent_problems,
    parents_pending,
    plan_json,
    recipe_sha256,
    rules_sha256,
    run_plan_id,
)

STEPS = "train.max_training_steps"
BATCH = "train.train_batch_size"
PAIR_OVERRIDES = TRAINING_NEUTRAL_OVERRIDES | {STEPS}


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CutPart(_Frozen):
    """One regenerated pool's share of the cut: a demo set of its own release."""

    regenerates: str  # id of the release whose pool W1 regenerates (same seeds, planner)
    release: Release | None = None
    demo_sets: DemoSetPins | None = None
    set_name: str | None = None  # the set of `demo_sets` this part takes


class SharedCut(_Frozen):
    """The one dataset every branch trains on: its parts joined in order."""

    name: str
    rule: str  # which episodes of each part, written before the data exists
    visuals_revision: str | None = None  # DA-33's revision that draws the target zone
    parts: list[CutPart] = Field(min_length=1)
    episodes: int | None = Field(default=None, gt=0)
    frames: int | None = Field(default=None, gt=0)  # meta/info.json total_frames
    stats_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class PairBranch(_Frozen):
    parent: str
    role: str


class EvalOf(_Frozen):
    """The frozen plan whose eval this plan runs, and that eval's set."""

    plan: str  # repo-relative
    run_plan_id: str
    eval_set: str  # directory name of the eval set (eval_set.py) built for that plan
    conditions_sha256: str = Field(min_length=64, max_length=64)


class TrayPairPlan(_Frozen):
    name: str
    purpose: Literal["paired_train"]
    story: str
    status: Literal["draft"] | None = None  # dropped once W1, W2 and a Decision are in
    site_id: str
    task: dict[str, str]
    embodiment: str
    code: dict[str, Pin]
    psi_model: PsiModel
    parents: dict[str, Parent | Stage1Parent]
    cut: SharedCut
    recipe: Recipe
    train_seeds: list[int] = Field(min_length=1, max_length=1)
    branches: dict[str, PairBranch]
    eval: Eval
    eval_of: EvalOf
    metric: dict[str, str]
    stats: Stats
    interpretation: Interpretation
    pricebook: str
    budget: Budget
    pinned_files: dict[str, str] | None = None  # pinned at freeze, with W1's revision

    @model_validator(mode="after")
    def _a_pair(self) -> TrayPairPlan:
        if len(self.branches) != 2:
            raise ValueError(f"a pair has two branches, not {sorted(self.branches)}")
        parents = [b.parent for b in self.branches.values()]
        if len(set(parents)) != 2:
            raise ValueError("the two branches need two parents: the VLM is what differs")
        return self

    @classmethod
    def load(cls, path: Path) -> TrayPairPlan:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def steps(self) -> int | None:
        value = self.recipe.overrides.get(STEPS)
        return value if isinstance(value, int) and not isinstance(value, bool) else None


def epochs(steps: int, batch: int, frames: int) -> float:
    """Passes over the cut: one sample per frame (observation horizon 1)."""
    return steps * batch / frames


def check(plan: TrayPairPlan, repo: Path = REPO) -> list[str]:
    """Everything wrong between the plan and the files it names; empty when it holds."""
    problems: list[str] = []
    recipe = Psi0Recipe.load(repo / plan.recipe.file)
    if recipe.stage != 3:
        problems.append(f"{plan.recipe.file} is stage {recipe.stage}, not 3")
    if recipe_sha256(recipe) != plan.recipe.sha256:
        problems.append(f"{plan.recipe.file} hashes to {recipe_sha256(recipe)}")
    for key, value in plan.recipe.overrides.items():
        if key not in PAIR_OVERRIDES:
            problems.append(f"override {key}: a pair may set only {sorted(PAIR_OVERRIDES)}")
        elif key not in recipe.args:
            problems.append(f"override {key} is not an arg of {plan.recipe.file}")
        elif isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            problems.append(f"override {key} must be a positive step count, not {value!r}")
    if STEPS not in plan.recipe.overrides:
        problems.append(f"the plan states its step count: recipe.overrides.{STEPS}")

    problems += parent_problems(plan.parents, recipe, plan.recipe.file)
    used = {b.parent for b in plan.branches.values()}
    if used != set(plan.parents):
        problems.append(f"parents {sorted(set(plan.parents) - used)} are pinned but unused")
    kinds = {name: plan.parents.get(b.parent) for name, b in plan.branches.items()}
    stage1 = [(n, p) for n, p in kinds.items() if isinstance(p, Stage1Parent)]
    release = [(n, p) for n, p in kinds.items() if isinstance(p, Parent)]
    if len(stage1) != 1 or len(release) != 1:
        problems.append("one branch takes a stage 1 parent and the other a release parent")
    else:
        (s_name, s_parent), (r_name, _) = stage1[0], release[0]
        assert isinstance(s_parent, Stage1Parent)
        if s_parent.vlm_stage1.from_parent != plan.branches[r_name].parent:
            problems.append(
                f"branch {s_name}: stage 1 starts from {s_parent.vlm_stage1.from_parent},"
                f" not branch {r_name}'s parent {plan.branches[r_name].parent}"
            )

    names = [part.regenerates for part in plan.cut.parts]
    if len(set(names)) != len(names):
        problems.append(f"cut {plan.cut.name}: a pool is regenerated twice: {names}")
    for part in plan.cut.parts:
        pins = (part.release, part.demo_sets, part.set_name)
        if all(pin is None for pin in pins):
            continue
        if any(pin is None for pin in pins):
            problems.append(
                f"part {part.regenerates}: pin release, demo_sets and set_name together"
            )
            continue
        assert part.release is not None and part.demo_sets is not None and part.set_name
        if part.release.id == part.regenerates:
            problems.append(f"part {part.regenerates}: pins the old release, not its regeneration")
        if part.release.data_class != "public":
            problems.append(f"part {part.regenerates}: data_class {part.release.data_class}")
        if part.set_name not in part.demo_sets.hashes:
            problems.append(f"part {part.regenerates}: set {part.set_name} is not pinned")
        if not (repo / part.demo_sets.file).is_file():
            problems.append(f"part {part.regenerates}: {part.demo_sets.file} is missing")
            continue
        problems += [
            f"part {part.regenerates}: {p}"
            for p in demo_set_problems(part.demo_sets, part.release, repo)
        ]

    problems += eval_of_problems(plan, repo)

    rules = plan.interpretation.rules_sha256
    if rules is None:
        problems.append("interpretation.rules_sha256: the reading rules are pinned before any run")
    else:
        doc = plan.interpretation.doc
        try:
            text = (repo / doc).read_text(encoding="utf-8")
            actual = rules_sha256(text, plan.interpretation.rules_marker)
        except (OSError, ValueError) as error:
            problems.append(f"{doc}: {error}")
        else:
            if actual != rules:
                problems.append(f"the reading rules in {doc} changed since the plan pinned them")

    budget = plan.budget
    if sorted(budget.runs) != sorted(plan.branches) or budget.round_runs:
        problems.append(f"budget: runs are exactly the branches {sorted(plan.branches)}")
    total = budget.cap_cu_per_run * len(budget.runs)
    if total > budget.ceiling_cu:
        problems.append(
            f"budget: {len(budget.runs)} runs x {budget.cap_cu_per_run:g} CU = {total:g} CU"
            f" over the ceiling of {budget.ceiling_cu:g}"
        )
    return problems


def eval_of_problems(plan: TrayPairPlan, repo: Path = REPO) -> list[str]:
    """The eval is the frozen plan's: conditions, stats, task and code pins all equal."""
    ref = plan.eval_of
    path = repo / ref.plan
    if not path.is_file():
        return [f"eval_of: {ref.plan} is missing"]
    base = TrayRunPlan.load(path)
    problems = []
    lock = lock_path(path)
    if not lock.is_file():
        problems.append(f"eval_of: {ref.plan} is not frozen")
    elif json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"] != run_plan_id(base):
        problems.append(f"eval_of: {ref.plan} changed since it was frozen")
    if run_plan_id(base) != ref.run_plan_id:
        problems.append(f"eval_of: {ref.plan} is {run_plan_id(base)}, not {ref.run_plan_id}")
    if not ref.eval_set.startswith(ref.run_plan_id):
        problems.append(f"eval_of: {ref.eval_set} is not an eval set of {ref.run_plan_id}")
    for field in ("eval", "stats", "metric", "task", "embodiment", "code", "psi_model"):
        if getattr(plan, field) != getattr(base, field):
            problems.append(f"eval_of: {field} differs from {ref.plan}")
    if plan.recipe.file != base.recipe.file or plan.recipe.sha256 != base.recipe.sha256:
        problems.append(f"eval_of: the recipe is not {ref.plan}'s")
    if plan.recipe.nproc_per_node != base.recipe.nproc_per_node:
        problems.append(f"eval_of: nproc_per_node is not {ref.plan}'s")
    if plan.train_seeds != base.train_seeds:
        problems.append(f"eval_of: train seeds are not {ref.plan}'s")
    return problems


def pending(plan: TrayPairPlan) -> list[str]:
    """Pins still null: no freeze and no launch until W1 (data) and W2 (stage 1) deliver."""
    out = parents_pending(plan.parents)
    for part in plan.cut.parts:
        for field in ("release", "demo_sets", "set_name"):
            if getattr(part, field) is None:
                out.append(f"cut part {part.regenerates}: {field} is not pinned yet (W1)")
    for field in ("visuals_revision", "episodes", "frames", "stats_sha256"):
        if getattr(plan.cut, field) is None:
            out.append(f"cut {plan.cut.name}: {field} is not pinned yet (W1)")
    if plan.pinned_files is None:
        out.append("pinned_files: pinned at freeze, with the target-zone scene of W1")
    return out


def freeze(plan_path: Path, repo: Path = REPO) -> Path:
    plan = TrayPairPlan.load(plan_path)
    problems = check(plan, repo) + file_pin_drift(plan.pinned_files, repo) + pending(plan)
    if plan.status == "draft":
        problems.append("status draft: drop it once a Decision orders this plan, then freeze")
    if problems:
        raise ValueError("; ".join(problems))
    lock = {
        "run_plan_id": run_plan_id(plan),
        "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "plan": plan_json(plan),
    }
    out = lock_path(plan_path)
    out.write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out


def summary(plan: TrayPairPlan, repo: Path = REPO) -> str:
    steps = plan.steps()
    batch = Psi0Recipe.load(repo / plan.recipe.file).args.get(BATCH)
    text = f"{run_plan_id(plan)}, branches {sorted(plan.branches)}, {steps} steps"
    if steps and isinstance(batch, int) and plan.cut.frames:
        passes = epochs(steps, batch * plan.recipe.nproc_per_node, plan.cut.frames)
        text += f", {passes:.2f} epochs of {plan.cut.name}"
    return text


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["check", "freeze"])
    parser.add_argument("plan", type=Path)
    parser.add_argument(
        "--launch", action="store_true", help="before a job: drafts, null pins and drift fail"
    )
    args = parser.parse_args(argv)
    repo = REPO
    if args.action == "freeze":
        out = freeze(args.plan, repo)
        print(f"wrote {out}: {json.loads(out.read_text())['run_plan_id']}")
        return 0
    plan = TrayPairPlan.load(args.plan)
    problems = check(plan, repo)
    text = f"{args.plan}: {summary(plan, repo)}"
    todo = pending(plan)
    if plan.status == "draft":
        text += ", draft"
    if todo:
        text += f", {len(todo)} pins pending"
    drift = file_pin_drift(plan.pinned_files, repo)
    warnings = []
    if args.launch:
        if plan.status == "draft":
            problems.append("DRAFT: no job runs a draft plan; it needs a Decision first")
        problems += [f"PENDING: {p}" for p in todo]
        problems += [f"{d}: re-freeze or record a Decision" for d in drift]
        lock = lock_path(args.plan)
        if not lock.is_file():
            problems.append(f"{args.plan} is not frozen: no {lock.name}")
        elif json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"] != run_plan_id(plan):
            problems.append(f"{args.plan} changed since it was frozen")
    else:
        warnings = [f"warning: {d} (fails with --launch)" for d in drift]
    for line in [*problems, *warnings]:
        print(line, file=sys.stderr)
    if not problems:
        print(text + (", launch OK" if args.launch else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

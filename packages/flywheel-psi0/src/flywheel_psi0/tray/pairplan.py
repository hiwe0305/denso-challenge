"""Paired stage 3 plan of the tray experiment: two VLMs x two data sizes (DA-34 task 6).

Hiếu 11/11/2026 (docs/he/tray.md section 19): after eval C showed the target zone on
table B is not drawn (the planner lines up on a hidden target; the policy sees only the
image), DA-33 draws the zone and regenerates both demo pools (W1) and DA-30 runs stage 1
on the cleaned egocentric export (W2). Then stage 3 runs train for 60000 steps, each on
one VLM and one data size (Hiếu 11/11/2026 "Thêm hai run 70%"):

    B_ALL  C's VLM after DA-30's stage 1 (`Stage1Parent`), cut ALL
    C_ALL  C's VLM (`Parent`), cut ALL: the full-demo mark
    B_70   B_ALL's VLM, subset S70: 70 % of each part of ALL, the same seeds for both
    C_70   C_ALL's VLM, the same subset S70

The plan is the one place their setup lives. Cut, subsets, recipe with its overrides,
train seed, eval and stats sit once at plan level, and a branch names only its parent
and its data (`data`: a subset, or the whole cut), so "identical except the VLM and the
subset" holds by construction. The branches must be every (parent, data) pair once:
two parents, one a stage 1 VLM grown from the other's VLM, both with the same action
header; with no subset that is the plain pair of B_ALL and C_ALL.

The cut joins one part per regenerated pool, as C+ joined C's and the targeted cut
(`cplus_cut`): each part is a demo set of its own release, pinned as the release, the
demo-set file and the set name. A subset takes, from each part, the first
ceil(fraction x n) seeds of that part's set ordered by sha256 of the seed (`subset_seeds`:
no choice by outcome or quality; rounded up per part, so both parts keep their shares),
and pins each part's list by its sha256 before any run. Every branch normalises with the
cut's one `meta/stats_psi0.json` (`cut.stats_sha256`; a subset's `stats: cut`): the 70 %
runs differ from ALL in the amount of data only. Until W1 and W2 deliver, the data and
stage 1 pins are null: `check` passes as a draft, `freeze` and `check --launch` refuse
and list what is missing (`pending`).

`comparisons` lists the paired differences the reading rules read (the block of
`interpretation`): one `primary` (the two-stage rule), `noninferiority` ones with their
margin, and `secondary` ones; `evidence` computes exactly these.

The recipe overrides may set `train.max_training_steps` (the plan's step count, for
every branch) besides the training-neutral ones of `runplan`. `checkpoints` names the
saved checkpoints the rules read (rule e of the block): `primary`, the metric, is the
last step; `early` an early read only (ckpt_40000 of the 60k runs, persisted to Drive
while training goes on). `schedule` says whether the runs share the account at once
(`parallel`, one Colab session each, one cu_watch batch) or one after the other, and
`waves`, if set, how the parallel runs split when Colab refuses a session; and
`balance_needed` the CU the account must hold for the guard's floor never to stop them.
The eval is the eval of a frozen plan (`eval_of`: same conditions, same stats, same code
pins), so the eval set of that plan pairs the branches condition by condition.

    python -m flywheel_psi0.tray.pairplan check configs/runplans/tray/he-tray-pair60k.yaml
    python -m flywheel_psi0.tray.pairplan check <plan> --launch
    python -m flywheel_psi0.tray.pairplan subset <plan>   # each subset's seeds, once W1 pins
    python -m flywheel_psi0.tray.pairplan freeze <plan>
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import itertools
import json
import math
import sys
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from flywheel_psi0.trainer.recipe import Psi0Recipe
from flywheel_psi0.tray.demo_sets import DemoSets
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
SAVE_EVERY = "train.checkpointing_steps"
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


class SubsetPart(_Frozen):
    """One cut part's share of a subset: how many of its seeds, and which (by sha256)."""

    regenerates: str  # the cut part, in the cut's order
    episodes: int | None = Field(default=None, gt=0)  # ceil(fraction x the part's set size)
    seeds_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class Subset(_Frozen):
    """A fixed share of the cut, the same episodes for every branch that trains on it."""

    name: str
    fraction: float = Field(gt=0, lt=1)
    rule: str  # written before the data exists
    order: Literal["sha256_seed"]  # `subset_seeds`: seeds by sha256 of str(seed), first k
    stats: Literal["cut"]  # normalised with the cut's stats_psi0.json, as the cut's branches
    parts: list[SubsetPart] = Field(min_length=1)
    episodes: int | None = Field(default=None, gt=0)
    frames: int | None = Field(default=None, gt=0)  # meta/info.json total_frames


class PairComparison(_Frozen):
    """One paired difference variant - baseline the reading rules read."""

    rule: str  # its letter in the rules block, e.g. "a′"
    variant: str
    baseline: str
    kind: Literal["primary", "noninferiority", "secondary"]
    margin: float | None = Field(default=None, gt=0, lt=1)  # noninferiority: CI low > -margin


class PairCheckpoints(_Frozen):
    """Which saved checkpoints the reading rules read (rule (e) of the plan's block)."""

    primary: int = Field(gt=0)  # the metric: the last step, so it equals the step count
    early: int | None = Field(default=None, gt=0)  # an early read, never a verdict


class Schedule(_Frozen):
    """How the runs share the Colab account, so the guard's floor never stops them."""

    mode: Literal["parallel", "sequential"]  # parallel: one session per branch at once
    floor_cu: float = Field(gt=0)  # the account balance at which guard and watchers stop
    persist: str  # how each complete ckpt_<step> reaches Drive while training runs
    # parallel only: the batches the runs fall back to when Colab refuses a session
    waves: list[list[str]] | None = None


class PairBranch(_Frozen):
    parent: str
    role: str
    data: str | None = None  # a subset's name; None: the whole cut


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
    subsets: list[Subset] | None = None
    recipe: Recipe
    train_seeds: list[int] = Field(min_length=1, max_length=1)
    branches: dict[str, PairBranch]
    comparisons: list[PairComparison] | None = None  # None: the plain pair, B against C
    eval: Eval
    eval_of: EvalOf
    metric: dict[str, str]
    stats: Stats
    interpretation: Interpretation
    pricebook: str
    budget: Budget
    checkpoints: PairCheckpoints
    schedule: Schedule
    pinned_files: dict[str, str] | None = None  # pinned at freeze, with W1's revision

    @model_validator(mode="after")
    def _every_vlm_on_every_data(self) -> TrayPairPlan:
        parents = {b.parent for b in self.branches.values()}
        if len(parents) != 2:
            raise ValueError("the branches need two parents: the VLM is one factor")
        names = [s.name for s in self.subsets or []]
        if len(set(names)) != len(names) or self.cut.name in names:
            raise ValueError(f"subset names {names} repeat or reuse the cut's name")
        datas = {self.data_of(b) for b in self.branches.values()}
        if not datas <= {self.cut.name, *names}:
            raise ValueError(f"branch data {sorted(datas - {self.cut.name, *names})} is no subset")
        if set(names) - datas:
            raise ValueError(f"subsets {sorted(set(names) - datas)} are pinned but unused")
        cells = sorted((b.parent, self.data_of(b)) for b in self.branches.values())
        if cells != sorted(itertools.product(parents, datas)):
            raise ValueError(
                f"the branches must be every (parent, data) pair once, not {cells}: "
                "the VLM and the data size are the only factors"
            )
        return self

    def data_of(self, branch: PairBranch) -> str:
        return branch.data or self.cut.name

    def subset(self, name: str) -> Subset | None:
        return next((s for s in self.subsets or [] if s.name == name), None)

    @classmethod
    def load(cls, path: Path) -> TrayPairPlan:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def steps(self) -> int | None:
        value = self.recipe.overrides.get(STEPS)
        return value if isinstance(value, int) and not isinstance(value, bool) else None


def epochs(steps: int, batch: int, frames: int) -> float:
    """Passes over the cut: one sample per frame (observation horizon 1)."""
    return steps * batch / frames


def subset_size(n: int, fraction: float) -> int:
    """ceil(fraction x n), exact: 0.7 x 10 is 7, not the 8 a float would round up to."""
    return math.ceil(Fraction(str(fraction)) * n)


def subset_seeds(seeds: Sequence[int], fraction: float) -> list[int]:
    """The subset of one part: seeds ordered by sha256 of str(seed), the first k, ascending.

    Depends on the seeds alone: no outcome, quality or order of the release enters.
    """
    if len(set(seeds)) != len(seeds):
        raise ValueError("a part lists a seed twice")
    ranked = sorted(seeds, key=lambda s: hashlib.sha256(str(s).encode()).hexdigest())
    return sorted(ranked[: subset_size(len(seeds), fraction)])


def seeds_sha256(seeds: Sequence[int]) -> str:
    """sha256 of the ascending seed list as compact JSON, e.g. `[1000,1003]`."""
    return hashlib.sha256(json.dumps(sorted(seeds), separators=(",", ":")).encode()).hexdigest()


def part_seeds(part: CutPart, repo: Path = REPO) -> list[int] | None:
    """The seeds of a pinned part's set, or None while W1 has not pinned it."""
    if part.demo_sets is None or part.set_name is None:
        return None
    sets = DemoSets.model_validate_json((repo / part.demo_sets.file).read_text(encoding="utf-8"))
    chosen = sets.sets.get(part.set_name)
    return None if chosen is None else list(chosen.seeds)


def subset_lists(plan: TrayPairPlan, repo: Path = REPO) -> dict[str, dict[str, list[int]]]:
    """Each subset's seed list per part, for the parts W1 has pinned."""
    out: dict[str, dict[str, list[int]]] = {}
    for subset in plan.subsets or []:
        for part in plan.cut.parts:
            seeds = part_seeds(part, repo)
            if seeds is not None:
                out.setdefault(subset.name, {})[part.regenerates] = subset_seeds(
                    seeds, subset.fraction
                )
    return out


def balance_needed(plan: TrayPairPlan) -> float:
    """CU the account must hold when the runs start: the floor plus every cap at stake.

    Parallel runs spend at the same time, so the guard's floor is safe only above the
    caps of all of them; sequential runs need one cap at a time (before each run).
    """
    runs = len(plan.budget.runs) if plan.schedule.mode == "parallel" else 1
    return plan.schedule.floor_cu + plan.budget.cap_cu_per_run * runs


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
    problems += checkpoint_problems(plan, recipe)

    problems += parent_problems(plan.parents, recipe, plan.recipe.file)
    used = {b.parent for b in plan.branches.values()}
    if used != set(plan.parents):
        problems.append(f"parents {sorted(set(plan.parents) - used)} are pinned but unused")
    kinds = {key: plan.parents.get(key) for key in used}
    stage1 = [(k, p) for k, p in kinds.items() if isinstance(p, Stage1Parent)]
    release = [k for k, p in kinds.items() if isinstance(p, Parent)]
    if len(stage1) != 1 or len(release) != 1:
        problems.append("one parent is a stage 1 VLM and the other a release parent")
    else:
        (s_key, s_parent), r_key = stage1[0], release[0]
        assert isinstance(s_parent, Stage1Parent)
        if s_parent.vlm_stage1.from_parent != r_key:
            problems.append(
                f"parent {s_key}: stage 1 starts from {s_parent.vlm_stage1.from_parent},"
                f" not the other branches' parent {r_key}"
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

    problems += subset_problems(plan, repo)
    problems += comparison_problems(plan)
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
    for flag in (f"--cap {budget.cap_cu_per_run:g}", f"--floor {plan.schedule.floor_cu:g}"):
        if flag not in budget.watcher:
            problems.append(f"budget.watcher does not say {flag}")
    waves = plan.schedule.waves
    if waves is not None:
        flat = [name for wave in waves for name in wave]
        if plan.schedule.mode != "parallel":
            problems.append("schedule.waves: only a parallel schedule falls back to waves")
        if sorted(flat) != sorted(plan.branches) or any(not wave for wave in waves):
            problems.append(f"schedule.waves: every branch in exactly one wave, {flat}")
    return problems


def subset_problems(plan: TrayPairPlan, repo: Path = REPO) -> list[str]:
    """Each subset follows the cut part by part, and its pins are what `subset_seeds` gives."""
    problems: list[str] = []
    order = [part.regenerates for part in plan.cut.parts]
    lists = subset_lists(plan, repo)
    for subset in plan.subsets or []:
        name = subset.name
        if [p.regenerates for p in subset.parts] != order:
            problems.append(f"subset {name}: parts are not the cut's, in order: {order}")
            continue
        for sp, part in zip(subset.parts, plan.cut.parts, strict=True):
            seeds = lists.get(name, {}).get(part.regenerates)
            if seeds is None:
                if sp.episodes is not None or sp.seeds_sha256 is not None:
                    problems.append(f"subset {name} part {sp.regenerates}: pinned before the part")
                continue
            if sp.episodes is not None and sp.episodes != len(seeds):
                problems.append(
                    f"subset {name} part {sp.regenerates}: {sp.episodes} episodes pinned,"
                    f" {subset.order} gives {len(seeds)}"
                )
            if sp.seeds_sha256 is not None and sp.seeds_sha256 != seeds_sha256(seeds):
                problems.append(
                    f"subset {name} part {sp.regenerates}: seeds_sha256 is not the list"
                    f" {subset.order} gives ({seeds_sha256(seeds)[:12]})"
                )
        counts = [sp.episodes for sp in subset.parts]
        if (
            subset.episodes is not None
            and None not in counts
            and subset.episodes != sum(c for c in counts if c is not None)
        ):
            problems.append(f"subset {name}: episodes {subset.episodes} is not the parts' sum")
        if plan.cut.episodes is not None and subset.episodes is not None:
            if subset.episodes >= plan.cut.episodes:
                problems.append(f"subset {name}: not smaller than cut {plan.cut.name}")
    return problems


def comparison_problems(plan: TrayPairPlan) -> list[str]:
    """One primary comparison of the VLM alone; noninferiority ones carry a margin."""
    if plan.comparisons is None:
        return [] if len(plan.branches) == 2 else ["comparisons: a plan of more than a pair"]
    problems: list[str] = []
    rules = [c.rule for c in plan.comparisons]
    if len(set(rules)) != len(rules):
        problems.append(f"comparisons: a rule appears twice: {rules}")
    for c in plan.comparisons:
        missing = {c.variant, c.baseline} - set(plan.branches)
        if missing or c.variant == c.baseline:
            problems.append(f"comparison {c.rule}: {c.variant} - {c.baseline} are not two branches")
        elif (c.kind == "noninferiority") != (c.margin is not None):
            problems.append(f"comparison {c.rule}: a margin goes with noninferiority only")
    primary = [c for c in plan.comparisons if c.kind == "primary"]
    if len(primary) != 1:
        problems.append(f"comparisons: exactly one primary, not {[c.rule for c in primary]}")
    elif not {primary[0].variant, primary[0].baseline} - set(plan.branches):
        variant, baseline = (plan.branches[n] for n in (primary[0].variant, primary[0].baseline))
        if plan.data_of(variant) != plan.data_of(baseline):
            problems.append(f"comparison {primary[0].rule}: the primary compares one data size")
        if not isinstance(plan.parents.get(variant.parent), Stage1Parent):
            problems.append(f"comparison {primary[0].rule}: the variant is the stage 1 VLM")
    return problems


def checkpoint_problems(plan: TrayPairPlan, recipe: Psi0Recipe) -> list[str]:
    """The read checkpoints exist: saved by the recipe, the primary one the last step."""
    reads = plan.checkpoints
    problems = []
    if reads.primary != plan.steps():
        problems.append(f"checkpoints.primary {reads.primary} is not the step count {plan.steps()}")
    if reads.early is not None and reads.early >= reads.primary:
        problems.append(f"checkpoints.early {reads.early} is not before {reads.primary}")
    every = recipe.args.get(SAVE_EVERY)
    if not isinstance(every, int) or isinstance(every, bool):
        return [*problems, f"{plan.recipe.file} has no integer {SAVE_EVERY}"]
    for name, step in (("primary", reads.primary), ("early", reads.early)):
        if step is not None and step % every:
            problems.append(f"checkpoints.{name} {step}: Psi0 saves every {every} steps only")
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
    for subset in plan.subsets or []:
        for sp in subset.parts:
            for field in ("episodes", "seeds_sha256"):
                if getattr(sp, field) is None:
                    out.append(f"subset {subset.name} part {sp.regenerates}: {field} (after W1)")
        for field in ("episodes", "frames"):
            if getattr(subset, field) is None:
                out.append(f"subset {subset.name}: {field} is not pinned yet (after W1)")
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
    for name, frames in [(plan.cut.name, plan.cut.frames)] + [
        (s.name, s.frames) for s in plan.subsets or []
    ]:
        if steps and isinstance(batch, int) and frames:
            passes = epochs(steps, batch * plan.recipe.nproc_per_node, frames)
            text += f", {passes:.2f} epochs of {name}"
    early = plan.checkpoints.early
    text += f", read ckpt {plan.checkpoints.primary}" + (f" (early {early})" if early else "")
    when = "at launch" if plan.schedule.mode == "parallel" else "before each run"
    text += f", {plan.schedule.mode}, balance >= {balance_needed(plan):g} CU {when}"
    return text


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["check", "freeze", "subset"])
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
    if args.action == "subset":
        lists = subset_lists(plan, repo)
        report = {
            name: {
                part: {"episodes": len(seeds), "seeds_sha256": seeds_sha256(seeds), "seeds": seeds}
                for part, seeds in parts.items()
            }
            for name, parts in lists.items()
        }
        print(json.dumps(report, indent=1))
        return 0 if lists else 1
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

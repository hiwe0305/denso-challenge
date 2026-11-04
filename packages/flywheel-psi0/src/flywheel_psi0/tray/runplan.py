"""RunPlans of the tray experiment: schema, checks, id and freeze (DA-34 AC 1, AC 6).

`configs/runplans/tray/he-tray.yaml` holds branches A, C and C-NOEGO of design
28/10/2026 section 6.2 in the shape of 03 section 8.1. The recipe, train seeds
and eval conditions sit once at plan level and a branch can only pick a demo
set and a parent checkpoint, so "same recipe, same steps, same condition seeds"
holds by construction. `check` ties the plan to the files it names: the recipe
hash, the parent paths of the recipe, the demo-set hashes (recomputed from the
seeds) and the dev split; for version 2 also the sha256 of the demo-set file, of
the eval config and scene/scorer sources (`pinned_files`), and of the reading
rules between the tier2-rules markers of the interpretation doc. With `--release`
it also checks every set's episode indices against the release's own export.
The only recipe override allowed is one that leaves training unchanged
(`train.validation_steps`), set once for all branches.

`run_plan_id` is `rp_` + sha256 of the plan as canonical JSON, cut to 12
characters. `freeze` writes `<plan>.lock.json` beside the plan; a test fails if
the plan changes afterwards, so the interpretation rules and branches fixed
before the first job (design 6.4) cannot drift silently.

`round-tray-cplus.yaml` is the slot for branch C+ of the Failure -> Data round
(section 6.6, task 5): it inherits everything from the frozen plan and stays a
draft until its targeted episodes exist.

    python -m flywheel_psi0.tray.runplan check configs/runplans/tray/he-tray.yaml
    python -m flywheel_psi0.tray.runplan check configs/runplans/tray/he-tray-v2.yaml \
        --release ~/denso-da34-pool/fwdata/releases/tray_s1_f9433b028c52
    python -m flywheel_psi0.tray.runplan check configs/runplans/tray/round-tray-cplus.yaml
    python -m flywheel_psi0.tray.runplan freeze configs/runplans/tray/he-tray.yaml
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from flywheel_psi0.trainer.recipe import Psi0Recipe
from flywheel_psi0.tray.demo_sets import DemoSets, canonical_sha256, read_release, set_hash
from flywheel_psi0.tray.quality import QualityFilter

REPO = Path(__file__).resolve().parents[5]
# Recipe args a plan may override for all its branches: they change what is logged,
# not the weights (PO 4/11/2026, docs/g0/psi0-finetune-cost.md 4.1 on S1-04).
TRAINING_NEUTRAL_OVERRIDES = frozenset({"train.validation_steps"})
STATUS_FIELDS = {"superseded_by"}
# The block of the interpretation doc that `Interpretation.rules_sha256` pins; the
# label above it ([Đề xuất], [Đã chốt]) stays outside, so approving it keeps the id.
RULES_MARKERS = ("<!-- tier2-rules -->", "<!-- /tier2-rules -->")
SPLIT_FILE = "configs/splits/default.yaml"


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


class QualityRef(_Frozen):
    file: str  # repo-relative quality.jsonl of the release's batch
    sha256: str = Field(min_length=64, max_length=64)
    filter: QualityFilter


class QaRef(_Frozen):
    reports_sha256: str = Field(min_length=64, max_length=64)  # DA-03 qa/reports.jsonl
    threshold_version: str


class DemoSetPins(_Frozen):
    file: str  # repo-relative
    file_sha256: str | None = Field(default=None, min_length=64, max_length=64)  # v2
    salt: str
    hashes: dict[str, str]
    quality: QualityRef | None = None
    qa: QaRef | None = None  # the sets left out DA-03 rejects (decision of 5/11/2026)


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


class LevelConditions(_Frozen):
    """Eval episodes at one level: one per seed of `seeds`."""

    level: Literal[0, 1, 2]
    seeds: SeedRange
    # condition: each seed is a scene. replicate: the level has one scene, so its seeds
    # only vary the policy noise (level 0 of the tray task, docs/he/tray.md 8.2).
    unit: Literal["condition", "replicate"]
    headline: bool  # pooled into the primary metric and the comparisons


class Eval(_Frozen):
    """Version 1: `levels` x `condition_seeds` x `rollout_replicates`, all levels alike.

    Version 2 (decision of 4/11/2026): `by_level`, with the eval clock and how the
    policy noise is seeded. Unset fields are left out of the id, so v1 keeps its id.
    """

    cli: Literal["eval-decoupled-wbc"]
    sim_mode: Literal["mujoco"]
    renderer: Literal["mujoco"]
    synchronous: bool
    split: Literal["dev"]
    levels: list[Literal[0, 1, 2]] | None = None
    condition_seeds: SeedRange | None = None  # the same seeds at every level
    rollout_replicates: int | None = Field(default=None, ge=1)
    by_level: list[LevelConditions] | None = None
    clock: Literal["sim", "wall"] | None = None  # FLYWHEEL_TRAY_EVAL_CLOCK of tray.run
    # per_episode_condition_seed: the client sends the condition seed on reset and the
    # server reseeds torch with it (docs/he/tray.md 8.5).
    policy_noise: Literal["per_episode_condition_seed"] | None = None
    episode_limit_s: float = Field(gt=0)

    @model_validator(mode="after")
    def _one_shape(self) -> Eval:
        v1 = (self.levels, self.condition_seeds, self.rollout_replicates)
        if self.by_level is None:
            if None in v1:
                raise ValueError("eval needs levels, condition_seeds and rollout_replicates")
            return self
        if any(field is not None for field in v1):
            raise ValueError("eval takes either by_level or levels/condition_seeds, not both")
        if self.clock is None or self.policy_noise is None:
            raise ValueError("eval by_level states its clock and policy_noise")
        levels = [c.level for c in self.by_level]
        if len(set(levels)) != len(levels):
            raise ValueError(f"eval by_level repeats a level: {levels}")
        for c in self.by_level:
            if c.level == 0 and (c.unit != "replicate" or c.headline):
                raise ValueError("level 0 has one scene: its seeds are replicates, not headline")
            if c.unit == "replicate" and c.headline:
                raise ValueError(f"level {c.level}: replicates of one scene cannot be headline")
        if not any(c.headline for c in self.by_level):
            raise ValueError("eval by_level has no headline level")
        return self

    def seed_ranges(self) -> list[tuple[int, SeedRange]]:
        if self.by_level is not None:
            return [(c.level, c.seeds) for c in self.by_level]
        assert self.levels is not None and self.condition_seeds is not None
        return [(level, self.condition_seeds) for level in self.levels]


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
    delta_pp: float | None = Field(default=None, gt=0)  # delta of the HE-T rules (branch B)
    rules_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class Budget(_Frozen):
    """Compute ceiling of the fine-tunes of a plan and of its round (PO 4/11/2026, tier 2)."""

    ceiling_cu: float = Field(gt=0)  # hard ceiling over every run in `runs`
    cap_cu_per_run: float = Field(gt=0)  # the watcher stops a run here
    runs: list[str] = Field(min_length=1)  # exactly the branches of this plan
    round_runs: list[str] = Field(default_factory=list)  # branches of round plans on it
    watcher: str  # what stops a run at its cap


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
    budget: Budget | None = None
    # Repo-relative path -> sha256 of files the eval reads but no other pin covers:
    # the task config, the split and the scene, scorer and eval-loop sources.
    pinned_files: dict[str, str] | None = None
    supersedes: str | None = None  # run_plan_id of a plan this one replaces before it ran
    # Repo path of the plan that replaced this one. Set after the freeze, so it is left
    # out of the id and the lock (STATUS_FIELDS): it says whether to run, not what runs.
    superseded_by: str | None = None

    @classmethod
    def load(cls, path: Path) -> TrayRunPlan:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def eval_conditions(self) -> list[tuple[int, int]]:
        """(level, seed) of every eval episode; the same list for every branch."""
        return [
            (level, seed)
            for level, seeds in self.eval.seed_ranges()
            for seed in range(seeds.start, seeds.stop)
        ]

    def headline_conditions(self) -> list[tuple[int, int]]:
        """The (level, seed) pooled into the primary metric: all of them in v1."""
        if self.eval.by_level is None:
            return self.eval_conditions()
        headline = {c.level for c in self.eval.by_level if c.headline}
        return [(level, seed) for level, seed in self.eval_conditions() if level in headline]


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


def plan_json(plan: BaseModel) -> Any:
    """The plan as JSON; unset optional fields are left out, so adding one keeps old ids.

    STATUS_FIELDS are left out too: marking a frozen plan superseded keeps its id."""
    return plan.model_dump(mode="json", exclude_none=True, exclude=STATUS_FIELDS)


def run_plan_id(plan: BaseModel) -> str:
    return "rp_" + canonical_sha256(plan_json(plan))[:12]


def lock_path(plan_path: Path) -> Path:
    return plan_path.with_name(plan_path.name.removesuffix(".yaml") + ".lock.json")


def rules_block(text: str) -> str:
    """The text between the tier2-rules markers: exactly one pair, in order."""
    begin, end = RULES_MARKERS
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ValueError(f"needs exactly one {begin} ... {end} block")
    start, stop = text.index(begin) + len(begin), text.index(end)
    if stop < start:
        raise ValueError(f"{end} comes before {begin}")
    return text[start:stop]


def rules_sha256(text: str) -> str:
    return hashlib.sha256(rules_block(text).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(plan: TrayRunPlan, repo: Path = REPO) -> list[str]:
    """Everything wrong between the plan and the files it names; empty when it holds."""
    problems: list[str] = []
    recipe = Psi0Recipe.load(repo / plan.recipe.file)
    if recipe.stage != 3:
        problems.append(f"{plan.recipe.file} is stage {recipe.stage}, not 3")
    if recipe_sha256(recipe) != plan.recipe.sha256:
        problems.append(f"{plan.recipe.file} hashes to {recipe_sha256(recipe)}")
    for key, value in plan.recipe.overrides.items():
        if key not in TRAINING_NEUTRAL_OVERRIDES:
            problems.append(f"override {key} changes training: every branch runs the recipe as is")
        elif key not in recipe.args:
            problems.append(f"override {key} is not an arg of {plan.recipe.file}")
        elif isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            problems.append(f"override {key} must be a positive step count, not {value!r}")

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

    sets_path = repo / plan.demo_sets.file
    sets = DemoSets.model_validate_json(sets_path.read_text(encoding="utf-8"))
    pinned_file = plan.demo_sets.file_sha256
    if pinned_file is not None and file_sha256(sets_path) != pinned_file:
        problems.append(f"{plan.demo_sets.file} is not the demo-set file the plan pins")
    if (sets.release_id, sets.release_hash) != (plan.release.id, plan.release.release_hash):
        problems.append(f"{plan.demo_sets.file} is for another release: {sets.release_id}")
    if sets.salt != plan.demo_sets.salt:
        problems.append(f"{plan.demo_sets.file} uses salt {sets.salt!r}")
    for name, pinned in plan.demo_sets.hashes.items():
        got = sets.sets.get(name)
        if got is None or got.set_hash != pinned:
            problems.append(f"demo set {name}: file has {got and got.set_hash}, plan pins {pinned}")
        elif (seeds_hash := set_hash(sets.release_hash, got.seeds)) != pinned:
            problems.append(f"demo set {name}: its seeds hash to {seeds_hash}, plan pins {pinned}")
    pinned_q, used_q = plan.demo_sets.quality, sets.quality
    if (pinned_q is None) != (used_q is None):
        problems.append("plan and demo-set file disagree on whether a quality filter was used")
    elif pinned_q is not None and used_q is not None:
        actual = hashlib.sha256((repo / pinned_q.file).read_bytes()).hexdigest()
        if not pinned_q.sha256 == used_q.file_sha256 == actual:
            problems.append(f"{pinned_q.file} is not the quality file the sets were cut from")
        if pinned_q.filter != used_q.filter:
            problems.append("plan pins other quality limits than the demo sets used")
    pinned_qa, used_qa = plan.demo_sets.qa, sets.qa
    if (pinned_qa is None) != (used_qa is None):
        problems.append("plan and demo-set file disagree on whether DA-03 QA rejects were left out")
    elif (
        pinned_qa is not None
        and used_qa is not None
        and (
            pinned_qa.reports_sha256 != used_qa.reports_sha256
            or pinned_qa.threshold_version != used_qa.threshold_version
        )
    ):
        problems.append("plan pins other DA-03 QA reports than the demo sets were cut after")
    ordered = sorted(sets.sets.values(), key=lambda s: s.n)
    for small, large in zip(ordered, ordered[1:]):
        if not set(small.seeds) <= set(large.seeds):
            problems.append(f"demo set of {small.n} is not inside the set of {large.n}")
        if not set(small.episode_indices) <= set(large.episode_indices):
            problems.append(f"episode indices of the set of {small.n} are not inside {large.n}'s")

    for name, branch in plan.branches.items():
        if branch.demo_set not in plan.demo_sets.hashes:
            problems.append(f"branch {name}: demo set {branch.demo_set} is not pinned")
        if branch.parent not in plan.parents:
            problems.append(f"branch {name}: parent {branch.parent} is not pinned")
    for comparison in plan.comparisons:
        for side in (comparison.a, comparison.b):
            if side not in plan.branches:
                problems.append(f"comparison names unknown branch {side}")

    budget = plan.budget
    if budget is not None:
        count = len(budget.runs) + len(budget.round_runs)
        total = budget.cap_cu_per_run * count
        if total > budget.ceiling_cu:
            problems.append(
                f"budget: {count} runs x {budget.cap_cu_per_run:g} CU = {total:g} CU"
                f" over the ceiling of {budget.ceiling_cu:g}"
            )
        for name in plan.branches:
            if name not in budget.runs:
                problems.append(f"budget: branch {name} has no run in the budget")
        for name in budget.runs:
            if name not in plan.branches:
                problems.append(f"budget: run {name} is not a branch of this plan")
        for name in budget.round_runs:
            if name in plan.branches:
                problems.append(f"budget: round run {name} is a branch of this plan")

    rules = plan.interpretation.rules_sha256
    if rules is not None:
        doc = plan.interpretation.doc
        try:
            actual = rules_sha256((repo / doc).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            problems.append(f"{doc}: {error}")
        else:
            if actual != rules:
                problems.append(f"the reading rules in {doc} changed since the plan pinned them")

    if plan.pinned_files is not None:
        for rel in (plan.task["config"], SPLIT_FILE):
            if rel not in plan.pinned_files:
                problems.append(f"pinned_files lacks {rel}, which the eval reads")
        for rel, sha in plan.pinned_files.items():
            path = repo / rel
            if not path.is_file():
                problems.append(f"pinned file {rel} is missing")
            elif file_sha256(path) != sha:
                problems.append(f"pinned file {rel} changed since the plan pinned it")

    split = yaml.safe_load((repo / SPLIT_FILE).read_text(encoding="utf-8"))
    dev = split["seed_ranges"][plan.eval.split]
    for level, seeds in plan.eval.seed_ranges():
        if not dev["start"] <= seeds.start < seeds.stop <= dev["stop"]:
            problems.append(
                f"eval seeds of level {level} [{seeds.start}, {seeds.stop}) leave the"
                f" {plan.eval.split} range"
            )
    return problems


def check_release(plan: TrayRunPlan, release_root: Path, repo: Path = REPO) -> list[str]:
    """Every set's episode indices against the release's own export (needs the release).

    The demo-set file lists seeds and episode indices as two ascending lists, so only
    the release says which index is which seed's; `check` alone cannot.
    """
    try:
        release_hash, episodes = read_release(release_root)
    except (OSError, ValueError, KeyError) as error:
        return [f"{release_root}: {error}"]
    if release_hash != plan.release.release_hash:
        return [f"{release_root} is release {release_hash}, not {plan.release.release_hash}"]
    index_of = {e.seed: e.episode_index for e in episodes}
    sets = DemoSets.model_validate_json((repo / plan.demo_sets.file).read_text(encoding="utf-8"))
    problems = []
    for name, demo_set in sets.sets.items():
        missing = [seed for seed in demo_set.seeds if seed not in index_of]
        if missing:
            problems.append(f"demo set {name}: seeds {missing[:5]} are not in the release")
        elif sorted(index_of[seed] for seed in demo_set.seeds) != demo_set.episode_indices:
            problems.append(f"demo set {name}: episode_indices are not its seeds' in the release")
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
    if parent.budget is not None and round_plan.branch not in parent.budget.round_runs:
        problems.append(
            f"budget: {round_plan.branch} has no round run in the budget of {round_plan.inherits}"
        )
    lock = lock_path(repo / round_plan.inherits)
    if not lock.is_file():
        problems.append(f"{round_plan.inherits} is not frozen")
    elif json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"] != run_plan_id(parent):
        problems.append(f"{round_plan.inherits} changed since it was frozen")
    targets = round_plan.targets
    if round_plan.status == "frozen" and (
        len(targets.seeds) != targets.n_add or not targets.set_hash
    ):
        problems.append("a frozen round needs its n_add targeted seeds and their set_hash")
    return problems


def freeze(plan_path: Path, repo: Path = REPO) -> Path:
    plan = TrayRunPlan.load(plan_path)
    problems = check(plan, repo)
    if plan.superseded_by is not None:
        problems.append(f"superseded by {plan.superseded_by}: freeze that plan instead")
    if not (repo / plan.interpretation.doc).is_file():
        problems.append(f"{plan.interpretation.doc} is missing: fix the reading rules first")
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["check", "freeze"])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--release", type=Path, help="check episode indices against it")
    args = parser.parse_args(argv)
    if args.action == "freeze":
        out = freeze(args.plan)
        print(f"wrote {out}: {json.loads(out.read_text())['run_plan_id']}")
        return 0
    raw = yaml.safe_load(args.plan.read_text(encoding="utf-8"))
    if raw.get("purpose") == "round":
        round_plan = TrayRoundPlan.model_validate(raw)
        problems = check_round(round_plan)
        summary = f"{args.plan}: round {round_plan.status}, branch {round_plan.branch}"
    else:
        plan = TrayRunPlan.model_validate(raw)
        problems = check(plan)
        if args.release is not None:
            problems += check_release(plan, args.release)
        summary = f"{args.plan}: {run_plan_id(plan)}, {len(plan.eval_conditions())} eval conditions"
        if plan.superseded_by is not None:
            problems.append(f"SUPERSEDED by {plan.superseded_by}: do not run this plan")
    for problem in problems:
        print(problem, file=sys.stderr)
    if not problems:
        print(summary)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

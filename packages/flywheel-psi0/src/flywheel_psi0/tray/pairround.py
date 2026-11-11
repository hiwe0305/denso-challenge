"""A Failure -> Data round on one branch of the paired plan: C70_R1 on C_70 (DA-34 task 7).

docs/he/tray.md section 20 (Hiếu 12/11/2026): the round starts from the failures of
`C_70`, the 70 % branch of the frozen paired plan (`pairplan`, `he-tray-pair60k.yaml`),
and adds at most B_add targeted episodes to C_70's data, S70. B_add is what the uniform
branch `C_ALL` adds to S70 (606 - 425 = 181 episodes), so the primary reading (r1) of the
rules block `round-c70-rules` pairs `C70_R1` with `C_ALL`: the same budget, chosen by
failure or added uniformly. (r2) pairs it with `C_70`.

Everything but the data is the base branch's, by check rather than by copy: the round's
`train` names the parent, step count, train seed and stats of `C_70` (ALL's
`stats_psi0.json`), and `check` fails on any other value. The C+ round
(`runplan.TrayRoundPlan`) inherits a `branch_train` plan; this one inherits a
`paired_train` plan, and `runplan check`/`freeze` hand it over here.

`check` ties the round to the paired plan (frozen, unchanged since), its branches and
eval, to the rows file of C_70's stage 1 rollouts (sha256 and counts) and, once pinned,
to the rules block and the targeted set (`runplan.check_targets`). `pending` lists the
pins still null; `freeze` refuses a draft or any of them, then writes the lock beside
the plan as every tray plan does. `check --launch` fails on a draft, a missing or stale
lock, or a pending pin; with `--targets-release` it also reads the targeted release.

    python -m flywheel_psi0.tray.runplan check configs/runplans/tray/round-tray-c70.yaml
    python -m flywheel_psi0.tray.runplan freeze configs/runplans/tray/round-tray-c70.yaml
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from flywheel_psi0.tray.pairplan import PairComparison, TrayPairPlan
from flywheel_psi0.tray.quality import QualityFilter
from flywheel_psi0.tray.runplan import (
    REPO,
    DemoSetPins,
    FilePin,
    Interpretation,
    Release,
    RoundTargets,
    check_targets_release,
    file_sha256,
    lock_path,
    plan_json,
    rules_sha256,
    run_plan_id,
)
from flywheel_psi0.tray.runplan import check_targets as _check_targets


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FailureCounts(_Frozen):
    rollouts: int = Field(gt=0)
    success: int = Field(ge=0)
    failures: int = Field(ge=0)


class RoundFailures(_Frozen):
    """Steps 1-3 of spec 6.1, already run: the base branch's stage 1 rollouts, one row each."""

    eval_dir: str
    runs_sha256: str = Field(min_length=64, max_length=64)  # runs.jsonl of the eval batch
    eval_set: str
    conditions_sha256: str = Field(min_length=64, max_length=64)
    checkpoint: int = Field(gt=0)
    rows: FilePin
    counts: FailureCounts
    cluster_key: list[str] = Field(min_length=1)


class RoundDiagnosis(_Frozen):
    """Spec 6.15 parameters of steps 4-8."""

    representatives_per_cluster: int = Field(gt=0)
    representative_seed: int
    reset_runs: int = Field(gt=0)
    tau_k: float = Field(gt=0, le=1)
    knn_k: int = Field(gt=0)
    tau_cov: str
    step6: Literal["available", "unavailable"]
    step7_rollouts_per_representative: int = Field(gt=0)


class RoundBudget(_Frozen):
    b_add_episodes: int = Field(gt=0)  # spec 7.3 rule 5, in episodes: one unit cost each
    per_failure_rollouts: int = Field(gt=0)
    per_cluster_cap: int = Field(gt=0)
    failures_per_cluster_max: int = Field(gt=0)
    order: str
    train_cap_cu: float = Field(gt=0)
    eval_cap_cu: float = Field(gt=0)
    diagnosis_cap_cu: float = Field(gt=0)


class PairRoundTargets(_Frozen):
    """The targeted set: empty in a draft, pinned at freeze like the C+ round's."""

    n_add_max: int = Field(gt=0)
    from_failures_of: str
    generator: str
    seed_window: tuple[int, int]  # inclusive: the train seeds the generator may use
    quality_filter: QualityFilter
    seeds: list[int] = Field(default_factory=list)
    set_hash: str | None = None
    conditions: FilePin | None = None
    selection: FilePin | None = None
    release: Release | None = None
    demo_sets: DemoSetPins | None = None
    set_name: str | None = None

    def as_round_targets(self) -> RoundTargets:
        """The C+ round's shape, so `runplan.check_targets` reads the set the same way."""
        fields = ("set_hash", "conditions", "selection", "release", "demo_sets", "set_name")
        return RoundTargets(
            n_add=max(len(self.seeds), 1),
            from_failures_of=self.from_failures_of,
            generator=self.generator,
            seeds=self.seeds,
            **{name: getattr(self, name) for name in fields},
        )


class RoundTrain(_Frozen):
    """The base branch's training, named so `check` can hold it equal."""

    parent: str
    data: str
    stats_sha256: str = Field(min_length=64, max_length=64)
    recipe: str
    steps: int = Field(gt=0)
    train_seed: int
    gpu: str


class RoundEval(_Frozen):
    eval_set: str
    checkpoint: int = Field(gt=0)
    stages: str
    server: str


class TrayPairRoundPlan(_Frozen):
    name: str
    purpose: Literal["round"]
    story: str
    status: Literal["draft", "frozen"]
    inherits: str  # repo-relative path of the frozen paired_train plan
    base_branch: str  # pi_0 of the round: the branch whose failures it reads
    branch: str  # the new branch
    uniform_branch: str  # the same budget added uniformly: what (r1) compares with
    max_rounds: Literal[1]
    failures: RoundFailures
    diagnosis: RoundDiagnosis
    budget: RoundBudget
    targets: PairRoundTargets
    train: RoundTrain
    eval: RoundEval
    comparisons: list[PairComparison] = Field(min_length=1)
    interpretation: Interpretation

    @classmethod
    def load(cls, path: Path) -> TrayPairRoundPlan:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def on_paired_plan(raw: dict[str, Any], repo: Path = REPO) -> bool:
    """A round whose `inherits` is a paired plan: this module's, not runplan's C+ shape."""
    if raw.get("purpose") != "round" or not isinstance(raw.get("inherits"), str):
        return False
    path = repo / raw["inherits"]
    if not path.is_file():
        return False
    parent = yaml.safe_load(path.read_text(encoding="utf-8"))
    return isinstance(parent, dict) and parent.get("purpose") == "paired_train"


def check_targets(targets: PairRoundTargets, repo: Path = REPO) -> list[str]:
    """A pinned targeted set against the files it names (`runplan.check_targets`)."""
    return _check_targets(targets.as_round_targets(), repo)


def pending_targets(targets: PairRoundTargets) -> list[str]:
    out = [] if targets.seeds else ["targets.seeds: the targeted set is not generated yet (7.5)"]
    for name in ("set_hash", "conditions", "selection", "release", "demo_sets", "set_name"):
        if getattr(targets, name) is None:
            out.append(f"targets.{name} is not pinned yet (7.5)")
    return out


def pending(plan: TrayPairRoundPlan) -> list[str]:
    """Pins still null: no freeze and no launch until generation and the rules are in."""
    out = pending_targets(plan.targets)
    if plan.interpretation.rules_sha256 is None:
        out.append("interpretation.rules_sha256: the reading rules are pinned at freeze")
    return out


def check(plan: TrayPairRoundPlan, repo: Path = REPO) -> list[str]:
    """Everything wrong between the round, its paired plan and the files it names."""
    path = repo / plan.inherits
    if not path.is_file():
        return [f"inherits: {plan.inherits} is missing"]
    pair = TrayPairPlan.load(path)
    problems: list[str] = []
    lock = lock_path(path)
    if not lock.is_file():
        problems.append(f"{plan.inherits} is not frozen")
    elif json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"] != run_plan_id(pair):
        problems.append(f"{plan.inherits} changed since it was frozen")

    branches = pair.branches
    if plan.branch in branches:
        problems.append(f"branch {plan.branch} already exists in {plan.inherits}")
    missing = [
        f"{role} {getattr(plan, role)} is not a branch of {plan.inherits}"
        for role in ("base_branch", "uniform_branch")
        if getattr(plan, role) not in branches
    ]
    if missing:
        return problems + missing
    base, uniform = branches[plan.base_branch], branches[plan.uniform_branch]
    base_data = pair.subset(pair.data_of(base))
    if base_data is None:
        problems.append(f"base_branch {plan.base_branch} trains on the whole cut: nothing to add")
    if uniform.parent != base.parent or pair.data_of(uniform) != pair.cut.name:
        problems.append(
            f"uniform_branch {plan.uniform_branch} is not {plan.base_branch}'s VLM on the"
            f" whole cut {pair.cut.name}"
        )
    if (
        base_data is not None
        and base_data.episodes is not None
        and pair.cut.episodes is not None
        and plan.budget.b_add_episodes != pair.cut.episodes - base_data.episodes
    ):
        problems.append(
            f"budget.b_add_episodes {plan.budget.b_add_episodes} is not what"
            f" {plan.uniform_branch} adds: {pair.cut.episodes} - {base_data.episodes} ="
            f" {pair.cut.episodes - base_data.episodes}"
        )
    if plan.targets.n_add_max != plan.budget.b_add_episodes:
        problems.append("targets.n_add_max is not budget.b_add_episodes")
    if plan.targets.from_failures_of != plan.base_branch:
        problems.append("targets must come from the failures of the base branch")

    problems += _train_problems(plan, pair)
    problems += _eval_problems(plan, pair)
    problems += _comparison_problems(plan, pair)
    problems += _failure_problems(plan, repo)
    problems += _target_problems(plan, pair, repo)
    rules = plan.interpretation.rules_sha256
    if rules is not None:
        doc = plan.interpretation.doc
        try:
            text = (repo / doc).read_text(encoding="utf-8")
            actual = rules_sha256(text, plan.interpretation.rules_marker)
        except (OSError, ValueError) as error:
            problems.append(f"{doc}: {error}")
        else:
            if actual != rules:
                problems.append(f"the reading rules in {doc} changed since the plan pinned them")
    return problems


def _train_problems(plan: TrayPairRoundPlan, pair: TrayPairPlan) -> list[str]:
    """The base branch's parent, steps, seed and stats: only the data may differ."""
    base = pair.branches[plan.base_branch]
    train = plan.train
    expected: dict[str, Any] = {
        "parent": base.parent,
        "steps": pair.steps(),
        "train_seed": pair.train_seeds[0],
        "stats_sha256": pair.cut.stats_sha256,
    }
    return [
        f"train.{key} is {getattr(train, key)!r}, {plan.base_branch}'s is {value!r}"
        for key, value in expected.items()
        if getattr(train, key) != value
    ]


def _eval_problems(plan: TrayPairRoundPlan, pair: TrayPairPlan) -> list[str]:
    """The round's failures were read, and its result is read, on the pair's eval set."""
    problems = []
    for where, eval_set, step in (
        ("failures", plan.failures.eval_set, plan.failures.checkpoint),
        ("eval", plan.eval.eval_set, plan.eval.checkpoint),
    ):
        if eval_set != pair.eval_of.eval_set:
            problems.append(f"{where}.eval_set {eval_set} is not {pair.eval_of.eval_set}")
        if step != pair.checkpoints.primary:
            problems.append(f"{where}.checkpoint {step} is not {pair.checkpoints.primary}")
    if plan.failures.conditions_sha256 != pair.eval_of.conditions_sha256:
        problems.append("failures.conditions_sha256 is not the pair's eval set")
    return problems


def _comparison_problems(plan: TrayPairRoundPlan, pair: TrayPairPlan) -> list[str]:
    """(r1) the round against the uniform branch, primary; others against pair branches."""
    problems = []
    rules = [c.rule for c in plan.comparisons]
    if len(set(rules)) != len(rules):
        problems.append(f"comparisons: a rule appears twice: {rules}")
    for c in plan.comparisons:
        if c.variant != plan.branch or c.baseline not in pair.branches:
            problems.append(f"comparison {c.rule}: {c.variant} - {c.baseline} is not the round")
            continue
        if (c.kind == "noninferiority") != (c.margin is not None):
            problems.append(f"comparison {c.rule}: a margin goes with noninferiority only")
    primary = [c for c in plan.comparisons if c.kind == "primary"]
    if len(primary) != 1 or primary[0].baseline != plan.uniform_branch:
        problems.append(
            f"comparisons: the primary comparison is {plan.branch} - {plan.uniform_branch}, once"
        )
    return problems


def _failure_problems(plan: TrayPairRoundPlan, repo: Path) -> list[str]:
    pin = plan.failures.rows
    path = repo / pin.file
    if not path.is_file():
        return [f"{pin.file} is missing"]
    if file_sha256(path) != pin.sha256:
        return [f"{pin.file} changed since the plan pinned it"]
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    success = sum(bool(r["success"]) for r in rows)
    found = {"rollouts": len(rows), "success": success, "failures": len(rows) - success}
    if found != plan.failures.counts.model_dump():
        return [f"failures.counts are not {pin.file}'s: {found}"]
    return []


def _target_problems(plan: TrayPairRoundPlan, pair: TrayPairPlan, repo: Path) -> list[str]:
    """The generator's window, ALL's quality filter, the budget; pinned files once frozen."""
    targets = plan.targets
    problems = []
    low, high = targets.seed_window
    if low > high:
        problems.append(f"targets.seed_window {targets.seed_window} is empty")
    filters = {
        p.demo_sets.quality.filter
        for p in pair.cut.parts
        if p.demo_sets is not None and p.demo_sets.quality is not None
    }
    if filters and filters != {targets.quality_filter}:
        problems.append("targets.quality_filter is not the filter ALL was cut with")
    seeds = targets.seeds
    if seeds != sorted(set(seeds)):
        problems.append("targets.seeds must be unique and ascending")
    if any(not low <= s <= high for s in seeds):
        problems.append(f"targets.seeds outside seed_window {targets.seed_window}")
    if len(seeds) > targets.n_add_max:
        problems.append(f"targets: {len(seeds)} seeds, more than n_add_max {targets.n_add_max}")
    if plan.status == "frozen" and not pending_targets(targets):
        problems += check_targets(targets, repo)
        pins = targets.demo_sets
        if pins is not None and (
            pins.quality is None or pins.quality.filter != targets.quality_filter
        ):
            problems.append("targets.demo_sets is not cut with targets.quality_filter")
    return problems


def freeze(plan_path: Path, repo: Path = REPO) -> Path:
    """Lock a round once its targets and rules are pinned; the paired plan is frozen already."""
    plan = TrayPairRoundPlan.load(plan_path)
    problems = check(plan, repo) + pending(plan)
    if plan.status != "frozen":
        problems.append("status draft: set status frozen with the targets, then freeze")
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


def launch_problems(plan: TrayPairRoundPlan, plan_path: Path) -> list[str]:
    """What stops a job: a draft, a pending pin, a missing or stale lock."""
    problems = [f"PENDING: {p}" for p in pending(plan)]
    if plan.status != "frozen":
        problems.append("DRAFT: no job runs a draft round; freeze it with its targets")
    lock = lock_path(plan_path)
    if not lock.is_file():
        problems.append(f"{plan_path} is not frozen: no {lock.name}")
    elif json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"] != run_plan_id(plan):
        problems.append(f"{plan_path} changed since it was frozen")
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("action", choices=["check", "freeze"])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--launch", action="store_true", help="before a job: drafts, pins fail")
    parser.add_argument("--targets-release", type=Path, help="the targeted release's export")
    args = parser.parse_args(argv)
    repo = REPO  # read at call time, so a test can point it at a copy
    if args.action == "freeze":
        out = freeze(args.plan, repo)
        print(f"wrote {out}: {json.loads(out.read_text())['run_plan_id']}")
        return 0
    plan = TrayPairRoundPlan.load(args.plan)
    problems = check(plan, repo)
    summary = (
        f"{args.plan}: round {plan.status}, branch {plan.branch} on {plan.base_branch}"
        f" of {plan.inherits}, {run_plan_id(plan)}"
    )
    todo = pending(plan)
    if todo:
        summary += f", {len(todo)} pins pending"
    if args.launch:
        problems += launch_problems(plan, args.plan)
    if args.targets_release is not None:
        problems += check_targets_release(
            plan.targets.as_round_targets(), args.targets_release, repo
        )
    for line in problems:
        print(line, file=sys.stderr)
    if not problems:
        print(summary + (", launch OK" if args.launch else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

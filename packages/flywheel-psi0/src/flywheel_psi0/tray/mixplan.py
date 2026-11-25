"""One stage 3 run on one dataset joined from N demo sets of N releases (DA-48).

Run M (Hiếu 25/11/2026) trains once on the fixed-jig tray scene: four parts, each the
set Q of one release (two full-episode releases of DA-41, two place-cut releases of
DA-46), Q being the seeds whose placement error is within 3 cm and 5 degrees
(`demo_sets --keep-seeds`). Each part is cut with `scripts/he/demo_subset.py` and the
parts are joined in the plan's order with `cplus_cut` (marker `meta/flywheel_subset.json`),
stats the joined set's own. `TrayRunPlan` holds one release and `TrayPairPlan` a full
grid of two parents, so neither fits; this plan reuses their pieces (`Release`,
`DemoSetPins`, `Parent`, `Recipe`, `Budget`, `Interpretation`, `Schedule`) for one run.

The cut pins each part (release, demo-set file and its sha256, set name, n) and the
joined dataset (episodes, frames, sha256 of `meta/stats_psi0.json`); the recipe override
`train.max_training_steps` is the plan's step count, changeable until the freeze;
`checkpoints` names the primary checkpoint and the early reads, all saved by the recipe
and none past the step count. Until the data is built the unknown pins are null: `check`
passes as a draft and `freeze` and `check --launch` refuse and list them (`pending`).

`cut_problems` checks a dataset against the pins with JSON reads only (marker, parts,
each episode's own seed, totals, lengths, stats sha256), so the Colab VM runs it before
anything is installed. `pack` writes the tar and its `.json` (`pair_cut.pack`) once the
dataset holds; `drive.cuts` is where the tar goes under MyDrive.

    python -m flywheel_psi0.tray.mixplan check configs/runplans/tray/he-tray-jig-m.yaml
    python -m flywheel_psi0.tray.mixplan check <plan> --data <dir>/M/<env name> [--launch]
    python -m flywheel_psi0.tray.mixplan freeze <plan>
    python -m flywheel_psi0.tray.mixplan pack <plan> --data <dir>/M/<env name> --out <dir>/M.tar
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from flywheel_psi0.trainer.recipe import Psi0Recipe
from flywheel_psi0.tray import pair_cut
from flywheel_psi0.tray.demo_sets import DemoSets
from flywheel_psi0.tray.pairplan import PAIR_OVERRIDES, SAVE_EVERY, STEPS, Schedule
from flywheel_psi0.tray.runplan import (
    REPO,
    Budget,
    DemoSetPins,
    Interpretation,
    Parent,
    Pin,
    PsiModel,
    Recipe,
    Release,
    Stage1Parent,
    demo_set_problems,
    lock_path,
    parent_problems,
    parents_pending,
    plan_json,
    recipe_sha256,
    rules_sha256,
    run_plan_id,
)


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MixPart(_Frozen):
    """One part of the joined dataset: a demo set of one release."""

    release_id: str  # the release this part is cut from, known before its pins
    n: int = Field(gt=0)  # episodes of the part's set, known before its pins
    release: Release | None = None
    demo_sets: DemoSetPins | None = None
    set_name: str | None = None  # the set of `demo_sets` this part takes


class MixCut(_Frozen):
    """The one dataset the run trains on: its parts joined in order."""

    name: str
    rule: str  # which episodes of each part, written before the run
    parts: list[MixPart] = Field(min_length=1)
    episodes: int = Field(gt=0)  # the sum of the parts' n
    frames: int | None = Field(default=None, gt=0)  # meta/info.json total_frames
    stats_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class MixBranch(_Frozen):
    parent: str
    role: str


class MixCheckpoints(_Frozen):
    """The saved checkpoints read: `primary` the metric, `reads` early looks only."""

    primary: int = Field(gt=0)
    reads: list[int] = Field(default_factory=list)


class MixDrive(_Frozen):
    """Folders under MyDrive: the packed cut, and the run directories `persist` copies."""

    cuts: str
    runs: str


class TrayMixPlan(_Frozen):
    name: str
    purpose: Literal["mix_train"]
    story: str
    status: Literal["draft"] | None = None  # dropped once the pins are in and Hiếu orders it
    site_id: str
    task: dict[str, str]
    embodiment: str
    code: dict[str, Pin]
    psi_model: PsiModel
    parents: dict[str, Parent | Stage1Parent]
    cut: MixCut
    recipe: Recipe
    train_seeds: list[int] = Field(min_length=1, max_length=1)
    branches: dict[str, MixBranch] = Field(min_length=1, max_length=1)
    checkpoints: MixCheckpoints
    interpretation: Interpretation
    pricebook: str
    budget: Budget
    schedule: Schedule
    drive: MixDrive

    @classmethod
    def load(cls, path: Path) -> TrayMixPlan:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def steps(self) -> int | None:
        value = self.recipe.overrides.get(STEPS)
        return value if isinstance(value, int) and not isinstance(value, bool) else None


def check(plan: TrayMixPlan, repo: Path = REPO) -> list[str]:
    """Everything wrong between the plan and the files it names; empty when it holds."""
    problems: list[str] = []
    recipe = Psi0Recipe.load(repo / plan.recipe.file)
    if recipe.stage != 3:
        problems.append(f"{plan.recipe.file} is stage {recipe.stage}, not 3")
    if recipe_sha256(recipe) != plan.recipe.sha256:
        problems.append(f"{plan.recipe.file} hashes to {recipe_sha256(recipe)}")
    for key, value in plan.recipe.overrides.items():
        if key not in PAIR_OVERRIDES:
            problems.append(f"override {key}: the plan may set only {sorted(PAIR_OVERRIDES)}")
        elif key not in recipe.args:
            problems.append(f"override {key} is not an arg of {plan.recipe.file}")
        elif isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            problems.append(f"override {key} must be a positive step count, not {value!r}")
    if STEPS not in plan.recipe.overrides:
        problems.append(f"the plan states its step count: recipe.overrides.{STEPS}")
    problems += checkpoint_problems(plan, recipe)

    problems += parent_problems(plan.parents, recipe, plan.recipe.file)
    ((name, branch),) = plan.branches.items()
    if name != plan.cut.name:
        problems.append(f"branch {name} does not train on cut {plan.cut.name}: name them alike")
    parent = plan.parents.get(branch.parent)
    if parent is None:
        problems.append(f"branch {name}: parent {branch.parent} is not pinned")
    used = {branch.parent}
    if isinstance(parent, Stage1Parent):
        used.add(parent.vlm_stage1.from_parent)  # its base: the action header and the check
    if set(plan.parents) - used:
        problems.append(f"parents {sorted(set(plan.parents) - used)} are pinned but unused")

    problems += part_problems(plan, repo)

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

    budget = plan.budget
    if budget.runs != list(plan.branches) or budget.round_runs:
        problems.append(f"budget: runs are exactly the branch {list(plan.branches)}")
    if budget.cap_cu_per_run > budget.ceiling_cu:
        problems.append(f"budget: cap {budget.cap_cu_per_run:g} CU over the ceiling")
    for flag in (f"--cap {budget.cap_cu_per_run:g}", f"--floor {plan.schedule.floor_cu:g}"):
        if flag not in budget.watcher:
            problems.append(f"budget.watcher does not say {flag}")
    if plan.schedule.waves is not None:
        problems.append("schedule.waves: one run has no waves")
    for field in ("cuts", "runs"):
        folder = PurePosixPath(getattr(plan.drive, field))
        if folder.is_absolute() or ".." in folder.parts or not folder.parts:
            problems.append(f"drive.{field} {folder}: a relative folder under MyDrive")
    return problems


def checkpoint_problems(plan: TrayMixPlan, recipe: Psi0Recipe) -> list[str]:
    """Every read checkpoint is saved by the recipe and none lies past the step count."""
    marks = plan.checkpoints
    problems = []
    steps = plan.steps()
    if steps is not None and marks.primary > steps:
        problems.append(f"checkpoints.primary {marks.primary} is past the step count {steps}")
    if marks.reads != sorted(set(marks.reads)) or any(r >= marks.primary for r in marks.reads):
        problems.append(f"checkpoints.reads {marks.reads}: ascending, unique, before the primary")
    every = recipe.args.get(SAVE_EVERY)
    if not isinstance(every, int) or isinstance(every, bool):
        return [*problems, f"{plan.recipe.file} has no integer {SAVE_EVERY}"]
    for step in [marks.primary, *marks.reads]:
        if step <= 0 or step % every:
            problems.append(f"checkpoint {step}: Psi0 saves every {every} steps only")
    return problems


def part_problems(plan: TrayMixPlan, repo: Path = REPO) -> list[str]:
    """Each pinned part against its demo-set file and release; the counts add up."""
    problems: list[str] = []
    ids = [part.release_id for part in plan.cut.parts]
    if len(set(ids)) != len(ids):
        problems.append(f"cut {plan.cut.name}: a release is a part twice: {ids}")
    total = sum(part.n for part in plan.cut.parts)
    if total != plan.cut.episodes:
        problems.append(
            f"cut {plan.cut.name}: episodes {plan.cut.episodes}, the parts sum to {total}"
        )
    for part in plan.cut.parts:
        label = f"part {part.release_id}"
        pins = (part.release, part.demo_sets, part.set_name)
        if all(pin is None for pin in pins):
            continue
        if any(pin is None for pin in pins):
            problems.append(f"{label}: pin release, demo_sets and set_name together")
            continue
        assert part.release is not None and part.demo_sets is not None and part.set_name
        if part.release.id != part.release_id:
            problems.append(f"{label}: pins release {part.release.id}")
        if part.release.data_class != "public":
            problems.append(f"{label}: data_class {part.release.data_class}")
        if part.demo_sets.file_sha256 is None:
            problems.append(f"{label}: demo_sets.file_sha256 is not pinned")
        if part.set_name not in part.demo_sets.hashes:
            problems.append(f"{label}: set {part.set_name} is not pinned")
        path = repo / part.demo_sets.file
        if not path.is_file():
            problems.append(f"{label}: {part.demo_sets.file} is missing")
            continue
        problems += [f"{label}: {p}" for p in demo_set_problems(part.demo_sets, part.release, repo)]
        demo = DemoSets.model_validate_json(path.read_text(encoding="utf-8")).sets.get(
            part.set_name
        )
        if demo is not None and demo.n != part.n:
            problems.append(
                f"{label}: set {part.set_name} has {demo.n} episodes, the plan {part.n}"
            )
    return problems


def pending(plan: TrayMixPlan) -> list[str]:
    """Pins still null: no freeze and no launch until the data is built and the rules fixed."""
    out = parents_pending(plan.parents)
    for part in plan.cut.parts:
        for field in ("release", "demo_sets", "set_name"):
            if getattr(part, field) is None:
                out.append(f"cut part {part.release_id}: {field} is not pinned yet")
    for field in ("frames", "stats_sha256"):
        if getattr(plan.cut, field) is None:
            out.append(f"cut {plan.cut.name}: {field} is not pinned yet")
    if plan.interpretation.rules_sha256 is None:
        out.append("interpretation.rules_sha256: the reading rules are pinned before the run")
    return out


def cut_problems(data: Path, plan: TrayMixPlan, repo: Path = REPO) -> list[str]:
    """Everything wrong between the joined dataset at `data` and the plan's pins."""
    marker = pair_cut.read_marker(data)
    if marker is None:
        return [f"{data / 'meta' / pair_cut.MARKER} missing: not a demo-set cut"]
    cut = plan.cut
    unpinned = [p.release_id for p in cut.parts if p.demo_sets is None or p.release is None]
    if unpinned:
        return [f"cut parts {unpinned} are not pinned yet"]
    problems = []
    if (marker.get("demo_set"), marker.get("n")) != (cut.name, cut.episodes):
        problems.append(
            f"cut is {marker.get('demo_set')!r} of n={marker.get('n')!r}, not {cut.name} of"
            f" {cut.episodes}"
        )
    parts = marker.get("parts", [])
    if len(parts) != len(cut.parts):
        return [*problems, f"cut has {len(parts)} parts, the plan {len(cut.parts)}"]
    rows = pair_cut.read_rows(data)
    start = 0
    for mark, part in zip(parts, cut.parts, strict=True):
        assert part.release is not None and part.demo_sets is not None and part.set_name
        sets = DemoSets.model_validate_json((repo / part.demo_sets.file).read_text("utf-8"))
        demo = sets.sets[part.set_name]
        label = f"part {part.release_id}"
        expected = {
            "release_id": part.release.id,
            "release_hash": part.release.release_hash,
            "set_hash": part.demo_sets.hashes[part.set_name],
            "n": part.n,
            "first_episode_index": start,
        }
        problems += [
            f"{label}: {key} is {mark.get(key)!r}, the plan's is {value!r}"
            for key, value in expected.items()
            if mark.get(key) != value
        ]
        episodes = mark.get("episodes", [])
        if [e["source_episode_index"] for e in episodes] != demo.episode_indices:
            problems.append(f"{label}: episodes are not the set's episode indices in its release")
        if [e["episode_index"] for e in episodes] != list(range(start, start + part.n)):
            problems.append(f"{label}: episodes are not renumbered from {start}")
        try:  # each episode's own seed, compared as sets: never zip seeds with indices
            seeds = [pair_cut.episode_seed(r) for r in rows[start : start + part.n]]
        except (KeyError, TypeError, ValueError):
            problems.append(f"{label}: a row of meta/episodes.jsonl carries no flywheel seed")
        else:
            if sorted(seeds) != demo.seeds:
                problems.append(f"{label}: the episodes' own seeds are not set {part.set_name}'s")
        start += part.n
    return problems + pair_cut._dataset_problems(data, start, cut.frames, cut.stats_sha256)


def launch_problems(plan: TrayMixPlan, plan_path: Path) -> list[str]:
    """What stops a job: draft, null pins, and a plan not frozen or changed since."""
    problems = [f"PENDING: {p}" for p in pending(plan)]
    if plan.status == "draft":
        problems.append("DRAFT: no job runs a draft plan; it needs a Decision first")
    lock = lock_path(plan_path)
    if not lock.is_file():
        problems.append(f"{plan_path} is not frozen: no {lock.name}")
    elif json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"] != run_plan_id(plan):
        problems.append(f"{plan_path} changed since it was frozen")
    return problems


def freeze(plan_path: Path, repo: Path = REPO) -> Path:
    plan = TrayMixPlan.load(plan_path)
    problems = check(plan, repo) + pending(plan)
    if plan.status == "draft":
        problems.append("status draft: drop it once a Decision orders this plan, then freeze")
    if not (repo / plan.interpretation.doc).is_file():
        problems.append(f"{plan.interpretation.doc} is missing: write the reading rules first")
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


def summary(plan: TrayMixPlan, repo: Path = REPO) -> str:
    steps = plan.steps()
    batch = Psi0Recipe.load(repo / plan.recipe.file).args.get("train.train_batch_size")
    text = f"{run_plan_id(plan)}, branch {list(plan.branches)[0]}, {len(plan.cut.parts)} parts"
    text += f", {plan.cut.episodes} episodes, {steps} steps"
    if steps and isinstance(batch, int) and plan.cut.frames:
        passes = steps * batch * plan.recipe.nproc_per_node / plan.cut.frames
        text += f", {passes:.2f} epochs"
    reads = plan.checkpoints.reads
    return text + f", read ckpt {plan.checkpoints.primary}" + (f" (early {reads})" if reads else "")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["check", "freeze", "pack"])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--data", type=Path, help="check, pack: the joined dataset dir")
    parser.add_argument("--out", type=Path, help="pack: <dir>/<cut name>.tar")
    parser.add_argument(
        "--launch", action="store_true", help="before a job: drafts, null pins, no lock fail"
    )
    args = parser.parse_args(argv)
    repo = REPO  # read at call time, so a test can point it at a copy
    if args.action == "freeze":
        out = freeze(args.plan, repo)
        print(f"wrote {out}: {json.loads(out.read_text())['run_plan_id']}")
        return 0
    plan = TrayMixPlan.load(args.plan)
    problems = check(plan, repo)
    if args.data is not None:
        problems += cut_problems(args.data, plan, repo)
    if args.action == "pack":
        if args.data is None or args.out is None:
            parser.error("pack needs --data and --out")
        if args.out.name != f"{plan.cut.name}.tar":
            parser.error(f"pack writes {plan.cut.name}.tar, the name the VM fetches")
        env = plan.task["env_id"].rsplit("/", 1)[-1]
        if args.data.name != env:
            parser.error(f"--data must end in {env}: Psi0 reads the folder name as the dataset")
        problems += [f"PENDING: {p}" for p in pending(plan)]
    elif args.launch:
        problems += launch_problems(plan, args.plan)
    for line in problems:
        print(line, file=sys.stderr)
    if problems:
        return 1
    if args.action == "pack":
        meta: dict[str, Any] = pair_cut.pack(args.data, plan.cut.name, args.out)
        print(json.dumps(meta, indent=1))
        return 0
    todo = pending(plan)
    text = f"{args.plan}: {summary(plan, repo)}"
    text += ", draft" if plan.status == "draft" else ""
    text += f", {len(todo)} pins pending" if todo else ""
    print(text + (", launch OK" if args.launch else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

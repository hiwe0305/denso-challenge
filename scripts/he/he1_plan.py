"""RunPlan of HE-1 on the two-table task: schema, demo sets, checks, freeze (DA-26 AC 1).

`configs/runplans/he/he-1.yaml` holds the grid of design 27/10/2026 section 7.3:
variants V-EGO, V-NOEGO (and the optional V-EGO10) x nested demo sets N10 < N20 <
N40 < N80 of the authors' teleop data x train seed. Recipe, eval set and stats sit
once at plan level and a point only picks a variant, a demo set and a seed, so
"same recipe, same steps, same conditions for every point" holds by construction.
Each point says whether it belongs to the preliminary result for the demo (AC 6)
or to the full grid run after it.

It reuses DA-34's tray code instead of copying it: the hash ranking and nested
sets of `flywheel_psi0.tray.demo_sets`, and the pins, recipe hash and
`run_plan_id` of `flywheel_psi0.tray.runplan`. Two things differ from the tray
plan. The robot data is psi-data, whose episodes carry no seed (S1-07, V6), so an
episode is keyed by its `episode_index` inside the pinned zip: `seeds` in the
demo-set file are episode indices. And the main eval set is not a seed range the
sim lays out at eval time: SIMPLE's two-table eval reads its conditions from a
dataset, so scripts/he/dev_eval_set.py draws them from the team's dev seeds and the
plan pins the sha256 of their env configs. The authors' `simple-eval` set (10 per
level, levels 0 and 1 are train scenes) stays as a secondary set for the baseline.

`check` recomputes the demo sets from the plan alone (episode count, exclusions,
salt, dataset hash) and compares them with the file. `parents` asks the Hugging
Face API for the LFS sha256 of every pinned file and compares the safetensors
headers and `config.json` of the parents (network, no weights downloaded).
`freeze` writes `he-1.lock.json` and the `Decision` of kind `plan_review` that
signs it.

    uv run python scripts/he/he1_plan.py sets --episodes episodes.jsonl \
        --plan configs/runplans/he/he-1.yaml --out configs/runplans/he/demo_sets.json
    uv run python scripts/he/he1_plan.py check configs/runplans/he/he-1.yaml
    uv run python scripts/he/he1_plan.py parents configs/runplans/he/he-1.yaml
    uv run python scripts/he/he1_plan.py freeze configs/runplans/he/he-1.yaml \
        --signed-by Hiếu --reason "..."
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import struct
import sys
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import yaml
from flywheel.contracts.entities import Decision
from flywheel_psi0.trainer.recipe import Psi0Recipe
from flywheel_psi0.tray.demo_sets import DemoSets, ReleaseEpisode, nested_sets
from flywheel_psi0.tray.runplan import (
    TRAINING_NEUTRAL_OVERRIDES,
    Parent,
    Pin,
    PsiModel,
    Recipe,
    SeedRange,
    Stats,
    lock_path,
    plan_json,
    recipe_sha256,
    run_plan_id,
)
from pydantic import BaseModel, ConfigDict, Field

REPO = Path(__file__).resolve().parents[2]
HF = "https://huggingface.co"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HfFile(_Frozen):
    repo: str
    kind: Literal["datasets", "models"]
    revision: str = Field(min_length=40, max_length=40)
    path: str
    sha256: str = Field(min_length=64, max_length=64)  # Hugging Face LFS oid at the revision


class Dataset(HfFile):
    episodes_jsonl_sha256: str = Field(min_length=64, max_length=64)  # meta/episodes.jsonl
    n_episodes: int = Field(gt=0)  # episode_index runs 0 .. n_episodes - 1
    data_class: Literal["public", "internal", "restricted"]
    location: str


class DemoSetPins(_Frozen):
    file: str  # repo-relative
    salt: str
    exclude: list[int]  # episode indices left out of every set
    exclude_reason: str
    sizes: dict[str, int]
    hashes: dict[str, str]


class Variant(_Frozen):
    parent: str
    role: str
    optional: bool = False


class Point(_Frozen):
    variant: str
    demo_set: str
    seed: int
    phase: Literal["preliminary", "full"]


class EvalSet(HfFile):
    levels: list[int]  # dr-level-<k> folders of the zip that are used
    conditions_per_level: int = Field(gt=0)


class DevEvalSet(_Frozen):
    """Conditions drawn from the team's dev seeds by scripts/he/dev_eval_set.py."""

    generator: str  # repo-relative
    salt: str
    simple_commit: str = Field(min_length=40, max_length=40)  # whose DR drew the scenes
    seeds: SeedRange  # the same seeds at every level
    levels: list[int]
    conditions_sha256: str = Field(min_length=64, max_length=64)
    location: str


class Eval(_Frozen):
    cli: Literal["eval-decoupled-wbc"]
    # "pending" until S1-03 settles the eval mode; `freeze` refuses a pending field.
    sim_mode: Literal["mujoco", "mujoco_isaac", "pending"]
    clock: Literal["sim", "wall", "pending"]
    # A proposed mode or set size still waiting for a signature; `freeze` refuses it too.
    awaiting: str | None = None
    synchronous: bool
    main: DevEvalSet  # every HE number is read on this set
    authors_set: EvalSet  # secondary: baseline and the published numbers only
    passes: dict[Literal["preliminary", "full"], int]  # rollouts per condition


class Baseline(_Frozen):
    weights: HfFile
    note: str


class Interpretation(_Frozen):
    doc: str  # repo-relative
    min_n_levels: int = Field(ge=1)  # spec section 3: CI lower bound > 0 at >= this many N
    floor_pp: float = Field(gt=0)  # below this at every point nothing is compared


class PreliminaryTest(_Frozen):
    """The test the preliminary result is read with (he-1.md 6.2)."""

    method: Literal["fisher_exact_two_sided"]
    alpha: float = Field(gt=0, lt=1)
    conditions_per_arm: int = Field(gt=0)


class He1RunPlan(_Frozen):
    name: str
    purpose: Literal["he_grid"]
    story: str
    site_id: str
    task: dict[str, str]
    embodiment: str
    code: dict[str, Pin]
    psi_model: PsiModel
    parents: dict[str, Parent]
    dataset: Dataset
    demo_sets: DemoSetPins
    recipe: Recipe
    variants: dict[str, Variant]
    points: list[Point] = Field(min_length=1)
    eval: Eval
    baseline: Baseline
    metric: dict[str, str]
    stats: Stats
    preliminary_test: PreliminaryTest
    comparisons: list[dict[str, str]]
    interpretation: Interpretation
    pricebook: str

    @classmethod
    def load(cls, path: Path) -> He1RunPlan:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def eval_conditions(self) -> list[tuple[int, int]]:
        """(level, seed) of every main eval condition; the same for every point."""
        dev = self.eval.main
        seeds = range(dev.seeds.start, dev.seeds.stop)
        return [(level, seed) for level in dev.levels for seed in seeds]


def open_items(plan: He1RunPlan) -> list[str]:
    """Fields still waiting for a decision; a plan with any of them is not frozen."""
    pending = [name for name in ("sim_mode", "clock") if getattr(plan.eval, name) == "pending"]
    items = [f"eval.{name} is pending (S1-03)" for name in pending]
    if plan.eval.awaiting:
        items.append(f"eval awaits: {plan.eval.awaiting}")
    return items


def demo_sets_from_plan(plan: He1RunPlan) -> DemoSets:
    """The demo sets the plan implies: psi-data episodes keyed by episode_index."""
    excluded = set(plan.demo_sets.exclude)
    pool = [
        ReleaseEpisode(episode_index=i, seed=i)
        for i in range(plan.dataset.n_episodes)
        if i not in excluded
    ]
    release_id = f"psi-data@{plan.dataset.revision[:7]}:{plan.dataset.path}"
    return nested_sets(
        release_id, plan.dataset.sha256, pool, plan.demo_sets.sizes, salt=plan.demo_sets.salt
    )


def read_episode_indices(episodes_jsonl: Path) -> list[int]:
    rows = [json.loads(line) for line in episodes_jsonl.read_text(encoding="utf-8").splitlines()]
    return [int(r["episode_index"]) for r in rows]


def check(plan: He1RunPlan, repo: Path = REPO) -> list[str]:
    """Everything wrong between the plan and the files it names; empty when it holds."""
    problems: list[str] = []
    recipe = Psi0Recipe.load(repo / plan.recipe.file)
    if recipe.stage != 3:
        problems.append(f"{plan.recipe.file} is stage {recipe.stage}, not 3")
    if recipe_sha256(recipe) != plan.recipe.sha256:
        problems.append(f"{plan.recipe.file} hashes to {recipe_sha256(recipe)}")
    for key, value in plan.recipe.overrides.items():
        if key not in TRAINING_NEUTRAL_OVERRIDES:
            problems.append(f"override {key} changes training: every point runs the recipe as is")
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
        for hf_path, local in paired:
            if Path(hf_path).parent.name != Path(local).name:
                problems.append(f"parent {name}: {hf_path} is not {local} of the recipe")
        if not parent.clean_for_main_task:
            problems.append(f"parent {name} is not clean for the main task (Q0)")
    for name, variant in plan.variants.items():
        if variant.parent not in plan.parents:
            problems.append(f"variant {name}: parent {variant.parent} is not pinned")

    pins = plan.demo_sets
    if set(pins.sizes) != set(pins.hashes):
        problems.append("demo_sets.sizes and demo_sets.hashes name different sets")
    bad = [i for i in pins.exclude if not 0 <= i < plan.dataset.n_episodes]
    if bad:
        problems.append(f"excluded episodes {bad} are not in the dataset")
    try:
        expected = demo_sets_from_plan(plan)
    except ValueError as error:
        problems.append(f"demo sets: {error}")
    else:
        recorded = DemoSets.model_validate_json((repo / pins.file).read_text(encoding="utf-8"))
        if recorded != expected:
            problems.append(f"{pins.file} is not the sets the plan implies: rerun `sets`")
        for name, pinned in pins.hashes.items():
            got = expected.sets.get(name)
            if got is None or got.set_hash != pinned:
                problems.append(f"demo set {name}: plan pins {pinned}, plan implies {got}")
        ordered = sorted(expected.sets.values(), key=lambda s: s.n)
        for small, large in zip(ordered, ordered[1:]):
            if not set(small.seeds) <= set(large.seeds):
                problems.append(f"demo set of {small.n} is not inside the set of {large.n}")

    seen: set[tuple[str, str, int]] = set()
    for point in plan.points:
        point_key = (point.variant, point.demo_set, point.seed)
        if point_key in seen:
            problems.append(f"point {point_key} is listed twice")
        seen.add(point_key)
        if point.variant not in plan.variants:
            problems.append(f"point {point_key}: unknown variant")
        if point.demo_set not in pins.hashes:
            problems.append(f"point {point_key}: demo set is not pinned")
        if point.phase not in plan.eval.passes:
            problems.append(f"point {point_key}: no eval passes for phase {point.phase}")
    for comparison in plan.comparisons:
        for side in (comparison["a"], comparison["b"]):
            if side not in plan.variants:
                problems.append(f"comparison names unknown variant {side}")
    main = plan.eval.main
    if not main.levels or not plan.eval.authors_set.levels:
        problems.append("an eval set uses no level")
    if not (repo / main.generator).is_file():
        problems.append(f"{main.generator} is missing")
    per_arm = len(plan.eval_conditions()) * plan.eval.passes["preliminary"]
    if plan.preliminary_test.conditions_per_arm != per_arm:
        problems.append(
            f"preliminary_test reads {plan.preliminary_test.conditions_per_arm} per arm, "
            f"the main eval gives {per_arm}"
        )
    split = yaml.safe_load((repo / "configs/splits/default.yaml").read_text(encoding="utf-8"))
    dev = split["seed_ranges"]["dev"]
    if not dev["start"] <= main.seeds.start < main.seeds.stop <= dev["stop"]:
        problems.append(f"eval seeds [{main.seeds.start}, {main.seeds.stop}) leave the dev range")
    return problems


def check_lock(plan: He1RunPlan, plan_path: Path) -> list[str]:
    lock = lock_path(plan_path)
    if not lock.is_file():
        return []
    frozen = json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"]
    if frozen != run_plan_id(plan):
        return [f"{plan_path} changed since it was frozen as {frozen}: write a new plan"]
    return []


def _hf_tree(f: HfFile) -> dict[str, Any]:
    folder, _, name = f.path.rpartition("/")
    url = f"{HF}/api/{f.kind}/{f.repo}/tree/{f.revision}/{folder}?expand=true"
    with urllib.request.urlopen(url, timeout=60) as response:
        listing = json.load(response)
    for entry in listing:
        if entry["path"] == f.path:
            return dict(entry)
    raise ValueError(f"{f.path} is not in {f.repo}@{f.revision[:7]}")


def _resolve(repo: str, kind: str, revision: str, path: str) -> str:
    prefix = "datasets/" if kind == "datasets" else ""
    return f"{HF}/{prefix}{repo}/resolve/{revision}/{path}"


def _get(url: str, first: int | None = None, last: int | None = None) -> bytes:
    headers = {} if first is None else {"Range": f"bytes={first}-{last}"}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return bytes(r.read())


def safetensors_header(url: str) -> dict[str, tuple[str, tuple[int, ...]]]:
    """Tensor name -> (dtype, shape), read from the header alone with two range requests."""
    (size,) = struct.unpack("<Q", _get(url, 0, 7))
    header = json.loads(_get(url, 8, 7 + size))
    header.pop("__metadata__", None)
    return {k: (v["dtype"], tuple(v["shape"])) for k, v in header.items()}


def check_parents(plan: He1RunPlan) -> dict[str, Any]:
    """LFS sha256 of every pinned file at its revision, and whether the parents load alike."""
    rev = plan.psi_model.revision
    files: list[tuple[str, HfFile]] = [
        ("dataset", plan.dataset),
        ("authors_eval_set", plan.eval.authors_set),
        ("baseline", plan.baseline.weights),
    ]
    for name, parent in plan.parents.items():
        for part, weights in (("vlm", parent.vlm), ("action_header", parent.action_header)):
            pinned = HfFile(
                repo=plan.psi_model.repo,
                kind="models",
                revision=rev,
                path=weights.path,
                sha256=weights.sha256,
            )
            files.append((f"{name}.{part}", pinned))
    report: dict[str, Any] = {"files": {}, "problems": []}
    for label, f in files:
        entry = _hf_tree(f)
        oid = (entry.get("lfs") or {}).get("oid")
        report["files"][label] = {"path": f.path, "size": entry.get("size"), "lfs_oid": oid}
        if oid != f.sha256:
            report["problems"].append(f"{label}: Hugging Face has {oid}, plan pins {f.sha256}")

    layouts: dict[str, dict[str, str]] = {}
    for name, parent in plan.parents.items():
        url = _resolve(plan.psi_model.repo, "models", rev, parent.vlm.path)
        vlm = safetensors_header(url)
        head = safetensors_header(
            _resolve(plan.psi_model.repo, "models", rev, parent.action_header.path)
        )
        config = _get(
            _resolve(
                plan.psi_model.repo, "models", rev, f"{Path(parent.vlm.path).parent}/config.json"
            )
        )
        layouts[name] = {
            "vlm_tensors": str(len(vlm)),
            "vlm_layout": hashlib.sha256(json.dumps(sorted(vlm.items())).encode()).hexdigest(),
            "action_header_tensors": str(len(head)),
            "action_header_layout": hashlib.sha256(
                json.dumps(sorted(head.items())).encode()
            ).hexdigest(),
            "config_json": hashlib.sha256(config).hexdigest(),
        }
    report["layouts"] = layouts
    first = next(iter(layouts.values()))
    for name, layout in layouts.items():
        if layout != first:
            report["problems"].append(f"parent {name} has another tensor layout or config")
    return report


def freeze(plan_path: Path, signed_by: str, reason: str, repo: Path = REPO) -> tuple[Path, Path]:
    """Write `<plan>.lock.json` and the signing `Decision` (kind plan_review) beside the plan.

    Nothing is written unless both files can be: the Decision is built first."""
    plan_path, repo = plan_path.resolve(), repo.resolve()
    plan = He1RunPlan.load(plan_path)
    problems = check(plan, repo) + open_items(plan)
    if not (repo / plan.interpretation.doc).is_file():
        problems.append(f"{plan.interpretation.doc} is missing: fix the reading rules first")
    if lock_path(plan_path).is_file():
        problems.append(f"{lock_path(plan_path)} exists: a frozen plan is not frozen again")
    if problems:
        raise ValueError("; ".join(problems))
    plan_id = run_plan_id(plan)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    lock = {"run_plan_id": plan_id, "frozen_at": now, "plan": plan_json(plan)}
    decision = Decision(
        kind="plan_review",
        subject_kind="run_plan",
        subject_id=plan_id,
        verdict="approved",
        signed_by=signed_by,
        reason=reason,
        task_id=plan.task["id"],
        site_id=plan.site_id,
        embodiment_id=plan.embodiment,
        criteria={
            "doc": plan.interpretation.doc,
            "min_n_levels": plan.interpretation.min_n_levels,
            "floor_pp": plan.interpretation.floor_pp,
            "preliminary_test": plan.preliminary_test.model_dump(),
        },
        meta={"plan": str(plan_path.relative_to(repo)), "frozen_at": now},
    )
    out = lock_path(plan_path)
    out.write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    decision_path = plan_path.with_name(plan_path.name.removesuffix(".yaml") + ".plan_review.json")
    decision_path.write_text(decision.model_dump_json(indent=1) + "\n", encoding="utf-8")
    return out, decision_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    p_sets = sub.add_parser("sets", help="write or check the demo-set file of a plan")
    p_sets.add_argument("--plan", type=Path, required=True)
    p_sets.add_argument("--episodes", type=Path, required=True, help="meta/episodes.jsonl")
    target = p_sets.add_mutually_exclusive_group(required=True)
    target.add_argument("--out", type=Path)
    target.add_argument("--check", type=Path)
    for name in ("check", "parents"):
        sub.add_parser(name).add_argument("plan", type=Path)
    p_freeze = sub.add_parser("freeze")
    p_freeze.add_argument("plan", type=Path)
    p_freeze.add_argument("--signed-by", required=True)
    p_freeze.add_argument("--reason", required=True)
    args = parser.parse_args(argv)

    if args.action == "sets":
        raw = yaml.safe_load(args.plan.read_text(encoding="utf-8"))
        plan_dataset = Dataset.model_validate(raw["dataset"])
        pins = DemoSetPins.model_validate(raw["demo_sets"])
        actual = hashlib.sha256(args.episodes.read_bytes()).hexdigest()
        if actual != plan_dataset.episodes_jsonl_sha256:
            print(f"{args.episodes} is not the pinned episodes.jsonl ({actual})", file=sys.stderr)
            return 1
        if read_episode_indices(args.episodes) != list(range(plan_dataset.n_episodes)):
            print(f"episode_index of {args.episodes} is not 0..{plan_dataset.n_episodes - 1}")
            return 1
        # Only dataset and demo_sets are read: hashes may still be placeholders.
        partial = He1RunPlan.model_construct(dataset=plan_dataset, demo_sets=pins)
        sets = demo_sets_from_plan(partial)
        text = sets.model_dump_json(indent=1) + "\n"
        if args.out is not None:
            args.out.write_text(text, encoding="utf-8")
            print(
                f"wrote {args.out}: " + ", ".join(f"{k}={v.set_hash}" for k, v in sets.sets.items())
            )
            return 0
        same = DemoSets.model_validate_json(args.check.read_text(encoding="utf-8")) == sets
        print(f"{args.check} {'matches' if same else 'differs from'} {args.episodes}")
        return 0 if same else 1
    if args.action == "freeze":
        lock, decision = freeze(args.plan, args.signed_by, args.reason)
        print(f"wrote {lock}: {json.loads(lock.read_text())['run_plan_id']}; {decision}")
        return 0
    plan = He1RunPlan.load(args.plan)
    if args.action == "parents":
        report = check_parents(plan)
        print(json.dumps(report, indent=1))
        return 1 if report["problems"] else 0
    problems = check(plan) + check_lock(plan, args.plan)
    for problem in problems:
        print(problem, file=sys.stderr)
    for item in open_items(plan):
        print(f"open: {item}")
    if not problems:
        preliminary = sum(p.phase == "preliminary" for p in plan.points)
        print(
            f"{args.plan}: {run_plan_id(plan)}, {len(plan.points)} points "
            f"({preliminary} preliminary), {len(plan.eval_conditions())} eval conditions"
        )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

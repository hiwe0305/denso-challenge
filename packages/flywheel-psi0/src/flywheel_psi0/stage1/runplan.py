"""The RunPlan of the short stage 1 run and its two pass criteria (DA-30 AC 1).

`configs/runplans/stage1/egodex-short.yaml` names the recipe, the parent `pre.*`
checkpoint, the dataset, the job and the overrides, and fixes before the run how it
is read:

* `loss_decreased`: the median train loss of the last `loss_window` lines is below
  that of the first `loss_window` (one batch per line, so a median over a window,
  not two single steps);
* `first_loss_matches`: a rerun of the first steps under another job id with the
  same seed starts at the same loss within `first_loss_rtol` (the story's test).

`run_plan_id` is computed as for the tray plans (`rp_` + sha256 of the plan's JSON).

    python -m flywheel_psi0.stage1.runplan check configs/runplans/stage1/egodex-short.yaml
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from flywheel_psi0.trainer.recipe import ArgValue, Psi0Recipe
from flywheel_psi0.tray.runplan import Pin, PsiModel, Weights, run_plan_id

REPO = Path(__file__).resolve().parents[5]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Code(_Frozen):
    psi0: Pin


class Parent(_Frozen):
    id: str  # a key of the recipe's `parents`
    vlm: Weights


class Source(_Frozen):
    url: str
    bytes: int = Field(gt=0)
    etag: str


class Dataset(_Frozen):
    id: str
    source: Source
    episodes_per_task: int = Field(gt=0)
    split_dir: str  # where Psi0's EgoDexDataset looks for train episodes
    precompute: str  # the authors' script that adds `actions_48d`, relative to Psi0


class Job(_Frozen):
    id: str
    seed: int
    nproc_per_node: int = Field(default=1, gt=0)


class Compute(_Frozen):
    gpu: str
    max_compute_units: float = Field(gt=0)


class Criteria(_Frozen):
    loss_window: int = Field(gt=0)
    repeat_steps: int = Field(gt=0)
    first_loss_rtol: float = Field(gt=0)


class Stage1Plan(_Frozen):
    name: str
    story: str
    code: Code
    psi_model: PsiModel
    recipe: str  # path from the repo root
    parent: Parent
    dataset: Dataset
    job: Job
    overrides: dict[str, ArgValue]
    compute: Compute
    criteria: Criteria

    @classmethod
    def load(cls, path: Path) -> Stage1Plan:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def load_recipe(self, repo: Path = REPO) -> Psi0Recipe:
        return Psi0Recipe.load(repo / self.recipe).with_overrides(self.overrides)

    @property
    def repeat_job_id(self) -> str:
        return f"{self.job.id}-repeat"


def check(plan: Stage1Plan, repo: Path = REPO) -> list[str]:
    """What is wrong with the plan against the files it names; empty when it holds."""
    problems: list[str] = []
    if not (repo / plan.recipe).exists():
        return [f"recipe {plan.recipe} not found"]
    unknown = sorted(set(plan.overrides) - set(Psi0Recipe.load(repo / plan.recipe).args))
    if unknown:
        problems.append(f"overrides {unknown} are not args of the recipe")
    try:
        recipe = plan.load_recipe(repo)
    except ValueError as error:
        return [*problems, str(error)]
    parent = recipe.parents.get(plan.parent.id)
    if parent is None:
        problems.append(f"parent {plan.parent.id!r} is not in the recipe's parents")
    elif not plan.parent.vlm.path.startswith(
        parent.model_name_or_path.removeprefix("cache/checkpoints/") + "/"
    ):
        problems.append(
            f"parent path {plan.parent.vlm.path} is not under {parent.model_name_or_path}"
        )
    if recipe.int_arg("train.validation_steps", 0) != 0:
        problems.append("val is on, but the dataset is written to a train split only")
    steps = recipe.int_arg("train.max_training_steps", 0)
    if steps < 2 * plan.criteria.loss_window:
        problems.append(f"{steps} steps leave no room for two loss windows")
    if plan.criteria.repeat_steps >= steps:
        problems.append("the rerun must be shorter than the run")
    return problems


def train_losses(metrics: Path, attempt: int | None = None) -> list[float]:
    """Finite train losses in step order; the highest attempt wins for a repeated step."""
    by_step: dict[int, tuple[int, float]] = {}
    for line in metrics.read_text(encoding="utf-8").splitlines():
        record: dict[str, Any] = json.loads(line)
        if record["split"] != "train" or not isinstance(record["loss"], (int, float)):
            continue
        if attempt is not None and record["attempt"] != attempt:
            continue
        step, tried = int(record["step"]), int(record["attempt"])
        if step not in by_step or tried >= by_step[step][0]:
            by_step[step] = (tried, float(record["loss"]))
    return [loss for _, (_, loss) in sorted(by_step.items())]


def loss_decreased(losses: Sequence[float], window: int) -> dict[str, Any]:
    if len(losses) < 2 * window:
        return {"passed": False, "reason": f"{len(losses)} train lines, need {2 * window}"}
    first = statistics.median(losses[:window])
    last = statistics.median(losses[-window:])
    return {"passed": last < first, "first_median": first, "last_median": last, "window": window}


def first_loss_matches(run: Sequence[float], rerun: Sequence[float], rtol: float) -> dict[str, Any]:
    if not run or not rerun:
        return {"passed": False, "reason": "no train line in the run or the rerun"}
    gap = abs(run[0] - rerun[0])
    return {
        "passed": gap <= rtol * abs(run[0]),
        "run": run[0],
        "rerun": rerun[0],
        "relative_gap": gap / abs(run[0]) if run[0] else float("inf"),
        "rtol": rtol,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a stage 1 RunPlan.")
    parser.add_argument("command", choices=["check"])
    parser.add_argument("plan", type=Path)
    args = parser.parse_args(argv)
    plan = Stage1Plan.load(args.plan)
    problems = check(plan)
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"OK {run_plan_id(plan)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

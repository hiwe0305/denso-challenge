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

The plan's DeepSpeed config is a file of this repo, not of Psi0: the authors'
`zero3_offload.json` leaves `optimizer.params.betas` and `eps` at "auto", which the
pinned accelerate (1.7.0) does not fill for a `DummyOptim` (run 1, 4/11/2026,
docs/he/stage1.md 1.7). `deepspeed_problems` checks the file against the recipe.

    python -m flywheel_psi0.stage1.runplan check configs/runplans/stage1/egodex-short.yaml
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from flywheel_psi0.stage1.egodex_sample import masking_waived
from flywheel_psi0.trainer.recipe import ArgValue, Psi0Recipe
from flywheel_psi0.tray.runplan import Pin, PsiModel, Weights, run_plan_id

REPO = Path(__file__).resolve().parents[5]

# The "auto" entries accelerate 1.7.0 fills when Psi0 prepares a model with a
# `DummyOptim` and a `DummyScheduler` and sets `train_micro_batch_size_per_gpu` itself
# (`Accelerator._prepare_deepspeed`, `DeepSpeedPlugin.set_mixed_precision`). Any other
# "auto" stops `accelerator.prepare` with "not found in kwargs".
FILLED_BY_ACCELERATE = frozenset(
    {
        "fp16.enabled",
        "bf16.enabled",
        "gradient_accumulation_steps",
        "gradient_clipping",
        "train_batch_size",
        "train_micro_batch_size_per_gpu",
        "zero_optimization.reduce_bucket_size",
        "zero_optimization.stage3_prefetch_bucket_size",
        "zero_optimization.stage3_param_persistence_threshold",
        "zero_optimization.stage3_gather_16bit_weights_on_model_save",
        "optimizer.params.lr",
        "optimizer.params.weight_decay",
        "scheduler.params.warmup_min_lr",
        "scheduler.params.warmup_max_lr",
        "scheduler.params.warmup_num_steps",
        "scheduler.params.total_num_steps",
    }
)


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Code(_Frozen):
    psi0: Pin


class Parent(_Frozen):
    id: str  # a key of the recipe's `parents`
    vlm: Weights


class Source(_Frozen):
    name: str  # the egocentric source, e.g. "egodex"
    url: str
    bytes: int = Field(gt=0)
    etag: str


class Dataset(_Frozen):
    id: str
    source: Source
    episodes_per_task: int = Field(gt=0)
    split_dir: str  # where Psi0's EgoDexDataset looks for train episodes
    precompute: str  # the authors' script that adds `actions_48d`, relative to Psi0
    data_class: Literal["public", "internal", "restricted"]
    identity_masked: bool  # went through the pipeline's identity-masking step

    @model_validator(mode="after")
    def _masked_unless_waived(self) -> Dataset:
        if not self.identity_masked and not masking_waived(self.source.name, self.data_class):
            raise ValueError(
                f"{self.id}: egocentric video must pass identity masking first (CLAUDE.md); "
                f"the waiver covers only source 'egodex' with data_class 'public', "
                f"not {self.source.name!r} with {self.data_class!r}"
            )
        return self


class ExportSource(_Frozen):
    """A DA-18 export, pinned by its id and by the sha256 of `pack`'s tarball."""

    name: str  # who recorded it, e.g. "team-ego" for the team's own videos
    export_id: str = Field(pattern=r"^egx_[0-9a-f]{16}$")
    tarball: str  # under the Drive root (/content/drive/MyDrive on Colab)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(gt=0)
    samples: int = Field(gt=0)


class ExportDataset(_Frozen):
    """The team's export (`flywheel_psi0.stage1.export_source`); it carries `actions_48d`."""

    kind: Literal["export"]
    id: str
    source: ExportSource
    split_dir: str
    data_class: Literal["public", "internal", "restricted"]
    identity_masked: bool

    @model_validator(mode="after")
    def _masked(self) -> ExportDataset:
        # The EgoDex waiver of 4/11/2026 is for Apple's zip only; an export of any
        # source, the team's own video first, must have passed identity masking.
        if not self.identity_masked:
            raise ValueError(
                f"{self.id}: an export must pass identity masking first (CLAUDE.md); "
                "the EgoDex waiver covers only Apple's published sample"
            )
        return self


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
    dataset: Dataset | ExportDataset  # Apple's EgoDex sample, or a DA-18 export
    job: Job
    deepspeed_config: str  # path from the repo root; replaces the recipe's
    overrides: dict[str, ArgValue]
    compute: Compute
    criteria: Criteria

    @classmethod
    def load(cls, path: Path) -> Stage1Plan:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def overrides_at(self, repo: Path = REPO) -> dict[str, ArgValue]:
        """The overrides with the plan's DeepSpeed config as an absolute path in `repo`."""
        return {**self.overrides, "train.deepspeed_config": str(repo / self.deepspeed_config)}

    def load_recipe(self, repo: Path = REPO) -> Psi0Recipe:
        return Psi0Recipe.load(repo / self.recipe).with_overrides(self.overrides_at(repo))

    @property
    def repeat_job_id(self) -> str:
        return f"{self.job.id}-repeat"


def _leaves(config: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    leaves: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, dict):
            leaves.update(_leaves(value, f"{prefix}{key}."))
        else:
            leaves[f"{prefix}{key}"] = value
    return leaves


def _number(value: ArgValue | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def deepspeed_problems(config: dict[str, Any], recipe: Psi0Recipe) -> list[str]:
    """What in a DeepSpeed config would stop `accelerator.prepare` or change the recipe."""
    leaves = _leaves(config)
    problems = [
        f"{key} is 'auto' and accelerate 1.7.0 does not fill it"
        for key, value in leaves.items()
        if value == "auto" and key not in FILLED_BY_ACCELERATE
    ]
    # Set here, not by accelerate, so the file states what the optimizer runs with.
    params = config.get("optimizer", {}).get("params", {})
    problems += [f"optimizer.params.{key} is 'auto'" for key, v in params.items() if v == "auto"]
    expected: dict[str, ArgValue | None] = {
        "lr": recipe.args.get("train.learning_rate"),
        "eps": recipe.args.get("train.lr_scheduler_kwargs.eps"),
        "weight_decay": recipe.args.get("train.lr_scheduler_kwargs.weight_decay"),
    }
    for key, want in expected.items():
        have, wanted = _number(params.get(key)), _number(want)
        if have is None or wanted is None or not math.isclose(have, wanted):
            problems.append(
                f"optimizer.params.{key} is {params.get(key)!r}, the recipe has {want!r}"
            )
    betas = recipe.args.get("train.lr_scheduler_kwargs.betas")
    have_betas = params.get("betas")
    if (
        not isinstance(betas, list)
        or not isinstance(have_betas, list)
        or len(betas) != len(have_betas)
        or not all(math.isclose(float(a), float(b)) for a, b in zip(have_betas, betas, strict=True))
    ):
        problems.append(f"optimizer.params.betas is {have_betas!r}, the recipe has {betas!r}")
    # Psi0 groups the vision tower and the projector at their own lr. WarmupLR sets one
    # lr for every group and starts it at 0; WarmupCosineLR scales each group's own lr,
    # by 1.0 here. It must start at iteration -1: only then does DeepSpeed 0.17.1 set
    # `_last_lr` in __init__, and Psi0 reads `get_last_lr()` on every micro-step, before
    # the first scheduler step at the accumulation boundary. The price: lr 0 for the
    # first group's first update.
    scheduler = config.get("scheduler", {})
    sparams = scheduler.get("params", {})
    if recipe.args.get("train.lr_scheduler_type") == "constant" and (
        scheduler.get("type") != "WarmupCosineLR"
        or sparams.get("warmup_min_ratio") != 1.0
        or sparams.get("cos_min_ratio") != 1.0
        or sparams.get("last_batch_iteration", -1) != -1
    ):
        problems.append(
            "the recipe's lr is constant per group: scheduler must be WarmupCosineLR "
            "with warmup_min_ratio and cos_min_ratio 1.0, from last_batch_iteration -1"
        )
    # Psi0 does not clip under DeepSpeed (pretrain.py:246); the config's clip is the only one.
    clip, max_norm = (
        _number(config.get("gradient_clipping")),
        _number(recipe.args.get("train.max_grad_norm")),
    )
    if clip is None or max_norm is None or not math.isclose(clip, max_norm):
        problems.append(
            f"gradient_clipping is {config.get('gradient_clipping')!r}, "
            f"the recipe's max_grad_norm is {recipe.args.get('train.max_grad_norm')!r}"
        )
    return problems


def check(plan: Stage1Plan, repo: Path = REPO) -> list[str]:
    """What is wrong with the plan against the files it names; empty when it holds."""
    problems: list[str] = []
    if not (repo / plan.recipe).exists():
        return [f"recipe {plan.recipe} not found"]
    unknown = sorted(set(plan.overrides) - set(Psi0Recipe.load(repo / plan.recipe).args))
    if unknown:
        problems.append(f"overrides {unknown} are not args of the recipe")
    if "train.deepspeed_config" in plan.overrides:
        problems.append("set the DeepSpeed config by `deepspeed_config`, not in overrides")
    if not (repo / plan.deepspeed_config).exists():
        return [*problems, f"deepspeed_config {plan.deepspeed_config} not found"]
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
    config = json.loads((repo / plan.deepspeed_config).read_text(encoding="utf-8"))
    problems += [f"{plan.deepspeed_config}: {p}" for p in deepspeed_problems(config, recipe)]
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

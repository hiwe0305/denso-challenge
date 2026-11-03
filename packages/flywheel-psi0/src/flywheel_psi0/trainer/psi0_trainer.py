"""`TrainerAdapter` for Psi0: run the author's `scripts/train.py` for one stage (DA-19 AC 2).

The recipe (`configs/models/psi0-stage{1,2,3}.yaml`) holds the author's args; the
TrainSpec picks the dataset, the parent checkpoint and the seed. `train` writes a
`launch.json`, starts `torchrun -m flywheel_psi0.trainer.launch` from the Psi0 repo
root in Psi0's own Python environment, and reads back what the launcher reported.

Job directory (03 section 7, `runs/<run_plan_id>/<job_id>/`):

    metrics.jsonl   one TrainingMetric per line, appended across attempts
    launch.json     what the launcher was given
    result.json     where Psi0 wrote its run and last checkpoint, and how it ended
    psi0/           Psi0's `--train.output_dir`; checkpoints under its run folder

Rerunning `train` with the same TrainSpec resumes: the timestamp is derived from the
job id, so Psi0 finds its own run folder, and the next attempt number is read from
`metrics.jsonl`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import numpy as np
from flywheel.contracts import (
    AdapterInfo,
    CheckpointRef,
    DatasetRef,
    MixSpec,
    ReleaseManifest,
    ResourceEstimate,
    ResourceUsage,
    TrainResult,
    TrainSpec,
)
from flywheel.contracts.artifacts import ActionLayout

from flywheel_psi0.trainer.launch import LaunchResult, LaunchSpec
from flywheel_psi0.trainer.recipe import ArgValue, Psi0Recipe
from flywheel_psi0.trainer.val_stats import HAND_GROUP, normalised_open_pose

Runner = Callable[[Sequence[str], Path, Mapping[str, str]], int]


def run_subprocess(command: Sequence[str], cwd: Path, env: Mapping[str, str]) -> int:
    return subprocess.run(list(command), cwd=cwd, env=dict(env), check=False).returncode


def _src_dir(module: str) -> str:
    """The `src/` directory a workspace package is imported from."""
    spec = importlib.util.find_spec(module)
    assert spec is not None and spec.submodule_search_locations is not None
    package_dir = Path(next(iter(spec.submodule_search_locations)))
    return str(package_dir.parents[module.count(".")])


class Psi0Trainer:
    """Train one Psi0 stage per TrainSpec with the author's code, unmodified."""

    def __init__(
        self,
        recipe: Psi0Recipe,
        psi0_root: Path,
        runs_root: Path,
        layout: ActionLayout,
        run_plan_id: str,
        release_id: str,
        psi0_commit: str,
        nproc_per_node: int = 1,
        overrides: Mapping[str, ArgValue] | None = None,
        python_bin: Path | None = None,
        runner: Runner = run_subprocess,
    ) -> None:
        self.recipe = recipe.with_overrides(overrides or {})
        self.psi0_root = psi0_root
        self.runs_root = runs_root
        self.layout = layout
        self.run_plan_id = run_plan_id
        self.release_id = release_id
        self.psi0_commit = psi0_commit
        self.nproc_per_node = nproc_per_node
        self.python_bin = python_bin or psi0_root / ".venv-psi" / "bin"
        self._runner = runner

    def info(self) -> AdapterInfo:
        return AdapterInfo(
            name=f"psi0-stage{self.recipe.stage}",
            version=self.psi0_commit,
            nondeterminism=("cuda", "dataloader_workers"),
        )

    def export_dataset(self, release: ReleaseManifest, mix: MixSpec, out_uri: str) -> DatasetRef:
        raise NotImplementedError("LeRobot v2.1 export is DA-02 (flywheel-data/export)")

    def estimate(self, spec: TrainSpec) -> ResourceEstimate:
        steps = self.recipe.int_arg("train.max_training_steps", 0)
        seconds = steps * self.recipe.estimate.seconds_per_step
        return ResourceEstimate(wall_seconds=seconds, gpu_seconds=seconds * self.nproc_per_node)

    # The pieces of `train`, public so a RunPlan can be checked without a GPU.

    def job_dir(self, spec: TrainSpec) -> Path:
        return self.runs_root / spec.job_id

    def checkpoint_id(self, spec: TrainSpec) -> str:
        return f"psi0-s{self.recipe.stage}-{spec.job_id}-s{spec.seed}"

    def global_batch_size(self) -> int:
        return (
            self.recipe.int_arg("train.train_batch_size", 16)
            * self.recipe.int_arg("train.gradient_accumulation_steps", 1)
            * self.nproc_per_node
        )

    def psi0_argv(self, spec: TrainSpec) -> list[str]:
        parent = self.recipe.parents.get(spec.parent.checkpoint_id)
        if parent is None:
            known = sorted(self.recipe.parents)
            raise KeyError(f"parent {spec.parent.checkpoint_id!r} not in the recipe: {known}")
        dataset = Path(spec.dataset.uri)
        fill = {
            "exp": f"fw-{spec.job_id}",
            "seed": str(spec.seed),
            # Psi0 resumes the run folder whose name ends in ".<timestamp>": no dots.
            "timestamp": re.sub(r"[^A-Za-z0-9_-]", "-", spec.job_id),
            "output_dir": str((self.job_dir(spec) / "psi0").resolve()),
            "dataset_root": str(dataset.parent.resolve()),
            "dataset_name": dataset.name,
            "vlm": parent.model_name_or_path,
            "action_header": parent.pretrained_action_header_path or "",
        }
        return self.recipe.argv(fill)

    def command(self) -> list[str]:
        return [
            str(self.python_bin / "torchrun"),
            f"--nproc_per_node={self.nproc_per_node}",
            "-m",
            "flywheel_psi0.trainer.launch",
        ]

    def environment(self) -> dict[str, str]:
        paths = [_src_dir("flywheel_psi0"), _src_dir("flywheel.contracts")]
        existing = os.environ.get("PYTHONPATH")
        return {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                [*dict.fromkeys(paths), *([existing] if existing else [])]
            ),
            "WANDB_MODE": "offline",
        }

    def next_attempt(self, spec: TrainSpec) -> int:
        metrics = self.job_dir(spec) / "metrics.jsonl"
        if not metrics.exists():
            return 0
        attempts = [json.loads(line)["attempt"] for line in metrics.read_text().splitlines()]
        return max(attempts, default=-1) + 1

    def hand_open_pose(self, spec: TrainSpec) -> list[float] | None:
        """The open hand in normalised units, from the dataset's `stats_psi0.json`."""
        stats_path = Path(spec.dataset.uri) / "meta" / "stats_psi0.json"
        hand = [i for i, d in enumerate(self.layout.dimensions) if d.group == HAND_GROUP]
        if not hand or not stats_path.exists():
            return None
        action = json.loads(stats_path.read_text(encoding="utf-8"))["action"]
        low, high = np.asarray(action["min"])[hand], np.asarray(action["max"])[hand]
        return [float(value) for value in normalised_open_pose(low, high)]

    def launch_spec(self, spec: TrainSpec) -> LaunchSpec:
        job_dir = self.job_dir(spec)
        return LaunchSpec(
            psi0_root=str(self.psi0_root.resolve()),
            trainer_module=self.recipe.trainer_module,
            argv=self.psi0_argv(spec),
            metrics_path=str((job_dir / "metrics.jsonl").resolve()),
            result_path=str((job_dir / "result.json").resolve()),
            identity={
                "run_plan_id": self.run_plan_id,
                "job_id": spec.job_id,
                "checkpoint_id": self.checkpoint_id(spec),
                "release_id": self.release_id,
                "attempt": self.next_attempt(spec),
                "vlm_frozen": self.recipe.vlm_frozen,
            },
            layout=self.layout,
            hand_open_pose=self.hand_open_pose(spec),
            global_batch_size=self.global_batch_size(),
        )

    def train(self, spec: TrainSpec) -> TrainResult:
        if not (self.psi0_root / ".env").exists():
            # scripts/train.py starts with `assert load_dotenv()`.
            raise FileNotFoundError(f"{self.psi0_root}/.env missing: cp .env.sample .env")
        job_dir = self.job_dir(spec)
        job_dir.mkdir(parents=True, exist_ok=True)
        launch_path = job_dir / "launch.json"
        launch_path.write_text(self.launch_spec(spec).model_dump_json(indent=2), encoding="utf-8")
        result_path = job_dir / "result.json"
        result_path.unlink(missing_ok=True)

        start = time.monotonic()
        returncode = self._runner(
            [*self.command(), str(launch_path.resolve())], self.psi0_root, self.environment()
        )
        wall = time.monotonic() - start

        result = (
            LaunchResult.model_validate_json(result_path.read_text(encoding="utf-8"))
            if result_path.exists()
            else LaunchResult(status="policy_error", error=f"no result.json, exit {returncode}")
        )
        ok = returncode == 0 and result.status == "ok" and result.checkpoint_dir is not None
        status = "ok" if ok else (result.status if result.status != "ok" else "policy_error")
        return TrainResult(
            job_id=spec.job_id,
            checkpoint=CheckpointRef(checkpoint_id=self.checkpoint_id(spec)) if ok else None,
            infra_status=status,
            usage=ResourceUsage(wall_seconds=wall, gpu_seconds=wall * self.nproc_per_node),
        )

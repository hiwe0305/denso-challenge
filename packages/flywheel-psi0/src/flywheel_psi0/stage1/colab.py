"""Run the stage 1 RunPlan on a Colab VM (DA-30 AC 1).

Uploaded with the flywheel sources and the plan, run on the VM in phases, each timed
into `<work>/report.json` (the `Report` of DA-19's driver) for the cost ledger
docs/g0/ledger/DA-30.csv:

    python3 -m flywheel_psi0.stage1.colab setup   --work /content/da30 --plan <plan>
    .venv-psi/bin/python -m flywheel_psi0.stage1.colab run    --work /content/da30 --plan <plan>
    .venv-psi/bin/python -m flywheel_psi0.stage1.colab repeat --work /content/da30 --plan <plan>
    python3 -m flywheel_psi0.stage1.colab persist --work /content/da30 --plan <plan>

`setup` builds Psi0's environment with DA-19's `setup` (which also fetches the stage 3
parents and the two-table data: a few minutes not needed here, kept to reuse it as
is), tries the plan's DeepSpeed config on a tiny model (`flywheel_psi0.stage1.preflight`:
CPU Adam build, `accelerator.prepare`, two steps) so a config the pinned accelerate
refuses fails in a minute instead of after the model load, downloads the plan's
`pre.*` parent at the pinned revision, fetches the EgoDex stand-in and runs the
authors' `actions_48d` script on it. `run` trains the plan's
job; `repeat` reruns its first steps under another job id and checks the first loss;
`persist` copies logs and metrics (not the weights) to Google Drive.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from flywheel_psi0.stage1.egodex_sample import fetch, layout_problems
from flywheel_psi0.trainer.colab import Report, sh
from flywheel_psi0.trainer.colab import setup as setup_psi0_env
from flywheel_psi0.trainer.psi0_trainer import _src_dir

DRIVE = Path("/content/drive/MyDrive/denso/da30")


def _plan(path: Path) -> Any:
    from flywheel_psi0.stage1.runplan import Stage1Plan

    return Stage1Plan.load(path)


def preflight_command(plan: Any, psi0: Path, repo: Path) -> str:
    """The pre-flight's torchrun line, with the recipe's optimizer and batch values."""
    recipe = plan.load_recipe(repo)
    arg = recipe.args.get
    betas = " ".join(str(b) for b in arg("train.lr_scheduler_kwargs.betas"))
    return (
        f"{psi0}/.venv-psi/bin/torchrun --nproc_per_node=1 -m flywheel_psi0.stage1.preflight "
        f"{repo / plan.deepspeed_config} --lr {arg('train.learning_rate')} --betas {betas} "
        f"--eps {arg('train.lr_scheduler_kwargs.eps')} "
        f"--weight-decay {arg('train.lr_scheduler_kwargs.weight_decay')} "
        f"--micro-batch {recipe.int_arg('train.train_batch_size', 0)} "
        f"--accumulation {recipe.int_arg('train.gradient_accumulation_steps', 1)} "
        f"--precision {arg('train.mixed_precision')} "
        f"--total-steps {recipe.int_arg('train.max_training_steps', 0)}"
    )


def preflight_env() -> dict[str, str]:
    """PYTHONPATH with the flywheel sources as absolute paths, as `Psi0Trainer.environment`."""
    paths = [_src_dir("flywheel_psi0"), _src_dir("flywheel.contracts")]
    existing = os.environ.get("PYTHONPATH")
    return {
        "PYTHONPATH": os.pathsep.join([*dict.fromkeys(paths), *([existing] if existing else [])])
    }


def setup(work: Path, plan_path: Path) -> None:
    import yaml

    plan = _plan(plan_path)  # validates first: unmasked video only under the EgoDex waiver
    raw = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    setup_psi0_env(work)
    psi0 = work / "Psi0"
    start = time.monotonic()
    try:
        sh(preflight_command(plan, psi0, work / "fw"), cwd=psi0, env=preflight_env())
    except subprocess.CalledProcessError as error:
        Report(work).phase("preflight", time.monotonic() - start, error=str(error))
        raise
    Report(work).phase("preflight", time.monotonic() - start)
    start = time.monotonic()
    parent_dir = raw["parent"]["vlm"]["path"].rsplit("/", 1)[0]
    sh(
        f'{psi0}/.venv-psi/bin/python -c "from huggingface_hub import snapshot_download; '
        f"snapshot_download('{raw['psi_model']['repo']}', repo_type='model', "
        f"revision='{raw['psi_model']['revision']}', allow_patterns=['{parent_dir}/*'], "
        f"local_dir='{psi0}/cache/checkpoints')\""
    )
    parent_seconds = time.monotonic() - start

    start = time.monotonic()
    dataset, root = raw["dataset"], work / "data" / "egodex"
    manifest = fetch(
        dataset["source"]["url"],
        root,
        dataset["split_dir"],
        int(dataset["episodes_per_task"]),
        dataset["source"]["etag"],
    )
    fetch_seconds = time.monotonic() - start

    start = time.monotonic()
    sh(
        f".venv-psi/bin/python {dataset['precompute']} --data_root {root} "
        f"--num_processes {os.cpu_count() or 4}",
        cwd=psi0,
    )
    problems = layout_problems(root, dataset["split_dir"])
    Report(work).phase(
        "setup_stage1",
        parent_seconds + fetch_seconds + time.monotonic() - start,
        parent_seconds=round(parent_seconds, 1),
        fetch_seconds=round(fetch_seconds, 1),
        precompute_seconds=round(time.monotonic() - start, 1),
        episodes=manifest["episodes"],
        tasks=manifest["tasks"],
        gigabytes=round(manifest["bytes"] / 1e9, 2),
        layout_problems=problems,
    )
    if problems:
        raise SystemExit("\n".join(problems))


def logging_runner(log_path: Path) -> Any:
    """`run_subprocess` that also keeps the job's stdout and stderr in `log_path`."""

    def run(command: Sequence[str], cwd: Path, env: Mapping[str, str]) -> int:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            process = subprocess.Popen(
                list(command),
                cwd=cwd,
                env=dict(env),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
            return process.wait()

    return run


def train(work: Path, plan_path: Path, repeat: bool) -> None:
    from flywheel.contracts import CheckpointRef, DatasetRef, TrainSpec

    from flywheel_psi0.stage1.runplan import first_loss_matches, loss_decreased, train_losses
    from flywheel_psi0.stage1.trainer import Stage1Trainer, egodex_layout
    from flywheel_psi0.trainer import Psi0Recipe
    from flywheel_psi0.tray.runplan import run_plan_id

    plan = _plan(plan_path)
    repo = work / "fw"
    overrides = plan.overrides_at(repo)
    job_id = plan.job.id
    if repeat:
        job_id = plan.repeat_job_id
        overrides["train.max_training_steps"] = plan.criteria.repeat_steps
        overrides["train.checkpointing_steps"] = plan.criteria.repeat_steps
    runs = work / "runs"
    trainer = Stage1Trainer(
        Psi0Recipe.load(repo / plan.recipe),
        psi0_root=work / "Psi0",
        runs_root=runs,
        layout=egodex_layout(),
        run_plan_id=run_plan_id(plan),
        release_id=plan.dataset.id,
        psi0_commit=plan.code.psi0.commit,
        nproc_per_node=plan.job.nproc_per_node,
        overrides=overrides,
        runner=logging_runner(runs / job_id / "train.log"),
    )
    spec = TrainSpec(
        job_id=job_id,
        dataset=DatasetRef(dataset_id=plan.dataset.id, uri=str(work / "data" / "egodex")),
        parent=CheckpointRef(checkpoint_id=plan.parent.id),
        seed=plan.job.seed,
    )
    start = time.monotonic()
    result = trainer.train(spec)
    # No result.json when the launcher died before writing one; TrainResult says so.
    result_path = runs / job_id / "result.json"
    launched = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
    metrics = runs / job_id / "metrics.jsonl"
    lines = metrics.read_text(encoding="utf-8").splitlines() if metrics.exists() else []
    losses = train_losses(metrics) if lines else []
    vram = [r["vram_gb"] for r in map(json.loads, lines) if r.get("vram_gb") is not None]
    details: dict[str, Any] = {
        "run_plan_id": run_plan_id(plan),
        "job_id": job_id,
        "infra_status": result.infra_status,
        "error": launched.get("error"),
        "checkpoint_step": launched.get("checkpoint_step"),
        "train_lines": len(losses),
        "first_losses": losses[:5],
        "last_losses": losses[-5:],
        "peak_vram_gb": max(vram, default=None),
    }
    if repeat:
        run_losses = train_losses(runs / plan.job.id / "metrics.jsonl")
        details["first_loss"] = first_loss_matches(
            run_losses, losses, plan.criteria.first_loss_rtol
        )
    else:
        details["loss_decreased"] = loss_decreased(losses, plan.criteria.loss_window)
    Report(work).phase("repeat" if repeat else "run", time.monotonic() - start, **details)


def persist(work: Path, plan_path: Path, durable: Path) -> None:
    """Copy each job's logs and metrics, without Psi0's run folder, to `durable`."""
    plan = _plan(plan_path)
    start = time.monotonic()
    for job_id in (plan.job.id, plan.repeat_job_id):
        job_dir = work / "runs" / job_id
        if job_dir.exists():
            (durable / job_id).mkdir(parents=True, exist_ok=True)
            sh(f"rsync -a --exclude 'psi0/' {job_dir}/ {durable / job_id}/")
    for name in ("report.json", "data/egodex/manifest.json"):
        if (work / name).exists():
            sh(f"cp {work / name} {durable}/")
    Report(work).phase("persist", time.monotonic() - start, target=str(durable))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("phase", choices=["setup", "run", "repeat", "persist"])
    parser.add_argument("--work", type=Path, default=Path("/content/da30"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--to", type=Path, default=DRIVE, help="durable directory")
    args = parser.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)
    if args.phase == "setup":
        setup(args.work, args.plan)
    elif args.phase in ("run", "repeat"):
        train(args.work, args.plan, repeat=args.phase == "repeat")
    else:
        persist(args.work, args.plan, args.to)


if __name__ == "__main__":
    main()

"""Run the stage 1 RunPlan on a Colab VM (DA-30 AC 1).

Uploaded with the flywheel sources and the plan, run on the VM in phases, each timed
into `<work>/report.json` (the `Report` of DA-19's driver) for the cost ledger
docs/g0/ledger/DA-30.csv:

    python3 -m flywheel_psi0.stage1.colab setup   --work /content/da30 --plan <plan>
    .venv-psi/bin/python -m flywheel_psi0.stage1.colab run    --work /content/da30 --plan <plan>
    .venv-psi/bin/python -m flywheel_psi0.stage1.colab repeat --work /content/da30 --plan <plan>
    python3 -m flywheel_psi0.stage1.colab persist --work /content/da30 --plan <plan>
    .venv-psi/bin/python -m flywheel_psi0.stage1.colab check-vlm --work /content/da30 --plan <plan>

`setup` builds Psi0's environment with DA-19's `setup` (which also fetches the stage 3
parents and the two-table data: a few minutes not needed here, kept to reuse it as
is), installs the CUDA toolkit of torch's CUDA when the VM has another one
(`cuda_toolchain`; `run` gets the same CUDA_HOME and PATH), tries the plan's
DeepSpeed config on a tiny model (`flywheel_psi0.stage1.preflight`:
CPU Adam build, `accelerator.prepare`, two steps) so a config the pinned accelerate
refuses fails in a minute instead of after the model load, downloads the plan's
`pre.*` parent at the pinned revision, fetches the EgoDex stand-in and runs the
authors' `actions_48d` script on it. `run` trains the plan's
job; `repeat` reruns its first steps under another job id and checks the first loss;
`persist` copies logs and metrics to Google Drive, and the trained VLM when the plan
sets `persist_vlm`; `check-vlm` then loads that Drive copy as stage 3 does.
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

from flywheel_psi0.stage1.cuda_toolchain import match as match_cuda_toolchain
from flywheel_psi0.stage1.egodex_sample import fetch, layout_problems
from flywheel_psi0.stage1.export_source import STATS_FILE, sha256, stats_coverage
from flywheel_psi0.stage1.export_source import fetch as fetch_export
from flywheel_psi0.stage1.vlm_checkpoint import load_check
from flywheel_psi0.stage1.vlm_checkpoint import package as package_vlm
from flywheel_psi0.trainer.colab import Report, sh
from flywheel_psi0.trainer.colab import setup as setup_psi0_env
from flywheel_psi0.trainer.psi0_trainer import _src_dir

DRIVE_ROOT = Path("/content/drive/MyDrive")
DRIVE = DRIVE_ROOT / "denso" / "da30"
PLAN_POINTER = "plan.path"  # in the work dir, written by setup
CUDA_ENV = "cuda_env.json"  # in the work dir: setup's CUDA_HOME and PATH, applied by run


def _plan(path: Path) -> Any:
    from flywheel_psi0.stage1.runplan import Stage1Plan

    return Stage1Plan.load(path)


def draft_reasons(plan: Any) -> list[str]:
    from flywheel_psi0.stage1.runplan import draft_reasons as reasons

    return reasons(plan)


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


def preflight_plan_problems(plan: Any, drive_root: Path) -> list[str]:
    """What stops `setup` before anything is installed or downloaded (no GPU time spent).

    A draft or a placeholder pin; data that is not `public` (CLAUDE.md: internal and
    restricted data never go to a hosted service, Colab included); an export tarball
    that is not on Drive at the plan's path and size. Its sha256 is checked on the VM's
    copy, in `_setup_export`.
    """
    problems = [f"draft: {reason}" for reason in draft_reasons(plan)]
    if plan.status == "draft" and not problems:
        problems.append("the plan is marked `status: draft`")
    if plan.dataset.data_class != "public":
        problems.append(f"data_class {plan.dataset.data_class}: only public data goes to Colab")
    if getattr(plan.dataset, "kind", None) == "export" and not problems:
        tarball = drive_root / plan.dataset.source.tarball
        if not tarball.is_file():
            problems.append(f"{tarball} not found (mount Drive before setup)")
        elif tarball.stat().st_size != plan.dataset.source.bytes:
            size = tarball.stat().st_size
            problems.append(f"{tarball} is {size} bytes, the plan pins {plan.dataset.source.bytes}")
    return problems


def setup(work: Path, plan_path: Path, drive_root: Path = DRIVE_ROOT) -> None:
    import yaml

    plan = _plan(plan_path)  # validates first: unmasked video only under the EgoDex waiver
    refused = preflight_plan_problems(plan, drive_root)
    if refused:
        raise SystemExit(f"{plan_path} not run:\n" + "\n".join(f"- {p}" for p in refused))
    raw = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    # The watcher's persist cell reads this to know which plan the session runs.
    (work / PLAN_POINTER).write_text(str(plan_path.resolve()), encoding="utf-8")
    setup_psi0_env(work)
    psi0 = work / "Psi0"
    start = time.monotonic()
    # Before the pre-flight, whose CPU Adam build needs nvcc to match torch's CUDA.
    toolchain = match_cuda_toolchain(psi0 / ".venv-psi" / "bin", sh=sh)
    (work / CUDA_ENV).write_text(json.dumps(toolchain["env"], indent=2), encoding="utf-8")
    Report(work).phase("cuda_toolchain", time.monotonic() - start, **toolchain)
    start = time.monotonic()
    try:
        sh(
            preflight_command(plan, psi0, work / "fw"),
            cwd=psi0,
            env=preflight_env() | toolchain["env"],
        )
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
    check_parent(psi0, plan)
    parent_seconds = time.monotonic() - start

    root = work / "data" / "egodex"
    if raw["dataset"].get("kind") == "export":
        details = _setup_export(plan, root, drive_root)
        stat_path = plan.load_recipe(work / "fw").args["data.transform.field.stat-path"]
        details["stats_coverage"] = stats_coverage(
            json.loads((root / STATS_FILE).read_text(encoding="utf-8")),
            json.loads((psi0 / str(stat_path)).read_text(encoding="utf-8")),
        )
    else:
        details = _setup_egodex_sample(raw["dataset"], root, psi0)
    problems = layout_problems(root, plan.dataset.split_dir)
    Report(work).phase(
        "setup_stage1",
        parent_seconds + details.pop("seconds"),
        parent_seconds=round(parent_seconds, 1),
        **details,
        layout_problems=problems,
    )
    if problems:
        raise SystemExit("\n".join(problems))


def check_parent(psi0: Path, plan: Any) -> None:
    """Stop unless the downloaded parent weights are the ones the plan pins."""
    weights = psi0 / "cache" / "checkpoints" / plan.parent.vlm.path
    got = sha256(weights) if weights.is_file() else "missing"
    if got != plan.parent.vlm.sha256:
        raise SystemExit(f"{weights}: sha256 {got}, the plan pins {plan.parent.vlm.sha256}")


def _setup_egodex_sample(dataset: dict[str, Any], root: Path, psi0: Path) -> dict[str, Any]:
    """Fetch the EgoDex stand-in and add `actions_48d` with the authors' script."""
    start = time.monotonic()
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
    precompute_seconds = time.monotonic() - start
    return {
        "seconds": fetch_seconds + precompute_seconds,
        "fetch_seconds": round(fetch_seconds, 1),
        "precompute_seconds": round(precompute_seconds, 1),
        "episodes": manifest["episodes"],
        "tasks": manifest["tasks"],
        "gigabytes": round(manifest["bytes"] / 1e9, 2),
    }


def _setup_export(plan: Any, root: Path, drive_root: Path) -> dict[str, Any]:
    """Get the plan's export tarball from Drive, check it and unpack it at `root`.

    The export already holds `actions_48d` (DA-18 writes it), so no precompute.
    Refused, before any training, unless every check of `export_source.fetch` holds.
    """
    source = plan.dataset.source
    start = time.monotonic()
    got = fetch_export(
        drive_root / source.tarball,
        source.sha256,
        root,
        source.export_id,
        plan.dataset.split_dir,
        plan.dataset.data_class,
        source.samples,
    )
    seconds = time.monotonic() - start
    return {
        "seconds": seconds,
        "fetch_seconds": round(seconds, 1),
        "export_id": got["export_id"],
        "episodes": got["samples"],
        "frames": got["frames"],
        "gigabytes": round(got["bytes"] / 1e9, 2),
    }


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


def apply_cuda_env(work: Path) -> dict[str, str]:
    """Give this process, and the job it launches, the CUDA_HOME and PATH of `setup`.

    The job's DeepSpeed builds CPU Adam again, and `Psi0Trainer.environment` starts from
    `os.environ`. Empty when `setup` wrote none (a work dir from before 11/11/2026).
    """
    path = work / CUDA_ENV
    env: dict[str, str] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    os.environ.update(env)
    return env


def train(work: Path, plan_path: Path, repeat: bool) -> None:
    from flywheel.contracts import CheckpointRef, DatasetRef, TrainSpec

    from flywheel_psi0.stage1.runplan import first_loss_matches, loss_decreased, train_losses
    from flywheel_psi0.stage1.trainer import Stage1Trainer, egodex_layout
    from flywheel_psi0.trainer import Psi0Recipe
    from flywheel_psi0.tray.runplan import run_plan_id

    plan = _plan(plan_path)
    cuda_env = apply_cuda_env(work)
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
        "cuda_env": cuda_env,
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
    """Copy each job's logs and metrics, without Psi0's run folder, to `durable`.

    Logs go first, so they are kept even if the session stops while the weights copy.
    With the plan's `persist_vlm`, the run's last checkpoint then goes to
    `durable/<job_id>/vlm` in the layout stage 3 loads (`vlm_checkpoint.package`).
    """
    plan = _plan(plan_path)
    start = time.monotonic()
    for job_id in (plan.job.id, plan.repeat_job_id):
        job_dir = work / "runs" / job_id
        if job_dir.exists():
            (durable / job_id).mkdir(parents=True, exist_ok=True)
            sh(f"rsync -a --exclude 'psi0/' {job_dir}/ {durable / job_id}/")
    for name in ("report.json", "data/egodex/manifest.json", "data/egodex/meta.json"):
        if (work / name).exists():
            sh(f"cp {work / name} {durable}/")
    details: dict[str, Any] = {"target": str(durable)}
    if plan.persist_vlm:
        details["vlm"] = persist_vlm(work, plan, durable / plan.job.id / "vlm")
    Report(work).phase("persist", time.monotonic() - start, **details)


def persist_vlm(work: Path, plan: Any, out: Path) -> dict[str, Any]:
    """Package the main job's last checkpoint at `out`; what was done, for the report."""
    from flywheel_psi0.tray.runplan import run_plan_id

    result_path = work / "runs" / plan.job.id / "result.json"
    launched = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
    if not launched.get("checkpoint_dir"):
        return {"saved": False, "reason": "no checkpoint in result.json"}
    steps = plan.load_recipe(work / "fw").int_arg("train.max_training_steps", 0)
    parent_dir = work / "Psi0" / "cache" / "checkpoints" / plan.parent.vlm.path.rsplit("/", 1)[0]
    manifest = package_vlm(
        Path(launched["checkpoint_dir"]),
        parent_dir,
        out,
        {
            "run_plan_id": run_plan_id(plan),
            "job_id": plan.job.id,
            "step": launched.get("checkpoint_step"),
            "final": launched.get("checkpoint_step") == steps,
            "dataset_id": plan.dataset.id,
            "psi0_commit": plan.code.psi0.commit,
            "parent": {"id": plan.parent.id, **plan.parent.vlm.model_dump()},
            # Under MyDrive, as DA-34's B plan pins `drive_dir`.
            "drive_dir": out.relative_to(DRIVE_ROOT).as_posix()
            if out.is_relative_to(DRIVE_ROOT)
            else str(out),
        },
    )
    return {
        "saved": True,
        "path": str(out),
        "step": manifest["step"],
        "final": manifest["final"],
        "drive_dir": manifest["drive_dir"],
        "weights_sha256": manifest["weights_sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
        "header_problems": manifest["header_problems"],
    }


def check_vlm(work: Path, plan_path: Path, durable: Path) -> None:
    """Load the persisted VLM from Drive as stage 3 would; run in Psi0's environment."""
    plan = _plan(plan_path)
    start = time.monotonic()
    result = load_check(durable / plan.job.id / "vlm")
    Report(work).phase("check_vlm", time.monotonic() - start, **result)
    if result["problems"]:
        raise SystemExit("\n".join(result["problems"]))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("phase", choices=["setup", "run", "repeat", "persist", "check-vlm"])
    parser.add_argument("--work", type=Path, default=Path("/content/da30"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--to", type=Path, default=DRIVE, help="durable directory")
    parser.add_argument("--drive-root", type=Path, default=DRIVE_ROOT, help="where tarballs live")
    args = parser.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)
    if args.phase == "setup":
        setup(args.work, args.plan, args.drive_root)
    elif args.phase in ("run", "repeat"):
        train(args.work, args.plan, repeat=args.phase == "repeat")
    elif args.phase == "check-vlm":
        check_vlm(args.work, args.plan, args.to)
    else:
        persist(args.work, args.plan, args.to)


if __name__ == "__main__":
    main()

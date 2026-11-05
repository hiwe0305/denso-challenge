"""Fine-tune one HE-1 point on a Colab L4 (DA-26 tasks 2 and 3, AC 1 and 2).

One Colab session per point, one point per session. Uploaded with the repo and run
on the VM from an SSH shell, in phases timed into `<work>/report.json` (the `Report`
of DA-19's driver) for the measured rows of docs/g0/ledger/DA-26.csv:

    cd /content/da26
    python3 fw/scripts/he/he1_colab.py setup --point V-EGO/N20/0
    Psi0/.venv-psi/bin/python fw/scripts/he/he1_colab.py train --point V-EGO/N20/0
    python3 fw/scripts/he/he1_colab.py persist [--watch 600 --pid P]
    python3 fw/scripts/he/he1_colab.py restore --point V-EGO/N20/0  # on a fresh VM
    python3 fw/scripts/he/he1_colab.py stage   # JSON for scripts/he/he1_fetch.py

Every phase loads `configs/runplans/he/he-1.yaml` and refuses to go on unless it is
the frozen plan (`he-1.lock.json`, rp_95c98a476499) and the point is one of its
`preliminary` points: tier 2 (Hiếu, 4/11/2026) pays for those only.

`setup` builds Psi0's environment with the steps of DA-19's `setup` up to, not
including, its downloads (`install_env`: DA-19's downloads are the baseline parents
and psi-data's current zip, unpinned; on V-NOEGO about 6 GB never used, on the
meter). Then it downloads what the plan pins, at the plan's revisions: the point's
parent pair from psi-model and the two-table zip from psi-data. Each file's sha256
must equal the plan's (the parents' Hugging Face LFS oid, the zip's and its
`episodes.jsonl`'s), or setup stops before any training: that is the "download and
check on the training VM" of task 2. Last it cuts the
point's demo set (scripts/he/demo_subset.py) into `<work>/sets/<N>/<task>`.

`train` runs Psi0Trainer (DA-19) with the plan's recipe and overrides on that cut,
the point's parent and train seed. `persist` copies every job of `<work>/runs`
(metrics, results and complete checkpoints, the weights included since eval needs
them) to Google Drive; with `--watch S --pid P` it syncs every S seconds while the
training process lives. Drive is mounted from the laptop right after setup:
`colab drivemount -s <session> /content/drive`; `persist` refuses a target under
/content/drive that is not a mount, which would fill the VM disk instead.

Until Drive is mounted (it needs Hiếu's browser consent, DA-30 4/11/2026) the
durable copy is the laptop: `stage` prints, as JSON, what eval needs from each job
(every file outside `checkpoints/`, and the latest complete `ckpt_<step>` without
its optimizer state) with sizes and sha256, and scripts/he/he1_fetch.py pulls those
files over `colab ssh --proxy-mode` and checks them against it. `stage` also gives
the training progress (last step, seconds per step) the fetcher's early stop reads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
PLAN = REPO / "configs/runplans/he/he-1.yaml"
DRIVE = Path("/content/drive/MyDrive/denso/da26")
FROZEN = "rp_95c98a476499"  # he-1.lock.json, signed by Hiếu 4/11/2026 (tier 2)
TOTAL_STEPS = 40000  # recipe R1 train.max_training_steps, checked by the tests
for package in ("flywheel-psi0", "flywheel-contracts", "flywheel-data"):
    if str(REPO / "packages" / package / "src") not in sys.path:
        sys.path.insert(0, str(REPO / "packages" / package / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flywheel_psi0.trainer.colab import (  # noqa: E402
    FLASH_ATTN_WHEEL,
    PSI0_COMMIT,
    PSI0_REPO,
    Report,
    completed_checkpoints,
    lock_constraints,
    repair_lock,
    sh,
    sync_job,
)
from flywheel_psi0.tray.runplan import lock_path  # noqa: E402
from he1_plan import He1RunPlan, Point, check, check_lock  # noqa: E402


def load_point(text: str, plan_path: Path = PLAN) -> tuple[He1RunPlan, Point, str]:
    """The frozen plan, its preliminary point named `VARIANT/SET/SEED`, and its run_plan_id."""
    plan = He1RunPlan.load(plan_path)
    lock = lock_path(plan_path)
    problems = check(plan) + check_lock(plan, plan_path)
    if not lock.is_file():
        problems.append(f"{lock} missing: the plan is not frozen")
    if problems:
        raise SystemExit("plan does not hold:\n  " + "\n  ".join(problems))
    frozen = json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"]
    if frozen != FROZEN:
        raise SystemExit(f"{lock} holds {frozen}; tier 2 approved {FROZEN} only")
    variant, demo_set, seed = text.split("/")
    for point in plan.points:
        if (point.variant, point.demo_set, point.seed) == (variant, demo_set, int(seed)):
            if point.phase != "preliminary":
                raise SystemExit(
                    f"{text} is a {point.phase} point; tier 2 pays for preliminary only"
                )
            return plan, point, frozen
    raise SystemExit(f"{text} is not a point of {plan_path}")


def job_id(point: Point) -> str:
    """`da26-t2-ft-vego-n20-s0`: Colab session, Drive folder; ledger job_da26_t2_ft_vego_n20_s0."""
    variant = point.variant.lower().replace("-", "")
    return f"da26-t2-ft-{variant}-{point.demo_set.lower()}-s{point.seed}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_problems(expected: dict[Path, str]) -> list[str]:
    """Every file whose sha256 is not the pinned one (or that is missing)."""
    problems = []
    for path, pinned in expected.items():
        found = sha256(path) if path.is_file() else "missing"
        if found != pinned:
            problems.append(f"{path}: sha256 {found}, plan pins {pinned}")
    return problems


def dataset_dir(work: Path, plan: He1RunPlan, point: Point) -> Path:
    return work / "sets" / point.demo_set / plan.task["id"]


def install_env(work: Path) -> float:
    """DA-19 `setup`'s environment steps, the same commands, without its downloads."""
    start = time.monotonic()
    psi0 = work / "Psi0"
    if not (psi0 / ".git").exists():
        sh(f"git clone --filter=blob:none {PSI0_REPO} {psi0}")
    sh(f"git checkout -q {PSI0_COMMIT}", cwd=psi0)
    sh("pip install -q uv")
    if not (psi0 / ".venv-psi").exists():
        sh("env -u UV_SYSTEM_PYTHON uv venv .venv-psi --python 3.11", cwd=psi0)
    constraints = work / "psi0-constraints.txt"
    constraints.write_text(lock_constraints(repair_lock((psi0 / "uv.lock").read_text())))
    sh(
        f"env -u UV_SYSTEM_PYTHON uv pip install --python .venv-psi/bin/python "
        f"-e . --group psi -c {constraints}",
        cwd=psi0,
        env={"GIT_LFS_SKIP_SMUDGE": "1"},
    )
    sh(
        f"env -u UV_SYSTEM_PYTHON uv pip install --no-config "
        f"--python {psi0}/.venv-psi/bin/python --no-deps '{FLASH_ATTN_WHEEL}'",
        cwd=work,
    )
    (psi0 / ".env").write_text(
        f"HF_HOME={work}/hf\nTOKENIZERS_PARALLELISM=false\nWANDB_MODE=offline\n"
    )
    return time.monotonic() - start


def setup(work: Path, point_text: str) -> None:
    plan, point, _ = load_point(point_text)
    env_seconds = install_env(work)
    psi0, python = work / "Psi0", work / "Psi0" / ".venv-psi" / "bin" / "python"
    start = time.monotonic()
    parent = plan.parents[plan.variants[point.variant].parent]
    # whole folders: Psi0 loads each as a directory (config, tokenizer, weights)
    weights = [f"{w.path.rsplit('/', 1)[0]}/*" for w in (parent.vlm, parent.action_header)]
    data = plan.dataset
    downloads = [
        (
            plan.psi_model.repo,
            "model",
            plan.psi_model.revision,
            weights,
            psi0 / "cache/checkpoints",
        ),
        (data.repo, "dataset", data.revision, [data.path], work / "he-data"),
    ]
    for repo, kind, revision, patterns, target in downloads:
        sh(
            f'{python} -c "from huggingface_hub import snapshot_download; '
            f"snapshot_download('{repo}', repo_type='{kind}', revision='{revision}', "
            f"allow_patterns={patterns!r}, local_dir='{target}')\""
        )
    zip_path = work / "he-data" / data.path
    pinned = {
        psi0 / "cache/checkpoints" / parent.vlm.path: parent.vlm.sha256,
        psi0 / "cache/checkpoints" / parent.action_header.path: parent.action_header.sha256,
        zip_path: data.sha256,
    }
    problems = hash_problems(pinned)
    if problems:
        raise SystemExit("pinned files differ, no training:\n  " + "\n  ".join(problems))
    src = work / "he-data" / "src"
    sh(f"rm -rf {src} && mkdir -p {src} && unzip -q {zip_path} -d {src}")
    source = src / plan.task["id"]
    problems = hash_problems({source / "meta" / "episodes.jsonl": data.episodes_jsonl_sha256})
    if problems:
        raise SystemExit("pinned files differ, no training:\n  " + "\n  ".join(problems))
    download_seconds = time.monotonic() - start

    start = time.monotonic()
    out = dataset_dir(work, plan, point)
    sh(f"rm -rf {out}")  # a cut is never patched, only rebuilt from the checked zip
    pythonpath = ":".join(
        str(REPO / "packages" / p / "src")
        for p in ("flywheel-psi0", "flywheel-contracts", "flywheel-data")
    )
    sh(
        f"{python} {REPO}/scripts/he/demo_subset.py --src {source} "
        f"--sets {REPO / plan.demo_sets.file} --set {point.demo_set} --out {out}",
        env={"PYTHONPATH": pythonpath},
    )
    Report(work).phase(
        "setup_he1",
        env_seconds + download_seconds + time.monotonic() - start,
        point=point_text,
        job_id=job_id(point),
        env_seconds=round(env_seconds, 1),
        download_seconds=round(download_seconds, 1),
        sha256_checked={str(p.relative_to(work)): h for p, h in pinned.items()},
        demo_set_hash=plan.demo_sets.hashes[point.demo_set],
        dataset=str(out),
    )


def train(work: Path, point_text: str) -> None:
    from flywheel.contracts import CheckpointRef, DatasetRef, TrainSpec
    from flywheel.contracts.artifacts import ActionLayout
    from flywheel_psi0.trainer import Psi0Recipe, Psi0Trainer
    from flywheel_psi0.trainer.colab import g1_layout_json

    plan, point, run_plan = load_point(point_text)
    if plan.code["psi0"].commit != PSI0_COMMIT:
        raise SystemExit(f"plan pins Psi0 {plan.code['psi0'].commit}, DA-19 setup {PSI0_COMMIT}")
    data = dataset_dir(work, plan, point)
    marker = json.loads((data / "meta" / "flywheel_subset.json").read_text())
    if marker["set_hash"] != plan.demo_sets.hashes[point.demo_set]:
        raise SystemExit(f"{data} holds set {marker['set_hash']}, not the plan's {point.demo_set}")
    spec = TrainSpec(
        job_id=job_id(point),
        dataset=DatasetRef(dataset_id=f"{marker['release_id']}#{point.demo_set}", uri=str(data)),
        parent=CheckpointRef(checkpoint_id=plan.variants[point.variant].parent),
        seed=point.seed,
    )
    trainer = Psi0Trainer(
        Psi0Recipe.load(REPO / plan.recipe.file),
        psi0_root=work / "Psi0",
        runs_root=work / "runs",
        layout=ActionLayout.model_validate({"dimensions": g1_layout_json()}),
        run_plan_id=run_plan,
        release_id=f"{marker['release_id']}#{point.demo_set}:{marker['set_hash'][:12]}",
        psi0_commit=PSI0_COMMIT,
        nproc_per_node=plan.recipe.nproc_per_node,
        overrides=dict(plan.recipe.overrides),
    )
    start = time.monotonic()
    result = trainer.train(spec)
    launched = json.loads((work / "runs" / spec.job_id / "result.json").read_text())
    Report(work).phase(
        "train",
        time.monotonic() - start,
        point=point_text,
        job_id=spec.job_id,
        run_plan_id=run_plan,
        infra_status=result.infra_status,
        checkpoint_step=launched.get("checkpoint_step"),
        checkpoint_dir=launched.get("checkpoint_dir"),
        error=launched.get("error"),
        overrides=dict(plan.recipe.overrides),
    )
    if result.infra_status != "ok":
        raise SystemExit(f"train ended {result.infra_status}: {launched.get('error')}")


def unmounted_drive(durable: Path, mounted: Callable[[str], bool] = os.path.ismount) -> bool:
    """A target under /content/drive with no Drive mounted there: it would be VM disk."""
    return durable.is_relative_to("/content/drive") and not mounted("/content/drive")


def persist(work: Path, durable: Path, watch: float | None = None, pid: int | None = None) -> None:
    """Copy every job of `<work>/runs` to durable storage, as DA-19's `persist` does one."""
    if unmounted_drive(durable):
        raise SystemExit(f"{durable}: Drive is not mounted; fetch to the laptop (he1_fetch.py)")
    start = time.monotonic()
    while watch and pid and alive(pid):
        for job in jobs(work):
            sync_job(job, durable / job.name)
        time.sleep(watch)
    for job in jobs(work):
        sync_job(job, durable / job.name)
        if (work / "report.json").exists():
            (durable / job.name / "report.json").write_bytes((work / "report.json").read_bytes())
    size = sum(
        p.stat().st_size
        for job in jobs(work)
        for p in (durable / job.name).rglob("*")
        if p.is_file()
    )
    Report(work).phase(
        "persist",
        time.monotonic() - start,
        jobs=[job.name for job in jobs(work)],
        target=str(durable),
        gigabytes=round(size / 1e9, 2),
    )


def stage(work: Path) -> dict[str, Any]:
    """What the laptop fetches from each job, with sizes and sha256 (cached by mtime).

    Every file outside `checkpoints/` (metrics, results, the run's argv and config)
    and, of the latest complete `ckpt_<step>`, every file but the optimizer state:
    eval serves `model.safetensors`, and a resume is not paid for in tier 2.

    The launch log's `train exit` is read once, before `report.json`: `train` writes
    its phase before the launch line appends the exit, so the pair read in this order
    never shows an exit without the phase of a run that ended ok (DA-26 b3: the exit
    landed while the new checkpoint was being hashed, and the job read as failed).
    A symlink that resolves outside the job dir is not listed but named in `skipped`:
    rsync copies the link, which dangles on the laptop and could never verify (W&B's
    `logs/debug-core.log` points into `/root/.cache`).
    """
    cache_path = work / "stage_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    exit_code = train_exit(work / "train.log")
    report = (
        json.loads((work / "report.json").read_text()) if (work / "report.json").exists() else {}
    )
    trained = report.get("phases", {}).get("train", {})
    staged = []
    for job in jobs(work):
        complete = completed_checkpoints(job)
        inside = job.resolve()
        outside = sorted(
            p for p in job.rglob("*") if p.is_symlink() and not p.resolve().is_relative_to(inside)
        )
        files = [
            p
            for p in job.rglob("*")
            if p.is_file() and "checkpoints" not in p.parts and p not in outside
        ]
        if complete:
            files += [
                p
                for p in complete[-1].rglob("*")
                if p.is_file() and not p.name.startswith("optimizer")
            ]
        entries = []
        for path in sorted(files):
            info = path.stat()
            key = str(path)
            if cache.get(key, {}).get("stamp") != [info.st_size, info.st_mtime]:
                cache[key] = {"stamp": [info.st_size, info.st_mtime], "sha256": sha256(path)}
            rel = str(path.relative_to(job))
            entries.append({"path": rel, "size": info.st_size, "sha256": cache[key]["sha256"]})
        staged.append(
            {
                "job": job.name,
                "checkpoint": complete[-1].name if complete else None,
                "train": train_state(trained, job.name, exit_code),
                "progress": progress(job / "metrics.jsonl"),
                "files": entries,
                "skipped": [str(p.relative_to(job)) for p in outside],
            }
        )
    cache_path.write_text(json.dumps(cache))
    return {"train": run_state(exit_code, staged), "jobs": staged}


def train_exit(log: Path) -> int | None:
    """N of the last `train exit N` the runbook's launch line wrote, or None."""
    lines = log.read_text().splitlines() if log.is_file() else []
    codes = [line.removeprefix("train exit ").strip() for line in lines]
    codes = [c for c, line in zip(codes, lines, strict=True) if line.startswith("train exit ")]
    return int(codes[-1]) if codes and codes[-1].isdigit() else (1 if codes else None)


def run_state(code: int | None, staged: list[dict[str, Any]]) -> str:
    """The launch as a whole: `failed` when `train` exited nonzero, or exited with no job.

    A train that dies before Psi0Trainer makes `runs/<job>` (no .env, a failed import,
    a refused hash or marker) leaves no job to carry a state; this one still says so.
    """
    if code is None:
        return "running"
    return "failed" if code != 0 or not staged else "ended"


def train_state(trained: dict[str, Any], job: str, exit_code: int | None) -> str:
    """`done`, `failed` or `running`.

    `done` only when the train phase of this job ended ok at the plan's last step:
    `train` writes its phase before it raises, so a crash at 25k with ckpt_20000 on
    disk also has one. A `train exit` line in the launch log with no such phase is a
    failure too (the process died before writing it).
    """
    if trained.get("job_id") == job:
        ok = trained.get("infra_status") == "ok"
        return "done" if ok and trained.get("checkpoint_step") == TOTAL_STEPS else "failed"
    if exit_code is not None:
        return "failed"
    return "running"


def progress(metrics: Path, skip: int = 200) -> dict[str, Any]:
    """Last train step and seconds per step since step `skip` of the latest attempt.

    The window holds the validation passes it spans, so the rate is what the
    remaining steps will cost, not the bare optimiser step.
    """
    rows = []
    if metrics.exists():
        for line in metrics.read_text().splitlines():
            try:
                row = json.loads(line)
            except ValueError:  # the trainer is mid-way through writing the last line
                continue
            if isinstance(row, dict) and row.get("split") == "train":
                rows.append(row)
    if rows:
        last = rows[-1].get("attempt")
        rows = [r for r in rows if r.get("attempt") == last]
    window = [r for r in rows if r["step"] >= skip]
    rate = None
    if len(window) > 1 and window[-1]["step"] > window[0]["step"]:
        elapsed = window[-1]["wall_time_s"] - window[0]["wall_time_s"]
        rate = elapsed / (window[-1]["step"] - window[0]["step"])
    return {"step": rows[-1]["step"] if rows else None, "s_per_step": rate}


def jobs(work: Path) -> list[Path]:
    return sorted(p for p in (work / "runs").glob("*") if p.is_dir())


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def restore(work: Path, durable: Path, point_text: str) -> None:
    """Bring a job back from durable storage onto a fresh VM before `train` resumes it."""
    _, point, _ = load_point(point_text)
    start = time.monotonic()
    job_dir = work / "runs" / job_id(point)
    job_dir.mkdir(parents=True, exist_ok=True)
    sh(f"rsync -a {durable / job_id(point)}/ {job_dir}/")
    Report(work).phase("restore", time.monotonic() - start, source=str(durable / job_id(point)))


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("phase", choices=["setup", "train", "persist", "restore", "stage"])
    parser.add_argument("--work", type=Path, default=Path("/content/da26"))
    parser.add_argument("--point", help="VARIANT/SET/SEED of a preliminary point, e.g. V-EGO/N20/0")
    parser.add_argument("--to", type=Path, default=DRIVE, help="durable directory (Drive)")
    parser.add_argument("--watch", type=float, help="`persist`: sync every N seconds")
    parser.add_argument("--pid", type=int, help="`persist --watch`: until this process ends")
    args = parser.parse_args(argv)
    if args.phase in ("setup", "train", "restore") and not args.point:
        parser.error(f"{args.phase} needs --point")
    args.work.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    if args.phase == "setup":
        setup(args.work, args.point)
    elif args.phase == "train":
        train(args.work, args.point)
    elif args.phase == "persist":
        persist(args.work, args.to, args.watch, args.pid)
    elif args.phase == "stage":
        print(json.dumps(stage(args.work)))
    else:
        restore(args.work, args.to, args.point)


if __name__ == "__main__":
    main()

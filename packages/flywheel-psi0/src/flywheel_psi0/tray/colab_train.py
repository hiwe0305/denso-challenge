"""Fine-tune branch C of tray RunPlan v2 on a Colab L4 (DA-34 task 2, AC 2).

VM side, one session for the one run tier 2 pays for here (C+ is the round's).
The repo goes to `<work>/fw` (`git archive` of master) and C's cut, built on
rtx3060 from the release, to `<work>/sets/C/<env name>`; then, from `<work>`:

    export PYTHONPATH=fw/packages/flywheel-psi0/src:fw/packages/flywheel-contracts/src
    python3 -m flywheel_psi0.tray.colab_train setup
    Psi0/.venv-psi/bin/python -m flywheel_psi0.tray.colab_train train

Both phases load `configs/runplans/tray/he-tray-v2.yaml` and refuse to go on unless
it is the frozen plan of tier 2 (`FROZEN`), `runplan.check` holds and no pinned
eval file has drifted: the `--launch` rule of docs/he/tray.md section 11, applied
again on the VM because the VM runs the uploaded copy, not the one checked on
rtx3060. `setup` builds Psi0's environment with the same commands as DA-26's
`scripts/he/he1_colab.py install_env`, downloads the baseline parent pair at the
plan's psi-model revision and checks each file against the plan's sha256, then
checks the uploaded cut (`cut_problems`). `train` runs Psi0Trainer with the plan's
recipe and override, the parent of branch C and the plan's train seed, and writes
the `train` phase of `<work>/report.json` the way he1_colab does.

What happens after is DA-26's code: `scripts/he/he1_colab.py stage` and
`persist` read only `<work>/runs`, `report.json` and `train.log`, and
`scripts/he/he1_fetch.py --remote-work /content/da34` pulls the checkpoints to the
laptop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from flywheel_psi0.trainer.colab import (
    FLASH_ATTN_WHEEL,
    PSI0_COMMIT,
    PSI0_REPO,
    Report,
    lock_constraints,
    repair_lock,
    sh,
)
from flywheel_psi0.tray.demo_sets import DemoSets
from flywheel_psi0.tray.runplan import (
    REPO,
    TrayRunPlan,
    check,
    lock_path,
    pinned_file_drift,
    run_plan_id,
)

PLAN = "configs/runplans/tray/he-tray-v2.yaml"
FROZEN = "rp_a04c14e79dfd"  # he-tray-v2.lock.json, merged in #116 (5/11/2026)
BRANCH = "C"  # tier 2: the only branch of the plan (C+ is round-tray-cplus.yaml)
WORK = Path("/content/da34")
MARKER = "flywheel_subset.json"  # written by scripts/he/demo_subset.py


def load_plan(repo: Path = REPO, plan_file: str = PLAN) -> tuple[TrayRunPlan, str]:
    """The frozen v2 plan and its run_plan_id, or SystemExit with every reason not to run."""
    plan = TrayRunPlan.load(repo / plan_file)
    problems = check(plan, repo)
    problems += [f"{d}: re-freeze or record a Decision" for d in pinned_file_drift(plan, repo)]
    if plan.superseded_by is not None:
        problems.append(f"superseded by {plan.superseded_by}")
    lock = lock_path(repo / plan_file)
    if not lock.is_file():
        problems.append(f"{lock} missing: the plan is not frozen")
    else:
        frozen = json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"]
        if frozen != run_plan_id(plan):
            problems.append(f"{plan_file} changed since it was frozen as {frozen}")
        elif frozen != FROZEN:
            problems.append(f"{lock.name} holds {frozen}; tier 2 approved {FROZEN} only")
    if BRANCH not in plan.branches or plan.budget is None or BRANCH not in plan.budget.runs:
        problems.append(f"branch {BRANCH} has no run in the plan's budget")
    if problems:
        raise SystemExit("plan does not hold, no training:\n  " + "\n  ".join(problems))
    return plan, FROZEN


def job_id(plan: TrayRunPlan) -> str:
    """`da34-t2-ft-c-s0`: Colab session and run folder; ledger job_da34_ft_C."""
    return f"da34-t2-ft-{BRANCH.lower()}-s{plan.train_seeds[0]}"


def dataset_dir(work: Path, plan: TrayRunPlan) -> Path:
    """Psi0 takes the folder name as the dataset name, like SIMPLE's env id."""
    return work / "sets" / BRANCH / plan.task["env_id"].rsplit("/", 1)[-1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


def cut_problems(data: Path, plan: TrayRunPlan, repo: Path = REPO) -> list[str]:
    """Everything wrong between C's uploaded cut and the plan's pins; empty when it holds."""
    marker_path = data / "meta" / MARKER
    if not marker_path.is_file():
        return [f"{marker_path} missing: not a demo-set cut"]
    marker: dict[str, Any] = json.loads(marker_path.read_text(encoding="utf-8"))
    sets = DemoSets.model_validate_json((repo / plan.demo_sets.file).read_text(encoding="utf-8"))
    demo = sets.sets[plan.branches[BRANCH].demo_set]
    problems = []
    expected = {
        "demo_set": plan.branches[BRANCH].demo_set,
        "set_hash": plan.demo_sets.hashes[plan.branches[BRANCH].demo_set],
        "release_id": plan.release.id,
        "release_hash": plan.release.release_hash,
        "n": demo.n,
    }
    for key, value in expected.items():
        if marker.get(key) != value:
            problems.append(f"cut {key} is {marker.get(key)!r}, the plan's is {value!r}")
    sources = [e["source_episode_index"] for e in marker.get("episodes", [])]
    if sources != demo.episode_indices:
        problems.append("cut episodes are not set C's episode indices in the release")
    if [e["episode_index"] for e in marker.get("episodes", [])] != list(range(len(sources))):
        problems.append("cut episodes are not renumbered 0 .. n-1")
    if not (data / "meta" / "stats_psi0.json").is_file():
        problems.append("cut has no meta/stats_psi0.json (own_train_set stats)")
    return problems


def install_env(work: Path) -> float:
    """The commands of scripts/he/he1_colab.py install_env (DA-19 setup, no downloads)."""
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


def setup(work: Path) -> None:
    plan, _ = load_plan()
    if plan.code["psi0"].commit != PSI0_COMMIT:
        raise SystemExit(f"plan pins Psi0 {plan.code['psi0'].commit}, DA-19 setup {PSI0_COMMIT}")
    data = dataset_dir(work, plan)
    problems = cut_problems(data, plan)  # before the env: a wrong upload costs no install
    if problems:
        raise SystemExit("C's cut does not hold, no training:\n  " + "\n  ".join(problems))
    env_seconds = install_env(work)
    psi0, python = work / "Psi0", work / "Psi0" / ".venv-psi" / "bin" / "python"
    start = time.monotonic()
    parent = plan.parents[plan.branches[BRANCH].parent]
    # whole folders: Psi0 loads each as a directory (config, tokenizer, weights)
    weights = [f"{w.path.rsplit('/', 1)[0]}/*" for w in (parent.vlm, parent.action_header)]
    sh(
        f'{python} -c "from huggingface_hub import snapshot_download; '
        f"snapshot_download('{plan.psi_model.repo}', repo_type='model', "
        f"revision='{plan.psi_model.revision}', allow_patterns={weights!r}, "
        f"local_dir='{psi0 / 'cache/checkpoints'}')\""
    )
    pinned = {
        psi0 / "cache/checkpoints" / parent.vlm.path: parent.vlm.sha256,
        psi0 / "cache/checkpoints" / parent.action_header.path: parent.action_header.sha256,
    }
    problems = []
    for path, expected in pinned.items():
        found = sha256(path) if path.is_file() else "missing"
        if found != expected:
            problems.append(f"{path}: sha256 {found}, plan pins {expected}")
    if problems:
        raise SystemExit("pinned weights differ, no training:\n  " + "\n  ".join(problems))
    Report(work).phase(
        "setup_tray_c",
        env_seconds + time.monotonic() - start,
        job_id=job_id(plan),
        run_plan_id=FROZEN,
        env_seconds=round(env_seconds, 1),
        download_seconds=round(time.monotonic() - start, 1),
        sha256_checked={str(p.relative_to(work)): h for p, h in pinned.items()},
        demo_set_hash=plan.demo_sets.hashes[plan.branches[BRANCH].demo_set],
        dataset=str(data),
    )


def train(work: Path) -> None:
    from flywheel.contracts import CheckpointRef, DatasetRef, TrainSpec
    from flywheel.contracts.artifacts import ActionLayout

    from flywheel_psi0.trainer import Psi0Recipe, Psi0Trainer
    from flywheel_psi0.trainer.colab import g1_layout_json

    plan, run_plan = load_plan()
    data = dataset_dir(work, plan)
    problems = cut_problems(data, plan)
    if problems:
        raise SystemExit("C's cut does not hold, no training:\n  " + "\n  ".join(problems))
    demo_set = plan.branches[BRANCH].demo_set
    set_hash = plan.demo_sets.hashes[demo_set]
    spec = TrainSpec(
        job_id=job_id(plan),
        dataset=DatasetRef(dataset_id=f"{plan.release.id}#{demo_set}", uri=str(data)),
        parent=CheckpointRef(checkpoint_id=plan.branches[BRANCH].parent),
        seed=plan.train_seeds[0],
    )
    trainer = Psi0Trainer(
        Psi0Recipe.load(REPO / plan.recipe.file),
        psi0_root=work / "Psi0",
        runs_root=work / "runs",
        layout=ActionLayout.model_validate({"dimensions": g1_layout_json()}),
        run_plan_id=run_plan,
        release_id=f"{plan.release.id}#{demo_set}:{set_hash[:12]}",
        psi0_commit=PSI0_COMMIT,
        nproc_per_node=plan.recipe.nproc_per_node,
        overrides=dict(plan.recipe.overrides),
    )
    start = time.monotonic()
    result = trainer.train(spec)
    launched = json.loads((work / "runs" / spec.job_id / "result.json").read_text())
    Report(work).phase(  # the phase he1_colab.py stage reads to call a job done
        "train",
        time.monotonic() - start,
        branch=BRANCH,
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("phase", choices=["setup", "train", "check"])
    parser.add_argument("--work", type=Path, default=WORK)
    args = parser.parse_args(argv)
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    if args.phase == "check":  # on rtx3060 before the upload, and in tests: no env, no GPU
        plan, run_plan = load_plan()
        problems = cut_problems(dataset_dir(args.work, plan), plan)
        print("\n".join(problems) or f"{run_plan} {job_id(plan)}: cut and plan hold")
        raise SystemExit(1 if problems else 0)
    args.work.mkdir(parents=True, exist_ok=True)
    if args.phase == "setup":
        setup(args.work)
    else:
        train(args.work)


if __name__ == "__main__":
    main()

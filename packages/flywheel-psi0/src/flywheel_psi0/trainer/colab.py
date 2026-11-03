"""Run a Psi0 stage 3 job on a Colab VM, interrupt it, resume it (DA-19 task 5, AC 5).

Uploaded with the flywheel sources and run on the VM in three phases, each timed
into `<work>/report.json` for the cost ledger (docs/g0/ledger/DA-19.csv):

    python3 -m flywheel_psi0.trainer.colab setup   --work /content/da19
    .venv-psi/bin/python -m flywheel_psi0.trainer.colab smoke --work /content/da19
    python3 -m flywheel_psi0.trainer.colab persist --work /content/da19 --to <durable dir>

`setup` uses only the standard library (the VM's python3): it clones Psi0 at the
pin, builds `.venv-psi` with the author's versions (see `repair_lock`), adds the
README's flash-attn 2.7.4.post1 from its prebuilt wheel (the Qwen3-VL backbone is
loaded with `flash_attention_2`, so training does not start without it), and
downloads the parent checkpoints and the two-table data from Hugging Face. The
data is `public` (design section 8.4).

`smoke` runs `Psi0Trainer` twice on the same TrainSpec: the first attempt is killed
once a train line past `--kill-at` is written, the second resumes from Psi0's last
`ckpt_<step>`. It reports whether attempt 1 starts at that checkpoint step and the
train loss on both sides of the cut, so "bước và loss nối liền" can be read off.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

PSI0_REPO = "https://github.com/physical-superintelligence-lab/Psi0.git"
PSI0_COMMIT = "cda3fdfafe47cb6fa75400d013de1bd36e3cea05"
PARENT = "psi0-baseline-egodex-he"
PARENT_DIRS = (
    "psi0/pre.fast.1by1.2601091803.ckpt.ego200k.he30k",
    "psi0/postpre.1by1.pad36.2601131206.ckpt.he30k",
)
TASK = "G1WholebodyLocomotionPickBetweenTablesTeleop-v0"
# The README's `flash_attn==2.7.4.post1`, prebuilt for torch 2.7 / CUDA 12 / cp311
# with the CXX11 ABI that PyPI's torch 2.7.0+cu126 uses (checked on the VM).
FLASH_ATTN_WHEEL = (
    "https://github.com/Dao-AILab/flash-attention/releases/download/v2.7.4.post1/"
    "flash_attn-2.7.4.post1+cu12torch2.7cxx11abiTRUE-cp311-cp311-linux_x86_64.whl"
)
JOB_ID = "da19-smoke-colab"

# Psi0's ACTION_SLICES_36D at the pin (src/psi/data/simple/__init__.py). Provisional
# until DA-01 publishes configs/embodiments/g1.yaml; group names may change there.
G1_GROUPS = (
    ("hand", 14),
    ("arm", 14),
    ("torso_rpy", 3),
    ("height", 1),
    ("base_velocity", 2),
    ("turn", 1),
    ("target_yaw", 1),
)


def g1_layout_json() -> list[dict[str, Any]]:
    return [
        {"name": f"{group}_{i}", "group": group, "masked": False}
        for group, size in G1_GROUPS
        for i in range(size)
    ]


class Report:
    """`report.json`: what ran, how long each phase took, what came out."""

    def __init__(self, work: Path) -> None:
        self.path = work / "report.json"
        self.data: dict[str, Any] = (
            json.loads(self.path.read_text()) if self.path.exists() else {"phases": {}}
        )

    def phase(self, name: str, seconds: float, **details: Any) -> None:
        self.data["phases"][name] = {"seconds": round(seconds, 1), **details}
        self.path.write_text(json.dumps(self.data, indent=2))


def sh(command: str, cwd: Path | None = None, env: Mapping[str, str] | None = None) -> None:
    print(f"$ {command}", flush=True)
    subprocess.run(command, shell=True, check=True, cwd=cwd, env={**os.environ, **(env or {})})


TUNA = "https://pypi.tuna.tsinghua.edu.cn"


def repair_lock(text: str) -> str:
    """Make Psi0's `uv.lock` at the pin parseable without changing any pinned version.

    At cda3fdf the lock mixes the Tsinghua PyPI mirror with PyPI and holds two
    copies of `jsonpointer` and of `jsonschema`'s `[package.optional-dependencies]`
    (a merge left both), and once the mirror is folded into PyPI, `defusedxml` and
    `uri-template` appear twice too. The mirror serves PyPI's files under the same
    paths with the same hashes, so pointing those URLs at PyPI keeps every hash
    checked; a package is then kept once per (name, version) - the copies
    differ only in `size` and `upload-time` - and a repeated sub-table once.

    The merge also left about 30 peripheral packages (notebook, ray, numba, timm...)
    at two versions, one per side, which `uv` cannot pick between when a dependency
    names them without a version. The newer one, from the later of the two locks,
    is kept. torch, numpy, pyarrow, transformers and the lerobot fork are not among
    them, so the training stack is the author's.
    """
    text = text.replace(f"{TUNA}/simple", "https://pypi.org/simple")
    text = text.replace(f"{TUNA}/packages/", "https://files.pythonhosted.org/packages/")
    head, *blocks = text.split("\n[[package]]\n")
    kept: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        identity = "\n".join(block.split("\n")[:2])  # name, version: all sources are PyPI now
        if identity in seen:
            continue
        seen.add(identity)
        # Drop a sub-table that repeats, header and body, inside one package.
        sections = block.split("\n\n[package.")
        unique = [sections[0]]
        for section in sections[1:]:
            if all(section.rstrip() != other.rstrip() for other in unique[1:]):
                unique.append(section)
            elif not unique[-1].endswith("\n"):
                unique[-1] += "\n"  # the dropped copy carried the block's last newline
        kept.append("\n\n[package.".join(unique))
    newest: dict[str, tuple[int | str, ...]] = {}
    for block in kept:
        name, version = _name_version(block)
        if _version_key(version) > newest.get(name, ()):
            newest[name] = _version_key(version)
    kept = [b for b in kept if _version_key(_name_version(b)[1]) == newest[_name_version(b)[0]]]
    return "\n[[package]]\n".join([head, *kept])


def lock_constraints(lock: str) -> str:
    """`name==version` for every registry package of a (repaired) `uv.lock`.

    Read from the first lines of each `[[package]]` block, which `uv` always writes
    as `name`, `version`, `source`, so no TOML parser is needed (tomllib is 3.11+).
    """
    constraints = []
    for block in lock.split("\n[[package]]\n")[1:]:
        name, version = _name_version(block)
        if version and 'source = { registry = "' in block.split("\n")[2]:
            constraints.append(f"{name}=={version}\n")
    return "".join(constraints)


def _name_version(block: str) -> tuple[str, str]:
    lines = block.split("\n")
    return lines[0].split('"')[1], (
        lines[1].split('"')[1] if lines[1].startswith("version") else ""
    )


def _version_key(version: str) -> tuple[int | str, ...]:
    """Enough ordering for release versions like `1.8.21`, `0.8.1.post1`, `0.23`."""
    return tuple(int(part) if part.isdigit() else part for part in version.split("."))


def setup(work: Path) -> None:
    start = time.monotonic()
    psi0 = work / "Psi0"
    if not (psi0 / ".git").exists():
        sh(f"git clone --filter=blob:none {PSI0_REPO} {psi0}")
    sh(f"git checkout -q {PSI0_COMMIT}", cwd=psi0)
    sh("pip install -q uv")
    lfs = {"GIT_LFS_SKIP_SMUDGE": "1"}
    if not (psi0 / ".venv-psi").exists():
        sh("env -u UV_SYSTEM_PYTHON uv venv .venv-psi --python 3.11", cwd=psi0)
    # The pin's uv.lock cannot be synced as is (see repair_lock), and it also lost
    # some entries (bokeh's xyzservices). Resolve the `psi` group afresh with every
    # version the lock records as a constraint: the author's stack stays exact
    # (torch 2.7.0, numpy 1.26.4, pyarrow 21.0.0, datasets 3.6.0, lerobot@09929d8),
    # only what the lock lacks is picked by uv.
    constraints = work / "psi0-constraints.txt"
    constraints.write_text(lock_constraints(repair_lock((psi0 / "uv.lock").read_text())))
    # Colab sets UV_SYSTEM_PYTHON, which would send the install to its python 3.13.
    sh(
        f"env -u UV_SYSTEM_PYTHON uv pip install --python .venv-psi/bin/python "
        f"-e . --group psi -c {constraints}",
        cwd=psi0,
        env=lfs,
    )
    # --no-config: Psi0's pyproject declares flash-attn a torch build dependency,
    # which only matters when building from source, not for the prebuilt wheel.
    sh(
        f"env -u UV_SYSTEM_PYTHON uv pip install --no-config "
        f"--python {psi0}/.venv-psi/bin/python --no-deps '{FLASH_ATTN_WHEEL}'",
        cwd=work,
    )
    # scripts/train.py asserts load_dotenv(); keep caches on the VM disk.
    (psi0 / ".env").write_text(
        f"HF_HOME={work}/hf\nTOKENIZERS_PARALLELISM=false\nWANDB_MODE=offline\n"
    )
    env_seconds = time.monotonic() - start

    start = time.monotonic()
    python = psi0 / ".venv-psi" / "bin" / "python"
    data = work / "data"
    downloads = [
        (
            "USC-PSI-Lab/psi-model",
            "model",
            [f"{d}/*" for d in PARENT_DIRS],
            psi0 / "cache" / "checkpoints",
        ),
        ("USC-PSI-Lab/psi-data", "dataset", [f"simple/{TASK}.zip"], data),
    ]
    for repo, kind, patterns, target in downloads:
        sh(
            f'{python} -c "from huggingface_hub import snapshot_download; '
            f"snapshot_download('{repo}', repo_type='{kind}', allow_patterns={patterns!r}, "
            f"local_dir='{target}')\""
        )
    if not (data / "simple" / TASK / "meta").exists():
        sh(f"unzip -q -o {data}/simple/{TASK}.zip -d {data}/simple")
    Report(work).phase(
        "setup",
        env_seconds + time.monotonic() - start,
        env_seconds=round(env_seconds, 1),
        download_seconds=round(time.monotonic() - start, 1),
        psi0_commit=PSI0_COMMIT,
    )


def train_steps(metrics: Path, attempt: int) -> list[tuple[int, float | str]]:
    """`(step, loss)` of the train lines one attempt wrote, in file order."""
    if not metrics.exists():
        return []
    rows = []
    for line in metrics.read_text().splitlines():
        record = json.loads(line)
        if record["split"] == "train" and record["attempt"] == attempt:
            rows.append((int(record["step"]), record["loss"]))
    return rows


def interrupting_runner(
    metrics: Path, attempt: int, kill_at: int, poll_seconds: float = 5.0
) -> Callable[[Sequence[str], Path, Mapping[str, str]], int]:
    """A `Psi0Trainer` runner that kills torchrun once `attempt` logs step `kill_at`."""

    def run(command: Sequence[str], cwd: Path, env: Mapping[str, str]) -> int:
        process = subprocess.Popen(list(command), cwd=cwd, env=dict(env), start_new_session=True)
        while process.poll() is None:
            if any(step >= kill_at for step, _ in train_steps(metrics, attempt)):
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(poll_seconds)
        return process.wait()

    return run


def continuity(metrics: Path, checkpoint_step: int | None) -> dict[str, Any]:
    """Where attempt 1 picked up, against the checkpoint attempt 0 left behind."""
    first, second = train_steps(metrics, 0), train_steps(metrics, 1)
    resumed_at = second[0][0] if second else None
    return {
        "attempt0_steps": [first[0][0], first[-1][0]] if first else None,
        "attempt1_steps": [second[0][0], second[-1][0]] if second else None,
        "checkpoint_step": checkpoint_step,
        "resumed_at_checkpoint": resumed_at is not None and resumed_at == checkpoint_step,
        "loss_before_cut": [loss for _, loss in first[-3:]],
        "loss_after_cut": [loss for _, loss in second[:3]],
    }


def smoke(work: Path, steps: int, every: int, kill_at: int) -> None:
    from flywheel.contracts import CheckpointRef, DatasetRef, TrainSpec
    from flywheel.contracts.artifacts import ActionLayout

    from flywheel_psi0.trainer import Psi0Recipe, Psi0Trainer
    from flywheel_psi0.trainer.psi0_trainer import run_subprocess

    recipes = work / "fw" / "configs" / "models"
    psi0_root = work / "Psi0"
    runs = work / "runs"
    spec = TrainSpec(
        job_id=JOB_ID,
        dataset=DatasetRef(dataset_id=f"psi-data-{TASK}", uri=str(work / "data" / "simple" / TASK)),
        parent=CheckpointRef(checkpoint_id=PARENT),
        seed=292285,
    )
    overrides: dict[str, Any] = {
        "train.max_training_steps": steps,
        "train.checkpointing_steps": every,
        "train.validation_steps": every,
        "train.val_num_batches": 2,
        "train.warmup_steps": 0,
    }
    metrics = runs / JOB_ID / "metrics.jsonl"
    outcomes = []
    for attempt in (0, 1):
        runner = interrupting_runner(metrics, attempt, kill_at) if attempt == 0 else run_subprocess
        trainer = Psi0Trainer(
            Psi0Recipe.load(recipes / "psi0-stage3.yaml"),
            psi0_root=psi0_root,
            runs_root=runs,
            layout=ActionLayout.model_validate({"dimensions": g1_layout_json()}),
            run_plan_id="rp-da19-smoke",
            release_id=f"psi-data-{TASK}",
            psi0_commit=PSI0_COMMIT,
            overrides=overrides,
            runner=runner,
        )
        start = time.monotonic()
        result = trainer.train(spec)
        launched = json.loads((runs / JOB_ID / "result.json").read_text())
        shutil.copy(runs / JOB_ID / "result.json", runs / JOB_ID / f"result.attempt{attempt}.json")
        outcomes.append(
            {
                "attempt": attempt,
                "seconds": round(time.monotonic() - start, 1),
                "infra_status": result.infra_status,
                "checkpoint_step": launched.get("checkpoint_step"),
                "checkpoint_dir": launched.get("checkpoint_dir"),
                "error": launched.get("error"),
            }
        )
    lines = metrics.read_text().splitlines() if metrics.exists() else []
    vram = [r["vram_gb"] for r in map(json.loads, lines) if r.get("vram_gb") is not None]
    Report(work).phase(
        "smoke",
        sum(outcome["seconds"] for outcome in outcomes),
        attempts=outcomes,
        continuity=continuity(metrics, outcomes[0]["checkpoint_step"]),
        peak_vram_gb=max(vram, default=None),
        overrides=overrides,
    )


def persist(work: Path, durable: Path) -> None:
    """Copy the job directory (metrics, results, Psi0 checkpoints) to durable storage."""
    start = time.monotonic()
    target = durable / JOB_ID
    shutil.copytree(work / "runs" / JOB_ID, target, dirs_exist_ok=True)
    shutil.copy(work / "report.json", target / "report.json")
    size = sum(path.stat().st_size for path in target.rglob("*") if path.is_file())
    Report(work).phase(
        "persist", time.monotonic() - start, target=str(target), gigabytes=round(size / 1e9, 2)
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("phase", choices=["setup", "smoke", "persist"])
    parser.add_argument("--work", type=Path, default=Path("/content/da19"))
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--every", type=int, default=20)
    parser.add_argument("--kill-at", type=int, default=30)
    parser.add_argument("--to", type=Path, help="durable directory for `persist`")
    args = parser.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)
    if args.phase == "setup":
        setup(args.work)
    elif args.phase == "smoke":
        smoke(args.work, args.steps, args.every, args.kill_at)
    else:
        if args.to is None:
            parser.error("persist needs --to")
        persist(args.work, args.to)


if __name__ == "__main__":
    main()

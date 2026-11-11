"""Serve one run of the four-run pair from a Colab L4 for the tray eval (DA-34 task 6.3).

Eval lanes 2-4 of docs/he/tray.md 19.5 (`B_70`, `C_70`, `C_ALL`; lane 1, `B_ALL`, serves
on rtx3060): the Psi0 server runs on a Colab L4, the SIMPLE client on rtx3060 reaches it
through the laptop (`colab ssh` forward to the VM, `ssh -R` to rtx3060), and
`eval_batch --server 127.0.0.1:<port>` drives it as it drives a local server. The server
is started exactly as `scripts/g0/serve_psi0.sh serve` starts it on rtx3060
(`docker/psi0/serve_psi0_seeded.py`, `--action-exec-horizon 24 --rtc`), so the two
runs of the primary comparison (a′, `B_70` - `C_70`) are served the same way.

Three phases, each refusing before anything loads:

    # laptop, once the checkpoint is on the laptop (he1_fetch) and verified:
    python -m flywheel_psi0.tray.colab_serve expect --runs fwdata/tray/runs --branch C_70 \
        --step 40000 --stats <ALL>/meta/stats_psi0.json
    # VM (after `he1_colab.py serve-setup --work /content/da34s` and the Drive mount):
    python3 -m flywheel_psi0.tray.colab_serve fetch --expected <expected-40000.json>
    python3 -m flywheel_psi0.tray.colab_serve serve --expected <expected-40000.json>

`expect` writes `<runs>/<job>/expected-<step>.json`: the sha256 of the files a server reads
(`argv.txt`, `run_config.json`, `checkpoints/ckpt_<step>/model.safetensors`) from the
laptop's verified copy. It refuses unless ALL's `stats_psi0.json` given hashes to the
plan's `cut.stats_sha256` and the normalisation bounds inside `run_config.json` are those
stats (states and action min/max, Psi0's padding aside): a run that normalised with its
own stats (an S70 run that recomputed them) is never served. `fetch` copies those files
from the run's Drive copy (`persist` of the training VM, under
`MyDrive/denso/da34/<job>/`), `serve` checks every sha256 against the laptop's before it
starts the server, and starts only when no other server answers on the port.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from flywheel_psi0.trainer.colab import Report
from flywheel_psi0.tray.colab_train import pair_job_id
from flywheel_psi0.tray.pairplan import TrayPairPlan
from flywheel_psi0.tray.runplan import REPO

PAIR_PLAN = "configs/runplans/tray/he-tray-pair60k.yaml"
DRIVE_RUNS = Path("/content/drive/MyDrive/denso/da34")  # he1_colab persist --to of the 4 runs
WORK = Path("/content/da34s")  # the serve VM's work root (he1_colab.py serve-setup --work)
PORT = 22085  # on the VM; the laptop forwards it
SERVE_ARGS = ("--action-exec-horizon", "24", "--rtc")  # serve_psi0.sh serve defaults
LAUNCHER = "docker/psi0/serve_psi0_seeded.py"  # in the repo copy on the VM (fw/)
BOUNDS = (("states", "state"), ("action", "action"))  # stats key -> run_config field prefix


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


def served(step: int) -> tuple[str, ...]:
    """What serve_psi0_simple reads of a run dir to serve checkpoint `step`."""
    return ("argv.txt", "run_config.json", f"checkpoints/ckpt_{step}/model.safetensors")


def run_dir(job_dir: Path) -> Path:
    """The one Psi0 run of a job (`psi0/finetune/<run>`), or ValueError."""
    runs = sorted(p for p in (job_dir / "psi0" / "finetune").glob("*") if p.is_dir())
    if len(runs) != 1:
        raise ValueError(f"{job_dir}: {len(runs)} runs under psi0/finetune, not one")
    return runs[0]


def bound_problems(run_config: dict[str, Any], stats: dict[str, Any]) -> list[str]:
    """Where the bounds a run normalised with are not those of `stats` (padding aside)."""
    field = run_config.get("data", {}).get("transform", {}).get("field", {})
    problems = []
    for key, prefix in BOUNDS:
        for end in ("min", "max"):
            want = list(stats.get(key, {}).get(end, []))
            found = list(field.get(f"{prefix}_{end}", []))
            if not want or len(found) < len(want):
                problems.append(f"{prefix}_{end}: {len(found)} values, stats {key} has {len(want)}")
                continue
            if any(not math.isclose(a, b, rel_tol=0, abs_tol=1e-7) for a, b in zip(found, want)):
                problems.append(f"{prefix}_{end} is not {key}.{end} of the cut's stats")
            if any(v != 0 for v in found[len(want) :]):
                problems.append(f"{prefix}_{end}: padding past {len(want)} is not zero")
    return problems


def expect(
    runs: Path, branch: str, step: int, stats: Path, plan_path: Path = REPO / PAIR_PLAN
) -> dict[str, Any]:
    """Laptop: the sha256 a serve VM must find, after the bounds check; written beside the job."""
    plan = TrayPairPlan.load(plan_path)
    if branch not in plan.branches:
        raise SystemExit(f"{branch} is not a branch of {plan_path.name}")
    if step not in (plan.checkpoints.primary, plan.checkpoints.early):
        raise SystemExit(f"step {step}: the rules read {plan.checkpoints.model_dump()} only")
    job = pair_job_id(branch, plan.train_seeds[0])
    if sha256(stats) != plan.cut.stats_sha256:
        raise SystemExit(f"{stats}: not ALL's stats (sha256 {sha256(stats)})")
    src = run_dir(runs / job)
    config = json.loads((src / "run_config.json").read_text(encoding="utf-8"))
    problems = bound_problems(config, json.loads(stats.read_text(encoding="utf-8")))
    missing = [rel for rel in served(step) if not (src / rel).is_file()]
    problems += [f"{src / rel} missing" for rel in missing]
    if problems:
        raise SystemExit(f"{job} is not served:\n  " + "\n  ".join(problems))
    want = {
        "branch": branch,
        "job": job,
        "run": src.name,
        "ckpt_step": step,
        "stats_sha256": plan.cut.stats_sha256,
        "files": {rel: sha256(src / rel) for rel in served(step)},
    }
    out = runs / job / f"expected-{step}.json"
    out.write_text(json.dumps(want, indent=1) + "\n")
    return want


def file_problems(base: Path, files: dict[str, str]) -> list[str]:
    problems = []
    for rel, digest in files.items():
        found = sha256(base / rel) if (base / rel).is_file() else "missing"
        if found != digest:
            problems.append(f"{base / rel}: sha256 {found}, the laptop's is {digest}")
    return problems


def fetch(expected: Path, work: Path = WORK, drive: Path = DRIVE_RUNS) -> list[str]:
    """VM: copy the served files from the run's Drive copy; return what was copied."""
    want = json.loads(expected.read_text())
    src = drive / want["job"] / "psi0" / "finetune" / want["run"]
    dest = work / "serve" / want["job"] / want["run"]
    copied = []
    for rel, digest in want["files"].items():
        if (dest / rel).is_file() and sha256(dest / rel) == digest:
            continue
        if not (src / rel).is_file():
            raise SystemExit(f"{src / rel} missing: is Drive mounted, and did persist copy it?")
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, dest / rel)
        copied.append(rel)
    shutil.copyfile(expected, work / "serve" / want["job"] / f"expected-{want['ckpt_step']}.json")
    problems = file_problems(dest, want["files"])
    if problems:
        raise SystemExit("Drive copy differs from the laptop's:\n  " + "\n  ".join(problems))
    return copied


def healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as reply:
            return bool(reply.status == 200 and b"ok" in reply.read())
    except OSError:
        return False


def serve(
    expected: Path,
    work: Path = WORK,
    port: int = PORT,
    python: str | None = None,
    launcher: Path | None = None,
    deadline_s: float = 900.0,
) -> dict[str, Any]:
    """VM: check every served file, then start one server for the run and wait for it."""
    start = time.monotonic()
    want = json.loads(expected.read_text())
    base = work / "serve" / want["job"] / want["run"]
    problems = file_problems(base, want["files"])
    if problems:
        raise SystemExit(
            "files differ from the laptop's, nothing served:\n  " + "\n  ".join(problems)
        )
    if healthy(port):
        raise SystemExit(
            f"a server already answers on {port}: stop it first (its pid is in report.json)"
        )
    src = work / "serve" / "Psi0"
    python = python or str(src / ".venv-psi" / "bin" / "python")
    launcher = launcher or work / "fw" / LAUNCHER
    argv = [
        python,
        str(launcher),
        *("--policy", "psi0", "--host", "127.0.0.1", "--port", str(port), "--device", "cuda:0"),
        *("--run-dir", str(base), "--ckpt-step", str(want["ckpt_step"])),
        *SERVE_ARGS,
    ]
    logs = work / "runs" / f"serve-{want['job']}"
    logs.mkdir(parents=True, exist_ok=True)
    name = f"server-{want['ckpt_step']}"
    with (logs / f"{name}.log").open("ab") as log_file:
        proc = subprocess.Popen(
            argv,
            cwd=src if src.is_dir() else work,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # outlives this phase
        )
    loaded = time.monotonic()
    while not healthy(port):
        if proc.poll() is not None or time.monotonic() - loaded > deadline_s:
            raise SystemExit(f"server of {want['job']} on {port} did not come up; see {name}.log")
        time.sleep(2)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/info", timeout=30) as reply:
        (logs / f"{name}.info.json").write_bytes(reply.read())
    row = {
        "job": want["job"],
        "branch": want["branch"],
        "ckpt_step": want["ckpt_step"],
        "port": port,
        "pid": proc.pid,
        "run": want["run"],
        "load_seconds": round(time.monotonic() - loaded, 1),
        "argv": argv[1:],
        "sha256_checked": want["files"],
        "stats_sha256": want["stats_sha256"],
    }
    Report(work).phase(
        f"serve_{want['branch'].lower()}_{want['ckpt_step']}", time.monotonic() - start, **row
    )
    return row


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("phase", choices=["expect", "fetch", "serve"])
    parser.add_argument("--runs", type=Path, help="expect: the laptop's fwdata/tray/runs")
    parser.add_argument("--branch", help="expect: B_ALL, C_ALL, B_70 or C_70")
    parser.add_argument("--step", type=int, help="expect: the checkpoint to serve")
    parser.add_argument("--stats", type=Path, help="expect: ALL's meta/stats_psi0.json")
    parser.add_argument("--expected", type=Path, help="fetch, serve: expected-<step>.json")
    parser.add_argument("--work", type=Path, default=WORK)
    parser.add_argument("--drive", type=Path, default=DRIVE_RUNS)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args(argv)
    if args.phase == "expect":
        if None in (args.runs, args.branch, args.step, args.stats):
            parser.error("expect needs --runs, --branch, --step and --stats")
        want = expect(args.runs, args.branch, args.step, args.stats)
        print(json.dumps({k: v for k, v in want.items() if k != "files"}))
        return 0
    if args.expected is None:
        parser.error(f"{args.phase} needs --expected")
    if args.phase == "fetch":
        print(json.dumps({"copied": fetch(args.expected, args.work, args.drive)}))
    else:
        print(json.dumps(serve(args.expected, args.work, args.port)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

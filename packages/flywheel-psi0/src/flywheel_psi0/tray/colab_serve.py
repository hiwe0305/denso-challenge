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

The round branch `C70_R1` (task 7, docs/he/tray.md 20.15) is served the same way: its
job is `colab_train.round_job_id`, the only step is the round's `eval.checkpoint`, and the
stats must hash to the round's `train.stats_sha256` (ALL's, as its cut is normalised
with). Stage 1 then runs on three such servers, `eval_batch --chunks` two chunks each.

Run M of DA-48 (`--branch M`, DA-47's eval on the jig2 scene) too: its plan must be frozen
with id `colab_train.MIX_FROZEN`, the steps are the plan's `checkpoints` (primary, then the
early reads of docs/he/tray-jig.md rule 6), the stats must hash to the joined set's
`cut.stats_sha256`, and its runs live under `MyDrive/<plan drive.runs>`. `expect` writes
that folder into the expected file (`drive_runs`) and `fetch` reads from it, so M needs no
`--drive`; an expected file without it (written before) reads `MyDrive/denso/da34`.

    python -m flywheel_psi0.tray.colab_serve expect --runs fwdata/tray/jig-m --branch M \
        --step 100000 --stats <M>/meta/stats_psi0.json

Run N of DA-50 (`--branch N`) is served the same way from its own plan
(`he-tray-jig-n.yaml`, approved id `colab_train.MIX_N_FROZEN`, job `da50-ft-n-s0`).
Its 6 GB weights need not be on the laptop: `--checkpoint-sha256 <hex>`, the sha256
recorded when training ended (read on Drive), stands for the weights file's, which then is
not read locally (and, if it is there, must hash to it). Every other served file is hashed
from the laptop's copy as before, and `fetch` and `serve` check the Drive and VM copies
against the expected file as always; the file records `"checkpoint_sha256_from": "recorded"`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NamedTuple

from flywheel_psi0.trainer.colab import Report
from flywheel_psi0.tray import colab_train
from flywheel_psi0.tray.colab_train import (
    MIX,
    MIX_N,
    ROUND_C70,
    ROUND_C70_PLAN,
    mix_job_id,
    pair_job_id,
    round_job_id,
)
from flywheel_psi0.tray.mixplan import TrayMixPlan, launch_problems
from flywheel_psi0.tray.pairplan import TrayPairPlan
from flywheel_psi0.tray.pairround import TrayPairRoundPlan
from flywheel_psi0.tray.runplan import REPO, run_plan_id

PAIR_PLAN = "configs/runplans/tray/he-tray-pair60k.yaml"
MYDRIVE = Path("/content/drive/MyDrive")
PAIR_DRIVE = "denso/da34"  # he1_colab persist --to of the 4 runs and of C70_R1
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


class Job(NamedTuple):
    job: str
    steps: tuple[int, ...]  # the checkpoints the reading rules read
    stats_sha256: str | None
    drive_runs: str  # under MyDrive: one folder per job, as persist --to writes them
    run_plan_id: str | None = None  # M: the frozen plan's id
    stats_name: str = "ALL's"


def _mix(plan_path: Path, branch: str = MIX) -> Job:
    """Run M or N: refused unless its plan is frozen and its id is the approved one."""
    _, frozen, constant, task = colab_train._mix_approval(branch)  # read at call time (monkeypatch)
    plan = TrayMixPlan.load(plan_path)
    problems = launch_problems(plan, plan_path)
    if frozen is None:
        problems.append(f"no {branch} plan is approved: {constant} is unset ({task})")
    elif run_plan_id(plan) != frozen:
        problems.append(f"{plan_path.name} is {run_plan_id(plan)}; only {frozen} is approved")
    if list(plan.branches) != [branch]:
        problems.append(f"the {branch} plan's branches are {list(plan.branches)}, not [{branch}]")
    if problems:
        raise SystemExit(
            f"{branch} plan does not hold, nothing served:\n  " + "\n  ".join(problems)
        )
    steps = (plan.checkpoints.primary, *plan.checkpoints.reads)
    job = mix_job_id(branch, plan.train_seeds[0], plan.story)
    return Job(job, steps, plan.cut.stats_sha256, plan.drive.runs, frozen, "the joined set's")


def _job(branch: str, plan_path: Path, round_path: Path, mix_path: Path | None) -> Job:
    """The job, the steps the rules read, the stats sha256 and Drive folder of a branch."""
    if branch in (MIX, MIX_N):
        return _mix(mix_path or REPO / colab_train._mix_approval(branch)[0], branch)
    plan = TrayPairPlan.load(plan_path)
    if branch in plan.branches:
        both = (plan.checkpoints.primary, plan.checkpoints.early)
        steps = tuple(s for s in both if s is not None)
        job = pair_job_id(branch, plan.train_seeds[0])
        return Job(job, steps, plan.cut.stats_sha256, PAIR_DRIVE)
    if branch == ROUND_C70:
        rnd = TrayPairRoundPlan.load(round_path)
        if rnd.branch == branch:
            job = round_job_id(branch, rnd.train.train_seed)
            return Job(job, (rnd.eval.checkpoint,), rnd.train.stats_sha256, PAIR_DRIVE)
    raise SystemExit(
        f"{branch} is not a branch of {plan_path.name}, its round {ROUND_C70}, {MIX} nor {MIX_N}"
    )


def expect(
    runs: Path,
    branch: str,
    step: int,
    stats: Path,
    plan_path: Path = REPO / PAIR_PLAN,
    round_path: Path = REPO / ROUND_C70_PLAN,
    mix_path: Path | None = None,
    checkpoint_sha256: str | None = None,
) -> dict[str, Any]:
    """Laptop: the sha256 a serve VM must find, after the bounds check; written beside the job.

    `mix_path` defaults to the plan of the branch (M or N). `checkpoint_sha256`, the weights'
    sha256 recorded when training ended, replaces hashing the weights file, which then need
    not be on the laptop (and, if it is, must hash to it).
    """
    if checkpoint_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", checkpoint_sha256):
        raise SystemExit(f"--checkpoint-sha256 {checkpoint_sha256!r}: not 64 lowercase hex chars")
    spec = _job(branch, plan_path, round_path, mix_path)
    job, stats_sha256 = spec.job, spec.stats_sha256
    if step not in spec.steps:
        raise SystemExit(f"step {step}: the rules read {list(spec.steps)} only for {branch}")
    if sha256(stats) != stats_sha256:
        raise SystemExit(f"{stats}: not {spec.stats_name} stats (sha256 {sha256(stats)})")
    src = run_dir(runs / job)
    config = json.loads((src / "run_config.json").read_text(encoding="utf-8"))
    problems = bound_problems(config, json.loads(stats.read_text(encoding="utf-8")))
    weights = served(step)[-1]  # checkpoints/ckpt_<step>/model.safetensors
    recorded = checkpoint_sha256 is not None
    missing = [
        rel
        for rel in served(step)
        if not (src / rel).is_file() and not (recorded and rel == weights)
    ]
    problems += [f"{src / rel} missing" for rel in missing]
    if recorded and (src / weights).is_file() and sha256(src / weights) != checkpoint_sha256:
        problems.append(
            f"{src / weights}: sha256 {sha256(src / weights)}, "
            f"--checkpoint-sha256 is {checkpoint_sha256}"
        )
    if problems:
        raise SystemExit(f"{job} is not served:\n  " + "\n  ".join(problems))
    want = {
        "branch": branch,
        "job": job,
        "run": src.name,
        "ckpt_step": step,
        "stats_sha256": stats_sha256,
        "run_plan_id": spec.run_plan_id,
        "drive_runs": spec.drive_runs,
        "files": {
            rel: checkpoint_sha256 if recorded and rel == weights else sha256(src / rel)
            for rel in served(step)
        },
    }
    if recorded:
        want["checkpoint_sha256_from"] = "recorded"
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


def fetch(expected: Path, work: Path = WORK, drive: Path | None = None) -> list[str]:
    """VM: copy the served files from the run's Drive copy; return what was copied.

    `drive` defaults to `MyDrive/<drive_runs>` of the expected file (DA-34's folder when the
    file predates the field).
    """
    want = json.loads(expected.read_text())
    if drive is None:
        drive = MYDRIVE / want.get("drive_runs", PAIR_DRIVE)
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
        "run_plan_id": want.get("run_plan_id"),
    }
    Report(work).phase(
        f"serve_{want['branch'].lower()}_{want['ckpt_step']}", time.monotonic() - start, **row
    )
    return row


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("phase", choices=["expect", "fetch", "serve"])
    parser.add_argument("--runs", type=Path, help="expect: the laptop's fwdata/tray/runs")
    parser.add_argument("--branch", help="expect: B_ALL, C_ALL, B_70, C_70, C70_R1, M or N")
    parser.add_argument("--step", type=int, help="expect: the checkpoint to serve")
    parser.add_argument(
        "--stats", type=Path, help="expect: ALL's (M: the joined set's) meta/stats_psi0.json"
    )
    parser.add_argument("--expected", type=Path, help="fetch, serve: expected-<step>.json")
    parser.add_argument("--work", type=Path, default=WORK)
    parser.add_argument(
        "--drive", type=Path, help="fetch: the runs folder; default MyDrive/<drive_runs>"
    )
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument(
        "--checkpoint-sha256",
        help="expect: the weights' recorded sha256 (64 hex); the file need not be local",
    )
    args = parser.parse_args(argv)
    if args.phase == "expect":
        if None in (args.runs, args.branch, args.step, args.stats):
            parser.error("expect needs --runs, --branch, --step and --stats")
        want = expect(
            args.runs, args.branch, args.step, args.stats, checkpoint_sha256=args.checkpoint_sha256
        )
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

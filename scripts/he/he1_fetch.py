"""Pull an HE-1 job's eval files from its Colab VM to the laptop (DA-26 task 3).

The fallback durable copy while Google Drive cannot be mounted (`colab drivemount`
needs Hiếu's browser consent, DA-30 4/11/2026): without it the VM disk is the only
copy, and a cap stop would lose a checkpoint worth about 17 CU.

`colab download` cannot carry a checkpoint: it reads the whole file through
Jupyter's contents API as one base64 JSON reply held in memory on both sides (8.3 GB
of base64 for the 6.25 GB `model.safetensors`, on a 14 GB laptop). So the files go
over `colab ssh --proxy-mode` with rsync, which streams and resumes a cut transfer
(`--partial-dir`). What to pull comes from the VM's own list, `he1_colab.py stage`:
every file outside `checkpoints/` and the latest complete `ckpt_<step>` without its
optimizer state, each with size and sha256. A file counts as fetched only when its
sha256 here equals the VM's; `fetched.json` in the job's folder says what holds.

    python3 scripts/he/he1_fetch.py once   --session S --registry R --dest fwdata/he/runs
    python3 scripts/he/he1_fetch.py follow --session S --registry R --dest fwdata/he/runs \
        --every 600 --stop-when-done

`once` is the CU watcher's soft-cap `--persist` hook. `follow` runs beside the job
from launch: it pulls every new complete checkpoint as it appears, so the cap-time
pull only has the last one left, and ends once training is done and its final
checkpoint is verified here (with `--stop-when-done` it then stops the session, so
the minutes left before the cap are not billed).

`probe` times a 1 GB rsync from the VM before setup, so a slow proxy shows at
minute 10, not at the first checkpoint: it writes `<registry>/<session>.probe.json`
and exits 4 under SLOW_MB_S.

`follow` also enforces the early stop of docs/he/he-1.md section 7 (mandatory, review
of #109): from step 2200 (the window then spans one validation pass) until the first
checkpoint, every pass projects the CU the job will have used once ckpt_40000 is
written and pulled here,

    spent + rate x (steps_left x s_per_step + saves_left x SAVE_S
                    + final_bytes / MB/s) / 3600 + SAFETY_CU

and stops the session (`colab stop`, exit 3) when that passes the watcher's stop line,
cap - rate x margin. `spent` and `cap` are the watcher's last `poll` line; MB/s is the
probe's, replaced by any later pull of over 1 GB. A stop at step 2200 costs about
1.3 CU; letting the cap stop it costs about 17 CU for a ckpt_30000 the plan has no
use for.

Never ssh to a session that is not running: `colab ssh -s NAME` creates a session
when NAME is missing. Each pull first checks that the session's watcher is alive (no
`exit` line in `<registry>/<session>.out`) and that `colab sessions` lists the name.
Exit codes: 0 every job's final checkpoint verified here; 1 not (yet); 2 refused;
3 stopped early; 4 probe under SLOW_MB_S.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

COLAB = Path(
    os.environ.get("COLAB_CLI", "~/project/wm-wam-review/.venv-colab-cli/bin/colab")
).expanduser()
REMOTE_WORK = "/content/da26"
SLOW_MB_S = 6.0  # below this a 6.25 GB checkpoint misses the ~18 min left before the cap
# Recipe R1 (configs/models/psi0-stage3.yaml, checked by test_he1_fetch.py).
TOTAL_STEPS, SAVE_EVERY = 40000, 10000
RATE_CU_H = 1.94  # L4 (docs/g0/psi0-finetune-cost.md section 3)
MARGIN_S = 430.0  # scripts/colab/cu_watch.py Timing().margin, checked by the tests
SAVE_S = 60.0  # assumption: one ckpt_<step> write on L4 (31 s on A100, DA-19)
SAFETY_CU = 0.1
FINAL_BYTES = 6.25e9  # model.safetensors of a stage 3 checkpoint (S1-03), until staged
DECIDE_FROM = 2200  # first pass whose rate window spans the validation at step 2000

Run = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def run(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(argv), capture_output=True, text=True, errors="replace")


def log(**fields: Any) -> None:
    print(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), **fields}), flush=True)


class Remote:
    """The VM of one session: a shell command and an rsync source, both over SSH."""

    def __init__(self, session: str, colab: Path = COLAB, work: str = REMOTE_WORK) -> None:
        self.session, self.work = session, work
        proxy = f"ProxyCommand={colab} ssh --proxy-mode -s {session}"
        options = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null"]
        options += ["-o", "ConnectTimeout=60", "-o", "ServerAliveInterval=30"]
        self.ssh = ["ssh", "-o", proxy, *options, "root@colab"]
        self.rsh = shlex.join(self.ssh[:-1])
        self.host = "root@colab:"
        self.source = f"root@colab:{work}/runs"

    def shell(self, command: str) -> list[str]:
        return [*self.ssh, command]

    def stage(self) -> list[str]:
        return self.shell(f"cd {self.work} && python3 fw/scripts/he/he1_colab.py stage")


class LocalRemote(Remote):
    """A VM stand-in on this disk, for dry runs and tests: same commands, no SSH."""

    def __init__(self, work: Path, python: str = sys.executable) -> None:
        self.session, self.work = "local", str(work)
        self.python = python
        self.ssh, self.rsh, self.host, self.source = [], "", "", f"{work}/runs"

    def shell(self, command: str) -> list[str]:
        return ["bash", "-c", command]

    def stage(self) -> list[str]:
        script = Path(__file__).resolve().parent / "he1_colab.py"
        return self.shell(f"{self.python} {script} stage --work {self.work}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


def verified(dest: Path, files: list[dict[str, Any]], fresh: bool = False) -> dict[str, str]:
    """sha256 of each listed file here, read once per (size, mtime) via `.hashes.json`.

    `fresh` reads every file again: the pass that may declare a job final never
    rests on the cache.
    """
    cache_path = dest / ".hashes.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    found = {}
    for f in files:
        path = dest / f["path"]
        if not path.is_file() or path.stat().st_size != f["size"]:
            continue
        stamp = [path.stat().st_size, path.stat().st_mtime]
        if fresh or cache.get(f["path"], {}).get("stamp") != stamp:
            cache[f["path"]] = {"stamp": stamp, "sha256": sha256(path)}
        found[f["path"]] = cache[f["path"]]["sha256"]
    if dest.is_dir():
        cache_path.write_text(json.dumps(cache))
    return found


def fetch_once(remote: Remote, dest_root: Path, runner: Run = run) -> list[dict[str, Any]]:
    """Pull what `stage` lists and is not here yet; return one status per job."""
    staged = runner(remote.stage())
    if staged.returncode != 0:
        raise RuntimeError(f"stage failed ({staged.returncode}): {staged.stderr[-500:]}")
    statuses = []
    for job in json.loads(staged.stdout)["jobs"]:
        dest = dest_root / job["job"]
        dest.mkdir(parents=True, exist_ok=True)
        files = job["files"]
        have = verified(dest, files, fresh=job["train_done"])
        wanted = [f for f in files if have.get(f["path"]) != f["sha256"]]
        start, size = time.monotonic(), sum(f["size"] for f in wanted)
        if wanted:
            for f in wanted:  # a wrong copy keeps size and mtime: rsync would skip it
                (dest / f["path"]).unlink(missing_ok=True)
            listing = dest / ".wanted"
            listing.write_text("".join(f["path"] + "\n" for f in wanted))
            argv = ["rsync", "-a", "--partial-dir=.rsync-partial", f"--files-from={listing}"]
            if remote.rsh:
                argv += ["-e", remote.rsh]
            pulled = runner([*argv, f"{remote.source}/{job['job']}/", f"{dest}/"])
            if pulled.returncode != 0:
                log(
                    event="rsync_failed",
                    job=job["job"],
                    code=pulled.returncode,
                    stderr=pulled.stderr[-500:],
                )
        seconds = time.monotonic() - start
        have = verified(dest, files, fresh=job["train_done"])
        bad = [f["path"] for f in files if have.get(f["path"]) != f["sha256"]]
        status = {
            "job": job["job"],
            "checkpoint": job["checkpoint"],
            "train_done": job["train_done"],
            "files": len(files),
            "bad_or_missing": bad,
            "pulled_bytes": size if wanted and not bad else None,
            "seconds": round(seconds, 1),
            "mb_per_s": round(size / 1e6 / seconds, 2) if wanted and not bad and seconds else None,
            "final": job["train_done"] and job["checkpoint"] is not None and not bad,
            "progress": job.get("progress", {}),
            "checkpoint_bytes": sum(f["size"] for f in files if "/checkpoints/" in f["path"]),
        }
        (dest / "fetched.json").write_text(json.dumps(status, indent=2))
        log(event="fetched", **status)
        if status["mb_per_s"] is not None and size > 1e9 and status["mb_per_s"] < SLOW_MB_S:
            log(
                event="ALERT",
                job=job["job"],
                message=f"{status['mb_per_s']} MB/s: the final checkpoint may not arrive "
                "before the cap stop; mount Drive or decide now",
            )
        statuses.append(status)
    return statuses


def probe(remote: Remote, dest: Path, megabytes: int = 1000, runner: Run = run) -> float:
    """MB/s of one rsync of `megabytes` of random data from the VM to `dest`."""
    remote_file, local = f"{remote.work}/probe.bin", dest / ".probe.bin"
    made = runner(
        remote.shell(f"mkdir -p {remote.work} && head -c {megabytes}M /dev/urandom > {remote_file}")
    )
    if made.returncode != 0:
        raise RuntimeError(f"probe file not made: {made.stderr[-300:]}")
    argv = ["rsync", "-a", *(["-e", remote.rsh] if remote.rsh else [])]
    start = time.monotonic()
    pulled = runner([*argv, f"{remote.host}{remote_file}", str(local)])
    seconds = time.monotonic() - start
    runner(remote.shell(f"rm -f {remote_file}"))
    size = local.stat().st_size if local.is_file() else 0
    local.unlink(missing_ok=True)
    if pulled.returncode != 0 or size != megabytes * 1024 * 1024:
        raise RuntimeError(f"probe pull failed ({pulled.returncode}): {pulled.stderr[-300:]}")
    return size / 1e6 / seconds


def watcher_meter(registry: Path, session: str) -> tuple[float, float] | None:
    """(spent, cap) of the watcher's last `poll` line, or None before its first poll."""
    path = registry / f"{session}.jsonl"
    if not path.is_file():
        return None
    for line in reversed(path.read_text().splitlines()):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("event") == "poll" and "spent" in row and "cap" in row:
            return float(row["spent"]), float(row["cap"])
    return None


def projected_cu(
    spent: float, step: int, s_per_step: float, mb_s: float, final_bytes: float
) -> float:
    """CU the job will have used once its last checkpoint is written and pulled here."""
    saves_left = len(range((step // SAVE_EVERY + 1) * SAVE_EVERY, TOTAL_STEPS + 1, SAVE_EVERY))
    seconds = (TOTAL_STEPS - step) * s_per_step + saves_left * SAVE_S + final_bytes / (mb_s * 1e6)
    return spent + RATE_CU_H * seconds / 3600 + SAFETY_CU


def stop_line(cap: float) -> float:
    """Spend at which the watcher stops the session (`over` of cu_watch.py)."""
    return cap - RATE_CU_H * MARGIN_S / 3600


def early_stop(
    status: dict[str, Any], meter: tuple[float, float] | None, mb_s: float
) -> dict[str, Any] | None:
    """The numbers of a mandatory early stop, or None while the job can still finish."""
    step, rate = status["progress"].get("step"), status["progress"].get("s_per_step")
    if meter is None or step is None or rate is None or not DECIDE_FROM <= step < SAVE_EVERY:
        return None
    spent, cap = meter
    final = status["checkpoint_bytes"] or FINAL_BYTES
    projected = projected_cu(spent, step, rate, mb_s, final)
    if projected <= stop_line(cap):
        return None
    return {
        "step": step,
        "s_per_step": round(rate, 4),
        "spent": spent,
        "mb_s": mb_s,
        "projected_cu": round(projected, 2),
        "stop_line": round(stop_line(cap), 3),
    }


def session_running(session: str, registry: Path, colab: Path, runner: Run = run) -> bool:
    """Its watcher is alive and `colab sessions` lists it: only then is ssh safe."""
    out = registry / f"{session}.out"
    if not out.is_file() or any(line.startswith("exit ") for line in out.read_text().splitlines()):
        return False
    listed = runner([str(colab), "sessions"])
    return listed.returncode == 0 and any(
        line.startswith(f"[{session}]") for line in listed.stdout.splitlines()
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("mode", choices=["once", "follow", "probe"])
    parser.add_argument("--session", required=True)
    parser.add_argument("--registry", type=Path, required=True, help="the batch's cu_watch dir")
    parser.add_argument("--dest", type=Path, required=True, help="laptop folder, one dir per job")
    parser.add_argument("--colab", type=Path, default=COLAB)
    parser.add_argument("--every", type=float, default=600.0, help="`follow`: seconds per pull")
    parser.add_argument("--stop-when-done", action="store_true", help="`follow`: then colab stop")
    parser.add_argument("--local-vm", type=Path, help="dry run: a VM work dir on this disk")
    args = parser.parse_args(argv)
    remote = LocalRemote(args.local_vm) if args.local_vm else Remote(args.session, args.colab)
    args.dest.mkdir(parents=True, exist_ok=True)
    lock = (args.dest / f".{args.session}.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX)  # the soft-cap `once` waits for a `follow` pull

    def running() -> bool:
        return bool(args.local_vm) or session_running(args.session, args.registry, args.colab)

    probe_file = args.registry / f"{args.session}.probe.json"
    if args.mode == "probe":
        if not running():
            log(event="refused", session=args.session, reason="watcher exited or not listed")
            return 2
        mb_s = probe(remote, args.dest)
        probe_file.write_text(json.dumps({"mb_per_s": round(mb_s, 2), "time": time.time()}))
        log(event="probe", session=args.session, mb_per_s=round(mb_s, 2))
        if mb_s < SLOW_MB_S:
            log(event="ALERT", message=f"{mb_s:.1f} MB/s < {SLOW_MB_S}: do not start setup")
            return 4
        return 0
    mb_s = json.loads(probe_file.read_text())["mb_per_s"] if probe_file.is_file() else SLOW_MB_S

    while True:
        if not running():
            log(event="refused", session=args.session, reason="watcher exited or not listed")
            return 2
        try:
            statuses = fetch_once(remote, args.dest)
        except (RuntimeError, ValueError, OSError) as error:
            log(event="fetch_error", session=args.session, error=str(error)[-500:])
            statuses = []
        for status in statuses:
            if status["mb_per_s"] is not None and (status["pulled_bytes"] or 0) > 1e9:
                mb_s = status["mb_per_s"]
        if args.mode == "follow":
            meter = watcher_meter(args.registry, args.session)
            for status in statuses:
                stop = early_stop(status, meter, mb_s)
                if stop is None:
                    continue
                code = 0
                if not args.local_vm:
                    code = run([str(args.colab), "stop", "-s", args.session]).returncode
                log(event="EARLY_STOP", session=args.session, stop_code=code, **stop)
                return 3
        done = bool(statuses) and all(s["final"] for s in statuses)
        if done and args.mode == "follow" and args.stop_when_done and not args.local_vm:
            stopped = run([str(args.colab), "stop", "-s", args.session])
            log(event="stopped_when_done", session=args.session, code=stopped.returncode)
        if done or args.mode == "once":
            return 0 if done else 1
        fcntl.flock(lock, fcntl.LOCK_UN)
        time.sleep(args.every)
        fcntl.flock(lock, fcntl.LOCK_EX)


if __name__ == "__main__":
    raise SystemExit(main())

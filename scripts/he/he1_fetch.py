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
While training runs, a log the trainer wrote to after `stage` listed it is expected
(`grown`), not a failed pull; the checkpoint files alone decide `bad_or_missing`.

    python3 scripts/he/he1_fetch.py once   --session S --registry R --dest fwdata/he/runs
    python3 scripts/he/he1_fetch.py follow --session S --registry R --dest fwdata/he/runs \
        --every 600 --stop-when-done

`once` is the CU watcher's soft-cap `--persist` hook. `follow` runs beside the job
from launch: it pulls every new complete checkpoint as it appears, so the cap-time
pull only has the last one left, and ends once training is done and its final
checkpoint is verified here (with `--stop-when-done` it then stops the session, so
the minutes left before the cap are not billed). From step 38000, and once training
has ended, it pulls every FINAL_EVERY_S instead of `--every`.

`probe` times a 1 GB rsync from the VM before setup, so a slow proxy shows at
minute 10, not at the first checkpoint: it writes `<dest>/.<session>.probe.json`
(not in the registry: the guard reads every `*.json` there as a watcher entry) and
exits 4 under SLOW_MB_S.

`follow` also enforces the early stop of docs/he/he-1.md section 7 (mandatory, review
of #109): from step 2200 (the window then spans one validation pass) every pass
projects the CU the job will have used once ckpt_40000 is written and pulled here,

    spent + rate x (steps_left x s_per_step + saves_left x SAVE_S + FINAL_EVERY_S
                    + VERIFY_S + final_bytes / MB/s) / 3600 + SAFETY_CU

Until the first checkpoint, a projection over the watcher's stop line, cap - rate x
margin, stops the session (exit 3); after it, the same projection only raises an
ALERT. `spent` and `cap` are the watcher's last `poll` line, if under METER_STALE_S
old; MB/s is the probe's, replaced by any later checkpoint pull of over 1 GB. A
pass from step 2200 that cannot project (no fresh meter, no s/step, a failed
`stage`) raises an ALERT every time and does not stop: a blind stop wastes what was
spent, while the watcher's cap still bounds the spend (and the guard stops a session
whose watcher stopped beating). A stop at step 2200 costs about 1.3 CU; letting the
cap stop it costs about 17 CU for a ckpt_30000 the plan has no use for.

A train that ended without ckpt_40000 (`stage` says `failed`) is pulled as far as it
got, then its session is stopped (exit 5). Every stop is confirmed: `colab stop` up to
three times until `colab sessions` no longer lists the session, then SIGTERM to its
watcher (which stops the session itself, exit 6 in its `.out`); a stop not confirmed
exits 6 with an ALERT on stderr: the session may still bill.

Never ssh to a session that is not running: `colab ssh -s NAME` creates a session
when NAME is missing. Each pull first checks that the session's watcher is alive (no
`exit` line in `<registry>/<session>.out`) and that `colab sessions` lists the name.
Exit codes: 0 every job's final checkpoint verified here; 1 not (yet); 2 refused;
3 stopped early; 4 probe under SLOW_MB_S; 5 train failed, session stopped; 6 a stop
not confirmed.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

COLAB = Path(
    os.environ.get("COLAB_CLI", "~/project/wm-wam-review/.venv-colab-cli/bin/colab")
).expanduser()
REMOTE_WORK = "/content/da26"
SLOW_MB_S = 6.0  # 2.9 MB/s fills the ~36 min left at cap 18; 6 keeps the early-stop room
# Recipe R1 (configs/models/psi0-stage3.yaml, checked by test_he1_fetch.py).
TOTAL_STEPS, SAVE_EVERY = 40000, 10000
RATE_CU_H = 1.94  # L4 (docs/g0/psi0-finetune-cost.md section 3)
MARGIN_S = 430.0  # scripts/colab/cu_watch.py Timing().margin, checked by the tests
SAVE_S = 60.0  # assumption: one ckpt_<step> write on L4 (31 s on A100, DA-19)
VERIFY_S = 60.0  # assumption: sha256 of the final checkpoint on the VM, then here
FINAL_EVERY_S = 60.0  # pass interval near and after the end: the final pull's lag
NEAR_END = TOTAL_STEPS - 2000
SAFETY_CU = 0.1
FINAL_BYTES = 6.25e9  # model.safetensors of a stage 3 checkpoint (S1-03), until staged
DECIDE_FROM = 2200  # first pass whose rate window spans the validation at step 2000
METER_STALE_S = 300.0  # the watcher polls every 60 s
TIMEOUT_S = 300.0  # any command but a pull
PULL_TIMEOUT_S = 3600.0  # 6.25 GB at 2 MB/s; a cut pull resumes from --partial-dir

Run = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def run(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run a command; a hung one ends as code 124 (as `timeout` does)."""
    limit = PULL_TIMEOUT_S if argv[0] == "rsync" else TIMEOUT_S
    try:
        return subprocess.run(
            list(argv), capture_output=True, text=True, errors="replace", timeout=limit
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(list(argv), 124, "", f"timed out after {limit:.0f} s")


def log(**fields: Any) -> None:
    print(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), **fields}), flush=True)


def alert(message: str, **fields: Any) -> None:
    """An ALERT in the log and on stderr, where the runbook looks."""
    log(event="ALERT", message=message, **fields)
    print(f"ALERT: {message}", file=sys.stderr, flush=True)


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


def in_checkpoint(f: dict[str, Any]) -> bool:
    return "/checkpoints/" in f["path"]


def fetch_once(remote: Remote, dest_root: Path, runner: Run = run) -> list[dict[str, Any]]:
    """Pull what `stage` lists and is not here yet; return one status per job."""
    staged = runner(remote.stage())
    if staged.returncode != 0:
        raise RuntimeError(f"stage failed ({staged.returncode}): {staged.stderr[-500:]}")
    statuses = []
    for job in json.loads(staged.stdout)["jobs"]:
        dest = dest_root / job["job"]
        dest.mkdir(parents=True, exist_ok=True)
        files, running = job["files"], job["train"] == "running"
        have = verified(dest, files, fresh=not running)
        wanted = [f for f in files if have.get(f["path"]) != f["sha256"]]
        start, size = time.monotonic(), sum(f["size"] for f in wanted)
        ckpt_size = sum(f["size"] for f in wanted if in_checkpoint(f))
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
        have = verified(dest, files, fresh=not running)
        bad, grown = [], []
        for f in files:
            if have.get(f["path"]) == f["sha256"]:
                continue
            if running and not in_checkpoint(f) and (dest / f["path"]).is_file():
                grown.append(f["path"])  # a log written to since `stage` listed it
            else:
                bad.append(f["path"])
        ckpt_ok = ckpt_size > 0 and not any(p for p in bad if "/checkpoints/" in p)
        status = {
            "job": job["job"],
            "checkpoint": job["checkpoint"],
            "train": job["train"],
            "files": len(files),
            "bad_or_missing": bad,
            "grown": grown,
            "pulled_bytes": size if wanted and not bad else None,
            "checkpoint_pulled_bytes": ckpt_size if ckpt_ok else None,
            "seconds": round(seconds, 1),
            "mb_per_s": round(ckpt_size / 1e6 / seconds, 2) if ckpt_ok and seconds else None,
            "final": job["train"] == "done"
            and job["checkpoint"] == f"ckpt_{TOTAL_STEPS}"
            and not bad,
            "progress": job.get("progress", {}),
            "checkpoint_bytes": sum(f["size"] for f in files if in_checkpoint(f)),
        }
        (dest / "fetched.json").write_text(json.dumps(status, indent=2))
        log(event="fetched", **status)
        if status["mb_per_s"] is not None and ckpt_size > 1e9 and status["mb_per_s"] < SLOW_MB_S:
            alert(
                f"{status['mb_per_s']} MB/s: the final checkpoint may not arrive before the "
                "cap stop; mount Drive or decide now",
                job=job["job"],
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


def watcher_meter(
    registry: Path, session: str, now: float | None = None
) -> tuple[float, float] | None:
    """(spent, cap) of the watcher's last `poll` line, or None if none is fresh."""
    path = registry / f"{session}.jsonl"
    if not path.is_file():
        return None
    for line in reversed(path.read_text().splitlines()):
        try:
            row = json.loads(line)
            if row.get("event") != "poll":
                continue
            age = (now or time.time()) - datetime.fromisoformat(row["time"]).timestamp()
            fresh = age <= METER_STALE_S
            return (float(row["spent"]), float(row["cap"])) if fresh else None
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    return None


def projected_cu(
    spent: float, step: int, s_per_step: float, mb_s: float, final_bytes: float
) -> float:
    """CU the job will have used once its last checkpoint is written and pulled here."""
    saves_left = len(range((step // SAVE_EVERY + 1) * SAVE_EVERY, TOTAL_STEPS + 1, SAVE_EVERY))
    seconds = (TOTAL_STEPS - step) * s_per_step + saves_left * SAVE_S
    seconds += FINAL_EVERY_S + VERIFY_S + final_bytes / (mb_s * 1e6)
    return spent + RATE_CU_H * seconds / 3600 + SAFETY_CU


def stop_line(cap: float) -> float:
    """Spend at which the watcher stops the session (`over` of cu_watch.py)."""
    return cap - RATE_CU_H * MARGIN_S / 3600


def judge(
    status: dict[str, Any], meter: tuple[float, float] | None, mb_s: float
) -> dict[str, Any] | None:
    """The early-stop verdict of one pass, or None before DECIDE_FROM or after training.

    `stop` (over the line before the first checkpoint), `late` (over it after: an
    ALERT only), `blind` (no projection possible) or `ok`.
    """
    step, rate = status["progress"].get("step"), status["progress"].get("s_per_step")
    if status["train"] != "running" or step is None or step < DECIDE_FROM:
        return None
    if meter is None or rate is None:
        reason = "no fresh watcher poll" if meter is None else "no s/step from metrics.jsonl"
        return {"verdict": "blind", "step": step, "reason": reason}
    spent, cap = meter
    final = status["checkpoint_bytes"] or FINAL_BYTES
    projected = projected_cu(spent, step, rate, mb_s, final)
    over = projected > stop_line(cap)
    return {
        "verdict": ("stop" if step < SAVE_EVERY else "late") if over else "ok",
        "step": step,
        "s_per_step": round(rate, 4),
        "spent": spent,
        "mb_s": mb_s,
        "projected_cu": round(projected, 2),
        "stop_line": round(stop_line(cap), 3),
    }


def listed(session: str, colab: Path, runner: Run = run) -> bool | None:
    """Whether `colab sessions` lists the session; None when the call fails."""
    out = runner([str(colab), "sessions"])
    if out.returncode != 0:
        return None
    return any(line.startswith(f"[{session}]") for line in out.stdout.splitlines())


def session_running(session: str, registry: Path, colab: Path, runner: Run = run) -> bool:
    """Its watcher is alive and `colab sessions` lists it: only then is ssh safe."""
    out = registry / f"{session}.out"
    if not out.is_file() or any(line.startswith("exit ") for line in out.read_text().splitlines()):
        return False
    return listed(session, colab, runner) is True


def stop_session(
    session: str,
    registry: Path,
    colab: Path,
    runner: Run = run,
    sleep: Callable[[float], None] = time.sleep,
    tries: int = 3,
    wait: float = 30.0,
    term_wait: float = 600.0,
) -> bool:
    """Stop the session and confirm `colab sessions` no longer lists it.

    `colab stop` up to `tries` times; then SIGTERM to the session's watcher (pid in
    its registry entry), which stops the session with confirmation and exits 6.
    """
    for attempt in range(1, tries + 1):
        code = runner([str(colab), "stop", "-s", session]).returncode
        sleep(wait)
        gone = listed(session, colab, runner) is False
        log(event="stop", session=session, attempt=attempt, code=code, gone=gone)
        if gone:
            return True
    try:
        pid = int(json.loads((registry / f"{session}.json").read_text())["pid"])
        os.kill(pid, signal.SIGTERM)
        log(event="stop_sigterm", session=session, pid=pid)
    except (OSError, ValueError, KeyError) as error:
        alert(f"{session}: colab stop not confirmed and no watcher to signal ({error})")
        return False
    for _ in range(max(1, int(term_wait // wait))):
        sleep(wait)
        if listed(session, colab, runner) is False:
            return True
    alert(f"{session}: stop not confirmed after SIGTERM to pid {pid}; it may still bill")
    return False


def no_session(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """`colab` of a dry run: every stop works and `sessions` lists nothing."""
    return subprocess.CompletedProcess(list(argv), 0, "", "")


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

    def stopped(code: int) -> int:
        """`code` once the session is confirmed stopped, else 6."""
        if args.local_vm:  # dry run: no session, and `colab` is never called
            confirmed = stop_session(
                args.session, args.registry, args.colab, runner=no_session, sleep=lambda s: None
            )
        else:
            confirmed = stop_session(args.session, args.registry, args.colab)
        return code if confirmed else 6

    probe_file = args.dest / f".{args.session}.probe.json"
    if args.mode == "probe":
        if not running():
            log(event="refused", session=args.session, reason="watcher exited or not listed")
            return 2
        mb_s = probe(remote, args.dest)
        probe_file.write_text(json.dumps({"mb_per_s": round(mb_s, 2), "time": time.time()}))
        log(event="probe", session=args.session, mb_per_s=round(mb_s, 2))
        if mb_s < SLOW_MB_S:
            alert(f"{mb_s:.1f} MB/s < {SLOW_MB_S}: do not start setup")
            return 4
        return 0
    mb_s = json.loads(probe_file.read_text())["mb_per_s"] if probe_file.is_file() else SLOW_MB_S
    last_step = 0

    while True:
        if not running():
            log(event="refused", session=args.session, reason="watcher exited or not listed")
            return 2
        try:
            statuses = fetch_once(remote, args.dest)
        except (RuntimeError, ValueError, OSError) as error:
            log(event="fetch_error", session=args.session, error=str(error)[-500:])
            if args.mode == "follow" and last_step >= DECIDE_FROM:
                alert(f"{args.session}: stage or pull failed past step {last_step}: no projection")
            statuses = []
        for status in statuses:
            if status["mb_per_s"] is not None and (status["checkpoint_pulled_bytes"] or 0) > 1e9:
                mb_s = status["mb_per_s"]
            last_step = max(last_step, status["progress"].get("step") or 0)
        failed = [s["job"] for s in statuses if s["train"] == "failed"]
        if failed:
            alert(f"{args.session}: train failed for {failed}; pulled what was complete")
            return stopped(5) if args.mode == "follow" else 5
        if args.mode == "follow":
            meter = watcher_meter(args.registry, args.session)
            for status in statuses:
                verdict = judge(status, meter, mb_s)
                if verdict is None or verdict["verdict"] == "ok":
                    continue
                if verdict["verdict"] == "stop":
                    log(event="EARLY_STOP", session=args.session, **verdict)
                    return stopped(3)
                alert(f"{args.session}: early-stop projection {verdict['verdict']}", **verdict)
        done = bool(statuses) and all(s["final"] for s in statuses)
        if done and args.mode == "follow" and args.stop_when_done:
            return stopped(0)
        if done or args.mode == "once":
            return 0 if done else 1
        ending = last_step >= NEAR_END or any(s["train"] != "running" for s in statuses)
        fcntl.flock(lock, fcntl.LOCK_UN)
        time.sleep(min(args.every, FINAL_EVERY_S) if ending else args.every)
        fcntl.flock(lock, fcntl.LOCK_EX)


if __name__ == "__main__":
    raise SystemExit(main())

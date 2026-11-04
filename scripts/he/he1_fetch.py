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

Never ssh to a session that is not running: `colab ssh -s NAME` creates a session
when NAME is missing. Each pull first checks that the session's watcher is alive (no
`exit` line in `<registry>/<session>.out`) and that `colab sessions` lists the name.
Exit codes: 0 every job's final checkpoint verified here; 1 not (yet); 2 refused.
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
        self.ssh, self.rsh, self.source = [], "", f"{work}/runs"

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
    parser.add_argument("mode", choices=["once", "follow"])
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

    while True:
        if not running():
            log(event="refused", session=args.session, reason="watcher exited or not listed")
            return 2
        try:
            statuses = fetch_once(remote, args.dest)
        except (RuntimeError, ValueError, OSError) as error:
            log(event="fetch_error", session=args.session, error=str(error)[-500:])
            statuses = []
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

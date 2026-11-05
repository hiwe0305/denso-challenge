"""Run the HE-1 tier 2 eval (F10): both N20 fine-tunes on the 10 dev conditions (DA-26 task 3).

One Colab L4 session serves both checkpoints, one Psi0 server each (VM ports 22085,
22086; about 6.2 GB VRAM each on the 23 GB card, S1-03). The Isaac client runs on
rtx3060, once, over an interleaved copy of the dev set: episode 2i is condition i for
the first arm, 2i + 1 the same condition for the second (Hiếu 5/11/2026: "eval xen
kẽ hai arm theo điều kiện"), so a stop at the cap always leaves complete pairs. The
arm order is the order of the plan's `preliminary` points (V-EGO, then V-NOEGO), the
same at every condition. One client run starts Isaac once (about 4 min, S1-03) instead
of once per episode.

The client cannot pick a server per episode: `eval-decoupled-wbc` takes one host and
port. `route` sits between them on the laptop. SIMPLE's agent resets once per episode
(`agent.reset` before stabilisation; its next `/act` carries `history.reset`), so the
n-th reset is episode n of the interleaved set, and `route` sends it, and every `/act`
after it, to that episode's arm. Before the first episode of each pair it projects
the CU the session will have used once that pair and the shutdown are done:

    spent + rate x (meter age + 2 x episode_s + END_S) / 3600 + SAFETY_CU

and starts the pair only if that stays under the watcher's stop line (18 - 1.94 x
430 / 3600 = 17.77 CU). `spent` is the watcher's last `poll` (fresh within 300 s;
otherwise it waits for one, then refuses). episode_s is PRIOR_EPISODE_S (33 min, the
mean of S1-03's 10-episode run on a shared rtx3060; one failed episode on an idle box
took 24.6 min) or 1.2 x the longest episode seen, whichever is more. Inside a pair
nothing is refused. A refused pair stops the client container and ends the run.

    python3 scripts/he/he1_eval.py interleave --src fwdata/he/dev-eval-v1-l0n10 \
        --out fwdata/he/eval-n20-interleaved
    python3 scripts/he/he1_eval.py preflight --set fwdata/he/eval-n20-interleaved
    python3 scripts/he/he1_eval.py probe  --session S --registry R --dest fwdata/he/runs
    python3 scripts/he/he1_eval.py upload --session S --registry R --runs fwdata/he/runs
    python3 scripts/he/he1_eval.py run    --session S --registry R --dest fwdata/he/runs \
        --set fwdata/he/eval-n20-interleaved
    python3 scripts/he/he1_eval.py results --dest fwdata/he/runs

`probe` times 1 GB down (he1_fetch.py's probe) and PUSH_MB up: the upload of the two
checkpoints (2 x 6.25 GB) is the largest cost before the first episode. `upload`
sends what a server reads (`argv.txt`, `run_config.json`, `ckpt_40000/model.safetensors`:
the normalisation bounds are inside run_config.json) with an `expected.json` of the
laptop's verified sha256; `he1_colab.py serve` checks them before it loads anything.

`preflight` checks rtx3060 read-only before the session starts (MemAvailable >= client +
16 GB, Hiếu's rule; fw/ and the same interleaved set in place; no client running; and
the box reserved for the eval, Hiếu 5/11/2026: no other denso process and no
`pol.train_stage_a`, see `other_jobs`).

`run` holds the session's single SSH connection for the forward (laptop 22285, 22286
to the VM's servers), checks that each server's /info run_dir is its arm's fine-tune,
forwards rtx3060's CLIENT_PORT back to `route` (ssh -R), checks rtx3060's MemAvailable
again, starts the client there under nohup setsid and a systemd-run MemoryMax scope
(scripts/he/he1_client.sh; docker --memory is the real cap of the container), and
waits for it. It stops the client itself when no request comes (FIRST_ACT_S after the
launch, ACT_IDLE_S after the last one) or the meter nears the stop line. Then, on
every way out once the session was seen running (refusal, failure, exception,
SIGTERM/SIGINT/SIGHUP): it closes the forwards, pulls the VM's eval job (server logs,
vm-logs) with `he1_fetch.py once`, stops the session with confirmation, and only then
pulls the client folder from rtx3060 (no CU) and writes `results.jsonl`. Everything
for Agent QA/QC lands in `<dest>/da26-t2-eval-n20/`: route.jsonl (every request:
episode, arm, latency, reply; every row tagged with the run; an earlier run's log is
kept as route-<run>.jsonl), client/ (client-<run>.log, eval/<run>/eval_stats.txt,
videos/<run>/, exit), server-*.log, vm-logs/, results.jsonl (the last run only).

Exit codes of `run`: 0 every planned pair ran; 3 a pair refused by the CU rule (the
pairs before it are complete); 4 rtx3060 short of RAM, client not started; 5 the
client, a server or a forward failed, or the run raised; 6 the session stop was not
confirmed (it may still bill); 7 a signal ended the run; 8 rtx3060 runs another job,
client not started. The session is stopped in every case but 6.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from he1_fetch import (  # noqa: E402
    COLAB,
    METER_STALE_S,
    RATE_CU_H,
    SAFETY_CU,
    Remote,
    Run,
    alert,
    log,
    probe,
    run,
    session_running,
    stop_line,
    stop_session,
)

REPO = HERE.parents[1]
PLAN = REPO / "configs/runplans/he/he-1.yaml"
EVAL_JOB = "da26-t2-eval-n20"  # Colab session, runs/<job>; ledger job_da26_t2_eval_isaac_n20
CAP = 18.0  # Hiếu 5/11/2026: "Nâng lên 18 + giữ rtx3060" (was 16; stop line 17.77)
VM_PORTS = (22085, 22086)  # one Psi0 server per arm on the VM, in arm order
LAPTOP_PORTS = (22285, 22286)  # laptop ends of the forward to VM_PORTS
ROUTE_PORT = 22185  # `route` on the laptop
CLIENT_PORT = 22095  # rtx3060 end of the reverse forward; 22085 is other stories' local server
# 33 min: S1-03's 10-episode mujoco_isaac run on rtx3060 shared with DA-34 and DA-35
# (docs/g0/psi0-eval.md); one failed episode on an idle box took 24.6 min (S1-03 3.4.1).
PRIOR_EPISODE_S = 1980.0
BOUND_FACTOR = 1.2  # an episode may take this much longer than the longest seen
END_S = 300.0  # assumption: client exit, forward close, VM log pull, a confirmed stop
METER_WAIT_S = 600.0  # a pair start waits this long for a fresh watcher poll, then refuses
POLL_S = 60.0  # wait_client: one look at rtx3060 per minute
FIRST_ACT_S = 1800.0  # launch to first request: kit cache copy, image, Isaac start (~4 min)
ACT_IDLE_S = 900.0  # no request this long once running: hung (> reset + METER_WAIT_S)
EXIT_WAIT_S = 600.0  # after a stop, how long he1_client.sh has to move files and write `exit`
RETRY_S = 180.0  # `forward` retries connection errors this long: a tunnel restart + connect
PUSH_MB = 256  # upload probe
CLIENT_GB = 20  # docker --memory of the client (S1-03: peak 15.75 GiB with page cache)
RAM_MARGIN_GB = 16  # Hiếu 3/11/2026: MemAvailable >= job + 16 GB before starting
CKPT = "checkpoints/ckpt_40000/model.safetensors"
SERVED = ("argv.txt", "run_config.json", CKPT)  # what serve_psi0_simple reads of a run dir
RTX = "rtx3060"
RTX_WORK = "denso-da26"  # ~/denso-da26 on rtx3060


@dataclass(frozen=True)
class Slot:
    """One episode of the interleaved set."""

    episode: int  # index in the interleaved set, the client's n-th episode
    pair: int  # condition index in the dev set, 0-based
    seed: int  # dev seed of the condition
    point: str  # VARIANT/SET/SEED
    job: str  # the fine-tune whose checkpoint serves it
    port: int  # VM port of that server

    @property
    def first(self) -> bool:
        return self.episode % 2 == 0


def ft_job(variant: str, demo_set: str, seed: int) -> str:
    """he1_colab.py's job_id of a point, without importing its training stack."""
    return f"da26-t2-ft-{variant.lower().replace('-', '')}-{demo_set.lower()}-s{seed}"


def arms(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """The plan's preliminary points in plan order: the arm order at every condition."""
    points = [p for p in plan["points"] if p["phase"] == "preliminary"]
    if len(points) != len(VM_PORTS):
        raise SystemExit(f"{len(points)} preliminary points; the eval serves {len(VM_PORTS)}")
    return points


def pair_order(plan: dict[str, Any]) -> list[Slot]:
    """c0:arm0, c0:arm1, c1:arm0, ...: interleaved by condition, arms in plan order."""
    seeds = plan["eval"]["main"]["seeds"]
    slots: list[Slot] = []
    for pair, seed in enumerate(range(seeds["start"], seeds["stop"])):
        for k, p in enumerate(arms(plan)):
            point = f"{p['variant']}/{p['demo_set']}/{p['seed']}"
            job = ft_job(p["variant"], p["demo_set"], p["seed"])
            slots.append(Slot(len(slots), pair, seed, point, job, VM_PORTS[k]))
    return slots


def load_plan(path: Path = PLAN) -> dict[str, Any]:
    import yaml

    plan: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return plan


def config_sha256(value: Any) -> str:
    """scripts/he/dev_eval_set.py's conditions hash: compact JSON, insertion order."""
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def interleave(src: Path, out: Path, plan: dict[str, Any]) -> list[Slot]:
    """Write the dev set with every condition twice, in `pair_order`, as LeRobot v2.1.

    `src` is the dev set as `dev_eval_set.py` wrote it (`conditions.jsonl` and
    `simple/<task>/dr-level-0/`). The rows must hash to the plan's conditions_sha256,
    and each episode's `environment_config` must be its row's: the client resets from
    that config, so the copy is the same scene. Only `episode_index` and `index` (and
    their per-episode stats) change; frames and videos are copied as they are.
    """
    import pyarrow as pa  # type: ignore[import-untyped]
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    main = plan["eval"]["main"]
    rows = [json.loads(line) for line in (src / "conditions.jsonl").read_text().splitlines()]
    if config_sha256(rows) != main["conditions_sha256"]:
        raise SystemExit(f"{src}/conditions.jsonl is not the plan's {main['conditions_sha256']}")
    task = plan["task"]["id"]
    level = src / "simple" / task / "dr-level-0"
    meta = level / "meta"
    episodes = [json.loads(line) for line in (meta / "episodes.jsonl").read_text().splitlines()]
    stats = [json.loads(line) for line in (meta / "episodes_stats.jsonl").read_text().splitlines()]
    for i, row in enumerate(rows):
        if json.loads(episodes[i]["environment_config"]) != row["environment_config"]:
            raise SystemExit(f"episode {i} of {level} is not condition {i} (seed {row['seed']})")
    info = json.loads((meta / "info.json").read_text())
    videos = [k for k, f in info["features"].items() if f["dtype"] == "video"]
    order = pair_order(plan)
    if len(rows) * len(VM_PORTS) != len(order):
        raise SystemExit(f"{len(rows)} conditions, the plan's seeds give {len(order)} episodes")
    target = out / "simple" / task / "dr-level-0"
    if out.exists():
        raise SystemExit(f"{out} exists; an interleaved set is written once")
    (target / "meta").mkdir(parents=True)
    new_episodes, new_stats, offset = [], [], 0
    for slot in order:
        i, k = slot.pair, slot.episode
        table = pq.read_table(level / f"data/chunk-000/episode_{i:06d}.parquet")
        n = table.num_rows
        index = list(range(offset, offset + n))
        table = table.set_column(
            table.schema.get_field_index("episode_index"), "episode_index", pa.array([k] * n)
        )
        table = table.set_column(table.schema.get_field_index("index"), "index", pa.array(index))
        (target / "data/chunk-000").mkdir(parents=True, exist_ok=True)
        pq.write_table(table, target / f"data/chunk-000/episode_{k:06d}.parquet")
        for key in videos:
            dest = target / f"videos/chunk-000/{key}/episode_{k:06d}.mp4"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(level / f"videos/chunk-000/{key}/episode_{i:06d}.mp4", dest)
        new_episodes.append({**episodes[i], "episode_index": k})
        row_stats = dict(stats[i]["stats"])
        for name, values in (("episode_index", [k] * n), ("index", index)):
            mean = sum(values) / n
            std = (sum((v - mean) ** 2 for v in values) / n) ** 0.5
            row_stats[name] = {
                "min": [min(values)],
                "max": [max(values)],
                "mean": [mean],
                "std": [std],
                "count": [n],
            }
        new_stats.append({"episode_index": k, "stats": row_stats})
        offset += n
    info.update(
        total_episodes=len(order),
        total_frames=offset,
        total_videos=len(order) * len(videos),
        splits={"train": f"0:{len(order)}"},
    )
    (target / "meta/info.json").write_text(json.dumps(info, indent=4))
    for name in ("tasks.jsonl", "modality.json"):
        if (meta / name).exists():
            shutil.copyfile(meta / name, target / "meta" / name)
    for name, lines in (("episodes.jsonl", new_episodes), ("episodes_stats.jsonl", new_stats)):
        (target / "meta" / name).write_text("".join(json.dumps(x) + "\n" for x in lines))
    (out / "order.json").write_text(
        json.dumps(
            {
                "conditions_sha256": main["conditions_sha256"],
                "source": str(src),
                "slots": [asdict(s) for s in order],
            },
            indent=1,
        )
    )
    return order


# --- the CU rule -------------------------------------------------------------


def meter(registry: Path, session: str) -> tuple[float, float, float] | None:
    """(poll time, spent, cap) of the watcher's last `poll` line, or None."""
    path = registry / f"{session}.jsonl"
    if not path.is_file():
        return None
    for line in reversed(path.read_text().splitlines()):
        try:
            row = json.loads(line)
            if row.get("event") == "poll":
                at = datetime.fromisoformat(row["time"]).timestamp()
                return at, float(row["spent"]), float(row["cap"])
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    return None


def episode_bound(seen: Sequence[float]) -> float:
    """Seconds one episode may take: PRIOR_EPISODE_S, or more after a slow episode."""
    return max(PRIOR_EPISODE_S, BOUND_FACTOR * max(seen, default=0.0))


def pair_verdict(
    reading: tuple[float, float, float] | None, now: float, seen: Sequence[float]
) -> dict[str, Any]:
    """Whether the next pair may start: `start`, `refuse` (over the line) or `blind`."""
    if reading is None or now - reading[0] > METER_STALE_S:
        return {"verdict": "blind", "meter_age_s": None if reading is None else now - reading[0]}
    at, spent, cap = reading
    if cap != CAP:  # the line is this driver's cap, never the watcher's row
        return {"verdict": "refuse", "why": f"watcher cap {cap} is not {CAP}", "cap": cap}
    pair_s = 2 * episode_bound(seen)
    projected = spent + RATE_CU_H * (max(0.0, now - at) + pair_s + END_S) / 3600 + SAFETY_CU
    line = stop_line(CAP)
    return {
        "verdict": "start" if projected <= line else "refuse",
        "spent": spent,
        "cap": cap,
        "stop_line": round(line, 3),
        "projected_cu": round(projected, 3),
        "pair_s": round(pair_s),
        "meter_age_s": now - at,
    }


def pairs_that_fit(
    spent_at_first: float, episode_s: float, cap: float = CAP, most: int = 10
) -> int:
    """How many pairs the rule starts if every episode takes `episode_s` (planning). The
    rule projects each pair with episode_bound, never less than a full-budget failure, so
    faster episodes save CU but do not loosen the gate."""
    spent, n = spent_at_first, 0
    bound = episode_bound([episode_s])
    while n < most and spent + RATE_CU_H * (2 * bound + END_S) / 3600 + SAFETY_CU <= stop_line(cap):
        spent += RATE_CU_H * 2 * episode_s / 3600
        n += 1
    return n


def waiting_gate(
    reading: Callable[[], tuple[float, float, float] | None],
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> Callable[[Slot, Sequence[float]], dict[str, Any]]:
    """`pair_verdict` on the watcher's meter; a blind meter is waited for METER_WAIT_S."""

    def gate(slot: Slot, seen: Sequence[float]) -> dict[str, Any]:
        end = clock() + METER_WAIT_S
        while True:
            verdict = pair_verdict(reading(), clock(), seen)
            if verdict["verdict"] != "blind" or clock() > end:
                return verdict
            sleep(15)

    return gate


# --- route -------------------------------------------------------------------


class Router:
    """Which arm serves each request; the CU rule at every pair start."""

    def __init__(
        self,
        order: Sequence[Slot],
        gate: Callable[[Slot, Sequence[float]], dict[str, Any]],
        write: Callable[[dict[str, Any]], None],
        on_refuse: Callable[[], None],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.order, self.gate, self.write, self.on_refuse = list(order), gate, write, on_refuse
        self.clock = clock
        self.episode = -1  # no reset seen yet
        self.started: list[float] = []
        self.refused: dict[str, Any] | None = None
        self.last_request: float | None = None  # wait_client's liveness signal
        self.lock = threading.Lock()

    def touch(self) -> None:
        self.last_request = self.clock()

    def seen(self) -> list[float]:
        return [b - a for a, b in zip(self.started, self.started[1:], strict=False)]

    def slot(self, body: dict[str, Any]) -> Slot | None:
        """The slot this `/act` belongs to, or None when it must not be served."""
        with self.lock:
            self.touch()
            if self.refused is not None:
                return None
            reset = bool((body.get("history") or {}).get("reset"))
            if not reset:
                if self.episode < 0:
                    self.refuse({"reason": "an /act before any reset"})
                    return None
                return self.order[self.episode]
            now = self.clock()
            nxt = self.episode + 1
            if nxt >= len(self.order):
                self.refuse({"reason": f"reset {nxt + 1} of a {len(self.order)}-episode plan"})
                return None
            slot = self.order[nxt]
            if slot.first:
                verdict = self.gate(
                    slot, self.seen() + ([now - self.started[-1]] if self.started else [])
                )
                self.write({"event": "pair_gate", "pair": slot.pair, **verdict})
                if verdict["verdict"] != "start":
                    self.refuse({"reason": "cu_rule", "pair": slot.pair, **verdict})
                    return None
            self.episode = nxt
            self.started.append(now)
            self.write({"event": "episode_start", **asdict(slot)})
            return slot

    def refuse(self, why: dict[str, Any]) -> None:
        self.refused = why
        self.write({"event": "refused", **why})
        self.on_refuse()

    def finish(self) -> None:
        """The client is done: close the last episode's timing."""
        with self.lock:
            if self.started:
                self.write(
                    {
                        "event": "last_episode_end",
                        "episode": self.episode,
                        "seconds": round(self.clock() - self.started[-1], 1),
                    }
                )


def forward(
    port: int,
    method: str,
    path: str,
    body: bytes | None,
    retry_s: float = RETRY_S,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[int, bytes]:
    """One request to a server on the laptop's forward.

    Connection errors (refused, reset, closed: the ssh forward restarting) are retried
    for `retry_s`; SIMPLE's client raises on any reply but 200 and has no retry of its
    own. A timeout is not retried: the server got the request and did not answer."""
    end = time.monotonic() + retry_s
    while True:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=600)
        try:
            headers = {"Content-Type": "application/json"} if body is not None else {}
            conn.request(method, path, body=body, headers=headers)
            reply = conn.getresponse()
            return reply.status, reply.read()
        except (ConnectionError, http.client.HTTPException) as error:
            if time.monotonic() >= end:
                raise ConnectionError(f"127.0.0.1:{port} {method} {path}: {error!r}") from error
            sleep(5)
        finally:
            conn.close()


def serve_routes(
    router: Router, ports: dict[int, int], listen: int, write: Callable[[dict[str, Any]], None]
) -> ThreadingHTTPServer:
    """The HTTP side of `route`: GET to the first arm's server, POST /act per `router`."""
    first = next(iter(ports.values()))

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status: int, data: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            try:
                self.reply(*forward(first, "GET", self.path, None))
            except OSError as error:
                self.reply(502, json.dumps({"status": f"upstream: {error}"}).encode())

        def do_POST(self) -> None:  # noqa: N802
            data = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                body = json.loads(data)
            except ValueError:
                self.reply(400, b'{"status": "not json"}')
                return
            slot = router.slot(body)
            if slot is None:
                self.reply(
                    503, json.dumps({"status": "refused", **(router.refused or {})}).encode()
                )
                return
            start = time.monotonic()
            try:
                status, reply = forward(ports[slot.port], "POST", self.path, data)
            except OSError as error:
                write({"event": "upstream_error", "episode": slot.episode, "error": str(error)})
                self.reply(502, json.dumps({"status": f"upstream: {error}"}).encode())
                return
            finally:
                router.touch()
            has_action = b'"action"' in reply[:4096]
            write(
                {
                    "event": "act",
                    "episode": slot.episode,
                    "job": slot.job,
                    "reset": bool((body.get("history") or {}).get("reset")),
                    "seconds": round(time.monotonic() - start, 3),
                    "status": status,
                    "action": has_action,
                    "bytes_in": len(data),
                    "bytes_out": len(reply),
                }
            )
            self.reply(status, reply)

        def log_message(self, *args: Any) -> None:
            pass

    return ThreadingHTTPServer(("127.0.0.1", listen), Handler)


class JsonLog:
    """Append-only JSON lines; with `run`, every row carries that run id."""

    def __init__(self, path: Path, run: str | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.run, self.lock = path, run, threading.Lock()

    def __call__(self, row: dict[str, Any]) -> None:
        head = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            **({"run": self.run} if self.run else {}),
        }
        with self.lock, self.path.open("a") as f:
            f.write(json.dumps({**head, **row}) + "\n")


# --- probe, upload -----------------------------------------------------------


def probe_push(remote: Remote, dest: Path, megabytes: int = PUSH_MB, runner: Run = run) -> float:
    """MB/s of one rsync of `megabytes` of random data from `dest` to the VM."""
    with_tmp = dest / f".push-{remote.session}.bin"
    with with_tmp.open("wb") as f:
        for _ in range(megabytes):
            f.write(os.urandom(1 << 20))
    target = f"{remote.work}/push.bin"
    argv = ["rsync", "-a", *(["-e", remote.rsh] if remote.rsh else [])]
    start = time.monotonic()
    pushed = runner([*argv, str(with_tmp), f"{remote.host}{target}"])
    seconds = time.monotonic() - start
    with_tmp.unlink(missing_ok=True)
    runner(remote.shell(f"rm -f {shlex.quote(target)}"))
    if pushed.returncode != 0:
        raise RuntimeError(f"push probe failed ({pushed.returncode}): {pushed.stderr[-300:]}")
    return megabytes * 1024 * 1024 / 1e6 / seconds


def run_dir(runs: Path, job: str) -> Path:
    """The Psi0 run dir of a fine-tune on the laptop: runs/<job>/psi0/finetune/<run>."""
    found = sorted((runs / job / "psi0" / "finetune").glob("*"))
    if len(found) != 1:
        raise SystemExit(f"{runs / job}: expected one Psi0 run dir, found {len(found)}")
    return found[0]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


def expected(runs: Path, job: str) -> dict[str, Any]:
    """What `serve` checks: each served file's sha256.

    From he1_fetch's verified cache (`.hashes.json`: path -> {"stamp": [size, mtime],
    "sha256": hex}) when the entry's stamp is the file's; computed here otherwise."""
    src = run_dir(runs, job)
    cache_path = runs / job / ".hashes.json"
    cache = json.loads(cache_path.read_text()) if cache_path.is_file() else {}
    files = {}
    for rel in SERVED:
        path = src / rel
        entry = cache.get(str(path.relative_to(runs / job)))
        entry = entry if isinstance(entry, dict) else {}
        stamp = [path.stat().st_size, path.stat().st_mtime]
        digest = entry.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or entry.get("stamp") != stamp:
            digest = file_sha256(path)
            log(event="hash_computed", job=job, file=rel)
        files[rel] = digest
    return {"job": job, "run": src.name, "files": files}


def upload(
    remote: Remote, runs: Path, jobs: Sequence[str], runner: Run = run
) -> list[dict[str, Any]]:
    """Send each job's served files to `<work>/serve/<job>/<run>/` with its expected.json."""
    rows = []
    for job in jobs:
        want = expected(runs, job)
        src = run_dir(runs, job)
        listing = runs / job / ".served"
        listing.write_text("".join(f"{rel}\n" for rel in SERVED))
        (runs / job / "expected.json").write_text(json.dumps(want, indent=1))
        dest = f"{remote.work}/serve/{job}"
        made = runner(remote.shell(f"mkdir -p {shlex.quote(dest + '/' + src.name)}"))
        if made.returncode != 0:
            raise RuntimeError(f"{job}: no target dir on the VM: {made.stderr[-300:]}")
        argv = [
            "rsync",
            "-a",
            "--partial-dir=.rsync-partial",
            *(["-e", remote.rsh] if remote.rsh else []),
        ]
        size = sum((src / rel).stat().st_size for rel in SERVED)
        start = time.monotonic()
        sent = runner(
            [*argv, f"--files-from={listing}", f"{src}/", f"{remote.host}{dest}/{src.name}/"]
        )
        sent2 = runner(
            [*argv, str(runs / job / "expected.json"), f"{remote.host}{dest}/expected.json"]
        )
        seconds = time.monotonic() - start
        if sent.returncode != 0 or sent2.returncode != 0:
            raise RuntimeError(f"{job}: upload failed: {(sent.stderr or sent2.stderr)[-300:]}")
        row = {
            "event": "uploaded",
            "job": job,
            "bytes": size,
            "seconds": round(seconds, 1),
            "mb_per_s": round(size / 1e6 / seconds, 2) if seconds else None,
        }
        log(**row)
        rows.append(row)
    return rows


# --- run ---------------------------------------------------------------------


RTX_SSH = ("ssh", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=15")


def rtx(command: str, runner: Run = run) -> subprocess.CompletedProcess[str]:
    done: subprocess.CompletedProcess[str] = runner([*RTX_SSH, RTX, command])
    return done


def mem_available_gb(runner: Run = run) -> float | None:
    out = rtx("grep MemAvailable /proc/meminfo", runner)
    try:
        return int(out.stdout.split()[1]) / 1024 / 1024 if out.returncode == 0 else None
    except (IndexError, ValueError):
        return None


def client_command(tag: str, episodes: int) -> str:
    """Start the client on rtx3060, detached, in a MemoryMax scope.

    The scope caps the launcher; the container runs under dockerd, outside it, and has
    its own cap (docker --memory, he1_client.sh)."""
    inner = (
        f"systemd-run --user --scope --quiet -p MemoryMax={CLIENT_GB + 4}G -p MemorySwapMax=0 "
        f"bash fw/scripts/he/he1_client.sh --set sets/interleaved --tag {shlex.quote(tag)} "
        f"--episodes {episodes} --port {CLIENT_PORT}"
    )
    return (
        f"cd ~/{RTX_WORK} && nohup setsid bash -c {shlex.quote(inner)} "
        f"< /dev/null > runs/{EVAL_JOB}/client-launch-{shlex.quote(tag)}.log 2>&1 &"
    )


def other_jobs(runner: Run = run) -> tuple[list[str], list[str]] | None:
    """What else runs on rtx3060: (blocking, noted), or None when it cannot be read.

    The box is reserved for the eval's client (Hiếu 5/11/2026): any other denso process
    blocks, and so does `pol.train_stage_a` (Hiếu's other project; the parent session
    asks him). Containers that are not the client are noted, not blocking. The patterns
    are bracketed so the remote shell running them does not match itself."""
    out = rtx(
        "pgrep -af '[d]enso'; echo ---; pgrep -af '[p]ol[.]train_stage_a'; echo ---; "
        "docker ps --format '{{.Names}}'",
        runner,
    )
    parts = out.stdout.split("---\n")
    if out.returncode != 0 or len(parts) != 3:
        return None
    denso, pol, containers = ([x for x in part.splitlines() if x.strip()] for part in parts)
    noted = [f"container {c}" for c in containers if c != "da26-eval-client"]
    return denso + pol, noted


def preflight(set_dir: Path, runner: Run = run) -> int:
    """Read-only check that rtx3060 can take the client; run it before the eval session.

    0 ready; 4 MemAvailable under client + 16 GB (Hiếu's rule); 6 another job on the box
    (`other_jobs`); 5 anything else: box unreachable, no ~/denso-da26/fw, a different
    interleaved set, a client still running."""
    need = CLIENT_GB + RAM_MARGIN_GB
    free = mem_available_gb(runner)
    others = other_jobs(runner)
    base = f"~/{RTX_WORK}"
    out = rtx(
        f"test -f {base}/fw/scripts/he/he1_client.sh && echo client; "
        f"sha256sum {base}/sets/interleaved/order.json 2>/dev/null | cut -d' ' -f1; "
        "docker ps -q -f name=da26-eval-client | wc -l",
        runner,
    )
    lines = out.stdout.split() if out.returncode == 0 else []
    problems = []
    if free is None or out.returncode != 0:
        problems.append("rtx3060 unreachable")
    else:
        if free < need:
            problems.append(f"MemAvailable {free:.1f} GB < {need} GB")
        if "client" not in lines:
            problems.append(f"no {base}/fw/scripts/he/he1_client.sh (git archive of master)")
        if file_sha256(set_dir / "order.json") not in lines:
            problems.append(f"{base}/sets/interleaved/order.json is not {set_dir}/order.json")
        if lines[-1:] != ["0"]:
            problems.append("a da26-eval-client container is running")
    if others is None:
        problems.append("could not list rtx3060's other jobs")
    busy, noted = others or ([], [])
    log(
        event="preflight",
        mem_available_gb=free,
        need_gb=need,
        problems=problems,
        other_jobs=busy,
        noted=noted,
    )
    for problem in problems + [f"rtx3060 is not reserved: {job}" for job in busy]:
        alert(f"preflight: {problem}")
    for note in noted:
        alert(f"preflight: also on rtx3060 (not blocking): {note}")
    if free is not None and free < need:
        return 4
    if busy:
        return 6
    return 5 if problems else 0


class Tunnel:
    """An ssh -N forward kept up while `run` lives; restarted when it drops."""

    def __init__(self, argv: list[str], write: Callable[[dict[str, Any]], None], name: str) -> None:
        self.argv, self.write, self.name = argv, write, name
        self.proc: subprocess.Popen[bytes] | None = None
        self.stopping = False
        self.thread = threading.Thread(target=self.keep, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def keep(self) -> None:
        while not self.stopping:
            self.proc = subprocess.Popen(self.argv, stdin=subprocess.DEVNULL)
            self.write({"event": "tunnel_up", "tunnel": self.name, "pid": self.proc.pid})
            code = self.proc.wait()
            if not self.stopping:
                self.write({"event": "tunnel_down", "tunnel": self.name, "code": code})
                time.sleep(15)

    def stop(self) -> None:
        self.stopping = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


def wait_health(
    port: int,
    deadline_s: float = 120.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    end = clock() + deadline_s
    while clock() < end:
        try:
            status, data = forward(port, "GET", "/health", None, retry_s=0)
            if status == 200 and b"ok" in data:
                return True
        except OSError:
            pass
        sleep(5)
    return False


def served_run_dir(port: int) -> str | None:
    """The run_dir the server behind a laptop port reports (`GET /info`), or None."""
    try:
        status, data = forward(port, "GET", "/info", None, retry_s=0)
        return str(json.loads(data)["run_dir"]) if status == 200 else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def open_route_log(job: Path, tag: str) -> JsonLog:
    """route.jsonl of this run, every row tagged with it; an earlier run's file is kept
    as route-<its run>.jsonl, so two runs never share one log."""
    path = job / "route.jsonl"
    if path.exists():
        first = path.read_text().split("\n", 1)[0]
        try:
            earlier = str(json.loads(first).get("run") or "")
        except ValueError:
            earlier = ""
        kept = job / f"route-{earlier or int(path.stat().st_mtime)}.jsonl"
        if kept.exists():
            raise SystemExit(f"{kept} exists; move it away before a new run")
        path.rename(kept)
    return JsonLog(path, run=tag)


def results(dest: Path) -> list[dict[str, Any]]:
    """One row per episode of the last client run: its tag's rows and files only."""
    job = dest / EVAL_JOB
    order = [Slot(**s) for s in json.loads((job / "order.json").read_text())["slots"]]
    route = job / "route.jsonl"
    events = [json.loads(x) for x in route.read_text().splitlines() if x.strip()]
    launches = [e for e in events if e["event"] == "client_launch"]
    rows: list[dict[str, Any]] = []
    if launches:
        tag = launches[-1]["tag"]
        events = [e for e in events if e.get("run", tag) == tag]
        stats_files = sorted((job / "client" / "eval" / tag).rglob("eval_stats.txt"))
        if len(stats_files) > 1:
            raise SystemExit(f"{len(stats_files)} eval_stats.txt under client/eval/{tag}")
        stats = {}
        for line in stats_files[0].read_text().splitlines() if stats_files else []:
            name, _, value = line.strip().partition(": ")
            if name.startswith("episode_"):
                stats[int(name.removeprefix("episode_"))] = value.strip() == "True"
        starts = {e["episode"]: e["time"] for e in events if e["event"] == "episode_start"}
        acts: dict[int, list[float]] = {}
        for e in events:
            if e["event"] == "act":
                acts.setdefault(e["episode"], []).append(e["seconds"])
        for slot in order:
            if slot.episode not in starts:
                continue
            latency = sorted(acts.get(slot.episode, []))
            rows.append(
                {
                    **asdict(slot),
                    "run": tag,
                    "success": stats.get(slot.episode),
                    "started": starts[slot.episode],
                    "act_calls": len(latency),
                    "act_p50_s": latency[len(latency) // 2] if latency else None,
                    "act_max_s": latency[-1] if latency else None,
                    "complete_pair": all(o.episode in stats for o in order if o.pair == slot.pair),
                }
            )
    (job / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return rows


@dataclass
class Env:
    """What `run_eval` reaches outside this process; the tests replace each part."""

    runner: Run  # ssh to rtx3060, rsync from it
    running: Callable[[], bool]  # the watcher is alive and lists the session
    stop: Callable[[], bool]  # stop the session; True once confirmed
    fetch: Callable[[], subprocess.CompletedProcess[str]]  # he1_fetch.py once
    reading: Callable[[], tuple[float, float, float] | None]  # the watcher's meter
    tunnel: Callable[[list[str], Callable[[dict[str, Any]], None], str], Any] = Tunnel
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.time
    laptop_ports: tuple[int, ...] = LAPTOP_PORTS
    route_port: int = ROUTE_PORT


def session_env(args: argparse.Namespace) -> Env:
    def fetch() -> subprocess.CompletedProcess[str]:
        return run(
            [
                *(sys.executable, str(HERE / "he1_fetch.py"), "once"),
                *("--session", args.session, "--registry", str(args.registry)),
                *("--dest", str(args.dest), "--colab", str(args.colab)),
            ]
        )

    return Env(
        runner=run,
        running=lambda: session_running(args.session, args.registry, args.colab),
        stop=lambda: stop_session(args.session, args.registry, args.colab),
        fetch=fetch,
        reading=lambda: meter(args.registry, args.session),
    )


class Interrupted(Exception):
    """SIGTERM, SIGINT or SIGHUP during `run`: the session is stopped all the same."""


def on_signal(signum: int, frame: Any) -> None:
    raise Interrupted(signal.Signals(signum).name)


def run_eval(args: argparse.Namespace, env: Env | None = None) -> int:
    """The eval, from a running session with both servers up to a confirmed stop.

    Once the session is seen running, every way out (a refusal, a failure, an
    exception, a signal) goes through `finish`, which stops the session."""
    env = env or session_env(args)
    plan = load_plan()
    order = [Slot(**s) for s in json.loads((args.set / "order.json").read_text())["slots"]]
    if order != pair_order(plan):
        raise SystemExit(f"{args.set}/order.json is not this plan's pair order")
    if not env.running():
        raise SystemExit(f"{args.session}: watcher gone or not listed; nothing started")
    job = args.dest / EVAL_JOB
    job.mkdir(parents=True, exist_ok=True)
    tag = f"{EVAL_JOB}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(env.clock()))}"
    signals = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)}
    for s in signals:
        signal.signal(s, on_signal)
    state: dict[str, Any] = {"server": None, "tunnels": [], "launched": False, "exited": False}
    write = JsonLog(job / "route.jsonl")  # replaced at once below
    router = Router(order, lambda s, seen: {"verdict": "refuse"}, write, lambda: None)
    code = 5
    try:
        write = open_route_log(job, tag)
        shutil.copyfile(args.set / "order.json", job / "order.json")
        stopped = threading.Event()

        def stop_client() -> None:
            rtx("docker stop -t 30 da26-eval-client", env.runner)
            stopped.set()

        router = Router(
            order,
            waiting_gate(env.reading, env.clock, env.sleep),
            write,
            lambda: threading.Thread(target=stop_client, daemon=True).start(),
            clock=env.clock,
        )
        code = drive(args, env, order, router, write, tag, stopped, stop_client, state)
    except Interrupted as why:
        alert(f"run interrupted by {why}; stopping the client and the session")
        write({"event": "interrupted", "signal": str(why)})
        code = 7
    except Exception as error:  # noqa: BLE001 - whatever failed, the session is stopped
        alert(f"run failed: {error!r}; stopping the client and the session")
        write({"event": "error", "error": repr(error)})
        code = 5
    finally:
        for s in signals:  # the stop below runs to its end
            signal.signal(s, signal.SIG_IGN)
        teardown(env, write, state)
    try:
        return finish(args, env, write, router, code)
    finally:
        for s, old in signals.items():
            signal.signal(s, old)


def drive(
    args: argparse.Namespace,
    env: Env,
    order: Sequence[Slot],
    router: Router,
    write: Callable[[dict[str, Any]], None],
    tag: str,
    stopped: threading.Event,
    stop_client: Callable[[], None],
    state: dict[str, Any],
) -> int:
    """RAM, forwards, servers, client launch, wait. Returns run's exit code."""
    need = CLIENT_GB + RAM_MARGIN_GB
    free = mem_available_gb(env.runner)
    write({"event": "rtx_mem", "mem_available_gb": free, "need_gb": need})
    if free is None or free < need:
        alert(f"rtx3060 MemAvailable {free} GB < {need} GB; client not started")
        return 4
    others = other_jobs(env.runner)
    write(
        {
            "event": "rtx_jobs",
            "other_jobs": None if others is None else others[0],
            "noted": None if others is None else others[1],
        }
    )
    if others is None:
        alert("could not list rtx3060's other jobs; client not started")
        return 5
    if others[0]:
        alert(f"rtx3060 is not reserved ({len(others[0])} other jobs); client not started")
        return 8
    for note in others[1]:
        alert(f"also on rtx3060 (not blocking): {note}")
    remote = Remote(args.session, args.colab)
    forwards = [
        f"-L127.0.0.1:{lp}:127.0.0.1:{vp}"
        for lp, vp in zip(env.laptop_ports, VM_PORTS, strict=True)
    ]
    argv = [*remote.ssh[:-1], "-N", "-o", "ExitOnForwardFailure=yes", *forwards, "root@colab"]
    state["tunnels"].append(env.tunnel(argv, write, "vm"))
    state["tunnels"][-1].start()
    if not all(wait_health(p, 300, env.sleep, env.clock) for p in env.laptop_ports):
        alert("a Psi0 server does not answer /health through the forward; client not started")
        return 5
    for slot, port in zip(order[: len(VM_PORTS)], env.laptop_ports, strict=True):
        served = served_run_dir(port)
        write({"event": "server_info", "job": slot.job, "port": port, "run_dir": served})
        if served is None or f"/serve/{slot.job}/" not in served:
            alert(f"laptop port {port} serves {served}, not {slot.job}; client not started")
            return 5
    ports = dict(zip(VM_PORTS, env.laptop_ports, strict=True))
    server = serve_routes(router, ports, env.route_port, write)
    state["server"] = server
    threading.Thread(target=server.serve_forever, daemon=True).start()
    reverse = f"-R127.0.0.1:{CLIENT_PORT}:127.0.0.1:{env.route_port}"
    argv = [*RTX_SSH, "-N", "-o", "ExitOnForwardFailure=yes", reverse, RTX]
    state["tunnels"].append(env.tunnel(argv, write, "rtx3060"))
    state["tunnels"][-1].start()
    env.sleep(10)
    out = f"~/{RTX_WORK}/runs/{EVAL_JOB}"
    # an `exit` left by an earlier attempt would end wait_client at once
    prepared = rtx(f"mkdir -p {out} && rm -f {out}/exit", env.runner)
    if prepared.returncode != 0:
        alert(f"rtx3060: could not prepare {out}; client not started")
        return 5
    state["launched"] = True
    launched = env.runner(["timeout", "20", *RTX_SSH, RTX, client_command(tag, len(order))])
    write({"event": "client_launch", "tag": tag, "code": launched.returncode})
    if launched.returncode != 0:
        alert(f"client launch on rtx3060 exited {launched.returncode}")
        return 5
    code, state["exited"] = wait_client(router, write, stopped, stop_client, env)
    router.finish()
    return code


def dead_or_late(
    last_request: float | None,
    launched: float,
    now: float,
    reading: tuple[float, float, float] | None,
) -> str | None:
    """Why the client must be stopped now, or None.

    No request FIRST_ACT_S after launch, or ACT_IDLE_S after the last one: the client
    or its tunnel is dead (a gate holds a request at most METER_WAIT_S). The CU line:
    the fresh meter says the session reaches the stop line before the shutdown is done
    (the pair rule should never let it; a backstop). The wall clock: the session cannot
    run longer than the cap allows at the meter's rate."""
    if last_request is None and now - launched > FIRST_ACT_S:
        return f"no request {now - launched:.0f} s after launch"
    if last_request is not None and now - last_request > ACT_IDLE_S:
        return f"no request for {now - last_request:.0f} s"
    if reading is not None and now - reading[0] <= METER_STALE_S:
        at, spent, _ = reading
        if spent + RATE_CU_H * (now - at + END_S) / 3600 + SAFETY_CU > stop_line(CAP):
            return f"spent {spent} CU: the shutdown would cross the stop line"
    if now - launched > CAP / RATE_CU_H * 3600:
        return f"{now - launched:.0f} s since launch: longer than cap {CAP} lasts"
    return None


def wait_client(
    router: Router,
    write: Callable[[dict[str, Any]], None],
    stopped: threading.Event,
    stop_client: Callable[[], None],
    env: Env,
) -> tuple[int, bool]:
    """Wait for the client's `exit` file on rtx3060; returns (code, exit seen).

    The client is stopped when `dead_or_late` says so (then 5), or by the router when
    the CU rule refuses a pair (0, a clean end). Either way he1_client.sh then has
    EXIT_WAIT_S to move its files and write `exit`; the container going away is not
    the end. Without an `exit` by then: 5. A nonzero client exit: 5."""
    path = f"~/{RTX_WORK}/runs/{EVAL_JOB}/exit"
    launched = env.clock()
    stop_at: float | None = None
    why: str | None = None
    misses = 0
    while True:
        env.sleep(POLL_S)
        now = env.clock()
        if stop_at is None and stopped.is_set():
            stop_at = now
        if stop_at is None:
            why = dead_or_late(router.last_request, launched, now, env.reading())
            if why:
                alert(f"stopping the client: {why}")
                write({"event": "client_stop", "why": why})
                stop_client()
                stop_at = now
        out = rtx(
            f"cat {path} 2>/dev/null; docker ps -q -f name=da26-eval-client | wc -l", env.runner
        )
        misses = 0 if out.returncode == 0 else misses + 1
        if misses and misses % 10 == 0:
            alert(f"rtx3060 unreachable {misses} polls in a row while the client runs")
        lines = out.stdout.split() if out.returncode == 0 else []
        cu = router.refused is not None and router.refused.get("reason") == "cu_rule"
        if len(lines) == 2:
            code = int(lines[0]) if lines[0].lstrip("-").isdigit() else -1
            write({"event": "client_exit", "code": code, "refused": cu, "stopped_for": why})
            return (0 if (code == 0 or cu) and why is None else 5), True
        if stop_at is not None and now - stop_at > EXIT_WAIT_S:
            alert(f"no exit file on rtx3060 {now - stop_at:.0f} s after the client stop")
            write({"event": "client_exit", "code": None, "refused": cu, "stopped_for": why})
            return 5, False


def teardown(env: Env, write: Callable[[dict[str, Any]], None], state: dict[str, Any]) -> None:
    """Close what `drive` opened; a client still running is stopped. Never raises."""
    steps: list[tuple[str, Callable[[], Any]]] = []
    if state["server"] is not None:
        steps.append(("route", state["server"].shutdown))
    steps += [(f"tunnel {t.name}", t.stop) for t in state["tunnels"]]
    if state["launched"] and not state["exited"]:
        steps.append(("client", lambda: rtx("docker stop -t 30 da26-eval-client", env.runner)))
    for name, step in steps:
        try:
            done = step()
            if isinstance(done, subprocess.CompletedProcess):
                write({"event": "client_stopped", "code": done.returncode})
        except Exception as error:  # noqa: BLE001 - the session stop comes next regardless
            write({"event": "teardown_failed", "step": name, "error": repr(error)})


def finish(
    args: argparse.Namespace,
    env: Env,
    write: Callable[[dict[str, Any]], None],
    router: Router,
    code: int,
) -> int:
    """VM logs first, then the confirmed stop (the last CU), then rtx3060's files (no CU)
    and results. Each step runs whatever the one before it did."""
    job = args.dest / EVAL_JOB
    try:
        fetched = env.fetch()
        write({"event": "vm_pulled", "code": fetched.returncode, "tail": fetched.stdout[-500:]})
    except Exception as error:  # noqa: BLE001
        write({"event": "vm_pull_failed", "error": repr(error)})
    try:
        confirmed = env.stop()
    except Exception as error:  # noqa: BLE001
        alert(f"{args.session}: stop raised {error!r}; it may still bill")
        confirmed = False
    write({"event": "session_stop", "confirmed": confirmed})
    pulled = env.runner(
        [
            *("rsync", "-a", "--timeout=120", "-e", " ".join(RTX_SSH)),
            *(f"{RTX}:{RTX_WORK}/runs/{EVAL_JOB}/", f"{job}/client/"),
        ]
    )
    write({"event": "client_pulled", "code": pulled.returncode})
    try:
        rows = results(args.dest)
        complete = {r["pair"] for r in rows if r["complete_pair"]}
        write({"event": "results", "episodes": len(rows), "complete_pairs": len(complete)})
    except (Exception, SystemExit) as error:  # noqa: BLE001
        write({"event": "results_failed", "error": repr(error)})
    if not confirmed:
        return 6
    if code:
        return code
    return 3 if router.refused and router.refused.get("reason") == "cu_rule" else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "mode", choices=["interleave", "preflight", "probe", "upload", "run", "results", "fit"]
    )
    parser.add_argument("--session", default=EVAL_JOB)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--dest", type=Path, default=REPO / "fwdata/he/runs")
    parser.add_argument("--runs", type=Path, default=REPO / "fwdata/he/runs")
    parser.add_argument("--src", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--set", type=Path)
    parser.add_argument("--colab", type=Path, default=COLAB)
    parser.add_argument("--spent", type=float, help="`fit`: CU spent when the first pair starts")
    parser.add_argument("--episode-s", type=float, default=PRIOR_EPISODE_S)
    args = parser.parse_args(argv)
    if args.mode == "interleave":
        order = interleave(args.src, args.out, load_plan())
        print(json.dumps({"episodes": len(order), "out": str(args.out)}))
        return 0
    if args.mode == "preflight":
        return preflight(args.set)
    if args.mode == "fit":
        print(pairs_that_fit(args.spent, args.episode_s, most=len(pair_order(load_plan())) // 2))
        return 0
    if args.mode == "results":
        rows = results(args.dest)
        print(
            json.dumps(
                {
                    "episodes": len(rows),
                    "successes": {
                        j: sum(
                            1 for r in rows if r["job"] == j and r["success"] and r["complete_pair"]
                        )
                        for j in sorted({r["job"] for r in rows})
                    },
                }
            )
        )
        return 0
    if args.registry is None:
        parser.error(f"{args.mode} needs --registry")
    if args.mode == "run":
        return run_eval(args)
    if not session_running(args.session, args.registry, args.colab):
        print(f"{args.session}: watcher gone or not listed; no ssh", file=sys.stderr)
        return 2
    remote = Remote(args.session, args.colab)
    if args.mode == "probe":
        down = probe(remote, args.dest)
        up = probe_push(remote, args.dest)
        row = {"mb_per_s": round(down, 2), "push_mb_per_s": round(up, 2), "time": time.time()}
        (args.dest / f".{args.session}.probe.json").write_text(json.dumps(row))
        log(event="probe", session=args.session, **row)
        return 0
    jobs = [s.job for s in pair_order(load_plan())[: len(VM_PORTS)]]
    upload(remote, args.runs, jobs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

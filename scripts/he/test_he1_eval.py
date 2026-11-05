"""Checks of the HE-1 eval driver (he1_eval.py, he1_colab.py serve), on CPU.

Run: uv run pytest scripts/he -q
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from he1_colab import job_id, load_point, refresh_vm_logs, serve, upload_problems, write_launch_env
from he1_eval import (
    ACT_IDLE_S,
    CAP,
    CLIENT_PORT,
    END_S,
    EXIT_WAIT_S,
    FIRST_ACT_S,
    METER_WAIT_S,
    POLL_S,
    PRIOR_EPISODE_S,
    RATE_CU_H,
    SAFETY_CU,
    SERVED,
    VM_PORTS,
    Env,
    JsonLog,
    Router,
    Slot,
    client_command,
    config_sha256,
    container_stop_command,
    dead_or_late,
    expected,
    forward,
    interleave,
    load_plan,
    meter,
    other_jobs,
    pair_order,
    pair_verdict,
    pairs_that_fit,
    preflight,
    results,
    run_eval,
    serve_routes,
    stop_command,
    stop_line,
    upload,
    wait_client,
    waiting_gate,
)
from he1_fetch import LocalRemote, verified

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TASK = "G1WholebodyLocomotionPickBetweenTablesTeleop-v0"
DEV_SET = Path.home() / "project/denso-challenge/fwdata/he/dev-eval-v1-l0n10"


def test_the_order_is_by_condition_with_the_arms_in_plan_order() -> None:
    plan = load_plan()
    order = pair_order(plan)
    assert len(order) == 20
    assert [s.episode for s in order] == list(range(20))
    assert [s.pair for s in order] == [i // 2 for i in range(20)]
    assert [s.seed for s in order] == [1000100 + i // 2 for i in range(20)]
    assert [s.point for s in order[:2]] == ["V-EGO/N20/0", "V-NOEGO/N20/0"]
    assert all(s.point == order[s.episode % 2].point for s in order)
    assert [s.port for s in order[:2]] == list(VM_PORTS)
    # the job names are he1_colab's, so each server loads the fine-tune of its point
    for slot in order[:2]:
        assert slot.job == job_id(load_point(slot.point)[1])
    assert [s.first for s in order[:4]] == [True, False, True, False]


def fake_dev_set(root: Path, n: int) -> tuple[Path, dict[str, Any]]:
    """A dev set as dev_eval_set.py writes it, `n` one-frame conditions, and a plan for it."""
    level = root / "simple" / TASK / "dr-level-0"
    (level / "meta").mkdir(parents=True)
    rows, episodes, stats = [], [], []
    for i in range(n):
        config = {"uid": "two_tables", "seed": 7 + i, "objects": {"box": [i, 0.5]}}
        rows.append({"level": 0, "seed": 7 + i, "environment_config": config})
        table = pa.table(
            {
                "action": [[float(i)] * 3],
                "timestamp": [0.0],
                "frame_index": [0],
                "episode_index": [i],
                "index": [i],
                "task_index": [0],
            }
        )
        (level / "data/chunk-000").mkdir(parents=True, exist_ok=True)
        pq.write_table(table, level / f"data/chunk-000/episode_{i:06d}.parquet")
        video = level / f"videos/chunk-000/observation.images.ego_view/episode_{i:06d}.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(f"video {i}".encode())
        episodes.append({"episode_index": i, "length": 1, "environment_config": json.dumps(config)})
        one = {"min": [i], "max": [i], "mean": [float(i)], "std": [0.0], "count": [1]}
        stats.append({"episode_index": i, "stats": {"episode_index": one, "index": one}})
    (root / "conditions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    info = {
        "codebase_version": "v2.1",
        "total_episodes": n,
        "total_frames": n,
        "total_videos": n,
        "splits": {"train": f"0:{n}"},
        "features": {
            "observation.images.ego_view": {"dtype": "video"},
            "action": {"dtype": "float32"},
        },
    }
    meta = level / "meta"
    (meta / "info.json").write_text(json.dumps(info))
    (meta / "tasks.jsonl").write_text('{"task_index": 0, "task": "pick"}\n')
    (meta / "episodes.jsonl").write_text("".join(json.dumps(e) + "\n" for e in episodes))
    (meta / "episodes_stats.jsonl").write_text("".join(json.dumps(s) + "\n" for s in stats))
    plan = load_plan()
    plan["eval"]["main"]["seeds"] = {"start": 7, "stop": 7 + n}
    plan["eval"]["main"]["conditions_sha256"] = config_sha256(rows)
    return root, plan


def test_the_interleaved_set_holds_each_condition_twice_in_order(tmp_path: Path) -> None:
    src, plan = fake_dev_set(tmp_path / "dev", 3)
    order = interleave(src, tmp_path / "out", plan)
    level = tmp_path / "out" / "simple" / TASK / "dr-level-0"
    episodes = [json.loads(x) for x in (level / "meta/episodes.jsonl").read_text().splitlines()]
    configs = [json.loads(e["environment_config"])["seed"] for e in episodes]
    assert configs == [7, 7, 8, 8, 9, 9] and [e["episode_index"] for e in episodes] == list(
        range(6)
    )
    for slot in order:
        table = pq.read_table(level / f"data/chunk-000/episode_{slot.episode:06d}.parquet")
        assert table.column("episode_index").to_pylist() == [slot.episode]
        assert table.column("index").to_pylist() == [slot.episode]
        assert table.column("action").to_pylist() == [[float(slot.pair)] * 3]
        video = (
            level / f"videos/chunk-000/observation.images.ego_view/episode_{slot.episode:06d}.mp4"
        )
        assert video.read_bytes() == f"video {slot.pair}".encode()
    stats = [json.loads(x) for x in (level / "meta/episodes_stats.jsonl").read_text().splitlines()]
    assert [s["stats"]["index"]["min"] for s in stats] == [[k] for k in range(6)]
    info = json.loads((level / "meta/info.json").read_text())
    assert (info["total_episodes"], info["total_frames"], info["splits"]) == (
        6,
        6,
        {"train": "0:6"},
    )
    saved = json.loads((tmp_path / "out" / "order.json").read_text())
    assert [Slot(**s) for s in saved["slots"]] == order


def test_a_set_that_is_not_the_plans_is_not_interleaved(tmp_path: Path) -> None:
    src, plan = fake_dev_set(tmp_path / "dev", 2)
    plan["eval"]["main"]["conditions_sha256"] = "0" * 64
    with pytest.raises(SystemExit, match="not the plan's"):
        interleave(src, tmp_path / "out", plan)
    src2, plan2 = fake_dev_set(tmp_path / "dev2", 2)
    episodes = src2 / "simple" / TASK / "dr-level-0" / "meta/episodes.jsonl"
    lines = episodes.read_text().splitlines()
    episodes.write_text("\n".join([lines[1], lines[0]]) + "\n")  # scenes swapped
    with pytest.raises(SystemExit, match="is not condition 0"):
        interleave(src2, tmp_path / "out2", plan2)


@pytest.mark.skipif(not DEV_SET.is_dir(), reason="the dev set lives on Hiếu's laptop only")
def test_the_real_dev_set_interleaves(tmp_path: Path) -> None:
    order = interleave(DEV_SET, tmp_path / "out", load_plan())
    assert len(order) == 20 and order == pair_order(load_plan())


def reading(spent: float, age: float = 30.0, now: float = 10_000.0) -> tuple[float, float, float]:
    return now - age, spent, CAP


def test_a_pair_starts_only_if_both_its_episodes_and_the_shutdown_fit() -> None:
    line = stop_line(CAP)
    worst = 2 * PRIOR_EPISODE_S + END_S
    fits = line - SAFETY_CU - RATE_CU_H * (30 + worst) / 3600 - 0.001
    assert pair_verdict(reading(fits), 10_000.0, [])["verdict"] == "start"
    assert pair_verdict(reading(fits + 0.01), 10_000.0, [])["verdict"] == "refuse"
    # a slower episode already seen raises the bound for every later pair
    assert pair_verdict(reading(fits), 10_000.0, [PRIOR_EPISODE_S + 120])["verdict"] == "refuse"
    # faster episodes never lower it below a full-budget failure
    assert pair_verdict(reading(fits), 10_000.0, [300.0, 400.0])["verdict"] == "start"


def test_a_stale_or_missing_meter_never_starts_a_pair() -> None:
    assert pair_verdict(None, 10_000.0, [])["verdict"] == "blind"
    assert pair_verdict(reading(1.0, age=301), 10_000.0, [])["verdict"] == "blind"


def test_the_line_is_the_drivers_cap_never_the_watchers_row() -> None:
    at, spent, _ = reading(1.0)
    verdict = pair_verdict((at, spent, 16.0), 10_000.0, [])
    assert verdict["verdict"] == "refuse" and "16.0" in verdict["why"]


def test_how_many_pairs_fit_under_the_cap() -> None:
    # the numbers of the PR and he-1.md 7.1 at cap 18 (Hiếu 5/11/2026); spent at the first
    # pair start, about 1.0 CU (probe, deploy, 12.5 GB upload at 11 MB/s, loads, Isaac)
    assert PRIOR_EPISODE_S == 33 * 60  # S1-03's 10-episode run on a shared rtx3060
    assert [pairs_that_fit(1.0, m * 60) for m in (33, 27, 24.6, 22, 20)] == [7, 9, 10, 10, 10]
    assert [pairs_that_fit(0.6, m * 60) for m in (33, 27, 24.6, 22, 20)] == [7, 9, 10, 10, 10]
    assert [pairs_that_fit(1.2, m * 60) for m in (33, 27, 24.6, 22, 20)] == [7, 9, 9, 10, 10]
    assert [pairs_that_fit(1.5, m * 60) for m in (33, 27, 24.6, 22, 20)] == [7, 8, 9, 10, 10]
    # the margin of the tenth pair: before-reset spend and episode length
    assert pairs_that_fit(1.05, 1476) == 10 and pairs_that_fit(1.06, 1476) == 9
    assert pairs_that_fit(1.0, 24.6 * 60) == 10 and pairs_that_fit(1.0, 24.8 * 60) == 9
    # the old cap 16, for the record: 8 pairs at 24.6 min, 6 at 33
    assert [pairs_that_fit(1.0, m, cap=16.0) for m in (1476, 1980)] == [8, 6]
    # fast episodes spend less, but the gate still projects a slow one
    assert pairs_that_fit(1.0, 600, most=20) == 20 and pairs_that_fit(15.5, 600) == 0


class Recorder:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.refusals = 0

    def __call__(self, row: dict[str, Any]) -> None:
        self.rows.append(row)

    def refuse(self) -> None:
        self.refusals += 1


def reset(seed: int = 0) -> dict[str, Any]:
    return {"history": {"reset": True}, "timestamp": str(seed)}


def test_each_reset_is_the_next_episode_and_its_arm_serves_it() -> None:
    order = pair_order(load_plan())
    log, gates = Recorder(), []
    now = [0.0]
    router = Router(
        order,
        lambda s, seen: gates.append((s.pair, list(seen))) or {"verdict": "start"},
        log,
        log.refuse,
        clock=lambda: now[0],
    )

    def at(t: float, body: dict[str, Any]) -> Any:
        now[0] = t
        return router.slot(body)

    assert at(0, reset()) == order[0] and router.last_request == 0
    assert at(50, {"history": {}}) == order[0] and router.last_request == 50
    assert at(100, reset()) == order[1]
    assert at(150, {}) == order[1]
    assert at(200, reset()) == order[2]
    # gated at pair starts only, with the length of every episode before it
    assert gates == [(0, []), (1, [100.0, 100.0])]
    assert [r["job"] for r in log.rows if r["event"] == "episode_start"] == [
        order[0].job,
        order[1].job,
        order[2].job,
    ]


def test_a_refused_pair_stops_the_client_and_every_later_request() -> None:
    order = pair_order(load_plan())
    log = Recorder()
    verdicts = iter([{"verdict": "start"}, {"verdict": "refuse", "projected_cu": 15.9}])
    router = Router(order, lambda s, seen: next(verdicts), log, log.refuse)
    assert router.slot(reset()) == order[0] and router.slot(reset()) == order[1]
    assert router.slot(reset()) is None
    assert router.slot({}) is None and router.slot(reset()) is None
    assert log.refusals == 1
    assert router.refused is not None and router.refused["reason"] == "cu_rule"
    assert router.refused["pair"] == 1


def test_an_act_before_any_reset_or_past_the_plan_is_refused() -> None:
    log = Recorder()
    router = Router(pair_order(load_plan()), lambda s, seen: {"verdict": "start"}, log, log.refuse)
    assert router.slot({"history": {}}) is None and log.refusals == 1
    log2 = Recorder()
    short = pair_order(load_plan())[:2]
    router2 = Router(short, lambda s, seen: {"verdict": "start"}, log2, log2.refuse)
    assert router2.slot(reset()) and router2.slot(reset())
    assert router2.slot(reset()) is None and "reset 3" in router2.refused["reason"]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def fake_psi0(name: str, run_dir: str = "") -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def reply(self, body: dict[str, Any]) -> None:
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            self.reply({"status": "ok", "server": name, "run_dir": run_dir})

        def do_POST(self) -> None:  # noqa: N802
            self.rfile.read(int(self.headers["Content-Length"]))
            self.reply({"action": [[0.0]], "server": name})

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def post(port: int, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/act",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as reply:
            return reply.status, json.loads(reply.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_the_router_forwards_each_episode_to_its_server_and_logs_every_call(tmp_path: Path) -> None:
    ego, noego = fake_psi0("ego"), fake_psi0("noego")
    order = pair_order(load_plan())
    write = JsonLog(tmp_path / "route.jsonl")
    verdicts = iter([{"verdict": "start"}, {"verdict": "refuse"}])
    router = Router(order, lambda s, seen: next(verdicts), write, lambda: None)
    listen = free_port()
    ports = {VM_PORTS[0]: ego.server_address[1], VM_PORTS[1]: noego.server_address[1]}
    server = serve_routes(router, ports, listen, write)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        got = [post(listen, b)[1].get("server") for b in (reset(), {}, reset(), {})]
        assert got == ["ego", "ego", "noego", "noego"]
        status, body = post(listen, reset())
        assert status == 503 and body["reason"] == "cu_rule"
        with urllib.request.urlopen(f"http://127.0.0.1:{listen}/info", timeout=10) as reply:
            assert json.loads(reply.read())["server"] == "ego"
    finally:
        for s in (server, ego, noego):
            s.shutdown()
    rows = [json.loads(x) for x in (tmp_path / "route.jsonl").read_text().splitlines()]
    acts = [r for r in rows if r["event"] == "act"]
    assert [(r["episode"], r["reset"], r["action"]) for r in acts] == [
        (0, True, True),
        (0, False, True),
        (1, True, True),
        (1, False, True),
    ]
    assert [r["event"] for r in rows if r["event"] in ("pair_gate", "refused")] == [
        "pair_gate",
        "pair_gate",
        "refused",
    ]


def test_results_keep_only_complete_pairs_as_complete(tmp_path: Path) -> None:
    job = tmp_path / "da26-t2-eval-n20"
    order = pair_order(load_plan())
    (job / "order.json").parent.mkdir(parents=True)
    (job / "order.json").write_text(json.dumps({"slots": [s.__dict__ for s in order]}))
    for tag, text in (
        ("old", "episode_0: False \nepisode_1: True \n"),
        ("new", "episode_0: True \nepisode_1: False \nepisode_2: True \n"),
    ):
        (job / f"client/eval/{tag}/x").mkdir(parents=True)
        (job / f"client/eval/{tag}/x/eval_stats.txt").write_text(text)
    events = [{"run": "old", "event": "client_launch", "tag": "old"}]
    events += [
        {"run": "old", "event": "episode_start", "episode": k, "time": "o"} for k in range(4)
    ]
    events += [{"run": "old", "event": "act", "episode": 0, "seconds": 9.0}]
    events += [{"run": "new", "event": "client_launch", "tag": "new"}]
    events += [
        {"run": "new", "event": "episode_start", "episode": k, "time": f"t{k}"} for k in range(3)
    ]
    events += [{"run": "new", "event": "act", "episode": 0, "seconds": s} for s in (0.4, 0.5, 2.0)]
    (job / "route.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    rows = results(tmp_path)  # the last launch's rows and files, never the old run's
    assert [(r["episode"], r["success"], r["complete_pair"]) for r in rows] == [
        (0, True, True),
        (1, False, True),
        (2, True, False),
    ]
    assert (rows[0]["act_calls"], rows[0]["act_p50_s"], rows[0]["act_max_s"]) == (3, 0.5, 2.0)
    assert {r["run"] for r in rows} == {"new"} and rows[0]["started"] == "t0"


def test_results_read_simples_real_eval_stats(tmp_path: Path) -> None:
    """testdata/s1-03-eval_stats.txt is S1-03's mujoco level-0 pass-1 run (b75c678, clock
    sim, rtx3060), as eval_decoupled_wbc wrote it: a header, then "episode_N: True "."""
    job = tmp_path / "da26-t2-eval-n20"
    order = pair_order(load_plan())
    (job / "client/eval/tg/x").mkdir(parents=True)
    (job / "order.json").write_text(json.dumps({"slots": [s.__dict__ for s in order]}))
    stats = (HERE / "testdata/s1-03-eval_stats.txt").read_text()
    (job / "client/eval/tg/x/eval_stats.txt").write_text(stats)
    events = [{"run": "tg", "event": "client_launch", "tag": "tg"}]
    events += [
        {"run": "tg", "event": "episode_start", "episode": k, "time": "t"} for k in range(10)
    ]
    (job / "route.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    assert [r["success"] for r in results(tmp_path)] == [k == 7 for k in range(10)]
    # sonic_wbc.py's line at the pinned image: f"episode_{i}: {success} ({reason})"
    (job / "client/eval/tg/x/eval_stats.txt").write_text(
        "episode_0: True (success)\nepisode_1: False (timeout)\n"
    )
    assert [r["success"] for r in results(tmp_path)][:2] == [True, False]


def fake_runs(runs: Path, job: str) -> Path:
    src = runs / job / "psi0/finetune" / f"fw-{job}.run"
    for rel in SERVED:
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(f"{job} {rel}")
    (src / "envs.txt").write_text("HF_TOKEN=Not Set\n")  # never uploaded
    return src


def test_upload_sends_what_a_server_reads_and_serve_checks_it(tmp_path: Path) -> None:
    jobs = [s.job for s in pair_order(load_plan())[:2]]
    runs, vm = tmp_path / "runs", tmp_path / "vm"
    for job in jobs:
        fake_runs(runs, job)
    rows = upload(LocalRemote(vm), runs, jobs)
    assert [r["job"] for r in rows] == jobs
    assert upload_problems(vm, jobs) == []
    sent = sorted(p.name for p in (vm / "serve" / jobs[0]).rglob("*") if p.is_file())
    assert sent == sorted(["argv.txt", "run_config.json", "model.safetensors", "expected.json"])
    weights = next((vm / "serve" / jobs[1]).rglob("model.safetensors"))
    weights.write_text("truncated")
    assert len(problems := upload_problems(vm, jobs)) == 1 and "model.safetensors" in problems[0]
    with pytest.raises(SystemExit, match="nothing served"):
        serve(vm, jobs)


FAKE_SERVER = """
import json, sys
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
port = int(sys.argv[sys.argv.index("--port") + 1])
run_dir = sys.argv[sys.argv.index("--run-dir") + 1]
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"status": "ok", "run_dir": run_dir}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
print("Server listens", port, flush=True)
HTTPServer(("127.0.0.1", port), H).serve_forever()
"""


def test_serve_starts_one_server_per_fine_tune_and_records_them(tmp_path: Path) -> None:
    jobs = [s.job for s in pair_order(load_plan())[:2]]
    runs, vm = tmp_path / "runs", tmp_path / "vm"
    for job in jobs:
        fake_runs(runs, job)
    upload(LocalRemote(vm), runs, jobs)
    launcher = tmp_path / "fake_server.py"
    launcher.write_text(FAKE_SERVER)
    ports = [free_port(), free_port()]
    serve(vm, jobs, ports, python=sys.executable, launcher=launcher, deadline_s=30)
    report = json.loads((vm / "report.json").read_text())["phases"]["serve"]
    try:
        assert [s["job"] for s in report["servers"]] == jobs
        assert [s["port"] for s in report["servers"]] == ports
        out = vm / "runs/da26-t2-eval-n20"
        for job in jobs:
            info = json.loads((out / f"server-{job}.info.json").read_text())
            assert info["run_dir"].endswith(f"serve/{job}/fw-{job}.run")
            assert "Server listens" in (out / f"server-{job}.log").read_text()
        assert (out / "vm-logs/launch-env.txt").is_file()
    finally:
        for s in report["servers"]:
            os.kill(s["pid"], 15)


def test_vm_logs_link_the_launch_logs_and_the_wandb_core_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "vm"
    job = work / "runs" / "da26-t2-ft-vego-n20-s0"
    (job / "wandb/run/logs").mkdir(parents=True)
    cache = tmp_path / "root-cache" / "core-debug-1.log"
    cache.parent.mkdir()
    cache.write_text("core 1\n")
    (job / "wandb/run/logs/debug-core.log").symlink_to(cache)
    (work / "train.log").write_text("step 1\n")
    (work / "report.json").write_text('{"phases": {}}')
    refresh_vm_logs(work, job)
    logs = job / "vm-logs"
    assert os.path.samefile(logs / "train.log", work / "train.log")
    assert os.path.samefile(logs / "core-debug-1.log", cache)
    with (work / "train.log").open("a") as f:
        f.write("train exit 0\n")
    assert (logs / "train.log").read_text().endswith("train exit 0\n")  # same file, grows
    # a source replaced by a new file (atomic write: new inode) is linked again
    (work / "report.tmp").write_text('{"phases": {"train": {}}}')
    os.replace(work / "report.tmp", work / "report.json")
    refresh_vm_logs(work, job)
    assert (logs / "report.json").read_text() == '{"phases": {"train": {}}}'
    assert {"nvidia-smi-q.txt", "df-h.txt", "free-m.txt"} <= {p.name for p in logs.iterdir()}
    monkeypatch.setenv("HF_TOKEN", "hf_secret")
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    write_launch_env(logs, "train")
    text = (logs / "launch-env.txt").read_text()
    assert "CUDA_VISIBLE_DEVICES=0" in text and "secret" not in text and "TOKEN" not in text


def test_the_client_pins_are_s1_03s() -> None:
    client = (REPO / "scripts/he/he1_client.sh").read_text()
    g0 = (REPO / "scripts/g0/eval_psi0.sh").read_text()
    for name in ("SIMPLE_IMAGE", "SIMPLE_FIX_COMMIT", "SIMPLE_FIX_SHA256"):
        theirs = re.search(rf'{name}="\$\{{{name}:-([^}}]+)\}}"', g0)
        ours = re.search(rf'^{name}="([^"]+)"', client, re.M)
        assert theirs and ours and theirs.group(1) == ours.group(1), name
    for name in ("SIMPLE_FIX_FILE", "WBC_YAML"):
        theirs = re.search(rf"^{name}=(\S+)", g0, re.M)
        ours = re.search(rf"^{name}=(\S+)", client, re.M)
        assert theirs and ours and theirs.group(1) == ours.group(1), name
    plan = load_plan()
    assert f"SIM_MODE={plan['eval']['sim_mode']}" in client
    assert f"CLOCK={plan['eval']['clock']}" in client
    assert subprocess.run(["bash", "-n", str(REPO / "scripts/he/he1_client.sh")]).returncode == 0


def test_the_eval_cap_is_the_decided_one() -> None:
    runbook = (REPO / "docs/he/he-1.md").read_text()
    watcher = [
        x for x in runbook.splitlines() if "cu_watch.py session" in x and "da26-t2-eval" in x
    ]
    assert CAP == 18.0 and len(watcher) == 1 and "--cap 18 " in watcher[0]


# --- review of #129: the hash cache, the session always stopped, a dead client ----------


def test_expected_reads_he1_fetchs_real_cache_and_serve_accepts_the_upload(tmp_path: Path) -> None:
    jobs = [s.job for s in pair_order(load_plan())[:2]]
    runs, vm = tmp_path / "runs", tmp_path / "vm"
    for job in jobs:
        src = fake_runs(runs, job)
        rels = [str((src / rel).relative_to(runs / job)) for rel in SERVED]
        # the cache as he1_fetch writes it: path -> {"stamp": [size, mtime], "sha256": hex}
        verified(runs / job, [{"path": r, "size": (runs / job / r).stat().st_size} for r in rels])
        cache = json.loads((runs / job / ".hashes.json").read_text())
        assert all(isinstance(cache[r], dict) for r in rels)
    upload(LocalRemote(vm), runs, jobs)
    assert upload_problems(vm, jobs) == []
    want = json.loads((vm / "serve" / jobs[0] / "expected.json").read_text())["files"]
    assert all(isinstance(v, str) and len(v) == 64 for v in want.values())


def test_expected_trusts_a_cache_entry_only_while_its_stamp_is_the_files(tmp_path: Path) -> None:
    job = pair_order(load_plan())[0].job
    runs = tmp_path / "runs"
    src = fake_runs(runs, job)
    weights = src / SERVED[2]
    rel = str(weights.relative_to(runs / job))
    stamp = [weights.stat().st_size, weights.stat().st_mtime]
    (runs / job / ".hashes.json").write_text(
        json.dumps({rel: {"stamp": stamp, "sha256": "a" * 64}})
    )
    assert expected(runs, job)["files"][SERVED[2]] == "a" * 64
    weights.write_text("changed since it was verified")
    assert expected(runs, job)["files"][SERVED[2]] != "a" * 64
    (runs / job / ".hashes.json").write_text(json.dumps({rel: "a" * 64}))  # not the format
    assert expected(runs, job)["files"][SERVED[2]] != "a" * 64


def test_meter_takes_the_last_well_formed_poll(tmp_path: Path) -> None:
    assert meter(tmp_path, "s") is None
    rows = [
        {"time": "2026-11-04T18:31:00+00:00", "event": "poll", "spent": 0.044, "cap": 16.0},
        {"time": "2026-11-04T18:32:00+00:00", "event": "poll", "spent": 0.08, "cap": 16.0},
        {"time": "2026-11-04T18:33:00+00:00", "event": "poll", "cap": 16.0},  # no spent
        {"time": "2026-11-04T18:34:00+00:00", "event": "exit", "spent": 9.0},
    ]
    (tmp_path / "s.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows) + "{cut")
    at, spent, cap = meter(tmp_path, "s") or (0.0, 0.0, 0.0)
    assert (spent, cap) == (0.08, 16.0) and at == 1793817120.0
    (tmp_path / "t.jsonl").write_text(json.dumps(rows[3]) + "\n")
    assert meter(tmp_path, "t") is None


class FakeTime:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start
        self.hooks: list[Any] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
        for hook in list(self.hooks):
            hook(self)


def test_the_gate_waits_for_a_fresh_meter_then_refuses() -> None:
    fake = FakeTime()
    readings = iter([None, None, (fake.now + 30, 1.0, CAP)])
    verdict = waiting_gate(lambda: next(readings), fake.clock, fake.sleep)(
        pair_order(load_plan())[0], []
    )
    assert verdict["verdict"] == "start" and fake.now == 1_000_030.0
    blind = waiting_gate(lambda: None, fake.clock, fake.sleep)(pair_order(load_plan())[0], [])
    assert blind["verdict"] == "blind" and fake.now > 1_000_030.0 + METER_WAIT_S


def test_forward_retries_connection_errors_until_the_server_is_back() -> None:
    port = free_port()
    started: list[ThreadingHTTPServer] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args: Any) -> None:
            pass

    def sleep(_: float) -> None:  # the second retry finds the server up
        if not started:
            started.append(ThreadingHTTPServer(("127.0.0.1", port), Handler))
            threading.Thread(target=started[0].serve_forever, daemon=True).start()

    assert forward(port, "GET", "/health", None, retry_s=30, sleep=sleep) == (200, b"ok")
    started[0].shutdown()
    started[0].server_close()
    with pytest.raises(ConnectionError):  # a port nobody answers: no retry left
        forward(port, "GET", "/health", None, retry_s=0)


def test_a_dead_or_late_client_is_named() -> None:
    t0 = 1_000_000.0
    fresh = (t0 + 100, 1.0, CAP)
    assert dead_or_late(None, t0, t0 + FIRST_ACT_S - 1, fresh) is None
    assert "after launch" in (dead_or_late(None, t0, t0 + FIRST_ACT_S + 1, None) or "")
    assert dead_or_late(t0 + 10, t0, t0 + 10 + ACT_IDLE_S - 1, None) is None
    assert "no request for" in (dead_or_late(t0 + 10, t0, t0 + 11 + ACT_IDLE_S, None) or "")
    near = (t0 + 100, stop_line(CAP) - 0.1, CAP)
    assert "stop line" in (dead_or_late(t0 + 100, t0, t0 + 120, near) or "")
    assert "longer than cap" in (
        dead_or_late(t0 + 9e9, t0, t0 + CAP / RATE_CU_H * 3600 + 1, None) or ""
    )


class Rtx:
    """rtx3060 over ssh, scripted: `exit` appears once `ready` says so."""

    def __init__(self, exit_code: str | None = None, containers: str = "1") -> None:
        self.exit_code, self.containers = exit_code, containers
        self.calls: list[str] = []
        self.reachable = True

    def __call__(self, argv: Any) -> subprocess.CompletedProcess[str]:
        command = " ".join(argv)
        self.calls.append(command)
        if not self.reachable:
            return subprocess.CompletedProcess(argv, 255, "", "unreachable")
        if "cat " in command and "/exit" in command:
            out = ([self.exit_code] if self.exit_code is not None else []) + [self.containers]
            return subprocess.CompletedProcess(argv, 0, "\n".join(out) + "\n", "")
        return subprocess.CompletedProcess(argv, 0, "", "")


def waiting_env(rtx: Rtx, fake: FakeTime, reading: Any = None) -> Env:
    return Env(
        runner=rtx,
        running=lambda: True,
        stop=lambda: True,
        fetch=lambda: subprocess.CompletedProcess([], 0, "", ""),
        reading=reading or (lambda: None),
        sleep=fake.sleep,
        clock=fake.clock,
    )


def idle_router(fake: FakeTime) -> Router:
    return Router(
        pair_order(load_plan()),
        lambda s, seen: {"verdict": "start"},
        lambda row: None,
        lambda: None,
        clock=fake.clock,
    )


def test_a_client_that_never_calls_is_stopped_and_its_exit_awaited() -> None:
    fake, rtx, stops = FakeTime(), Rtx(containers="0"), []
    stopped = threading.Event()

    def stop() -> None:
        stops.append(fake.now)
        fake.hooks.append(
            lambda f: setattr(rtx, "exit_code", "137") if f.now > stops[0] + 120 else None
        )

    code, seen = wait_client(idle_router(fake), Recorder(), stopped, stop, waiting_env(rtx, fake))
    assert (code, seen) == (5, True) and len(stops) == 1
    assert FIRST_ACT_S < stops[0] - 1_000_000.0 <= FIRST_ACT_S + POLL_S


def test_a_client_gone_quiet_is_stopped_and_bounded_without_an_exit() -> None:
    fake, rtx, stops = FakeTime(), Rtx(), []
    router = idle_router(fake)
    router.slot(reset())  # one episode started, then nothing
    code, seen = wait_client(
        router, Recorder(), threading.Event(), lambda: stops.append(1), waiting_env(rtx, fake)
    )
    assert (code, seen) == (5, False) and stops == [1]
    assert fake.now - 1_000_000.0 <= ACT_IDLE_S + EXIT_WAIT_S + 3 * POLL_S


def test_an_unreachable_box_does_not_hold_the_session_past_the_stop() -> None:
    fake, rtx = FakeTime(), Rtx()
    rtx.reachable = False
    code, seen = wait_client(
        idle_router(fake), Recorder(), threading.Event(), lambda: None, waiting_env(rtx, fake)
    )
    assert (code, seen) == (5, False)
    assert fake.now - 1_000_000.0 <= FIRST_ACT_S + EXIT_WAIT_S + 3 * POLL_S


def test_after_a_cu_refusal_the_client_gets_time_to_write_its_files() -> None:
    fake, rtx = FakeTime(), Rtx(containers="0")  # container already gone, files not moved
    router = idle_router(fake)
    stopped = threading.Event()
    router.refused = {"reason": "cu_rule", "pair": 4}
    router.last_request = fake.now
    stopped.set()
    fake.hooks.append(lambda f: setattr(rtx, "exit_code", "1") if f.now > 1_000_000 + 300 else None)
    code, seen = wait_client(router, Recorder(), stopped, lambda: None, waiting_env(rtx, fake))
    assert (code, seen) == (0, True) and fake.now > 1_000_300


def test_the_client_exit_code_decides_a_normal_end() -> None:
    for exit_code, want in (("0", 0), ("1", 5)):
        fake = FakeTime()
        router = idle_router(fake)
        router.last_request = fake.now
        got = wait_client(
            router, Recorder(), threading.Event(), lambda: None, waiting_env(Rtx(exit_code), fake)
        )
        assert got == (want, True)


def test_the_cu_line_stops_a_pair_that_overran() -> None:
    fake, stops = FakeTime(), []
    router = idle_router(fake)
    router.last_request = fake.now
    fake.hooks.append(lambda f: setattr(router, "last_request", f.now))  # still calling
    near = lambda: (fake.now - 30, stop_line(CAP) - 0.05, CAP)  # noqa: E731
    rtx = Rtx()

    def stop() -> None:
        stops.append(1)
        rtx.exit_code = "137"

    assert wait_client(
        router, Recorder(), threading.Event(), stop, waiting_env(rtx, fake, near)
    ) == (5, True)
    assert stops == [1]


def test_preflight_checks_rtx3060_read_only(tmp_path: Path) -> None:
    (tmp_path / "order.json").write_text("{}")
    digest = __import__("hashlib").sha256(b"{}").hexdigest()

    def box(mem_kb: int, out: str, jobs: str = "---\n---\n") -> Any:
        def runner(argv: Any) -> subprocess.CompletedProcess[str]:
            command = argv[-1]
            assert not any(w in command for w in ("rm ", "mkdir", "docker run", "docker stop"))
            if "MemAvailable" in command:
                return subprocess.CompletedProcess(argv, 0, f"MemAvailable: {mem_kb} kB\n", "")
            if "pgrep" in command:
                return subprocess.CompletedProcess(argv, 0, jobs, "")
            return subprocess.CompletedProcess(argv, 0, out, "")

        return runner

    gb = 1024 * 1024
    assert preflight(tmp_path, box(40 * gb, f"client\n{digest}\n0\n")) == 0
    assert preflight(tmp_path, box(30 * gb, f"client\n{digest}\n0\n")) == 4
    assert preflight(tmp_path, box(40 * gb, f"client\n{'b' * 64}\n0\n")) == 5
    assert preflight(tmp_path, box(40 * gb, f"{digest}\n0\n")) == 5
    assert preflight(tmp_path, box(40 * gb, f"client\n{digest}\n1\n")) == 5
    # the box is reserved for the eval (Hiếu 5/11/2026); what rtx3060 ran on 5/11:
    ready = f"client\n{digest}\n0\n"
    da35 = "2757013 /usr/bin/bash /home/ubuntu/denso-da35-s2fix/prod-1105.sh\n"
    pol = "3161441 .venv-policy/bin/python -m pol.train_stage_a --variant POLV\n"
    hsk = "hsk_worker\nhsk_api\nhsk_redis\n"
    assert preflight(tmp_path, box(40 * gb, ready, f"{da35}---\n---\n")) == 6
    assert preflight(tmp_path, box(40 * gb, ready, f"---\n{pol}---\n")) == 6
    assert preflight(tmp_path, box(40 * gb, ready, f"---\n---\n{hsk}")) == 0  # noted only
    assert preflight(tmp_path, box(40 * gb, ready, "garbled")) == 5


def test_the_job_listing_does_not_match_its_own_shell() -> None:
    import re

    seen: list[str] = []

    def runner(argv: Any) -> subprocess.CompletedProcess[str]:
        seen.append(argv[-1])
        return subprocess.CompletedProcess(argv, 0, "---\n---\n", "")

    assert other_jobs(runner) == ([], [])
    # pgrep -f matches the remote `bash -c <command>` line too; the brackets keep it out
    assert not re.search("denso", seen[0]) and not re.search("pol[.]train_stage_a", seen[0])


# --- run_eval end to end, on fakes ------------------------------------------------------


class DummyTunnel:
    def __init__(self, argv: list[str], write: Any, name: str) -> None:
        self.name, self.stopped = name, False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        self.stopped = True


class Box:
    """rtx3060 for run_eval: RAM, the launch, the exit file, and the pull of its files."""

    def __init__(self, calls: list[str], mem_gb: int = 40, launch_code: int = 0) -> None:
        self.calls, self.mem_gb, self.launch_code = calls, mem_gb, launch_code
        self.tag: str | None = None
        self.exit: str | None = None
        self.on_launch: Any = None
        self.on_prepare: Any = None
        self.jobs = "---\n---\n"
        self.on_mem: Any = None
        self.on_container_stop: Any = None

    def __call__(self, argv: Any) -> subprocess.CompletedProcess[str]:
        argv = list(argv)
        command = argv[-1]
        ok = subprocess.CompletedProcess(argv, 0, "", "")
        if argv[0] == "rsync":
            self.calls.append("rsync")
            if self.tag:
                dest = Path(argv[-1]) / "eval" / self.tag / "x"
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "eval_stats.txt").write_text(
                    "".join(f"episode_{k}: {k % 3 == 0} \n" for k in range(4))
                )
            return ok
        if command == container_stop_command():  # a CU refusal: the container alone
            self.calls.append("container stop")
            if self.on_container_stop:
                self.on_container_stop()
            return ok
        if "docker stop" in command:  # stop_command: the launcher's group, then the container
            assert "kill -TERM --" in command and "client-" in command
            self.calls.append("docker stop")
            return ok
        if "MemAvailable" in command:
            if self.on_mem:
                self.on_mem()
            return subprocess.CompletedProcess(
                argv, 0, f"MemAvailable: {self.mem_gb << 20} kB\n", ""
            )
        if "pgrep" in command:
            return subprocess.CompletedProcess(argv, 0, self.jobs, "")
        if "he1_client.sh" in command:
            self.calls.append("launch")
            self.tag = command.split("--tag ")[1].split()[0]
            if self.on_launch:
                self.on_launch()
            return subprocess.CompletedProcess(argv, self.launch_code, "", "")
        if command.startswith("mkdir -p"):
            self.calls.append("prepare")
            if self.on_prepare:
                self.on_prepare()
            return ok
        if "cat " in command:
            return subprocess.CompletedProcess(argv, 0, (self.exit or "") + "\n1\n", "")
        return ok


def eval_setup(tmp_path: Path, jobs_served: list[str] | None = None) -> tuple[Any, ...]:
    order = pair_order(load_plan())
    sets = tmp_path / "set"
    sets.mkdir()
    (sets / "order.json").write_text(json.dumps({"slots": [asdict(s) for s in order]}))
    jobs = jobs_served or [order[0].job, order[1].job]
    servers = [fake_psi0(j, f"/content/da26/serve/{j}/fw-{j}.run") for j in jobs]
    args = argparse.Namespace(
        set=sets,
        dest=tmp_path / "runs",
        session="da26-t2-eval-n20",
        registry=tmp_path / "reg",
        colab=Path("colab"),
    )
    calls: list[str] = []
    fake = FakeTime(time.time())
    box = Box(calls)
    env = Env(
        runner=box,
        running=lambda: True,
        stop=lambda: calls.append("stop") or True,
        fetch=lambda: calls.append("fetch") or subprocess.CompletedProcess([], 0, "", ""),
        reading=lambda: (fake.now - 20, 1.0, CAP),
        tunnel=DummyTunnel,
        sleep=fake.sleep,
        clock=fake.clock,
        laptop_ports=tuple(s.server_address[1] for s in servers),
        route_port=free_port(),
    )
    return args, env, box, calls, servers, order


def test_run_short_of_ram_on_rtx3060_still_stops_the_session(tmp_path: Path) -> None:
    args, env, box, calls, servers, _ = eval_setup(tmp_path)
    box.mem_gb = 30
    try:
        assert run_eval(args, env) == 4
    finally:
        [s.shutdown() for s in servers]
    assert calls == ["fetch", "stop", "rsync"]  # VM logs, the stop, then rtx3060 (no CU)


def test_run_on_a_box_that_is_not_reserved_starts_no_client(tmp_path: Path) -> None:
    args, env, box, calls, servers, _ = eval_setup(tmp_path)
    box.jobs = "2757013 /usr/bin/bash /home/ubuntu/denso-da35-s2fix/prod-1105.sh\n---\n---\n"
    try:
        assert run_eval(args, env) == 8
    finally:
        [s.shutdown() for s in servers]
    assert calls == ["fetch", "stop", "rsync"]


def test_run_that_raises_still_stops_the_session(tmp_path: Path) -> None:
    args, env, box, calls, servers, _ = eval_setup(tmp_path)

    def broken(*a: Any) -> Any:
        raise RuntimeError("ssh exploded")

    env.tunnel = broken
    try:
        assert run_eval(args, env) == 5
    finally:
        [s.shutdown() for s in servers]
    assert calls == ["fetch", "stop", "rsync"]
    rows = [
        json.loads(x) for x in (args.dest / "da26-t2-eval-n20/route.jsonl").read_text().splitlines()
    ]
    assert any(r["event"] == "error" and "ssh exploded" in r["error"] for r in rows)


def test_run_signalled_stops_the_session_and_restores_the_handlers(tmp_path: Path) -> None:
    args, env, box, calls, servers, _ = eval_setup(tmp_path)
    before = signal.getsignal(signal.SIGTERM)
    box.on_prepare = lambda: os.kill(os.getpid(), signal.SIGTERM)
    try:
        assert run_eval(args, env) == 7
    finally:
        [s.shutdown() for s in servers]
    assert calls == ["prepare", "fetch", "stop", "rsync"]
    assert signal.getsignal(signal.SIGTERM) == before


def test_run_refuses_servers_that_are_not_their_arms(tmp_path: Path) -> None:
    order = pair_order(load_plan())
    args, env, box, calls, servers, _ = eval_setup(tmp_path, [order[1].job, order[0].job])
    try:
        assert run_eval(args, env) == 5
    finally:
        [s.shutdown() for s in servers]
    assert "launch" not in calls and calls[-3:] == ["fetch", "stop", "rsync"]


def test_a_failed_launch_does_not_wait_and_stops_what_may_have_started(tmp_path: Path) -> None:
    args, env, box, calls, servers, _ = eval_setup(tmp_path)
    box.launch_code = 124
    try:
        assert run_eval(args, env) == 5
    finally:
        [s.shutdown() for s in servers]
    assert calls == ["prepare", "launch", "docker stop", "fetch", "stop", "rsync"]


def test_an_unconfirmed_stop_is_exit_6(tmp_path: Path) -> None:
    args, env, box, calls, servers, _ = eval_setup(tmp_path)
    box.mem_gb = 30
    env.stop = lambda: False
    try:
        assert run_eval(args, env) == 6
    finally:
        [s.shutdown() for s in servers]


def test_a_full_run_routes_logs_and_scores_its_own_episodes(tmp_path: Path) -> None:
    args, env, box, calls, servers, order = eval_setup(tmp_path)
    job = args.dest / "da26-t2-eval-n20"
    job.mkdir(parents=True)
    (job / "route.jsonl").write_text(json.dumps({"run": "earlier", "event": "x"}) + "\n")
    done = threading.Event()

    def client() -> None:  # what SIMPLE's client sends: 2 pairs, 2 /act per episode
        for _ in range(4):
            post(env.route_port, reset())
            post(env.route_port, {"history": {}})
        box.exit = "0"
        done.set()

    box.on_launch = lambda: threading.Thread(target=client, daemon=True).start()
    env.sleep = lambda s: done.wait(10) if s == POLL_S else None
    try:
        assert run_eval(args, env) == 0
    finally:
        [s.shutdown() for s in servers]
    assert calls == ["prepare", "launch", "fetch", "stop", "rsync"]
    assert (job / "route-earlier.jsonl").is_file()  # the earlier run's log is kept apart
    rows = [json.loads(x) for x in (job / "route.jsonl").read_text().splitlines()]
    assert {r["run"] for r in rows} == {box.tag}
    acts = [r for r in rows if r["event"] == "act"]
    assert [(r["episode"], r["job"]) for r in acts[::2]] == [(k, order[k].job) for k in range(4)]
    scored = [json.loads(x) for x in (job / "results.jsonl").read_text().splitlines()]
    assert [(r["episode"], r["success"], r["complete_pair"]) for r in scored] == [
        (0, True, True),
        (1, False, True),
        (2, False, True),
        (3, True, True),
    ]


# --- re-review of #129: shutdown on every way out, results kept, SIGHUP, the launcher ------


def test_a_route_log_that_cannot_be_kept_still_stops_the_session(tmp_path: Path) -> None:
    args, env, box, calls, servers, _ = eval_setup(tmp_path)
    job = args.dest / "da26-t2-eval-n20"
    job.mkdir(parents=True)
    (job / "route.jsonl").write_text(json.dumps({"run": "x", "event": "y"}) + "\n")
    (job / "route-x.jsonl").write_text("kept earlier\n")
    try:
        assert run_eval(args, env) == 5
    finally:
        [s.shutdown() for s in servers]
    assert calls == ["fetch", "stop", "rsync"]
    assert (job / "route-x.jsonl").read_text() == "kept earlier\n"
    # and preflight --dest refuses it before any session is started
    (tmp_path / "set2").mkdir()
    (tmp_path / "set2/order.json").write_text("{}")
    digest = __import__("hashlib").sha256(b"{}").hexdigest()

    def ready(argv: Any) -> subprocess.CompletedProcess[str]:
        command = argv[-1]
        out = (
            "MemAvailable: 41943040 kB\n"
            if "MemAvailable" in command
            else ("---\n---\n" if "pgrep" in command else f"client\n{digest}\n0\n")
        )
        return subprocess.CompletedProcess(argv, 0, out, "")

    assert preflight(tmp_path / "set2", ready, dest=args.dest) == 5
    assert preflight(tmp_path / "set2", ready) == 0


def test_a_system_exit_inside_the_run_still_stops_the_session(tmp_path: Path) -> None:
    args, env, box, calls, servers, _ = eval_setup(tmp_path)

    def bail() -> None:
        raise SystemExit("deep inside")

    box.on_prepare = bail
    try:
        assert run_eval(args, env) == 5
    finally:
        [s.shutdown() for s in servers]
    assert calls == ["prepare", "fetch", "stop", "rsync"]


def test_a_second_signal_during_the_shutdown_does_not_cut_it_short(tmp_path: Path) -> None:
    args, env, box, calls, servers, _ = eval_setup(tmp_path)
    box.on_prepare = lambda: os.kill(os.getpid(), signal.SIGTERM)
    fetch = env.fetch

    def fetch_signalled() -> subprocess.CompletedProcess[str]:
        os.kill(os.getpid(), signal.SIGINT)  # a second one, while the VM logs are pulled
        return fetch()

    env.fetch = fetch_signalled
    try:
        assert run_eval(args, env) == 7
    finally:
        [s.shutdown() for s in servers]
    assert calls == ["prepare", "fetch", "stop", "rsync"]
    rows = [
        json.loads(x) for x in (args.dest / "da26-t2-eval-n20/route.jsonl").read_text().splitlines()
    ]
    assert {"event", "signals"} <= rows[-1].keys() and rows[-1]["signals"] == ["SIGINT"]


def test_an_inherited_ignored_sighup_stays_ignored(tmp_path: Path) -> None:
    args, env, box, calls, servers, _ = eval_setup(tmp_path)
    box.mem_gb = 30
    seen: list[Any] = []
    box.on_mem = lambda: seen.append(signal.getsignal(signal.SIGHUP))
    before = signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        assert run_eval(args, env) == 4
        assert seen == [signal.SIG_IGN] and signal.getsignal(signal.SIGHUP) == signal.SIG_IGN
    finally:
        signal.signal(signal.SIGHUP, before)
        [s.shutdown() for s in servers]


def test_a_run_that_never_launched_keeps_the_earlier_results(tmp_path: Path) -> None:
    job = tmp_path / "da26-t2-eval-n20"
    order = pair_order(load_plan())
    (job / "client/eval/old/x").mkdir(parents=True)
    (job / "order.json").write_text(json.dumps({"slots": [asdict(s) for s in order]}))
    (job / "client/eval/old/x/eval_stats.txt").write_text("episode_0: True \nepisode_1: True \n")
    old = [{"run": "old", "event": "client_launch", "tag": "old"}]
    old += [{"run": "old", "event": "episode_start", "episode": k, "time": "t"} for k in range(2)]
    (job / "route-old.jsonl").write_text("".join(json.dumps(e) + "\n" for e in old))
    assert len(results(tmp_path, job / "route-old.jsonl")) == 2  # an earlier run, again
    assert (job / "results-old.jsonl").read_text() == (job / "results.jsonl").read_text()
    kept = (job / "results.jsonl").read_text()
    (job / "route.jsonl").write_text(json.dumps({"run": "new", "event": "rtx_mem"}) + "\n")
    assert results(tmp_path) == [] and (job / "results.jsonl").read_text() == kept


def test_the_stop_kills_our_launcher_even_before_its_container_exists(tmp_path: Path) -> None:
    """The real launcher and stop commands, run here with HOME at tmp_path: a fake
    systemd-run (runs the command), a he1_client.sh still in setup (sleeping), a fake
    docker. The stop kills the launcher's group; the EXIT trap writes `exit`."""
    home, shims = tmp_path / "home", tmp_path / "bin"
    work = home / "denso-da26"
    (work / "runs/da26-t2-eval-n20").mkdir(parents=True)
    (work / "fw/scripts/he").mkdir(parents=True)
    shims.mkdir()
    (shims / "systemd-run").write_text(
        '#!/bin/bash\nwhile [ "$1" != bash ]; do shift; done\nexec "$@"\n'
    )
    (shims / "docker").write_text(f'#!/bin/bash\necho "$*" >> {tmp_path}/docker.calls\n')
    for shim in shims.iterdir():
        shim.chmod(0o755)
    (work / "fw/scripts/he/he1_client.sh").write_text(
        "status=1\ntrap 'echo \"$status\" > runs/da26-t2-eval-n20/exit' EXIT\nsleep 60 & wait\n"
    )
    environ = {**os.environ, "HOME": str(home), "PATH": f"{shims}:{os.environ['PATH']}"}
    subprocess.run(["bash", "-c", client_command("tg", 20)], env=environ, check=True)
    pgid_file = work / "runs/da26-t2-eval-n20/client-tg.pgid"
    deadline = time.monotonic() + 10
    while not pgid_file.is_file() and time.monotonic() < deadline:
        time.sleep(0.05)
    pgid = int(pgid_file.read_text())
    time.sleep(0.3)
    group = subprocess.run(
        ["pgrep", "-g", str(pgid), "-af", "he1_client"], capture_output=True, text=True
    )
    assert "he1_client.sh --set sets/interleaved --tag tg --episodes 20" in group.stdout
    # a stranger in another group is never signalled, whatever the pgid file says
    stranger = subprocess.Popen(["setsid", "sleep", "30"])
    time.sleep(0.2)
    other = work / "runs/da26-t2-eval-n20/client-zz.pgid"
    other.write_text(str(stranger.pid))
    subprocess.run(["bash", "-c", stop_command("zz")], env=environ, check=False)
    assert stranger.poll() is None
    stranger.kill()
    subprocess.run(["bash", "-c", stop_command("tg")], env=environ, check=False)
    deadline = time.monotonic() + 10
    while subprocess.run(["pgrep", "-g", str(pgid)], capture_output=True).returncode == 0:
        assert time.monotonic() < deadline, "the launcher's group survived the stop"
        time.sleep(0.05)
    assert (work / "runs/da26-t2-eval-n20/exit").read_text().strip() == "1"
    assert "stop -t 30 da26-eval-client" in (tmp_path / "docker.calls").read_text()


def info_server(payload: bytes) -> ThreadingHTTPServer:
    """A server that answers GET /info with the bytes a real Psi0 server sent."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_the_client_setup_accepts_the_real_servers_info(tmp_path: Path) -> None:
    """The real he1_client.sh, up to the step after its /info check, behind the real
    router and the /info bytes both fine-tune servers sent on 5/11/2026 (testdata/,
    copied from fwdata/he/runs/da26-t2-eval-n20/). Their run dirs do not name the task;
    the check copied from S1-03 refused them and the run exited 5 with no episode. Shims:
    awk reports 95 GB MemAvailable; SIMPLE_ASSETS is missing, so the script stops at its
    next check, before docker."""
    infos = [
        (HERE / f"testdata/server-{job}.info.json").read_bytes()
        for job in ("da26-t2-ft-vego-n20-s0", "da26-t2-ft-vnoego-n20-s0")
    ]
    for payload in infos:
        assert TASK.lower().removesuffix("-v0") not in payload.decode()
    work, shims = tmp_path / "denso-da26", tmp_path / "bin"
    (work / "fw/scripts/he").mkdir(parents=True)
    (work / "fw/scripts/he/he1_client.sh").write_text(
        (REPO / "scripts/he/he1_client.sh").read_text()
    )
    (work / f"sets/interleaved/simple/{TASK}/dr-level-0").mkdir(parents=True)
    (work / "sets/interleaved/order.json").write_text("{}\n")
    shims.mkdir()
    real_awk = subprocess.run(["bash", "-c", "command -v awk"], capture_output=True, text=True)
    (shims / "awk").write_text(
        '#!/bin/bash\n[[ "$*" == *MemAvailable* ]] && { echo 99614720; exit 0; }\n'
        f'exec {real_awk.stdout.strip()} "$@"\n'
    )
    (shims / "awk").chmod(0o755)
    servers = [info_server(p) for p in infos]
    write = JsonLog(tmp_path / "route.jsonl")
    router = Router(
        pair_order(load_plan()), lambda s, seen: {"verdict": "start"}, write, lambda: None
    )
    listen = free_port()
    ports = {VM_PORTS[i]: s.server_address[1] for i, s in enumerate(servers)}
    route = serve_routes(router, ports, listen, write)
    threading.Thread(target=route.serve_forever, daemon=True).start()
    try:
        done = subprocess.run(
            [
                "bash",
                "fw/scripts/he/he1_client.sh",
                "--set",
                "sets/interleaved",
                "--tag",
                "tg",
                "--episodes",
                "20",
                "--port",
                str(listen),
            ],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=60,
            env={
                **os.environ,
                "PATH": f"{shims}:{os.environ['PATH']}",
                "SIMPLE_ASSETS": str(tmp_path / "no-assets"),
            },
        )
    finally:
        for s in (route, *servers):
            s.shutdown()
    out = work / "runs/da26-t2-eval-n20"
    assert "does not serve" not in done.stderr
    assert f"ERROR: no {tmp_path}/no-assets/assets" in done.stderr, done.stderr
    assert (out / "server_info-tg.json").read_bytes() == infos[0] + b"\n"
    assert (out / "exit").read_text().strip() == "1"


def test_the_launch_returns_at_once_while_the_client_keeps_running(tmp_path: Path) -> None:
    """The real launch command, run as ssh runs it: `bash -c` with stdout and stderr on
    pipes that the caller reads to EOF. A client still running must not hold them. With
    `cd X && nohup ... &` the backgrounded list kept them and waited for the client, and
    the launch ssh hit its 20 s timeout (eval attempt 2, 5/11/2026)."""
    home, shims = tmp_path / "home", tmp_path / "bin"
    work = home / "denso-da26"
    (work / "runs/da26-t2-eval-n20").mkdir(parents=True)
    (work / "fw/scripts/he").mkdir(parents=True)
    shims.mkdir()
    (shims / "systemd-run").write_text(
        '#!/bin/bash\nwhile [ "$1" != bash ]; do shift; done\nexec "$@"\n'
    )
    (shims / "systemd-run").chmod(0o755)
    (work / "fw/scripts/he/he1_client.sh").write_text("exec sleep 30\n")
    environ = {**os.environ, "HOME": str(home), "PATH": f"{shims}:{os.environ['PATH']}"}
    start = time.monotonic()
    done = subprocess.run(
        ["bash", "-c", client_command("tg", 20)],
        env=environ,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=10,
    )
    took = time.monotonic() - start
    pgid_file = work / "runs/da26-t2-eval-n20/client-tg.pgid"
    deadline = time.monotonic() + 5
    while not pgid_file.is_file() and time.monotonic() < deadline:
        time.sleep(0.05)
    pgid = int(pgid_file.read_text())
    try:
        assert done.returncode == 0 and took < 3, (done.returncode, took)
        alive = subprocess.run(["pgrep", "-g", str(pgid), "-a"], capture_output=True, text=True)
        assert "sleep 30" in alive.stdout
    finally:
        subprocess.run(["pkill", "-g", str(pgid)], check=False)
    # a missing work dir fails the launch instead of starting anything
    gone = {**environ, "HOME": str(tmp_path / "nobody")}
    failed = subprocess.run(
        ["bash", "-c", client_command("tg", 20)], env=gone, capture_output=True, timeout=10
    )
    assert failed.returncode == 1


# --- eval attempt 3: a CU refusal stops the container alone, the client moves its files ---


def test_a_cu_refusal_stops_only_the_container_and_ends_clean(tmp_path: Path) -> None:
    """Pair 1's gate refuses: the router's stop is container_stop_command, never the
    launcher's group kill, and the run ends 3 with both episodes of pair 0 scored."""
    args, env, box, calls, servers, order = eval_setup(tmp_path)
    spent = {"cu": 1.0}
    fake_now = env.clock
    env.reading = lambda: (fake_now() - 20, spent["cu"], CAP)
    done = threading.Event()
    refused: list[int] = []

    def client() -> None:  # pair 0 runs; at pair 1's first reset the meter is past the line
        for _ in range(2):
            post(env.route_port, reset())
            post(env.route_port, {"history": {}})
        spent["cu"] = 17.0
        refused.append(post(env.route_port, reset())[0])

    def container_stopped() -> None:  # SIMPLE's container is gone; the script writes `exit`
        box.exit = "143"
        done.set()

    box.on_launch = lambda: threading.Thread(target=client, daemon=True).start()
    box.on_container_stop = container_stopped
    fake_sleep = env.sleep  # the fake clock still runs: a stop with no `exit` is bounded
    env.sleep = lambda s: (done.wait(10), fake_sleep(s)) if s == POLL_S else None
    try:
        assert run_eval(args, env) == 3
    finally:
        [s.shutdown() for s in servers]
    assert refused == [503]
    assert "container stop" in calls and "docker stop" not in calls
    job = args.dest / "da26-t2-eval-n20"
    scored = [json.loads(x) for x in (job / "results.jsonl").read_text().splitlines()]
    assert [(r["episode"], r["complete_pair"]) for r in scored] == [(0, True), (1, True)]


def test_after_the_refusal_stop_the_real_client_moves_its_files(tmp_path: Path) -> None:
    """The real launcher and he1_client.sh, then the command a CU refusal sends. Shims:
    awk (95 GB MemAvailable), systemd-run (runs the command), sha256sum (the pinned task
    file), docker, whose `run` of the client is SIMPLE mid-episode: eval_stats.txt and a
    video written, then running until `docker stop` or a signal kills it, as the real
    docker CLI dies with its container. Attempt 3's stop killed the launcher's group,
    he1_client.sh with it, and `exit` was 1 with nothing moved (5/11/2026)."""
    home, shims = tmp_path / "home", tmp_path / "bin"
    work = home / "denso-da26"
    out = work / "runs/da26-t2-eval-n20"
    out.mkdir(parents=True)
    (work / "fw/scripts/he").mkdir(parents=True)
    (work / "fw/scripts/he/he1_client.sh").write_text(
        (REPO / "scripts/he/he1_client.sh").read_text()
    )
    (work / f"sets/interleaved/simple/{TASK}/dr-level-0").mkdir(parents=True)
    (work / "sets/interleaved/order.json").write_text("{}\n")
    assets = tmp_path / "assets"
    for d in ("assets", "robots", "scenes"):
        (assets / d).mkdir(parents=True)
    task_file = "g1_wholebody_locomotion_pick_between_tables_teleop.py"
    (work / "simple/patches/b75c678").mkdir(parents=True)
    (work / "simple/patches/b75c678" / task_file).write_text("# the b75c678 task file\n")
    pid_file = tmp_path / "container.pid"
    shims.mkdir()
    real = {
        tool: subprocess.run(
            ["bash", "-c", f"command -v {tool}"], capture_output=True, text=True
        ).stdout.strip()
        for tool in ("awk", "sha256sum")
    }
    (shims / "awk").write_text(
        '#!/bin/bash\n[[ "$*" == *MemAvailable* ]] && { echo 99614720; exit 0; }\n'
        f'exec {real["awk"]} "$@"\n'
    )
    (shims / "sha256sum").write_text(
        f'#!/bin/bash\n[[ "$1" == *{task_file} ]] && '
        '{ echo "51bce5d6c0311219d9a827b589910d915521dccc89b69a1ab20ff35081b6dc8f  $1"; exit 0; }\n'
        f'exec {real["sha256sum"]} "$@"\n'
    )
    (shims / "systemd-run").write_text(
        '#!/bin/bash\nwhile [ "$1" != bash ]; do shift; done\nexec "$@"\n'
    )
    (shims / "docker").write_text(
        f"""#!/bin/bash
echo "$*" >> {tmp_path}/docker.calls
if [[ "$1" == stop ]]; then
  pid=$(cat {pid_file}) && kill -TERM "$pid"
  while kill -0 "$pid" 2>/dev/null; do sleep 0.05; done
  exit 0
fi
[[ "$*" == *"--entrypoint cat"* ]] && {{ echo "DOMAIN_ID: 0"; exit 0; }}
args=("$@")
for i in "${{!args[@]}}"; do
  case "${{args[$i]}}" in
    *:/workspace/simple/data) data="${{args[$i]%:/workspace/simple/data}}" ;;
    data/runs/*) tag="${{args[$i]#data/runs/}}" ;;
  esac
done
ep="$data/evals/psi0_decoupled_wbc/psi0-x.{TASK}/dr-level-0/episode_0"
mkdir -p "$data/runs/$tag" "$ep"
printf 'episode_0: False \\n' > "$data/runs/$tag/eval_stats.txt"
echo frames > "$ep/head_stereo_left.mp4"
echo $$ > {pid_file}
exec sleep 300
"""
    )
    for shim in shims.iterdir():
        shim.chmod(0o755)
    info = info_server((HERE / "testdata/server-da26-t2-ft-vego-n20-s0.info.json").read_bytes())
    environ = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{shims}:{os.environ['PATH']}",
        "SIMPLE_ASSETS": str(assets),
    }
    launch = client_command("tg", 1).replace(
        f"--port {CLIENT_PORT}", f"--port {info.server_address[1]}"
    )
    try:
        subprocess.run(["bash", "-c", launch], env=environ, check=True, timeout=10)
        deadline = time.monotonic() + 30
        while not pid_file.is_file() and time.monotonic() < deadline:
            assert not (out / "exit").exists(), (out / "client-launch-tg.log").read_text()
            time.sleep(0.05)
        assert pid_file.is_file(), "the client never reached its docker run"
        subprocess.run(["bash", "-c", container_stop_command()], env=environ, timeout=30)
        deadline = time.monotonic() + 30
        while not (out / "exit").is_file() and time.monotonic() < deadline:
            time.sleep(0.05)
    finally:
        info.shutdown()
        if (out / "client-tg.pgid").is_file():
            pgid = (out / "client-tg.pgid").read_text().strip()
            subprocess.run(["pkill", "-g", pgid], check=False)
    assert (out / "exit").read_text().strip() == "143"
    assert (out / "eval/tg/eval_stats.txt").read_text() == "episode_0: False \n"
    assert (out / "videos/tg/episode_0/head_stereo_left.mp4").is_file()
    summary = json.loads((out / "summary-tg.json").read_text())
    assert summary["client_exit"] == 143 and summary["clock"] == "sim"

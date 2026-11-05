"""Checks of the HE-1 eval driver (he1_eval.py, he1_colab.py serve), on CPU.

Run: uv run pytest scripts/he -q
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from he1_colab import job_id, load_point, refresh_vm_logs, serve, upload_problems, write_launch_env
from he1_eval import (
    CAP,
    END_S,
    PRIOR_EPISODE_S,
    RATE_CU_H,
    SAFETY_CU,
    SERVED,
    VM_PORTS,
    JsonLog,
    Router,
    Slot,
    config_sha256,
    interleave,
    load_plan,
    pair_order,
    pair_verdict,
    pairs_that_fit,
    results,
    serve_routes,
    stop_line,
    upload,
)
from he1_fetch import LocalRemote

REPO = Path(__file__).resolve().parents[2]
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


def test_how_many_pairs_fit_under_the_cap() -> None:
    # every number below is for the PR and he-1.md; spent at the first pair start
    assert pairs_that_fit(0.6, PRIOR_EPISODE_S) == 9
    assert pairs_that_fit(0.9, PRIOR_EPISODE_S) == 9
    assert pairs_that_fit(0.6, 33 * 60) == 6  # S1-03's 10-episode run on a busy box
    assert pairs_that_fit(0.6, 22 * 60) == 10
    # about 1.0 CU before the first reset (probe, deploy, 12.5 GB upload at 11 MB/s, loads)
    assert pairs_that_fit(1.0, PRIOR_EPISODE_S) == 9
    assert pairs_that_fit(1.0, 22.1 * 60) == 10 and pairs_that_fit(1.0, 22.3 * 60) == 9
    assert pairs_that_fit(1.18, PRIOR_EPISODE_S) == 9 and pairs_that_fit(1.2, PRIOR_EPISODE_S) == 8
    # fast episodes spend less, but the gate still projects a full-budget failure
    assert pairs_that_fit(1.0, 600, most=20) == 20 and pairs_that_fit(14.0, 600) == 0


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
    clock = iter(float(t) for t in range(0, 10_000, 100))
    router = Router(
        order,
        lambda s, seen: gates.append((s.pair, list(seen))) or {"verdict": "start"},
        log,
        log.refuse,
        clock=lambda: next(clock),
    )
    assert router.slot(reset()) == order[0]
    assert router.slot({"history": {}}) == order[0]
    assert router.slot(reset()) == order[1]
    assert router.slot({}) == order[1]
    assert router.slot(reset()) == order[2]
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


def fake_psi0(name: str) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def reply(self, body: dict[str, Any]) -> None:
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            self.reply({"status": "ok", "server": name})

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
    (job / "client/eval/t").mkdir(parents=True)
    (job / "order.json").write_text(json.dumps({"slots": [s.__dict__ for s in order]}))
    (job / "client/eval/t/eval_stats.txt").write_text(
        "episode_0: True \nepisode_1: False \nepisode_2: True \n"
    )
    events = [{"event": "episode_start", "episode": k, "time": f"t{k}"} for k in range(3)]
    events += [{"event": "act", "episode": 0, "seconds": s} for s in (0.4, 0.5, 2.0)]
    (job / "route.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    rows = results(tmp_path)
    assert [(r["episode"], r["success"], r["complete_pair"]) for r in rows] == [
        (0, True, True),
        (1, False, True),
        (2, True, False),
    ]
    assert (rows[0]["act_calls"], rows[0]["act_p50_s"], rows[0]["act_max_s"]) == (3, 0.5, 2.0)


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
    assert CAP == 16.0 and "--cap 16" in runbook

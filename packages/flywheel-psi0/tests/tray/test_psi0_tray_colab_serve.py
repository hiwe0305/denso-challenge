"""Serve lane of the four-run pair, on CPU: bounds, sha256 hand-off, one server (DA-34 6.3)."""

from __future__ import annotations

import json
import os
import signal
import socket
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel_psi0.tray import colab_serve
from flywheel_psi0.tray.colab_serve import bound_problems, expect, fetch, serve, sha256

REPO = Path(__file__).resolve().parents[4]
PAIR = REPO / "configs/runplans/tray/he-tray-pair60k.yaml"
RUN = "fw-da34-t6-ft-c-70-s0.simple.flow1000.cosine.lr1.0e-04.b16.gpus1.da34-t6-ft-c-70-s0"
STATS = {
    "states": {"min": [-1.0, 0.5], "max": [1.0, 2.0]},
    "action": {"min": [0.0, -3.0, 1.0], "max": [0.0, 3.0, 4.0]},
}


def _config(stats: dict[str, Any], pad: int = 2) -> dict[str, Any]:
    """run_config.json's normalisation fields: the stats, padded with zeros as Psi0 pads."""
    field = {
        f"{prefix}_{end}": [*stats[key][end], *([0.0] * pad)]
        for key, prefix in colab_serve.BOUNDS
        for end in ("min", "max")
    }
    return {"data": {"transform": {"field": field}}}


def _run(runs: Path, stats: dict[str, Any], step: int = 40000) -> Path:
    src = runs / "da34-t6-ft-c-70-s0" / "psi0" / "finetune" / RUN
    (src / f"checkpoints/ckpt_{step}").mkdir(parents=True)
    (src / "argv.txt").write_text("train ...")
    (src / "run_config.json").write_text(json.dumps(_config(stats)))
    (src / f"checkpoints/ckpt_{step}/model.safetensors").write_bytes(b"weights")
    return src


def _plan(tmp_path: Path, stats: Path) -> Path:
    raw = yaml.safe_load(PAIR.read_text())
    raw["cut"]["stats_sha256"] = sha256(stats)  # the fake stats stand for ALL's
    out = tmp_path / "plan.yaml"
    out.write_text(yaml.safe_dump(raw, allow_unicode=True))
    return out


def test_bounds_must_be_the_cuts_stats_padding_aside() -> None:
    assert bound_problems(_config(STATS), STATS) == []
    own = json.loads(json.dumps(STATS))
    own["states"]["max"][1] = 1.9  # an S70 run that recomputed its stats
    assert bound_problems(_config(own), STATS) == ["state_max is not states.max of the cut's stats"]
    padded = _config(STATS)
    padded["data"]["transform"]["field"]["action_min"][-1] = 0.5
    assert bound_problems(padded, STATS) == ["action_min: padding past 3 is not zero"]
    assert bound_problems({}, STATS)[0] == "state_min: 0 values, stats states has 2"


def test_expect_writes_the_laptops_sha256_only_for_alls_stats(tmp_path: Path) -> None:
    stats = tmp_path / "stats_psi0.json"
    stats.write_text(json.dumps(STATS))
    plan = _plan(tmp_path, stats)
    runs = tmp_path / "runs"
    src = _run(runs, STATS)
    want = expect(runs, "C_70", 40000, stats, plan)
    assert (want["job"], want["run"], want["ckpt_step"]) == ("da34-t6-ft-c-70-s0", RUN, 40000)
    assert want["files"]["checkpoints/ckpt_40000/model.safetensors"] == sha256(
        src / "checkpoints/ckpt_40000/model.safetensors"
    )
    assert json.loads((runs / want["job"] / "expected-40000.json").read_text()) == want
    with pytest.raises(SystemExit, match="the rules read"):
        expect(runs, "C_70", 50000, stats, plan)
    other = tmp_path / "other.json"
    other.write_text("{}")
    with pytest.raises(SystemExit, match="not ALL's stats"):
        expect(runs, "C_70", 40000, other, plan)
    (src / "run_config.json").write_text(json.dumps(_config({**STATS, "states": STATS["action"]})))
    with pytest.raises(SystemExit, match="state_min"):
        expect(runs, "C_70", 40000, stats, plan)


def test_expect_serves_the_round_run_at_the_rounds_checkpoint_only(tmp_path: Path) -> None:
    # C70_R1 (tray.md 20.15): not a branch of the pair plan; job, step and stats are the round's
    stats = tmp_path / "stats_psi0.json"
    stats.write_text(json.dumps(STATS))
    raw = yaml.safe_load((REPO / "configs/runplans/tray/round-tray-c70.yaml").read_text())
    raw["train"]["stats_sha256"] = sha256(stats)
    round_plan = tmp_path / "round.yaml"
    round_plan.write_text(yaml.safe_dump(raw, allow_unicode=True))
    runs = tmp_path / "runs"
    run = RUN.replace("t6-ft-c-70", "t7-ft-c70-r1")
    src = runs / "da34-t7-ft-c70-r1-s0" / "psi0" / "finetune" / run
    (src / "checkpoints/ckpt_60000").mkdir(parents=True)
    (src / "argv.txt").write_text("train ...")
    (src / "run_config.json").write_text(json.dumps(_config(STATS)))
    (src / "checkpoints/ckpt_60000/model.safetensors").write_bytes(b"weights")
    pair = _plan(tmp_path, stats)
    want = expect(runs, "C70_R1", 60000, stats, pair, round_plan)
    assert (want["job"], want["run"], want["ckpt_step"]) == ("da34-t7-ft-c70-r1-s0", run, 60000)
    assert (runs / want["job"] / "expected-60000.json").is_file()
    with pytest.raises(SystemExit, match="the rules read"):
        expect(runs, "C70_R1", 40000, stats, pair, round_plan)
    other = tmp_path / "other.json"
    other.write_text("{}")
    with pytest.raises(SystemExit, match="not ALL's stats"):
        expect(runs, "C70_R1", 60000, other, pair, round_plan)
    with pytest.raises(SystemExit, match="not a branch"):
        expect(runs, "C70_R2", 60000, stats, pair, round_plan)


def test_fetch_copies_from_drive_and_checks_against_the_laptop(tmp_path: Path) -> None:
    stats = tmp_path / "stats_psi0.json"
    stats.write_text(json.dumps(STATS))
    runs = tmp_path / "laptop"
    _run(runs, STATS)
    want = expect(runs, "C_70", 40000, stats, _plan(tmp_path, stats))
    expected = runs / want["job"] / "expected-40000.json"
    drive = tmp_path / "drive"
    _run(drive, STATS)  # what persist left on Drive: the same bytes
    work = tmp_path / "vm"
    assert sorted(fetch(expected, work, drive)) == sorted(want["files"])
    assert fetch(expected, work, drive) == []  # already there and checked: nothing copied
    (work / "serve" / want["job"] / RUN / "argv.txt").unlink()
    (drive / want["job"] / "psi0/finetune" / RUN / "argv.txt").write_text("another run")
    with pytest.raises(SystemExit, match="differs from the laptop's"):
        fetch(expected, work, drive)
    with pytest.raises(SystemExit, match="is Drive mounted"):
        fetch(expected, tmp_path / "vm2", tmp_path / "unmounted")


FAKE_SERVER = """
import http.server, json, sys
port = int(sys.argv[sys.argv.index("--port") + 1])
argv = sys.argv[1:]
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"ok" if self.path == "/health" else json.dumps({"argv": argv}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", port), H).serve_forever()
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_serve_checks_then_starts_one_server_with_the_local_args(tmp_path: Path) -> None:
    stats = tmp_path / "stats_psi0.json"
    stats.write_text(json.dumps(STATS))
    runs = tmp_path / "laptop"
    _run(runs, STATS)
    want = expect(runs, "C_70", 40000, stats, _plan(tmp_path, stats))
    expected = runs / want["job"] / "expected-40000.json"
    work = tmp_path / "vm"
    launcher = tmp_path / "fake_server.py"
    launcher.write_text(FAKE_SERVER)
    port = _free_port()
    with pytest.raises(SystemExit, match="nothing served"):  # nothing fetched yet
        serve(expected, work, port, sys.executable, launcher)
    fetch(expected, work, runs)
    row = serve(expected, work, port, sys.executable, launcher, deadline_s=30)
    try:
        assert row["argv"][-4:] == ["40000", "--action-exec-horizon", "24", "--rtc"]
        assert row["argv"][row["argv"].index("--run-dir") + 1] == str(
            work / "serve" / want["job"] / RUN
        )
        info = work / "runs" / f"serve-{want['job']}" / "server-40000.info.json"
        assert json.loads(info.read_text())["argv"][:2] == ["--policy", "psi0"]
        report = json.loads((work / "report.json").read_text())["phases"]["serve_c_70_40000"]
        assert report["stats_sha256"] == sha256(stats) and report["pid"] == row["pid"]
        with pytest.raises(SystemExit, match="already answers"):
            serve(expected, work, port, sys.executable, launcher)
    finally:
        os.killpg(row["pid"], signal.SIGTERM)

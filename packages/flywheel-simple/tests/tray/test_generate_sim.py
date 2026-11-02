"""Batch generation in sim: visuals gate, attempt log, recording, resume (DA-33 AC 4, 5).

Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m pytest packages/flywheel-simple/tests/tray/test_generate_sim.py -m sim -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.sim


def test_generator_refuses_to_run_without_visuals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from flywheel_simple.tray import generate as gen

    monkeypatch.setattr(gen, "default_manifest_path", lambda: None)
    with pytest.raises(RuntimeError, match="SimReady"):
        gen.generate(tmp_path, n_attempts=1, level=1, seed_start=1)


def test_two_attempts_are_logged_and_recorded_then_resume_skips_them(tmp_path: Path) -> None:
    from flywheel_simple.tray.generate import generate, read_log, shard_dir

    summary = generate(tmp_path, n_attempts=2, level=1, seed_start=1)
    log = shard_dir(tmp_path, 0) / "gen_log.jsonl"
    rows = read_log(log)
    assert [r["seed"] for r in rows] == [1, 2]
    assert summary.attempts == 2 and summary.recorded == sum(r["recorded"] for r in rows)
    assert all(r["qa"] == "pass" for r in rows if r["recorded"]), rows
    assert all(r["wall_s"] > 0 and r["gpu_name"] for r in rows)

    info = json.loads((shard_dir(tmp_path, 0) / "raw/meta/info.json").read_text())
    assert info["total_episodes"] == summary.recorded

    again = generate(tmp_path, n_attempts=1, level=1, seed_start=1)
    assert again.attempts == 1 and [r["seed"] for r in read_log(log)] == [1, 2, 3]

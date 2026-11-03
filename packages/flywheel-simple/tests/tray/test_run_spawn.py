"""The runner prepares workers that SIMPLE's eval spawns: env id, condition reader, eval patches.

A spawned worker re-imports the runner as `__mp_main__` with
`runpy.run_module(..., run_name="__mp_main__", alter_sys=True)` (multiprocessing.spawn's
`_fixup_main_from_name`) and never calls `main()`. The CPU tests replay that
import with a fake `simple_task`; the `sim` test runs `eval-decoupled-wbc
--num-workers 2` on an empty eval set, so each worker only builds the tray env.
It runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m pytest packages/flywheel-simple/tests/tray/test_run_spawn.py -m sim -v
"""

from __future__ import annotations

import importlib
import os
import runpy
import subprocess
import sys
import types
from pathlib import Path

import pytest

RUN = "flywheel_simple.tray.run"
EVAL_MODULES = (
    "simple.cli.eval_decoupled_wbc",
    "simple.baselines.psi0_decoupled_wbc",
    "simple.agents.sonic_decoupled_wbc_agent",
)
ENV_ID = "simple/G1WholebodyTrayTransferTeleop-v0"


@pytest.fixture
def simple_fakes(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], types.ModuleType]:
    """Calls to a fake `simple_task.register` and a fake `simple.datasets.lerobot`.

    The runner is not yet imported.
    """
    calls: list[str] = []
    task = types.ModuleType("flywheel_simple.tray.simple_task")
    task.register = lambda: calls.append("register")  # type: ignore[attr-defined]
    task.live_env = lambda: None  # type: ignore[attr-defined]
    lerobot = types.ModuleType("simple.datasets.lerobot")
    client = types.ModuleType("simple.baselines.client")
    client.HttpActionClient = type(  # type: ignore[attr-defined]
        "HttpActionClient", (), {"query_action": lambda self, *a, **k: None}
    )
    evals = [types.ModuleType(name) for name in EVAL_MODULES]
    for fake in (task, lerobot, client, *evals):
        monkeypatch.setitem(sys.modules, fake.__name__, fake)
    monkeypatch.delitem(sys.modules, RUN, raising=False)
    monkeypatch.setattr(sys, "argv", ["eval-decoupled-wbc", ENV_ID, "--num-workers", "2"])
    return calls, lerobot


def test_spawned_worker_registers_the_env_and_reads_tray_conditions(
    simple_fakes: tuple[list[str], types.ModuleType],
) -> None:
    calls, lerobot = simple_fakes
    worker = runpy.run_module(RUN, run_name="__mp_main__", alter_sys=True)
    assert calls == ["register"]
    assert lerobot.get_episode_lerobot is worker["get_episode_lerobot"]
    assert all(isinstance(sys.modules[m].time, worker["SimTime"]) for m in EVAL_MODULES)
    client = sys.modules["simple.baselines.client"].HttpActionClient
    assert getattr(client.query_action, "flywheel_condition_seed", False)


def test_plain_import_patches_nothing(simple_fakes: tuple[list[str], types.ModuleType]) -> None:
    calls, lerobot = simple_fakes
    importlib.import_module(RUN)
    assert calls == []
    assert not hasattr(lerobot, "get_episode_lerobot")


@pytest.mark.sim
def test_two_spawned_eval_workers_build_the_tray_env(tmp_path: Path) -> None:
    (tmp_path / "evals" / ENV_ID / "train").mkdir(parents=True)  # no episodes: build the env only
    cmd = [
        sys.executable, "-m", RUN, "eval-decoupled-wbc", ENV_ID, "psi0_decoupled_wbc",
        "--data-format", "rlds_numpy", "--eval-dir", str(tmp_path / "evals"),
        "--sim-mode", "mujoco", "--headless", "--no-save-video",
        "--host", "127.0.0.1", "--port", "9", "--num-workers", "2",
    ]  # fmt: skip
    import flywheel_simple

    src = str(Path(flywheel_simple.__file__).resolve().parents[1])  # cwd moves to tmp_path
    path = os.pathsep.join(filter(None, [src, os.environ.get("PYTHONPATH")]))
    env = {**os.environ, "PYTHONPATH": path, "FLYWHEEL_TRAY_DIR": str(tmp_path / "scene")}
    proc = subprocess.run(cmd, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=900)
    logs = "\n".join(path.read_text() for path in sorted(tmp_path.rglob("eval_worker_*.log")))
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-4000:] + logs[-4000:]
    assert logs.count(f"Creating environment: {ENV_ID}") == 2

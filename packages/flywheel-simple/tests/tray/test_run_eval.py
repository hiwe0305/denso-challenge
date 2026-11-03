"""Eval patches of the runner: sim clock and the condition seed on reset (CPU, fake SIMPLE)."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

EVAL_MODULES = (
    "simple.cli.eval_decoupled_wbc",
    "simple.baselines.psi0_decoupled_wbc",
    "simple.agents.sonic_decoupled_wbc_agent",
)


class FakeClient:
    def query_action(  # same signature as simple.baselines.client.HttpActionClient
        self,
        image_dict: Any,
        instruction: Any,
        state_dict: Any,
        condition_dict: Any,
        history: dict[str, Any] | None = None,
        dataset: str = "grasp",
        gt_action: Any = None,
    ) -> dict[str, Any] | None:
        return history


@pytest.fixture
def fake_simple(monkeypatch: pytest.MonkeyPatch) -> dict[str, types.ModuleType]:
    """Fake eval modules and a live tray env whose episode has condition seed 1000123."""
    import time

    modules = {}
    for name in EVAL_MODULES:
        module = types.ModuleType(name)
        module.time = time  # type: ignore[attr-defined]
        modules[name] = module
    client = types.ModuleType("simple.baselines.client")
    client.HttpActionClient = type("HttpActionClient", (FakeClient,), {})  # type: ignore[attr-defined]
    modules[client.__name__] = client
    task = types.ModuleType("flywheel_simple.tray.simple_task")
    env = SimpleNamespace(task=SimpleNamespace(sample=SimpleNamespace(seed=1000123)))
    task.live_env = lambda: env  # type: ignore[attr-defined]
    modules[task.__name__] = task
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delenv("FLYWHEEL_TRAY_EVAL_CLOCK", raising=False)
    return modules


def test_eval_runs_on_sim_time_by_default(fake_simple: dict[str, types.ModuleType]) -> None:
    from flywheel_simple.tray.run import SimTime, prepare_eval

    prepare_eval()
    assert all(isinstance(fake_simple[name].time, SimTime) for name in EVAL_MODULES)


def test_wall_clock_on_request(
    fake_simple: dict[str, types.ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    from flywheel_simple.tray.run import prepare_eval

    monkeypatch.setenv("FLYWHEEL_TRAY_EVAL_CLOCK", "wall")
    prepare_eval()
    assert all(fake_simple[name].time is time for name in EVAL_MODULES)
    monkeypatch.setenv("FLYWHEEL_TRAY_EVAL_CLOCK", "real")
    with pytest.raises(ValueError, match="sim or wall"):
        prepare_eval()


def test_reset_request_carries_the_condition_seed(fake_simple: dict[str, types.ModuleType]) -> None:
    from flywheel_simple.tray.run import prepare_eval

    prepare_eval()
    prepare_eval()  # applied twice (main and a re-import): wrapped once
    client = fake_simple["simple.baselines.client"].HttpActionClient()
    sent = client.query_action({}, "carry", {}, {}, history={"reset": True}, dataset="simple")
    assert sent == {"reset": True, "seed": 1000123}
    assert client.query_action({}, "carry", {}, {}, history={}) == {}
    assert client.query_action({}, "carry", {}, {}, {"reset": True}) == {
        "reset": True,
        "seed": 1000123,
    }

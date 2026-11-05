"""CPU test of docker/psi0/serve_psi0_seeded.py (S1-03, docs/he/tray.md 8.5).

Fake torch, fake Server. No `from __future__ import annotations` here: like Psi0's
serve_psi0_simple.py, the fake keeps real annotation objects, which FastAPI reads as is.
"""

import importlib.util
import inspect
import sys
import types
from pathlib import Path
from typing import Any

import pytest

LAUNCHER = Path(__file__).resolve().parents[2] / "docker" / "psi0" / "serve_psi0_seeded.py"


def load_launcher() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("serve_psi0_seeded", LAUNCHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRequest:
    """Stands in for fastapi.Request in the signature."""


def make_server() -> Any:
    class FakeServer:
        def __init__(self) -> None:
            self.calls: list[Any] = []

        def predict_action(self, payload: dict[str, Any], http_request: FakeRequest) -> str:
            self.calls.append(payload)
            return "action"

    return FakeServer


@pytest.fixture
def fake_torch(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[int]]:
    seen: dict[str, list[int]] = {"manual_seed": [], "cuda_manual_seed_all": []}
    torch = types.ModuleType("torch")
    torch.manual_seed = seen["manual_seed"].append  # type: ignore[attr-defined]
    cuda = types.SimpleNamespace(manual_seed_all=seen["cuda_manual_seed_all"].append)
    torch.cuda = cuda  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", torch)
    return seen


def test_reset_with_seed_seeds_torch_then_delegates(fake_torch: dict[str, list[int]]) -> None:
    launcher = load_launcher()
    server_cls = make_server()
    launcher.install(server_cls, launcher.torch_seed)
    server = server_cls()
    payload = {"history": {"reset": True, "seed": 1234}, "state": {}}

    assert server.predict_action(payload, FakeRequest()) == "action"
    assert fake_torch == {"manual_seed": [1234], "cuda_manual_seed_all": [1234]}
    assert server.calls == [payload]


@pytest.mark.parametrize(
    "history",
    [
        {"reset": True},  # SIMPLE's own client: no seed
        {"seed": 7},  # seed without reset: mid-episode, keep the stream
        {"reset": False, "seed": 7},
        {"reset": True, "seed": None},
        {},
        None,  # the sonic client posts history as null
    ],
)
def test_no_seed_behaves_as_before(fake_torch: dict[str, list[int]], history: Any) -> None:
    launcher = load_launcher()
    server_cls = make_server()
    launcher.install(server_cls, launcher.torch_seed)
    server = server_cls()

    assert server.predict_action({"history": history}, FakeRequest()) == "action"
    assert fake_torch == {"manual_seed": [], "cuda_manual_seed_all": []}
    assert len(server.calls) == 1


def test_signature_is_kept_for_fastapi() -> None:
    launcher = load_launcher()
    server_cls = make_server()
    original = inspect.signature(server_cls.predict_action)
    bound_original = inspect.signature(server_cls().predict_action)

    launcher.install(server_cls, lambda seed: None)

    assert server_cls.predict_action.__wrapped__ is not None
    assert inspect.signature(server_cls.predict_action) == original
    # FastAPI inspects the bound method that run() registers: (payload, http_request).
    bound = inspect.signature(server_cls().predict_action)
    assert bound == bound_original
    assert list(bound.parameters) == ["payload", "http_request"]
    assert bound.parameters["http_request"].annotation is FakeRequest

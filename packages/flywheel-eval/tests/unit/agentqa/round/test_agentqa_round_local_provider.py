"""Which endpoint errors the local provider lets the gateway send again (DA-43 task 5.1)."""

from __future__ import annotations

import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import pytest
from flywheel.eval.agentqa.endpoint import OpenAIEndpoint
from flywheel.eval.agentqa.round.gateway import Gateway
from flywheel.eval.agentqa.round.providers import ProviderError
from flywheel.eval.agentqa.round.providers.local import LocalEndpointModel
from helpers_round import admitted_run
from test_agentqa_round_gateway import Factory, make_config, request


def _http(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://127.0.0.1:9/v1", code, "x", Message(), None)


class _Raising:
    def __init__(self, error: BaseException) -> None:
        self.error, self.calls = error, 0

    def open(self, req: urllib.request.Request, timeout: float) -> None:
        self.calls += 1
        raise self.error


def _model(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> tuple[
        LocalEndpointModel, _Raising]:
    opener = _Raising(error)
    monkeypatch.setattr(OpenAIEndpoint, "_opener", lambda self: opener)
    endpoint = OpenAIEndpoint(base_url="http://127.0.0.1:9/v1", model="m", revision="r")
    return LocalEndpointModel(endpoint), opener


@pytest.mark.parametrize(("error", "retry"), [
    (_http(400), False), (_http(401), False), (_http(404), False), (_http(302), False),
    (_http(429), True), (_http(500), True), (_http(503), True),
    (urllib.error.URLError("refused"), True), (TimeoutError("timed out"), True),
    (ConnectionResetError("reset"), True),
])
def test_only_network_errors_timeouts_429_and_5xx_are_retryable(
        monkeypatch: pytest.MonkeyPatch, error: BaseException, retry: bool) -> None:
    model, _ = _model(monkeypatch, error)
    with pytest.raises(ProviderError) as raised:
        model.chat("s", "u", reply_schema=None, max_tokens=100, timeout_s=5)
    assert raised.value.retryable is retry


def test_a_400_is_sent_once_and_counts_one_call(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model, opener = _model(monkeypatch, _http(400))
    gateway = Gateway(admitted_run(tmp_path), make_config(), factory=Factory(local=model),  # type: ignore[arg-type]
                      sleep=lambda s: None)
    assert gateway.call("rank", request()).status == "failed"
    assert opener.calls == 1 and gateway.usage.calls == 1

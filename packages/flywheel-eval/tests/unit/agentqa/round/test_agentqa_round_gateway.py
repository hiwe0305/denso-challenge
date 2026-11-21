"""The model gateway: class check, budget, retries, record and replay (DA-43 task 5.1)."""

from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.eval.agentqa.endpoint import OpenAIEndpoint
from flywheel.eval.agentqa.round.gateway import MODEL_CALLS_FILE, Gateway
from flywheel.eval.agentqa.round.gateway_config import (
    Budget,
    GatewayConfig,
    GatewayRefused,
    Profile,
    Retry,
)
from flywheel.eval.agentqa.round.providers import ChatModel, ProviderError, ProviderReply
from flywheel.eval.agentqa.round.records import ModelCallRecord, ModelRequest
from helpers_round import ScriptedChat, admitted_run

LOCAL = Profile(provider="local_openai", hosted=False, endpoint="agent", max_tokens=500,
                timeout_s=30)
HOSTED = Profile(provider="openai_compatible", hosted=True, model="m",
                 api_key_env="FW_TEST_HOSTED_KEY", max_tokens=500, timeout_s=30,
                 usd_per_mtok_in=1000.0, usd_per_mtok_out=1000.0)
ROLES = ("adjudicate", "rank", "look")


def make_config(*, rank_public: str = "local", hosted: bool = False,
                budget: Budget | None = None, retries: int = 2) -> GatewayConfig:
    routes: dict[str, dict[str, str]] = {
        r: {"public": "local", "internal": "local", "restricted": "local"} for r in ROLES}
    routes["rank"]["public"] = rank_public
    return GatewayConfig.model_validate({
        "profiles": {"local": LOCAL, "hosted": HOSTED}, "routes": routes,
        "budget": budget or Budget(max_calls=10, max_input_tokens=10_000, max_usd=1.0,
                                   chars_per_token=2.0),
        "retry": Retry(retries=retries, base_delay_s=1.5), "hosted_enabled": hosted})


class Factory:
    """Hands out scripted providers by profile name and counts what it built."""

    def __init__(self, **providers: ScriptedChat) -> None:
        self.providers = providers
        self.built: list[str] = []

    def __call__(self, name: str, profile: Profile) -> ChatModel:
        self.built.append(name)
        return self.providers[name]


def request(unit: str = "u1", user: str = '{"facts": []}', max_tokens: int = 200) -> ModelRequest:
    return ModelRequest(unit=unit, system="You rank.", user=user, max_tokens=max_tokens)


def lines(run: Path) -> list[ModelCallRecord]:
    return [ModelCallRecord.model_validate_json(x)
            for x in (run / MODEL_CALLS_FILE).read_text().splitlines()]


# --- the class check -----------------------------------------------------------------

@pytest.mark.parametrize(("data_class", "confirmed", "hosted_on", "needle"), [
    ("public", True, False, "hosted block is off"),
    ("public", False, True, "unknown"),
    ("internal", True, True, "internal"),
    ("restricted", True, True, "restricted"),
])
def test_hosted_route_is_refused_before_any_provider_is_built(
        tmp_path: Path, data_class: str, confirmed: bool, hosted_on: bool, needle: str) -> None:
    run = admitted_run(tmp_path, data_class, confirmed=confirmed)  # type: ignore[arg-type]
    config = make_config(hosted=hosted_on)
    if data_class != "public":  # the config validator refuses this; the gateway must too
        routes = {r: dict(t) for r, t in config.routes.items()}
        routes["rank"][data_class] = "hosted"  # type: ignore[index]
        config = GatewayConfig.model_construct(**{**dict(config), "routes": routes})
    else:
        config = make_config(rank_public="hosted", hosted=hosted_on)
    factory = Factory(local=ScriptedChat([]), hosted=ScriptedChat([]))
    with pytest.raises(GatewayRefused, match=needle):
        Gateway(run, config, factory=factory)
    assert factory.built == [] and not (run / MODEL_CALLS_FILE).exists()


def test_call_checks_the_class_again(tmp_path: Path) -> None:
    run = admitted_run(tmp_path, "public")
    factory = Factory(local=ScriptedChat([]), hosted=ScriptedChat(["{}"]))
    gateway = Gateway(run, make_config(rank_public="hosted", hosted=True), factory=factory)
    unknown = admitted_run(tmp_path, "public", confirmed=False, name="other")
    gateway._admission = Gateway(unknown, make_config(), factory=factory)._admission
    with pytest.raises(GatewayRefused, match="unknown"):
        gateway.call("rank", request())
    assert factory.built == [] and not (run / MODEL_CALLS_FILE).exists()


def test_no_admission_and_unknown_role_are_refused(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(GatewayRefused, match="class is unknown"):
        Gateway(empty, make_config(), factory=Factory())
    gateway = Gateway(admitted_run(tmp_path), make_config(), factory=Factory())
    with pytest.raises(GatewayRefused, match="unknown role"):
        gateway.call("summarize", request())


def test_confirmed_public_pack_may_reach_a_hosted_profile(tmp_path: Path) -> None:
    run = admitted_run(tmp_path, "public")
    hosted = ScriptedChat([ProviderReply("{}", 100, 10)], host="api.example")
    factory = Factory(local=ScriptedChat([]), hosted=hosted)
    gateway = Gateway(run, make_config(rank_public="hosted", hosted=True), factory=factory)
    reply = gateway.call("rank", request())
    assert reply.status == "ok" and factory.built == ["hosted"]
    (line,) = lines(run)
    assert line.hosted and line.host == "api.example" and line.data_class == "public"
    assert line.usd == pytest.approx((100 + 10) * 1000.0 / 1e6)


def test_the_default_factory_builds_no_hosted_provider_yet(tmp_path: Path) -> None:
    gateway = Gateway(admitted_run(tmp_path), make_config(rank_public="hosted", hosted=True))
    with pytest.raises(GatewayRefused, match="task 5.4"):
        gateway.call("rank", request())


# --- budget --------------------------------------------------------------------------

def test_max_calls_stops_the_gateway_without_raising(tmp_path: Path) -> None:
    run = admitted_run(tmp_path)
    local = ScriptedChat(["a", "b", "c"])
    budget = Budget(max_calls=2, max_input_tokens=10_000, max_usd=0, chars_per_token=2)
    gateway = Gateway(run, make_config(budget=budget), factory=Factory(local=local))
    statuses = [gateway.call("adjudicate", request(unit=f"u{i}")).status for i in range(4)]
    assert statuses == ["ok", "ok", "budget_exhausted", "budget_exhausted"]
    assert len(local.calls) == 2 and gateway.usage.exhausted == "max_calls 2"
    assert [x.tries for x in lines(run)] == [1, 1, 0, 0]


def test_input_tokens_are_capped_before_the_call(tmp_path: Path) -> None:
    budget = Budget(max_calls=10, max_input_tokens=50, max_usd=0, chars_per_token=2)
    local = ScriptedChat(["a"])
    gateway = Gateway(admitted_run(tmp_path), make_config(budget=budget),
                      factory=Factory(local=local))
    reply = gateway.call("rank", request(user="x" * 200))  # ~105 tokens estimated
    assert reply.status == "budget_exhausted" and local.calls == []


def test_hosted_dollars_are_capped(tmp_path: Path) -> None:
    budget = Budget(max_calls=10, max_input_tokens=10_000, max_usd=0.2, chars_per_token=2)
    hosted = ScriptedChat([ProviderReply("{}", 100, 50)] * 3)
    gateway = Gateway(admitted_run(tmp_path), make_config(rank_public="hosted", hosted=True,
                                                          budget=budget),
                      factory=Factory(local=ScriptedChat([]), hosted=hosted))
    # estimated (11 + 200) x 1000 / 1e6 = 0.211 USD at max_tokens 200, over 0.2
    assert gateway.call("rank", request()).status == "budget_exhausted"
    assert hosted.calls == []


# --- retries -------------------------------------------------------------------------

def test_retries_back_off_and_then_succeed(tmp_path: Path) -> None:
    waits: list[float] = []
    local = ScriptedChat([ProviderError("timeout"), ProviderError("503"), "ok"])
    gateway = Gateway(admitted_run(tmp_path), make_config(), factory=Factory(local=local),
                      sleep=waits.append)
    assert gateway.call("rank", request()).status == "ok"
    assert waits == [1.5, 3.0] and len(local.calls) == 3
    assert local.calls[0][2:] == (200, 30)  # max_tokens and the profile's timeout


def test_a_call_that_keeps_failing_is_an_outcome(tmp_path: Path) -> None:
    run = admitted_run(tmp_path)
    local = ScriptedChat([ProviderError("down")] * 3)
    gateway = Gateway(run, make_config(), factory=Factory(local=local), sleep=lambda s: None)
    reply = gateway.call("rank", request())
    assert reply.status == "failed" and "down" in reply.error and len(local.calls) == 3
    assert lines(run)[0].tries == 3


def test_not_retryable_and_cut_replies_are_not_tried_again(tmp_path: Path) -> None:
    local = ScriptedChat([ProviderError("window", retryable=False),
                          ProviderReply('{"half', 10, 500, cut=True)])
    gateway = Gateway(admitted_run(tmp_path), make_config(), factory=Factory(local=local),
                      sleep=lambda s: None)
    assert gateway.call("rank", request(unit="a")).status == "failed"
    cut = gateway.call("rank", request(unit="b"))
    assert cut.status == "cut" and cut.text == '{"half' and len(local.calls) == 2


# --- record and replay ---------------------------------------------------------------

def test_a_recorded_request_is_answered_from_the_file(tmp_path: Path) -> None:
    run = admitted_run(tmp_path)
    ticks = iter([10.0, 12.5, 20.0, 20.0])
    first = Gateway(run, make_config(), factory=Factory(local=ScriptedChat(["A"])),
                    clock=lambda: next(ticks))
    assert first.call("rank", request()).text == "A"
    again = ScriptedChat(["B", "C"])
    second = Gateway(run, make_config(), factory=Factory(local=again))
    replayed = second.call("rank", request())
    assert (replayed.text, replayed.replayed, replayed.call_id) == ("A", True, "M1")
    assert again.calls == [] and second.usage.calls == 0
    assert second.call("rank", request(max_tokens=300)).text == "B"  # another request
    records = lines(run)
    assert [r.call_id for r in records] == ["M1", "M2"]
    assert records[0].seconds == 2.5 and records[0].tokens_in == 100


def test_a_failed_call_is_not_replayed(tmp_path: Path) -> None:
    run = admitted_run(tmp_path)
    Gateway(run, make_config(retries=0),
            factory=Factory(local=ScriptedChat([ProviderError("x")]))).call("rank", request())
    reply = Gateway(run, make_config(), factory=Factory(local=ScriptedChat(["ok"]))
                    ).call("rank", request())
    assert reply.status == "ok" and not reply.replayed and len(lines(run)) == 2


# --- the local adapter, and no key in any file ---------------------------------------

class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def test_local_endpoint_sends_the_key_but_no_file_holds_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "sk-test-0123456789abcdef"
    monkeypatch.setenv("FW_TEST_LOCAL_KEY", secret)
    agent = tmp_path / "agent.yaml"
    agent.write_text(yaml.safe_dump({"local_hosts": [], "models": {"agent": {
        "base_url": "http://127.0.0.1:9/v1", "model": "nemo", "revision": "d1",
        "max_tokens": 300, "timeout_s": 60, "api_key_env": "FW_TEST_LOCAL_KEY"}}}))
    sent: list[urllib.request.Request] = []

    class Opener:
        def open(self, req: urllib.request.Request, timeout: float) -> _Response:
            sent.append(req)
            body = {"choices": [{"message": {"content": f'{{"echo": "{secret}"}}'},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 42, "completion_tokens": 7}}
            return _Response(json.dumps(body).encode())

    monkeypatch.setattr(OpenAIEndpoint, "_opener", lambda self: Opener())
    run = admitted_run(tmp_path)
    gateway = Gateway(run, make_config(), agent_config=agent)
    reply = gateway.call("rank", request(max_tokens=400))
    assert reply.status == "ok"
    (req,) = sent
    assert req.get_header("Authorization") == f"Bearer {secret}"
    body: dict[str, Any] = json.loads(req.data)  # type: ignore[arg-type]
    assert body["max_tokens"] == 300 and body["response_format"] == {"type": "json_object"}
    (line,) = lines(run)
    assert (line.model, line.revision, line.host) == ("nemo", "d1", "127.0.0.1")
    assert (line.tokens_in, line.tokens_out, line.tokens_estimated) == (42, 7, False)
    for path in run.rglob("*"):
        text = path.read_text()
        assert secret not in text and "Authorization" not in text and "Bearer" not in text

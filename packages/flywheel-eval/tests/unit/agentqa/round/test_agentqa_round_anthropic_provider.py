"""The anthropic provider, with a fake client and the real SDK exception classes (DA-43 5.4).

Needs the optional `agentqa-hosted` group; skipped as a whole when it is not installed.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from flywheel.eval.agentqa.round.gateway import Gateway, build_provider
from flywheel.eval.agentqa.round.gateway_config import GatewayRefused, Profile
from flywheel.eval.agentqa.round.providers import ProviderError
from flywheel.eval.agentqa.round.providers.anthropic import AnthropicModel
from flywheel.eval.agentqa.round.records import ModelRequest
from helpers_round import admitted_run
from test_agentqa_round_gateway import make_config

anthropic = pytest.importorskip("anthropic", reason="needs the agentqa-hosted group")
httpx2 = pytest.importorskip("httpx2", reason="needs the agentqa-hosted group")

KEY_ENV = "FW_TEST_HOSTED_KEY"
SECRET = "sk-test-secret-value"


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(KEY_ENV, SECRET)


def block(kind: str, text: str = "") -> Any:
    return SimpleNamespace(type=kind, text=text) if kind == "text" else SimpleNamespace(type=kind)


def message(blocks: list[Any], stop: str = "end_turn", usage: Any = None) -> Any:
    usage = SimpleNamespace(input_tokens=11, output_tokens=7) if usage is None else usage
    return SimpleNamespace(content=blocks, stop_reason=stop, usage=usage)


class FakeClient:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.sent: dict[str, Any] = {}
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> Any:
        self.sent = kwargs
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def status_error(code: int) -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "https://x.example/v1/messages")
    return anthropic.APIStatusError("boom", response=httpx2.Response(code, request=request),
                                    body=None)


def claude(outcome: Any, **kw: Any) -> tuple[AnthropicModel, FakeClient]:
    client = FakeClient(outcome)
    return AnthropicModel("claude-x", KEY_ENV, client=client, **kw), client


def ask(model: Any) -> Any:
    return model.chat("sys", "usr", reply_schema={"type": "object"}, max_tokens=50, timeout_s=9)



# --- anthropic ------------------------------------------------------------------------

def test_anthropic_keeps_text_blocks_only_and_counts_tokens() -> None:
    model, client = claude(message([block("thinking"), block("text", "a"), block("text", "b")]),
                           thinking=True)
    reply = ask(model)
    assert (reply.text, reply.tokens_in, reply.tokens_out, reply.cut) == ("ab", 11, 7, False)
    assert client.sent["thinking"] == {"type": "adaptive"}
    assert client.sent["timeout"] == 9 and client.sent["max_tokens"] == 50
    assert client.sent["system"] == "sys" and client.sent["messages"][0]["content"] == "usr"


def test_anthropic_sends_no_sampling_params_schema_or_thinking_by_default() -> None:
    model, client = claude(message([block("text", "x")]))
    ask(model)
    for name in ("temperature", "top_p", "top_k", "thinking", "output_config", "tools"):
        assert name not in client.sent


def test_anthropic_cut_and_bad_usage() -> None:
    model, _ = claude(message([block("text", "half")], stop="max_tokens",
                              usage=SimpleNamespace(input_tokens=-1, output_tokens="x")))
    reply = ask(model)
    assert reply.cut and reply.tokens_in is None and reply.tokens_out is None


def test_anthropic_identity() -> None:
    model = AnthropicModel("claude-x", KEY_ENV, base_url="https://api.xah.io/",
                           client=FakeClient(0))
    assert (model.revision, model.host, model.key_env) == ("claude-x", "api.xah.io", KEY_ENV)
    assert AnthropicModel("m", KEY_ENV, client=FakeClient(0)).host == "api.anthropic.com"


@pytest.mark.parametrize(("code", "retry"), [(429, True), (500, True), (502, True), (529, True),
                                             (400, False), (401, False), (403, False),
                                             (404, False)])
def test_anthropic_status_errors(code: int, retry: bool) -> None:
    model, _ = claude(status_error(code))
    with pytest.raises(ProviderError) as info:
        ask(model)
    assert info.value.retryable is retry


def test_anthropic_connection_and_timeout_are_retryable() -> None:
    request = httpx2.Request("POST", "https://x.example/v1/messages")
    for error in (anthropic.APIConnectionError(request=request),
                  anthropic.APITimeoutError(request=request)):
        model, _ = claude(error)
        with pytest.raises(ProviderError) as info:
            ask(model)
        assert info.value.retryable


@pytest.mark.parametrize("reply", [message([block("text", "x")], stop="refusal"),
                                   message([block("thinking")]),
                                   message([block("text", "  ")])])
def test_anthropic_refusal_and_empty_are_not_retryable(reply: Any) -> None:
    model, _ = claude(reply)
    with pytest.raises(ProviderError) as info:
        ask(model)
    assert not info.value.retryable


def test_building_with_a_key_opens_no_connection() -> None:
    model = AnthropicModel("m", KEY_ENV, base_url="https://api.xah.io")
    assert model.host == "api.xah.io"


def test_missing_key_is_refused_without_a_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KEY_ENV)
    with pytest.raises(GatewayRefused, match=KEY_ENV) as info:
        AnthropicModel("m", KEY_ENV)
    assert SECRET not in str(info.value)


# --- the build seam for the anthropic kind ------------------------------------------

def hosted(**kw: Any) -> Profile:
    base: dict[str, Any] = {"provider": "anthropic", "hosted": True, "model": "claude-x",
                            "api_key_env": KEY_ENV, "max_tokens": 10, "timeout_s": 5}
    return Profile.model_validate({**base, **kw})


def test_build_provider_builds_the_anthropic_kind() -> None:
    built = build_provider("a", hosted(base_url="https://api.xah.io", thinking=True))
    assert isinstance(built, AnthropicModel) and built.host == "api.xah.io"


def test_build_provider_names_the_profile_when_the_key_is_missing(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KEY_ENV)
    with pytest.raises(GatewayRefused, match=f"profile a: .*{KEY_ENV}"):
        build_provider("a", hosted())


def test_gateway_with_the_default_factory_runs_a_hosted_call_only_after_the_class_check(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KEY_ENV)  # a refused run must not even read the key
    config = make_config(rank_public="hosted", hosted=False)
    with pytest.raises(GatewayRefused, match="hosted block is off"):
        Gateway(admitted_run(tmp_path, "public"), config)
    with pytest.raises(GatewayRefused, match="unknown"):
        Gateway(admitted_run(tmp_path, "public", confirmed=False, name="o"),
                make_config(rank_public="hosted", hosted=True))
    # allowed class: the key variable is then what is missing, and the call refuses
    gateway = Gateway(admitted_run(tmp_path, "public", name="p"),
                      make_config(rank_public="hosted", hosted=True))
    with pytest.raises(GatewayRefused, match=KEY_ENV):
        gateway.call("rank", ModelRequest(unit="u", system="s", user="u", max_tokens=5))

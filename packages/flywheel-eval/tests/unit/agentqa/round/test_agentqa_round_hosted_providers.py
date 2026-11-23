"""The hosted providers and their build seam, with fakes for the SDK and the network (DA-43 5.4)."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from flywheel.eval.agentqa.round.gateway import Gateway, build_provider
from flywheel.eval.agentqa.round.gateway_config import GatewayRefused, Profile
from flywheel.eval.agentqa.round.providers import ProviderError
from flywheel.eval.agentqa.round.providers.anthropic import AnthropicModel
from flywheel.eval.agentqa.round.providers.openai_hosted import OpenAICompatibleModel
from flywheel.eval.agentqa.round.records import ModelRequest
from helpers_round import admitted_run
from test_agentqa_round_gateway import make_config

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


def test_missing_key_is_refused_without_a_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KEY_ENV)
    with pytest.raises(GatewayRefused, match=KEY_ENV) as info:
        AnthropicModel("m", KEY_ENV)
    assert SECRET not in str(info.value)
    monkeypatch.setenv(KEY_ENV, " ")
    with pytest.raises(GatewayRefused, match=KEY_ENV):
        OpenAICompatibleModel("m", KEY_ENV, "https://h.example/v1")


def test_building_with_a_key_opens_no_connection() -> None:
    model = AnthropicModel("m", KEY_ENV, base_url="https://api.xah.io")
    assert model.host == "api.xah.io"


# --- openai-compatible ----------------------------------------------------------------

class Resp(io.BytesIO):
    def __enter__(self) -> Resp:
        return self


class FakeOpener:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.request: urllib.request.Request | None = None
        self.timeout = 0.0

    def open(self, request: urllib.request.Request, timeout: float) -> Any:
        self.request, self.timeout = request, timeout
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return Resp(json.dumps(self.outcome).encode())


def chat_body(content: str = "hi", finish: str = "stop", usage: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"choices": [{"message": {"content": content},
                                         "finish_reason": finish}]}
    body["usage"] = {"prompt_tokens": 5, "completion_tokens": 3} if usage is None else usage
    return body


def openai(outcome: Any) -> tuple[OpenAICompatibleModel, FakeOpener]:
    opener = FakeOpener(outcome)
    return OpenAICompatibleModel("m", KEY_ENV, "https://h.example/v1/",
                                 opener=opener), opener  # type: ignore[arg-type]


def test_openai_request_and_reply() -> None:
    model, opener = openai(chat_body())
    reply = ask(model)
    assert (reply.text, reply.tokens_in, reply.tokens_out, reply.cut) == ("hi", 5, 3, False)
    request = opener.request
    assert request is not None and request.full_url == "https://h.example/v1/chat/completions"
    assert request.get_header("Authorization") == f"Bearer {SECRET}"
    sent = json.loads(request.data)  # type: ignore[arg-type]
    assert sent["max_tokens"] == 50 and opener.timeout == 9
    assert [m["role"] for m in sent["messages"]] == ["system", "user"]
    assert "temperature" not in sent and "response_format" not in sent
    assert (model.host, model.revision, model.key_env) == ("h.example", "m", KEY_ENV)


def test_openai_cut_and_missing_usage() -> None:
    reply = ask(openai(chat_body(finish="length", usage={}))[0])
    assert reply.cut and reply.tokens_in is None and reply.tokens_out is None


@pytest.mark.parametrize("url", ["http://h.example/v1", "h.example/v1", "https:///v1"])
def test_openai_refuses_a_non_https_base_url(url: str) -> None:
    with pytest.raises(GatewayRefused, match="https"):
        OpenAICompatibleModel("m", KEY_ENV, url)


@pytest.mark.parametrize(("code", "retry"), [(429, True), (500, True), (529, True),
                                             (400, False), (401, False), (403, False),
                                             (404, False), (302, False)])
def test_openai_status_errors(code: int, retry: bool) -> None:
    error = urllib.error.HTTPError("https://h.example", code, "x", {}, None)  # type: ignore[arg-type]
    with pytest.raises(ProviderError) as info:
        ask(openai(error)[0])
    assert info.value.retryable is retry


@pytest.mark.parametrize("error", [urllib.error.URLError("down"), TimeoutError()])
def test_openai_network_errors_are_retryable(error: Exception) -> None:
    with pytest.raises(ProviderError) as info:
        ask(openai(error)[0])
    assert info.value.retryable


@pytest.mark.parametrize("body", [{}, {"choices": []}, chat_body(content="")])
def test_openai_bad_replies_are_not_retryable(body: dict[str, Any]) -> None:
    with pytest.raises(ProviderError) as info:
        ask(openai(body)[0])
    assert not info.value.retryable


# --- the profile and the seam ---------------------------------------------------------

def hosted(**kw: Any) -> Profile:
    base: dict[str, Any] = {"provider": "anthropic", "hosted": True, "model": "claude-x",
                            "api_key_env": KEY_ENV, "max_tokens": 10, "timeout_s": 5}
    return Profile.model_validate({**base, **kw})


def test_profile_validator_for_thinking_and_base_url() -> None:
    assert hosted(thinking=True).thinking
    with pytest.raises(ValueError, match="anthropic provider only"):
        hosted(provider="openai_compatible", base_url="https://h.example", thinking=True)
    with pytest.raises(ValueError, match="needs a base_url"):
        hosted(provider="openai_compatible")
    with pytest.raises(ValueError, match="anthropic provider only"):
        Profile(provider="local_openai", hosted=False, endpoint="agent", max_tokens=1,
                timeout_s=1, thinking=True)
    with pytest.raises(ValueError, match="only an endpoint"):
        Profile(provider="local_openai", hosted=False, endpoint="agent", max_tokens=1,
                timeout_s=1, base_url="https://h.example")


def test_build_provider_builds_each_hosted_kind() -> None:
    first = build_provider("a", hosted(base_url="https://api.xah.io", thinking=True))
    assert isinstance(first, AnthropicModel) and first.host == "api.xah.io"
    second = build_provider("b", hosted(provider="openai_compatible",
                                        base_url="https://h.example/v1"))
    assert isinstance(second, OpenAICompatibleModel) and second.host == "h.example"


def test_build_provider_refusals_name_the_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(GatewayRefused, match="profile b: .*https"):
        build_provider("b", hosted(provider="openai_compatible", base_url="http://h.example"))
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

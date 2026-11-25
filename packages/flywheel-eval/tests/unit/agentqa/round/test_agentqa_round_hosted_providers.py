"""The OpenAI-compatible provider and the hosted build seam, with a fake network (DA-43 5.4).

The anthropic provider against the real SDK classes is tested in
test_agentqa_round_anthropic_provider.py (needs the optional SDK); what needs no SDK
(the URL and environment checks, billed failures) runs here against a fake SDK module.
"""

from __future__ import annotations

import importlib
import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from flywheel.eval.agentqa.round.gateway import Gateway, build_provider
from flywheel.eval.agentqa.round.gateway_config import Budget, GatewayRefused, Profile
from flywheel.eval.agentqa.round.providers import ProviderError
from flywheel.eval.agentqa.round.providers import anthropic as anthropic_provider
from flywheel.eval.agentqa.round.providers.anthropic import AnthropicModel
from flywheel.eval.agentqa.round.providers.openai_hosted import OpenAICompatibleModel
from flywheel.eval.agentqa.round.records import ModelCallRecord, ModelRequest
from helpers_round import admitted_run
from test_agentqa_round_gateway import make_config

KEY_ENV = "FW_TEST_HOSTED_KEY"
SECRET = "sk-test-secret-value"


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(KEY_ENV, SECRET)


def ask(model: Any) -> Any:
    return model.chat("sys", "usr", reply_schema={"type": "object"}, max_tokens=50, timeout_s=9)




def test_empty_key_is_refused_without_a_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(KEY_ENV, " ")
    with pytest.raises(GatewayRefused, match=KEY_ENV) as info:
        OpenAICompatibleModel("m", KEY_ENV, "https://h.example/v1")
    assert SECRET not in str(info.value)


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


@pytest.mark.parametrize(("body", "tokens"), [
    ({"choices": [], "usage": {"prompt_tokens": 40, "completion_tokens": 9}}, (40, 9)),
    (chat_body(content=""), (5, 3)),
    ({"error": "no"}, (None, None)),
    ([1, 2], (None, None)),
])
def test_openai_answered_failures_are_billed_with_their_usage(
        body: Any, tokens: tuple[int | None, int | None]) -> None:
    with pytest.raises(ProviderError) as info:
        ask(openai(body)[0])
    assert info.value.billed and (info.value.tokens_in, info.value.tokens_out) == tokens


def test_openai_non_json_body_is_billed_without_usage() -> None:
    model, opener = openai({})
    opener.open = lambda request, timeout: Resp(b"<html>oops</html>")  # type: ignore[method-assign]
    with pytest.raises(ProviderError) as info:
        ask(model)
    assert info.value.billed and info.value.tokens_in is None


@pytest.mark.parametrize("error", [
    urllib.error.HTTPError("https://h.example", 500, "x", {}, None),  # type: ignore[arg-type]
    urllib.error.URLError("down")])
def test_openai_http_and_network_errors_are_not_billed(error: Exception) -> None:
    with pytest.raises(ProviderError) as info:
        ask(openai(error)[0])
    assert not info.value.billed


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


def test_build_provider_builds_the_openai_compatible_kind() -> None:
    built = build_provider("b", hosted(provider="openai_compatible",
                                       base_url="https://h.example/v1"))
    assert isinstance(built, OpenAICompatibleModel) and built.host == "h.example"


def test_build_provider_refusal_names_the_profile() -> None:
    with pytest.raises(GatewayRefused, match="profile b: .*https"):
        build_provider("b", hosted(provider="openai_compatible", base_url="http://h.example"))


def test_building_the_anthropic_kind_without_the_sdk_names_the_group(
        monkeypatch: pytest.MonkeyPatch) -> None:
    real = importlib.import_module

    def refuse(name: str, *args: Any, **kw: Any) -> Any:
        if name == "anthropic":
            raise ImportError("No module named 'anthropic'")
        return real(name, *args, **kw)

    monkeypatch.setattr(importlib, "import_module", refuse)
    with pytest.raises(GatewayRefused, match="agentqa-hosted"):
        build_provider("a", hosted())


# --- anthropic without the SDK: URL, environment ----------------------------------------

class FakeSDK:
    """Stands in for the `anthropic` module; keeps what the provider built the client with."""

    class APIConnectionError(Exception):
        pass

    def __init__(self) -> None:
        self.client_kwargs: dict[str, Any] = {}
        self.http_kwargs: dict[str, Any] = {}

    def DefaultHttpxClient(self, **kwargs: Any) -> str:  # noqa: N802 - the SDK's name
        self.http_kwargs = kwargs
        return "http-client"

    def Anthropic(self, **kwargs: Any) -> Any:  # noqa: N802 - the SDK's name
        self.client_kwargs = kwargs
        return SimpleNamespace(messages=SimpleNamespace(create=None))


@pytest.fixture
def fake_sdk(monkeypatch: pytest.MonkeyPatch) -> FakeSDK:
    sdk = FakeSDK()
    monkeypatch.setattr(anthropic_provider, "_sdk", lambda: sdk)
    return sdk


@pytest.mark.parametrize("url", ["http://api.anthropic.com", "api.anthropic.com/v1",
                                 "https:///v1", "ftp://h.example"])
def test_anthropic_refuses_a_non_https_or_host_less_base_url(fake_sdk: FakeSDK,
                                                             url: str) -> None:
    with pytest.raises(GatewayRefused, match="https with a host"):
        AnthropicModel("m", KEY_ENV, base_url=url)
    assert fake_sdk.client_kwargs == {}


def test_build_provider_refuses_an_http_anthropic_profile(fake_sdk: FakeSDK) -> None:
    with pytest.raises(GatewayRefused, match="profile a: .*https"):
        build_provider("a", hosted(base_url="http://api.xah.io"))


def test_anthropic_without_base_url_sends_the_default_host_explicitly(
        fake_sdk: FakeSDK, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ANTHROPIC_BASE_URL", "HTTPS_PROXY", "https_proxy", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://elsewhere.example:8080")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-other")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok-other")
    model = AnthropicModel("m", KEY_ENV)
    sent = fake_sdk.client_kwargs
    assert sent["base_url"] == "https://api.anthropic.com" and model.host == "api.anthropic.com"
    assert sent["api_key"] == SECRET and sent["max_retries"] == 0
    assert sent["http_client"] == "http-client"
    assert fake_sdk.http_kwargs == {"trust_env": False, "follow_redirects": False, "mounts": {
        "all://": None, "http://": None, "https://": None}}


def test_anthropic_named_base_url_is_passed_as_given(fake_sdk: FakeSDK,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://elsewhere.example")
    model = AnthropicModel("m", KEY_ENV, base_url="https://api.xah.io/v1")
    assert fake_sdk.client_kwargs["base_url"] == "https://api.xah.io/v1"
    assert model.host == "api.xah.io"


def test_anthropic_refuses_custom_headers_from_the_environment(
        fake_sdk: FakeSDK, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", "Authorization: Bearer other")
    with pytest.raises(GatewayRefused, match="ANTHROPIC_CUSTOM_HEADERS") as info:
        AnthropicModel("m", KEY_ENV)
    assert "other" not in str(info.value) and fake_sdk.client_kwargs == {}
    monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", "  ")  # blank: nothing to send
    AnthropicModel("m", KEY_ENV)


# --- anthropic without the SDK: failures the server answered are billed --------------------

class StatusError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"HTTP {code}")
        self.status_code = code


def claude_message(text: str, stop: str, usage: Any) -> Any:
    blocks = [SimpleNamespace(type="text", text=text)] if text else [
        SimpleNamespace(type="thinking")]
    return SimpleNamespace(content=blocks, stop_reason=stop, usage=usage)


def claude(outcome: Any) -> AnthropicModel:
    def create(**kwargs: Any) -> Any:
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    return AnthropicModel("claude-x", KEY_ENV,
                          client=SimpleNamespace(messages=SimpleNamespace(create=create)))


THINKING_ONLY = claude_message("", "max_tokens",
                               SimpleNamespace(input_tokens=1200, output_tokens=4096))


@pytest.mark.parametrize(("outcome", "tokens"), [
    (THINKING_ONLY, (1200, 4096)),
    (claude_message("no", "refusal", SimpleNamespace(input_tokens=30, output_tokens=2)),
     (30, 2)),
    (claude_message(" ", "end_turn", None), (None, None)),
])
def test_anthropic_answered_failures_are_billed_with_their_usage(
        fake_sdk: FakeSDK, outcome: Any, tokens: tuple[int | None, int | None]) -> None:
    with pytest.raises(ProviderError) as info:
        ask(claude(outcome))
    failure = info.value
    assert failure.billed and not failure.retryable
    assert (failure.tokens_in, failure.tokens_out) == tokens


def test_anthropic_status_and_connection_errors_are_not_billed(fake_sdk: FakeSDK) -> None:
    for error in (StatusError(500), FakeSDK.APIConnectionError()):
        with pytest.raises(ProviderError) as info:
            ask(claude(error))
        assert not info.value.billed


def gateway_lines(run: Path) -> list[ModelCallRecord]:
    return [ModelCallRecord.model_validate_json(x)
            for x in (run / "model_calls.jsonl").read_text().splitlines()]


def anthropic_gateway(tmp_path: Path, outcome: Any) -> tuple[Gateway, Path]:
    run = admitted_run(tmp_path, "public")
    budget = Budget(max_calls=10, max_input_tokens=10_000, max_usd=100.0, chars_per_token=2)
    config = make_config(rank_public="hosted", hosted=True, budget=budget, retries=0)
    model = claude(outcome)
    return Gateway(run, config, factory=lambda name, profile: model), run


def test_an_empty_anthropic_reply_is_charged_by_the_gateway(fake_sdk: FakeSDK,
                                                            tmp_path: Path) -> None:
    gateway, run = anthropic_gateway(tmp_path, THINKING_ONLY)
    reply = gateway.call("rank", ModelRequest(unit="u", system="s", user="u", max_tokens=200))
    assert reply.status == "failed" and "empty reply" in reply.error and reply.text == ""
    (line,) = gateway_lines(run)
    usd = (1200 + 4096) * 1000.0 / 1e6  # the HOSTED profile's prices
    assert (line.tokens_in, line.tokens_out, line.tokens_estimated) == (1200, 4096, False)
    assert line.usd == pytest.approx(usd) and line.status == "failed"
    assert gateway.usage.usd == pytest.approx(usd) and gateway.usage.tokens_out == 4096


def test_an_empty_anthropic_reply_without_usage_is_charged_at_the_bounds(
        fake_sdk: FakeSDK, tmp_path: Path) -> None:
    gateway, run = anthropic_gateway(tmp_path, claude_message("", "end_turn", None))
    gateway.call("rank", ModelRequest(unit="u", system="s" * 10, user="u" * 30, max_tokens=200))
    (line,) = gateway_lines(run)
    assert (line.tokens_in, line.tokens_out, line.tokens_estimated) == (20, 200, True)
    assert line.usd == pytest.approx((20 + 200) * 1000.0 / 1e6) == gateway.usage.usd

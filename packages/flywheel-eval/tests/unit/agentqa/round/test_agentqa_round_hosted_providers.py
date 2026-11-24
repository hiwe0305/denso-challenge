"""The OpenAI-compatible provider and the hosted build seam, with a fake network (DA-43 5.4).

The anthropic provider needs the optional SDK and is tested in
test_agentqa_round_anthropic_provider.py.
"""

from __future__ import annotations

import importlib
import io
import json
import urllib.error
import urllib.request
from typing import Any

import pytest
from flywheel.eval.agentqa.round.gateway import build_provider
from flywheel.eval.agentqa.round.gateway_config import GatewayRefused, Profile
from flywheel.eval.agentqa.round.providers import ProviderError
from flywheel.eval.agentqa.round.providers.openai_hosted import OpenAICompatibleModel

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

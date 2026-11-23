"""The hosted Anthropic provider: the official SDK behind the round's `ChatModel` (DA-43 task 5.4).

The SDK is imported when a model is built, so the package imports without it; without the
`agentqa-hosted` group the build is refused with a message saying so. Building reads the
key from the named variable and opens no connection. The SDK's own retries are off
(`max_retries=0`): the gateway retries and records every try.

Never sent: `temperature`, `top_p`, `top_k` (newer Claude models refuse them) and any
provider-side reply schema (a reseller gateway may not support it; the code checks the
reply instead). Thinking, when asked for, is adaptive and its blocks are dropped.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from flywheel.eval.agentqa.round.gateway_config import GatewayRefused
from flywheel.eval.agentqa.round.providers import ProviderError, ProviderReply

DEFAULT_HOST = "api.anthropic.com"


def _sdk() -> Any:
    try:
        import anthropic
    except ImportError as error:
        raise GatewayRefused("the anthropic SDK is not installed; install the "
                             "agentqa-hosted group (uv sync --extra agentqa-hosted)") from error
    return anthropic


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def retryable_status(status: int) -> bool:
    """Whether the same request may succeed later: 429, any 5xx (529 included)."""
    return status == 429 or status >= 500


class AnthropicModel:
    """One hosted Claude model. `client` is injectable for tests."""

    def __init__(self, model: str, api_key_env: str, *, base_url: str | None = None,
                 thinking: bool = False, client: Any = None) -> None:
        self._model, self._key_env, self._base_url = model, api_key_env, base_url
        self._thinking = thinking
        sdk = _sdk()
        self._sdk = sdk
        if client is None:
            key = os.environ.get(api_key_env, "")
            if not key.strip():
                raise GatewayRefused(f"the key variable {api_key_env} is not set or is empty")
            client = sdk.Anthropic(api_key=key, base_url=base_url, max_retries=0)
        self._client = client

    @property
    def model(self) -> str:
        return self._model

    @property
    def revision(self) -> str:
        return self._model  # a hosted model has no revision beside its id

    @property
    def host(self) -> str:
        return (urlparse(self._base_url).hostname if self._base_url else None) or DEFAULT_HOST

    @property
    def key_env(self) -> str | None:
        return self._key_env

    def _classify(self, error: Exception) -> ProviderError:
        status = getattr(error, "status_code", None)
        if isinstance(status, int):
            return ProviderError(f"{self.host}: HTTP {status}", retryable=retryable_status(status))
        if isinstance(error, self._sdk.APIConnectionError):  # incl. APITimeoutError
            return ProviderError(f"{self.host}: {type(error).__name__}", retryable=True)
        return ProviderError(f"{self.host}: {type(error).__name__}", retryable=False)

    def chat(self, system: str, user: str, *, reply_schema: dict[str, Any] | None,
             max_tokens: int, timeout_s: float) -> ProviderReply:
        del reply_schema  # enforced by code on the reply, not by the provider
        params: dict[str, Any] = {
            "model": self._model, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": user}], "timeout": timeout_s}
        if self._thinking:
            params["thinking"] = {"type": "adaptive"}
        try:
            message = self._client.messages.create(**params)
        except Exception as error:
            raise self._classify(error) from error
        stop = getattr(message, "stop_reason", None)
        if stop == "refusal":
            raise ProviderError(f"{self.host}: the model refused", retryable=False)
        text = "".join(b.text for b in message.content
                       if getattr(b, "type", None) == "text" and isinstance(b.text, str))
        if not text.strip():
            raise ProviderError(f"{self.host}: empty reply (stop_reason {stop})", retryable=False)
        usage = getattr(message, "usage", None)
        return ProviderReply(text=text, tokens_in=_count(getattr(usage, "input_tokens", None)),
                             tokens_out=_count(getattr(usage, "output_tokens", None)),
                             cut=stop == "max_tokens")

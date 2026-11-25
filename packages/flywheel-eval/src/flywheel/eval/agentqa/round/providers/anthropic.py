"""The hosted Anthropic provider: the official SDK behind the round's `ChatModel` (DA-43 task 5.4).

The SDK is imported when a model is built, so the package imports without it; without the
`agentqa-hosted` group the build is refused with a message saying so. Building reads the
key from the named variable and opens no connection. The SDK's own retries are off
(`max_retries=0`): the gateway retries and records every try.

https only, as the OpenAI-style provider. The SDK (2.12.0) reads the environment for where
requests go and what they carry; every such input is given explicitly instead, so the key
goes to the host the record names: the base URL (else `ANTHROPIC_BASE_URL` would win, and
`https://api.anthropic.com` is passed when the profile names none), the key (else
`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, a profile or federation would), and an HTTP
client that ignores proxy and TLS variables. `ANTHROPIC_CUSTOM_HEADERS`, which the SDK lays
over the key header and no argument can switch off, is refused when set.

Never sent: `temperature`, `top_p`, `top_k` (newer Claude models refuse them) and any
provider-side reply schema (a reseller gateway may not support it; the code checks the
reply instead). Thinking, when asked for, is adaptive and its blocks are dropped.
"""

from __future__ import annotations

import importlib
import os
from typing import Any
from urllib.parse import urlparse

from flywheel.eval.agentqa.round.gateway_config import GatewayRefused
from flywheel.eval.agentqa.round.providers import ProviderError, ProviderReply

DEFAULT_HOST = "api.anthropic.com"
# Read by the SDK at build time and laid over its own headers, `Authorization` included.
CUSTOM_HEADERS_ENV = "ANTHROPIC_CUSTOM_HEADERS"


def _sdk() -> Any:
    # Imported by name: the SDK is an optional group, absent from the default environment.
    try:
        return importlib.import_module("anthropic")
    except ImportError as error:
        raise GatewayRefused("the anthropic SDK is not installed; install the "
                             "agentqa-hosted group (uv sync --extra agentqa-hosted)") from error


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def retryable_status(status: int) -> bool:
    """Whether the same request may succeed later: 429, any 5xx (529 included)."""
    return status == 429 or status >= 500


class AnthropicModel:
    """One hosted Claude model. `client` is injectable for tests."""

    def __init__(self, model: str, api_key_env: str, *, base_url: str | None = None,
                 thinking: bool = False, client: Any = None) -> None:
        url = base_url or f"https://{DEFAULT_HOST}"  # explicit: never ANTHROPIC_BASE_URL
        parts = urlparse(url)
        if parts.scheme != "https" or not parts.hostname:
            raise GatewayRefused("a hosted base_url must be https with a host")
        self._model, self._key_env, self._host = model, api_key_env, parts.hostname
        self._thinking = thinking
        sdk = _sdk()
        self._sdk = sdk
        if client is None:
            key = os.environ.get(api_key_env, "")
            if not key.strip():
                raise GatewayRefused(f"the key variable {api_key_env} is not set or is empty")
            if os.environ.get(CUSTOM_HEADERS_ENV, "").strip():
                raise GatewayRefused(f"{CUSTOM_HEADERS_ENV} is set; the SDK would send its "
                                     "headers, which can replace the key, to the host: unset it")
            # No proxy (the SDK maps HTTP(S)_PROXY to mounts; ours win) and no TLS or
            # netrc variables (trust_env), as the OpenAI-style provider ignores proxies.
            http = sdk.DefaultHttpxClient(
                trust_env=False, mounts={"all://": None, "http://": None, "https://": None})
            client = sdk.Anthropic(api_key=key, base_url=url, max_retries=0, http_client=http)
        self._client = client

    @property
    def model(self) -> str:
        return self._model

    @property
    def revision(self) -> str:
        return self._model  # a hosted model has no revision beside its id

    @property
    def host(self) -> str:
        return self._host

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

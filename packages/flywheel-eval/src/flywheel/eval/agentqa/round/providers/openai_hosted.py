"""The hosted OpenAI-style provider: `POST {base_url}/chat/completions` (DA-43 task 5.4).

Standard library only. https only; redirects are refused and proxies ignored, so the key
goes to the one host named in the profile. Not `endpoint.OpenAIEndpoint`, which refuses
every host outside the team's network on purpose. Sends no temperature.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from flywheel.eval.agentqa.round.gateway_config import GatewayRefused
from flywheel.eval.agentqa.round.providers import ProviderError, ProviderReply
from flywheel.eval.agentqa.round.providers.anthropic import retryable_status


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None  # the 3xx then surfaces as an HTTPError, which is not retried


def _default_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


def _count(usage: object, key: str) -> int | None:
    value = usage.get(key) if isinstance(usage, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


class OpenAICompatibleModel:
    """One hosted chat-completions model. `opener` is injectable for tests."""

    def __init__(self, model: str, api_key_env: str, base_url: str, *,
                 opener: urllib.request.OpenerDirector | None = None) -> None:
        parts = urlparse(base_url)
        if parts.scheme != "https" or not parts.hostname:
            raise GatewayRefused("a hosted base_url must be https with a host")
        self._model, self._key_env = model, api_key_env
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._host = parts.hostname
        key = os.environ.get(api_key_env, "")
        if not key.strip():
            raise GatewayRefused(f"the key variable {api_key_env} is not set or is empty")
        self._key = key
        self._opener = opener or _default_opener()

    @property
    def model(self) -> str:
        return self._model

    @property
    def revision(self) -> str:
        return self._model

    @property
    def host(self) -> str:
        return self._host

    @property
    def key_env(self) -> str | None:
        return self._key_env

    def chat(self, system: str, user: str, *, reply_schema: dict[str, Any] | None,
             max_tokens: int, timeout_s: float) -> ProviderReply:
        del reply_schema  # enforced by code on the reply, not by the provider
        body = json.dumps({
            "model": self._model, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]}).encode("utf-8")
        request = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._key}"})
        try:
            with self._opener.open(request, timeout=timeout_s) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raise ProviderError(f"{self._host}: HTTP {error.code}",
                                retryable=retryable_status(error.code)) from error
        except (urllib.error.URLError, OSError) as error:  # incl. TimeoutError
            raise ProviderError(f"{self._host}: {type(error).__name__}",
                                retryable=True) from error
        try:
            data = json.loads(raw)
            choice = data["choices"][0]
            text = choice["message"]["content"]
            finish = choice.get("finish_reason")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
            raise ProviderError(f"{self._host}: the reply is not a chat reply",
                                retryable=False) from error
        if not isinstance(text, str) or not text.strip():
            raise ProviderError(f"{self._host}: empty reply (finish_reason {finish})",
                                retryable=False)
        usage = data.get("usage")
        return ProviderReply(text=text, tokens_in=_count(usage, "prompt_tokens"),
                             tokens_out=_count(usage, "completion_tokens"),
                             cut=finish == "length")

"""The local provider: version 3's `OpenAIEndpoint`, unchanged, behind the round's `ChatModel`.

The endpoint keeps refusing any host outside the team's network (`check_local_url`),
ignores proxies and refuses redirects. Per call the gateway may lower the reply cap and
the timeout below the endpoint's own; it never raises them.
"""

from __future__ import annotations

import urllib.error
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlparse

from flywheel.eval.agentqa.endpoint import EndpointError, OpenAIEndpoint, ReplyCut
from flywheel.eval.agentqa.round.providers import ProviderError, ProviderReply


def _count(usage: dict[str, Any] | None, key: str) -> int | None:
    value = usage.get(key) if usage else None
    return value if isinstance(value, int) and value >= 0 else None


def retryable(error: EndpointError) -> bool:
    """Whether sending the same request again can help: a network error, a timeout, 429, 5xx.

    `EndpointError` carries no status code or kind of its own; `endpoint.complete` raises it
    `from` the urllib exception, so the cause is read, never the message. An HTTP status
    other than 429 and 5xx (a 400 for a bad request, a refused redirect) and a reply that
    is not a chat reply (bad JSON, no message) are not retried. Cleaner would be a
    `status` attribute on `EndpointError` in `endpoint.py`.
    """
    cause = error.__cause__
    if isinstance(cause, urllib.error.HTTPError):  # before URLError and OSError, its bases
        return cause.code == 429 or cause.code >= 500
    return isinstance(cause, urllib.error.URLError | OSError)  # incl. TimeoutError


@dataclass(frozen=True)
class LocalEndpointModel:
    endpoint: OpenAIEndpoint

    @property
    def model(self) -> str:
        return self.endpoint.model

    @property
    def revision(self) -> str:
        return self.endpoint.revision

    @property
    def host(self) -> str:
        return urlparse(self.endpoint.base_url).hostname or ""

    @property
    def key_env(self) -> str | None:
        return self.endpoint.api_key_env

    def _window_too_small(self) -> bool:
        window, budget = self.endpoint.served_window, self.endpoint.context_tokens
        return window is not None and budget is not None and window < budget

    def chat(self, system: str, user: str, *, reply_schema: dict[str, Any] | None,
             max_tokens: int, timeout_s: float) -> ProviderReply:
        base = self.endpoint
        # The endpoint asks the window once and raises once; after that it would send
        # every prompt to a server that cuts them, so the refusal is kept here.
        if self._window_too_small():
            raise ProviderError(f"{base.base_url}: served window {base.served_window} < "
                                f"{base.context_tokens}", retryable=False)
        # A copy with the lower limits; it shares the base's state, so the served
        # window is asked once per run, not once per call.
        call = replace(base, max_tokens=min(max_tokens, base.max_tokens),
                       timeout_s=min(timeout_s, base.timeout_s),
                       json_mode=base.json_mode or reply_schema is not None,
                       _state=base._state)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        cut = False
        try:
            text = call.complete(messages)
        except ReplyCut as error:
            text, cut = error.content, True
        except EndpointError as error:
            raise ProviderError(str(error), retryable=retryable(error)) from error
        usage = call.last_usage
        return ProviderReply(text=text, tokens_in=_count(usage, "prompt_tokens"),
                             tokens_out=_count(usage, "completion_tokens"), cut=cut)

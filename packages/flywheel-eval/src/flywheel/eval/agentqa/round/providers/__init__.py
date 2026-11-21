"""What the model gateway needs of a provider (architecture 20/11 section 8).

One small class per provider kind, all behind `ChatModel`. Only the gateway builds
them (`gateway.build_provider`), and only after it has checked the pack's data class.
Building a provider must not open a connection: the gateway builds it before it looks
a request up in `model_calls.jsonl`.

This `ChatModel` is the round pipeline's; version 3's `endpoint.ChatModel`
(`complete(messages)`) is unchanged and still serves `fw agentqa run`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderReply:
    """The text of one reply and what the provider said it cost.

    Token counts are None when the server did not report them; the gateway then
    records its own estimate and says so.
    """

    text: str
    tokens_in: int | None
    tokens_out: int | None
    cut: bool = False  # the server stopped at max_tokens; `text` is the cut reply


class ProviderError(RuntimeError):
    """A call that brought no reply. `retryable`: network, timeout or overload."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class ChatModel(Protocol):
    """One chat turn: system text, user text, an optional reply schema, limits."""

    @property
    def model(self) -> str: ...

    @property
    def revision(self) -> str: ...

    @property
    def host(self) -> str: ...

    @property
    def key_env(self) -> str | None:
        """Name of the variable holding the key, so the gateway can scrub its value."""
        ...

    def chat(self, system: str, user: str, *, reply_schema: dict[str, Any] | None,
             max_tokens: int, timeout_s: float) -> ProviderReply: ...


__all__ = ["ChatModel", "ProviderError", "ProviderReply"]

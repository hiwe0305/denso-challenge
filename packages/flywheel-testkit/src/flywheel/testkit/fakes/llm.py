"""Deterministic local replacement for an LLM endpoint in tests."""

from collections import deque
from collections.abc import Iterable


class FakeLLM:
    def __init__(self, responses: Iterable[str]) -> None:
        self._responses = deque(responses)
        self.requests: list[str] = []

    def complete(self, prompt: str) -> str:
        self.requests.append(prompt)
        if not self._responses:
            raise RuntimeError("No fake LLM responses remain")
        return self._responses.popleft()

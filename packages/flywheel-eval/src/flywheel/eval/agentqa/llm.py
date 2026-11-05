"""The one call the agent makes to a model, and the client that makes it for real.

`LLMClient` is a single method, `complete(prompt) -> str`, which is exactly what
`flywheel.testkit.fakes.llm.FakeLLM` offers, so development and CI run the whole agent
on the fake and only a run on the 3060 machine reaches Nemotron (DA-20 AC 1).

`ChatEndpointClient` talks to an OpenAI-style `/chat/completions` endpoint with the
standard library, so the lane adds no dependency. It opens its connection without
looking at the proxy variables of the environment: a request to a model served on our
own network must not be routed through a proxy that is somewhere else.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable

from flywheel.contracts.agentqa import AgentModel
from flywheel.eval.agentqa.settings import Endpoint, Prompt


class LLMError(RuntimeError):
    """The model did not answer, or answered in a shape nothing can use."""


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, prompt: str) -> str: ...


class ChatEndpointClient:
    """A local OpenAI-style chat endpoint, one user message per call."""

    def __init__(self, endpoint: Endpoint) -> None:
        self._endpoint = endpoint
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def complete(self, prompt: str) -> str:
        endpoint = self._endpoint
        body = json.dumps(
            {
                "model": endpoint.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": endpoint.temperature,
                "max_tokens": endpoint.max_tokens,
                "stream": False,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{endpoint.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=endpoint.timeout_s) as response:
                payload = json.load(response)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise LLMError(f"{endpoint.base_url}: {exc}") from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"{endpoint.base_url}: reply has no choices[0].message.content") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError(f"{endpoint.base_url}: the model returned no text")
        return content


def agent_model(endpoint: Endpoint, prompt: Prompt) -> AgentModel:
    """The `AgentModel` a report carries: which model, which prompt, which temperature."""
    return AgentModel(
        name=endpoint.model,
        revision=endpoint.revision,
        temperature=endpoint.temperature,
        prompt_sha256=prompt.sha256,
    )

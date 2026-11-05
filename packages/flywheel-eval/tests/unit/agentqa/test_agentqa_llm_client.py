"""DA-20 task 1: the client of the local chat endpoint, against a real local HTTP server."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
from flywheel.eval.agentqa.llm import ChatEndpointClient, LLMError, agent_model
from flywheel.eval.agentqa.settings import Endpoint, load_endpoint, load_prompt

REPO = Path(__file__).resolve().parents[5]


class _Server:
    """Answers every POST with `status` and `body`, and keeps what it was sent."""

    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body
        self.requests: list[dict[str, Any]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - name fixed by http.server
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                outer.requests.append({"path": self.path, "body": json.loads(raw)})
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(outer.body)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                pass

        self.http = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.http.server_port}/v1"
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)

    def __enter__(self) -> _Server:
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.http.shutdown()
        self.http.server_close()


def _reply(text: str) -> bytes:
    return json.dumps({"choices": [{"message": {"role": "assistant", "content": text}}]}).encode()


@pytest.fixture
def endpoint() -> Iterator[Endpoint]:
    yield load_endpoint(REPO / "configs" / "eval" / "agentqa" / "endpoint.yaml")


def test_complete_posts_one_user_message_and_returns_the_text(endpoint: Endpoint) -> None:
    with _Server(200, _reply('{"final": {}}')) as server:
        text = ChatEndpointClient(replace(endpoint, base_url=server.url)).complete("hello")
    assert text == '{"final": {}}'
    (request,) = server.requests
    assert request["path"] == "/v1/chat/completions"
    body = request["body"]
    assert body["model"] == endpoint.model
    assert body["temperature"] == endpoint.temperature
    assert body["max_tokens"] == endpoint.max_tokens
    assert body["messages"] == [{"role": "user", "content": "hello"}]


def test_a_proxy_in_the_environment_is_not_used(
    endpoint: Endpoint, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    with _Server(200, _reply("ok")) as server:
        client = ChatEndpointClient(replace(endpoint, base_url=server.url))
        assert client.complete("hi") == "ok"


@pytest.mark.parametrize(
    "status, body",
    [
        (500, b'{"error": "out of memory"}'),
        (200, b"not json"),
        (200, b'{"choices": []}'),
        (200, b'{"choices": [{"message": {}}]}'),
        (200, b'{"choices": [{"message": {"content": "   "}}]}'),
        (200, b'{"choices": [{"message": {"content": 7}}]}'),
    ],
)
def test_an_unusable_answer_is_an_llm_error(endpoint: Endpoint, status: int, body: bytes) -> None:
    with _Server(status, body) as server:
        client = ChatEndpointClient(replace(endpoint, base_url=server.url))
        with pytest.raises(LLMError):
            client.complete("hi")


def test_a_server_that_is_not_there_is_an_llm_error(endpoint: Endpoint) -> None:
    with _Server(200, b"{}") as server:
        url = server.url
    client = ChatEndpointClient(replace(endpoint, base_url=url, timeout_s=2.0))
    with pytest.raises(LLMError):
        client.complete("hi")


def test_agent_model_carries_the_model_and_the_prompt_hash(endpoint: Endpoint) -> None:
    prompt = load_prompt(REPO / "configs" / "eval" / "agentqa" / "prompts" / "tool_protocol.md")
    model = agent_model(endpoint, prompt)
    assert (model.name, model.revision, model.temperature) == (
        endpoint.model,
        endpoint.revision,
        endpoint.temperature,
    )
    assert model.prompt_sha256 == prompt.sha256

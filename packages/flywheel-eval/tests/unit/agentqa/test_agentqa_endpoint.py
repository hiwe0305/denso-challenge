"""DA-20 AC 1: the local OpenAI-style endpoint, its config, and recorded replies."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
from agentqa_build import AGENT_YAML
from flywheel.eval.agentqa.endpoint import (
    EndpointError,
    OpenAIEndpoint,
    RecordingModel,
    ReplayModel,
    load_endpoint,
)

SEEN: list[dict[str, Any]] = []


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - http.server's name
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append({"path": self.path, "body": body, "auth": self.headers.get("Authorization")})
        reply = {"choices": [{"message": {"role": "assistant", "content": '{"ok": true}'}}]}
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/v1"
    httpd.shutdown()


def test_a_chat_turn_goes_to_chat_completions_in_json_mode(
    server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    SEEN.clear()
    monkeypatch.setenv("FW_TEST_KEY", "secret")
    model = OpenAIEndpoint(base_url=server, model="nemotron", revision="q4",
                           api_key_env="FW_TEST_KEY")
    assert model.complete([{"role": "user", "content": "hi"}]) == '{"ok": true}'
    (call,) = SEEN
    assert call["path"] == "/v1/chat/completions"
    assert call["body"]["model"] == "nemotron"
    assert call["body"]["temperature"] == 0.0
    assert call["body"]["response_format"] == {"type": "json_object"}
    assert call["auth"] == "Bearer secret"


def test_no_server_is_an_endpoint_error() -> None:
    model = OpenAIEndpoint(base_url="http://127.0.0.1:9/v1", model="m", revision="r",
                           timeout_s=0.5)
    with pytest.raises(EndpointError):
        model.complete([{"role": "user", "content": "hi"}])


def test_the_config_names_both_models_and_the_url_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = load_endpoint("agent", AGENT_YAML)
    assert agent.model.startswith("nemotron") and agent.temperature == 0.0
    vision = load_endpoint("vision", AGENT_YAML)
    assert vision.model.startswith("qwen3.5") and not vision.json_mode
    monkeypatch.setenv("FW_AGENTQA_AGENT_URL", "http://localhost:18080/v1")
    assert load_endpoint("agent", AGENT_YAML).base_url == "http://localhost:18080/v1"
    with pytest.raises(ValueError, match="models.nope"):
        load_endpoint("nope", AGENT_YAML)


def test_recorded_replies_replay_in_order(server: str, tmp_path: Path) -> None:
    path = tmp_path / "replies.jsonl"
    live = RecordingModel(OpenAIEndpoint(base_url=server, model="nemotron", revision="q4"), path)
    live.complete([{"role": "user", "content": "a"}])
    live.complete([{"role": "user", "content": "b"}])
    replay = ReplayModel.from_file(path)
    assert replay.name == "nemotron"
    assert [replay.complete([]), replay.complete([])] == ['{"ok": true}'] * 2
    with pytest.raises(EndpointError):
        replay.complete([])

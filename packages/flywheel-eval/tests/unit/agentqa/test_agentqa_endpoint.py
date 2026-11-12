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
    ReplyCut,
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
    assert "Nemotron-3.5-Bolt-E4B" in agent.model and agent.temperature == 0.0
    assert agent.context_tokens == 16384  # the agent checks the server's window
    monkeypatch.setenv("FW_AGENTQA_AGENT_MODEL", "nemotron-3.5-bolt:e4b")
    monkeypatch.setenv("FW_AGENTQA_AGENT_REVISION", "69f2be39b309")
    other = load_endpoint("agent", AGENT_YAML)
    assert (other.model, other.revision) == ("nemotron-3.5-bolt:e4b", "69f2be39b309")
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


@pytest.mark.parametrize("url", [
    "https://api.openai.com/v1", "http://8.8.8.8:11434/v1", "ftp://127.0.0.1/v1", "127.0.0.1:80",
])
def test_an_endpoint_outside_our_network_is_refused(url: str) -> None:
    with pytest.raises(ValueError, match="machine of ours|http"):
        OpenAIEndpoint(base_url=url, model="m", revision="r")


def test_the_url_override_passes_the_same_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FW_AGENTQA_AGENT_URL", "https://api.example.com/v1")
    with pytest.raises(ValueError, match="machine of ours"):
        load_endpoint("agent", AGENT_YAML)
    for url in ("http://10.0.0.5:11434/v1", "http://rtx3060:11434/v1", "http://[::1]:8000/v1"):
        monkeypatch.setenv("FW_AGENTQA_AGENT_URL", url)
        assert load_endpoint("agent", AGENT_YAML).base_url == url


class _Redirect(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - http.server's name
        self.send_response(307)
        self.send_header("Location", "https://api.example.com/v1/chat/completions")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args: object) -> None:
        pass


def test_a_redirect_and_the_proxy_variables_are_not_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    httpd = HTTPServer(("127.0.0.1", 0), _Redirect)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        # A proxy that does not exist: the request only works if it is ignored.
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
        monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
        model = OpenAIEndpoint(base_url=f"http://127.0.0.1:{httpd.server_address[1]}/v1",
                               model="m", revision="r", timeout_s=2.0)
        with pytest.raises(EndpointError, match="redirect .* refused"):
            model.complete([{"role": "user", "content": "hi"}])
    finally:
        httpd.shutdown()


class _Ollama(BaseHTTPRequestHandler):
    """An Ollama-like server: `finish` for every reply, `window` in /api/ps (None: absent)."""

    finish = "stop"
    window: int | None = 16384

    def _send(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802 - http.server's name
        self.rfile.read(int(self.headers["Content-Length"]))
        self._send({"choices": [{"message": {"content": '{"decisions": [{"ci'},
                                 "finish_reason": self.finish}],
                    "usage": {"prompt_tokens": 2642, "completion_tokens": 6144}})

    def do_GET(self) -> None:  # noqa: N802 - http.server's name
        entry: dict[str, Any] = {"name": "nemotron", "model": "nemotron"}
        if self.window is not None:
            entry["context_length"] = self.window
        self._send({"models": [entry]})

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def ollama() -> Iterator[tuple[str, type[_Ollama]]]:
    handler = type("Handler", (_Ollama,), {})
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/v1", handler
    httpd.shutdown()


def test_a_reply_cut_at_max_tokens_is_its_own_error(
    ollama: tuple[str, type[_Ollama]], tmp_path: Path
) -> None:
    """PR #185 review S1: a cut reply used to come back as half a JSON object."""
    url, handler = ollama
    handler.finish = "length"
    live = RecordingModel(OpenAIEndpoint(base_url=url, model="nemotron", revision="q4"),
                          tmp_path / "r.jsonl")
    with pytest.raises(ReplyCut, match="max_tokens 4096") as cut:
        live.complete([{"role": "user", "content": "hi"}])
    assert cut.value.content == '{"decisions": [{"ci'
    (row,) = [json.loads(x) for x in (tmp_path / "r.jsonl").read_text().splitlines()]
    assert row["finish_reason"] == "length" and row["usage"]["completion_tokens"] == 6144
    with pytest.raises(ReplyCut):  # a replay meets the same cut
        ReplayModel.from_file(tmp_path / "r.jsonl").complete([])


@pytest.mark.parametrize(("window", "refused"), [(4096, True), (16384, False), (None, False)])
def test_the_servers_window_is_checked_once(
    ollama: tuple[str, type[_Ollama]], window: int | None, refused: bool
) -> None:
    """PR #185 review S4: Ollama's default window was 4096 on the laptop of #175."""
    url, handler = ollama
    handler.window = window
    model = OpenAIEndpoint(base_url=url, model="nemotron", revision="q4", context_tokens=16384)
    if refused:
        with pytest.raises(EndpointError, match="4096-token window"):
            model.complete([{"role": "user", "content": "hi"}])
        return
    model.complete([{"role": "user", "content": "hi"}])
    assert model.served_window == window and model.last_usage == {
        "prompt_tokens": 2642, "completion_tokens": 6144}

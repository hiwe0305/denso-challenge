"""DA-04 task 3: the labelling-model client and how answers are read (D6)."""

from __future__ import annotations

import base64
import json
import threading
import urllib.error
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from flywheel.data.ingest.egocentric.vlm import (
    EndpointRefused,
    ModelLabeler,
    ModelPointer,
    ModelSuggester,
    OpenAIVision,
    parse_index,
    parse_point,
    parse_sentence,
)


@pytest.fixture
def server() -> Iterator[tuple[str, list[dict[str, Any]]]]:
    seen: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append({"path": self.path, "body": body})
            data = json.dumps({"choices": [{"message": {"content": "Image 3."}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args: Any) -> None:
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1", seen
    httpd.shutdown()


def test_the_client_posts_images_as_data_urls(server: tuple[str, list[dict[str, Any]]]) -> None:
    url, seen = server
    model = OpenAIVision(url, "robobrain-test", timeout_s=5)
    assert model.complete("which?", [b"\xff\xd8one", b"\xff\xd8two"]) == "Image 3."
    request = seen[0]
    assert request["path"] == "/v1/chat/completions"
    body = request["body"]
    assert body["model"] == "robobrain-test" and body["temperature"] == 0.0
    content = body["messages"][0]["content"]
    assert [c["type"] for c in content] == ["image_url", "image_url", "text"]
    prefix = "data:image/jpeg;base64,"
    assert base64.b64decode(content[1]["image_url"]["url"][len(prefix):]) == b"\xff\xd8two"
    assert len(model.latencies_s) == 1


def test_the_roles_turn_answers_into_frames_sentences_and_points(
    server: tuple[str, list[dict[str, Any]]]
) -> None:
    url, _ = server
    model = OpenAIVision(url, "m", timeout_s=5)
    assert ModelSuggester(model).suggest([b"a"] * 4, [10, 20, 30, 40], "grasp", "x") == 30
    assert ModelLabeler(model).describe([b"a"], "pick", "x") == "Image 3."
    assert ModelPointer(model).point(b"a", "cup", (640, 360)) is None


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:11434/v1", "http://localhost:8000/v1", "http://10.0.0.5/v1",
    "https://192.168.1.20:8443/v1", "http://[::1]:8000/v1",
])
def test_local_endpoints_are_accepted(url: str) -> None:
    assert OpenAIVision(url + "/", "m").endpoint == url


@pytest.mark.parametrize("url", [
    "https://api.openai.com/v1", "http://8.8.8.8/v1", "http://rtx3060.example.com/v1",
    "ftp://127.0.0.1/v1", "file:///etc/passwd", "127.0.0.1:11434/v1", "http:///v1",
])
def test_other_endpoints_are_refused(url: str) -> None:
    """Review of PR 152: egocentric frames go to no hosted API (CLAUDE.md)."""
    with pytest.raises(EndpointRefused):
        OpenAIVision(url, "m")


def test_a_named_host_needs_local_hosts() -> None:
    with pytest.raises(EndpointRefused, match="local_hosts"):
        OpenAIVision("http://rtx3060:11434/v1", "m")
    assert OpenAIVision("http://rtx3060:11434/v1", "m", local_hosts=("rtx3060",)).endpoint


def test_the_client_ignores_proxy_variables(
    server: tuple[str, list[dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    url, seen = server
    for name in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")  # nothing listens there
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    assert OpenAIVision(url, "m", timeout_s=5).complete("which?", [b"a"]) == "Image 3."
    assert len(seen) == 1


def test_a_redirect_is_refused() -> None:
    hits: list[str] = []

    class Redirect(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            hits.append(self.path)
            self.send_response(307)
            self.send_header("Location", "http://8.8.8.8/v1/chat/completions")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args: Any) -> None:
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        model = OpenAIVision(f"http://127.0.0.1:{httpd.server_port}/v1", "m", timeout_s=5)
        with pytest.raises(urllib.error.HTTPError, match="redirect to http://8.8.8.8"):
            model.complete("which?", [b"a"])
        assert hits == ["/v1/chat/completions"]
    finally:
        httpd.shutdown()


@pytest.mark.parametrize(("text", "n", "expected"), [
    ("3", 5, 2), ("Image 5.", 5, 4), ("image 0", 5, None), ("7", 5, None), ("none", 5, None),
])
def test_parse_index(text: str, n: int, expected: int | None) -> None:
    assert parse_index(text, n) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ('<points coords="1 1 543 567">the box</points>', (0.543, 0.567)),  # Molmo2-4B, seen
    ('<points coords="1 1 543 567 2 600 500;2 1 10 10">x</points>', (0.543, 0.567)),
    ('<points coords="1 523 412">cup</points>', (0.523, 0.412)),
    ('<point x="61.5" y="40.0" alt="cup">cup</point>', (0.615, 0.40)),  # Molmo 1
    ("[(700, 526)]", (0.700, 0.526)),  # Qwen3-VL / RoboBrain, 0-1000
    ("[0.25, 0.5]", (0.25, 0.5)),
    ("(1280, 540)", (1280 / 1920, 0.5)),  # pixels of a 1920x1080 frame
    ("no point here", None),
    ("[(1500, 2000)]", None),
])
def test_parse_point(text: str, expected: tuple[float, float] | None) -> None:
    point = parse_point(text, (1920, 1080))
    if expected is None:
        assert point is None
    else:
        assert point == pytest.approx(expected)


def test_parse_sentence() -> None:
    assert parse_sentence('"Pick up the black stapler."\n') == "Pick up the black stapler."
    assert parse_sentence("Sentence: Place it in the lid.") == "Place it in the lid."
    assert parse_sentence("ok") is None
    assert parse_sentence("") is None

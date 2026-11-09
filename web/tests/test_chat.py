"""The chat pane, read-only minimum (DESIGN.md §5.4, §6.2).

What is checked is what the pane may not do, more than what it says:

* it reads as `agent_ro`: no group S on M3 (R8), no sealed evaluation even when
  ADMIN asks (BR-10);
* nothing that is not `public` reaches the prompt (R6), and the endpoint must
  be a machine of ours;
* a message keeps the ids it loaded and the sha256 of the prompt, not the
  prompt (§5.4 point 3), and the assistant never carries an action.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from web.api.actions import ActionStore
from web.api.app import create_app
from web.api.chat import (
    AGENT_ROLE,
    LocalEndpoint,
    build_context,
    build_prompt,
    prompt_sha256,
)
from web.api.readmodel import SinkReadModel, SinkTables
from web.fwsync.runner import run_import
from web.fwsync.sink import JsonlSink

ROOT = Path(__file__).resolve().parents[2]
MOCK = ROOT / "mock" / "demo-17-11"
DEMO_DAY = datetime(2026, 11, 17, 9, 0, tzinfo=timezone.utc)
SEALED = "ev_B_holdout"


class ScriptedModel:
    """Answers with a fixed text and keeps every prompt it was sent."""

    name = "scripted-test"

    def __init__(self) -> None:
        self.prompts: list[list[dict[str, str]]] = []

    def complete(self, messages: Sequence[dict[str, str]]) -> str:
        self.prompts.append(list(messages))
        return "Trả lời thử."


@pytest.fixture(scope="module")
def sink(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("sink")
    result = run_import(MOCK, JsonlSink(directory=directory), origin="mock")
    assert result.status == "ok", result.errors
    return directory


@pytest.fixture
def model(sink: Path) -> SinkReadModel:
    return SinkReadModel(SinkTables(sink), now=lambda: DEMO_DAY)


@pytest.fixture
def scripted() -> ScriptedModel:
    return ScriptedModel()


@pytest.fixture
def client(model: SinkReadModel, scripted: ScriptedModel, tmp_path: Path) -> TestClient:
    return TestClient(create_app(model, ActionStore(tmp_path / "state"), chat_model=scripted))


def _ask(client: TestClient, screen: str, focus: dict[str, Any], question: str = "Tóm tắt",
         role: str | None = None) -> dict[str, Any]:
    headers = {"X-Fw-Role": role} if role else {}
    session = client.post("/api/chat/sessions", json={"screen": screen, "focus": focus},
                          headers=headers)
    assert session.status_code == 201, session.text
    reply = client.post(f"/api/chat/sessions/{session.json()['id']}/messages",
                        json={"content": question})
    assert reply.status_code == 201, reply.text
    body: dict[str, Any] = reply.json()
    return body


def test_mock_has_a_sealed_evaluation(model: SinkReadModel) -> None:
    """The BR-10 test below means something only if the mock seals one evaluation."""
    assert model.evaluation(SEALED, "ADMIN") is not None
    assert model.evaluation(SEALED, AGENT_ROLE) is None


def test_turn_keeps_ids_and_hash_not_the_prompt(client: TestClient,
                                                scripted: ScriptedModel) -> None:
    body = _ask(client, "M7", {"recommendation_id": "rec_round1", "cluster_id": "clu_1"})
    assistant = body["assistant"]
    assert assistant["content"] == "Trả lời thử."
    assert assistant["model"] == "scripted-test"
    assert assistant["proposed_action"] is None  # read-only minimum: never an action
    assert assistant["prompt_sha256"] == prompt_sha256(scripted.prompts[0])
    loaded = {(x["kind"], x["id"]) for x in assistant["context_snapshot"]["loaded"]}
    assert ("recommendation", "rec_round1") in loaded
    assert ("cluster_card", "clu_1") in loaded
    # §5.4 point 3: the stored message holds no copy of the context block.
    assert "NGỮ CẢNH" not in json.dumps(assistant, ensure_ascii=False)
    assert body["user"]["prompt_sha256"] is None

    session = client.get(f"/api/chat/sessions/{assistant['session_id']}").json()
    assert [m["role"] for m in session["messages"]] == ["user", "assistant"]
    assert session["context_recommendation_id"] == "rec_round1"


def test_second_turn_carries_the_first(client: TestClient, scripted: ScriptedModel) -> None:
    first = _ask(client, "M6", {"evaluation_id": "ev_B_dev"}, "Câu một")
    session_id = first["assistant"]["session_id"]
    client.post(f"/api/chat/sessions/{session_id}/messages", json={"content": "Câu hai"})
    contents = [m["content"] for m in scripted.prompts[1]]
    assert contents[-3:] == ["Câu một", "Trả lời thử.", "Câu hai"]


def test_sealed_evaluation_is_not_read_even_for_admin(client: TestClient,
                                                      scripted: ScriptedModel) -> None:
    body = _ask(client, "M6", {"evaluation_id": SEALED}, role="ADMIN")
    snapshot = body["assistant"]["context_snapshot"]
    assert snapshot["loaded"] == []
    assert {"kind": "evaluation", "id": SEALED} in snapshot["missing"]
    assert SEALED not in scripted.prompts[0][1]["content"].split("KHÔNG THẤY")[0]


def test_sealed_evaluation_absent_from_the_screen_list(model: SinkReadModel) -> None:
    prompt = build_prompt(build_context(model, "M6", {}), "M6", [], "?")
    context = prompt[1]["content"]
    assert "ev_B_dev" in context
    assert SEALED not in context


def test_m3_loads_nothing_of_group_s(model: SinkReadModel) -> None:
    """R8: the agent reads neither the answer key nor the scores derived from it."""
    calls: list[str] = []

    class Spy:
        def __getattr__(self, name: str) -> Any:
            calls.append(name)
            return getattr(model, name)

    context = build_context(Spy(), "M3", {"dataset_id": "bench_kbd_teleop"})
    assert context.loaded == []
    assert not [c for c in calls if c.startswith("defect")]
    for screen in ("M1", "M2", "M4", "M5", "M6", "M7", "M8", "M9", "M10"):
        build_context(Spy(), screen, {})
    assert not [c for c in calls if c.startswith("defect")]


def test_non_public_records_never_reach_the_prompt(model: SinkReadModel) -> None:
    """R6: an internal dataset and an internal episode are listed as withheld, not sent."""

    class Internal:
        def __getattr__(self, name: str) -> Any:
            return getattr(model, name)

        def datasets(self) -> list[dict[str, Any]]:
            rows = model.datasets()
            return [{**rows[0], "data_class": "internal"}, *rows[1:]]

        def dataset(self, ref: str) -> dict[str, Any] | None:
            row = model.dataset(ref)
            return None if row is None else {**row, "data_class": "restricted"}

        def episodes(self, ref: str) -> list[dict[str, Any]] | None:
            rows = model.episodes(ref) or []
            return [{**rows[0], "data_class": "internal"}, *rows[1:]]

    secret = model.datasets()[0]["id"]
    listing = build_context(Internal(), "M2", {})
    prompt = build_prompt(listing, "M2", [], "?")[1]["content"]
    context_block = prompt.split("NGỮ CẢNH:")[1]
    assert secret not in context_block
    assert {"id": secret, "data_class": "internal"} in listing.withheld

    focused = build_context(Internal(), "M2", {"dataset_id": "ds_kbd_teleop"})
    kinds = {x["kind"] for x in focused.loaded}
    assert "dataset" not in kinds  # the record itself is restricted
    assert {"id": "ds_kbd_teleop", "data_class": "restricted"} in focused.withheld
    episodes = focused.records["dataset_episodes:ds_kbd_teleop"]
    assert all(e["data_class"] == "public" for e in episodes)
    assert any(w["data_class"] == "internal" for w in focused.withheld[1:])


def test_long_context_is_cut_and_says_so(model: SinkReadModel,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("web.api.chat.CONTEXT_CHARS", 200)
    context = build_context(model, "M1", {})
    prompt = build_prompt(context, "M1", [], "?")
    assert prompt[1]["content"].endswith("…(cắt)")
    assert context.snapshot()["truncated"] is True


def test_without_a_model_the_chat_answers_503(model: SinkReadModel, tmp_path: Path) -> None:
    client = TestClient(create_app(model, ActionStore(tmp_path)))
    session = client.post("/api/chat/sessions", json={"screen": "M1"}).json()
    reply = client.post(f"/api/chat/sessions/{session['id']}/messages", json={"content": "?"})
    assert reply.status_code == 503
    assert reply.json()["code"] == "CHAT_MODEL_UNAVAILABLE"
    assert client.get(f"/api/chat/sessions/{session['id']}").json()["messages"] == []


@pytest.mark.parametrize(("body", "code"), [
    ({"screen": "M42"}, "BAD_SCREEN"),
    ({"screen": "M6", "focus": {"episode_id": "x"}}, "BAD_FOCUS"),
    ({"screen": "M6", "focus": ["ev_B_dev"]}, "BAD_FOCUS"),
])
def test_bad_session_bodies(client: TestClient, body: dict[str, Any], code: str) -> None:
    reply = client.post("/api/chat/sessions", json=body)
    assert reply.status_code == 422
    assert reply.json()["code"] == code


def test_bad_messages(client: TestClient) -> None:
    session = client.post("/api/chat/sessions", json={"screen": "M1"}).json()
    path = f"/api/chat/sessions/{session['id']}/messages"
    assert client.post(path, json={"content": "  "}).json()["code"] == "EMPTY_MESSAGE"
    assert client.post(path, json={"content": "x" * 4001}).json()["code"] == "MESSAGE_TOO_LONG"
    missing = client.post("/api/chat/sessions/chs_9999/messages", json={"content": "?"})
    assert missing.status_code == 404


@pytest.mark.parametrize("url", [
    "https://api.openai.com/v1",
    "http://example.com/v1",
    "ftp://127.0.0.1/v1",
])
def test_endpoint_must_be_ours(url: str) -> None:
    with pytest.raises(ValueError):
        LocalEndpoint(base_url=url, model="m")


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:11434/v1",
    "http://localhost:8001/v1",
    "http://192.168.1.20:11434/v1",
])
def test_endpoint_on_our_machines(url: str) -> None:
    assert LocalEndpoint(base_url=url, model="m").name == "m"


def test_named_host_must_be_listed() -> None:
    with pytest.raises(ValueError):
        LocalEndpoint(base_url="http://gpu-3060:11434/v1", model="m")
    LocalEndpoint(base_url="http://gpu-3060:11434/v1", model="m", local_hosts=("gpu-3060",))


def test_endpoint_failure_is_a_502(model: SinkReadModel, tmp_path: Path) -> None:
    dead = LocalEndpoint(base_url="http://127.0.0.1:9/v1", model="m", timeout_s=2)
    client = TestClient(create_app(model, ActionStore(tmp_path), chat_model=dead))
    session = client.post("/api/chat/sessions", json={"screen": "M8"}).json()
    reply = client.post(f"/api/chat/sessions/{session['id']}/messages", json={"content": "?"})
    assert reply.status_code == 502
    assert reply.json()["code"] == "CHAT_MODEL_FAILED"


def test_endpoint_speaks_openai_chat_and_ignores_proxies(
        model: SinkReadModel, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One real HTTP turn against a local server; a proxy variable must not divert it."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 (http.server naming)
            length = int(self.headers["Content-Length"])
            seen.append({"path": self.path, "body": json.loads(self.rfile.read(length))})
            reply = json.dumps({"choices": [{"message": {"content": " Có 4 cụm. "}}]})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(reply.encode("utf-8"))

        def log_message(self, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("HTTP_PROXY", "http://10.255.255.1:9")
    monkeypatch.setenv("http_proxy", "http://10.255.255.1:9")
    try:
        endpoint = LocalEndpoint(base_url=f"http://127.0.0.1:{server.server_port}/v1",
                                 model="nemotron-test", timeout_s=5)
        client = TestClient(create_app(model, ActionStore(tmp_path), chat_model=endpoint))
        body = _ask(client, "M7", {"recommendation_id": "rec_round1"}, "Có mấy cụm?")
    finally:
        server.shutdown()
    assert body["assistant"]["content"] == "Có 4 cụm."
    assert body["assistant"]["model"] == "nemotron-test"
    assert seen[0]["path"] == "/v1/chat/completions"
    sent = seen[0]["body"]
    assert sent["model"] == "nemotron-test"
    assert body["assistant"]["prompt_sha256"] == prompt_sha256(sent["messages"])

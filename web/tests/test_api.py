"""The web API (milestone M2) on the JSONL sink of `fwsync`.

Three things are checked:

1. **Parity.** Every request recorded in ``fixtures/api_parity.json`` (written
   by ``web/fe/src/mocks/parity.test.ts`` from what MSW serves) returns the
   same body from FastAPI. The FE was built against MSW, so this is what
   lets it switch to the backend with no code change (§6.4).
2. **The rules of §7.3 and the business rules the API enforces**: one error
   shape, Idempotency-Key, BR-07, BR-10, mandatory reasons.
3. **The write loop of §3.2**: a click lands in ``human_actions.jsonl`` and
   ``fwsync export`` turns it into an outbox artifact carrying ``source_action_id``.
"""

from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from web.api.actions import ActionStore
from web.api.app import SyncConfig, create_app
from web.api.readmodel import PostgresReadModel, SinkReadModel, SinkTables, js_round
from web.fwsync.runner import run_export, run_import
from web.fwsync.sink import JsonlSink

ROOT = Path(__file__).resolve().parents[2]
MOCK = ROOT / "mock" / "demo-17-11"
PARITY = Path(__file__).parent / "fixtures" / "api_parity.json"

#: Same instant as DEMO_DAY in web/fe/src/test/setup.ts: the holdout sealed
#: until 20/11 stays sealed whenever the test runs.
DEMO_DAY = datetime(2026, 11, 17, 9, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def sink(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("sink")
    result = run_import(MOCK, JsonlSink(directory=directory), origin="mock")
    assert result.status == "ok", result.errors
    return directory


def make_client(sink: Path, state: Path) -> TestClient:
    model = SinkReadModel(SinkTables(sink), now=lambda: DEMO_DAY)
    return TestClient(create_app(model, ActionStore(state)))


@pytest.fixture
def client(sink: Path, tmp_path: Path) -> TestClient:
    return make_client(sink, tmp_path / "state")


# ---------------------------------------------------------------- parity


def _same(a: Any, b: Any, where: str) -> list[str]:
    """Structural equality; numbers equal within 1e-9 (JS and Python sum floats in
    different orders), and 20 == 20.0 because JSON does not tell them apart."""
    if isinstance(a, bool) or isinstance(b, bool):
        return [] if a is b else [f"{where}: {a!r} != {b!r}"]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return [] if math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9) else [f"{where}: {a} != {b}"]
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f"{where}: keys differ {sorted(set(a) ^ set(b))}"]
        return [d for k in a for d in _same(a[k], b[k], f"{where}.{k}")]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{where}: length {len(a)} != {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in _same(x, y, f"{where}[{i}]")]
    return [] if a == b else [f"{where}: {a!r} != {b!r}"]


PARITY_CASES = json.loads(PARITY.read_text(encoding="utf-8"))


@pytest.mark.parametrize("request_line", sorted(PARITY_CASES))
def test_api_matches_what_msw_serves(client: TestClient, request_line: str) -> None:
    role, path = request_line.split(" ", 1)
    headers = {} if role == "-" else {"X-Fw-Role": role}
    response = client.get(f"/api{path}", headers=headers)
    assert response.status_code == 200, response.text
    diffs = _same(response.json(), PARITY_CASES[request_line], request_line)
    assert not diffs, "\n".join(diffs[:10])


def test_parity_covers_every_read_endpoint_of_7_1(client: TestClient) -> None:
    """A read route nobody compares is a route that can drift; list them all."""
    paths = client.get("/openapi.json").json()["paths"]
    routes = {path for path, ops in paths.items() if "get" in ops and path.startswith("/api")}
    assert len(routes) == 30
    covered = set()
    for line in PARITY_CASES:
        path = line.split(" ", 1)[1].split("?")[0]
        for route in routes:
            pattern = route.removeprefix("/api").split("/")
            parts = path.split("/")
            if len(pattern) == len(parts) and all(
                p.startswith("{") or p == q for p, q in zip(pattern, parts)
            ):
                covered.add(route)
    # /actions/{id} is covered by the write tests below; it has no fixed id to record.
    assert routes - covered == {"/api/actions/{action_id}"}


# ---------------------------------------------------------------- §7.3 and rules


def test_errors_have_one_shape(client: TestClient) -> None:
    response = client.get("/api/clusters/nope/card")
    assert response.status_code == 404
    assert sorted(response.json()) == ["code", "hint", "message", "ref"]
    assert client.get("/api/results/branches").json()["code"] == "TASK_REQUIRED"


def test_sealed_holdout_is_admin_only(client: TestClient) -> None:
    ids = [e["evaluation_id"] for e in client.get("/api/evaluations").json()["items"]]
    assert "ev_B_holdout" not in ids
    assert client.get("/api/evaluations/ev_B_holdout").status_code == 404
    admin = client.get("/api/evaluations/ev_B_holdout", headers={"X-Fw-Role": "ADMIN"})
    assert admin.status_code == 200 and admin.json()["is_sealed"] is True


def test_pages_have_a_cursor(client: TestClient) -> None:
    first = client.get("/api/cost/ledger?limit=5").json()
    assert len(first["items"]) == 5 and first["total"] == 14
    second = client.get(f"/api/cost/ledger?limit=5&cursor={first['next_cursor']}").json()
    assert {r["id"] for r in first["items"]}.isdisjoint({r["id"] for r in second["items"]})


APPROVE_ALL = {
    "items": [{"intervention_id": f"iv_{i}", "decision": "APPROVE"} for i in range(1, 5)]
}


def test_decision_needs_a_key_and_is_idempotent(client: TestClient) -> None:
    url = "/api/recommendations/rec_round1/decision"
    assert client.post(url, json=APPROVE_ALL).status_code == 400
    a = client.post(url, json=APPROVE_ALL, headers={"Idempotency-Key": "k1"})
    b = client.post(url, json=APPROVE_ALL, headers={"Idempotency-Key": "k1"})
    assert a.status_code == 202 and a.json()["sync_status"] == "PENDING"
    assert b.json()["action_id"] == a.json()["action_id"]
    status = client.get(f"/api/actions/{a.json()['action_id']}").json()
    assert status["action_kind"] == "RECOMMENDATION_DECISION"


def test_same_key_survives_a_restart(sink: Path, tmp_path: Path) -> None:
    url = "/api/recommendations/rec_round1/decision"
    key = {"Idempotency-Key": "k"}
    first = make_client(sink, tmp_path).post(url, json=APPROVE_ALL, headers=key)
    again = make_client(sink, tmp_path).post(url, json=APPROVE_ALL, headers=key)
    assert again.json()["action_id"] == first.json()["action_id"]


def test_decision_rules(client: TestClient) -> None:
    url = "/api/recommendations/rec_round1/decision"
    reject = {"items": [{"intervention_id": "iv_2", "decision": "REJECT"}]}
    no_reason = client.post(url, json=reject, headers={"Idempotency-Key": "k2"})
    assert no_reason.status_code == 422 and no_reason.json()["code"] == "REASON_REQUIRED"
    over = client.post(
        url,
        json={"items": [{"intervention_id": "iv_2", "decision": "APPROVE_EDITED",
                         "approved_quantity": 80, "reason": "x"}]},
        headers={"Idempotency-Key": "k3"},
    )
    assert over.status_code == 422 and over.json()["code"] == "BR-07"


def test_override_needs_a_reason(client: TestClient) -> None:
    url = "/api/clusters/clu_2/diagnosis-override"
    bad = client.post(url, json={"diagnosis": "KY_NANG_YEU"}, headers={"Idempotency-Key": "o1"})
    assert bad.status_code == 422
    ok = client.post(url, json={"diagnosis": "KY_NANG_YEU", "reason": "xem video"},
                     headers={"Idempotency-Key": "o2"})
    assert ok.status_code == 202


def test_a_click_reaches_the_outbox(sink: Path, tmp_path: Path) -> None:
    """§3.2: API → human_actions.jsonl → `fwsync export` → artifact with source_action_id."""
    client = make_client(sink, tmp_path / "state")
    action_id = client.post("/api/recommendations/rec_round1/decision", json=APPROVE_ALL,
                            headers={"Idempotency-Key": "e2e"}).json()["action_id"]
    store = tmp_path / "state" / "human_actions.jsonl"
    actions = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
    result = run_export(actions, tmp_path / "outbox")
    assert result.status == "ok"
    artifact = json.loads(next((tmp_path / "outbox").glob("*.json")).read_text(encoding="utf-8"))
    assert artifact["source_action_id"] == action_id
    assert artifact["payload"]["items"][0]["intervention_id"] == "iv_1"


def test_postgres_read_model_says_what_is_missing() -> None:
    with pytest.raises(RuntimeError, match="W8"):
        PostgresReadModel(dsn="postgresql://x")


def test_js_round_rounds_half_up_like_the_fe() -> None:
    assert js_round(0.5, 0) == 1.0  # Python's round(0.5) is 0
    assert js_round(2.5, 0) == 3.0
    assert js_round(-2.5, 0) == -2.0  # Math.round(-2.5) === -2


# ---------------------------------------------------------------- M4 over HTTP


def _sync_client(sink: Path, tmp_path: Path, *, fake_core: bool = True) -> TestClient:
    """A client on its own copy of the sink: a sync run writes into the sink."""
    own = tmp_path / "sink"
    shutil.copytree(sink, own)
    config = SyncConfig(outbox=tmp_path / "outbox", inbox=tmp_path / "inbox", sink=own,
                        fake_core=fake_core, origin="mock")
    model = SinkReadModel(SinkTables(own), now=lambda: DEMO_DAY)
    return TestClient(create_app(model, ActionStore(tmp_path / "state"), config))


def test_sync_run_is_for_admin_and_lead_only(sink: Path, tmp_path: Path) -> None:
    client = _sync_client(sink, tmp_path)
    assert client.post("/api/sync/run").status_code == 403
    assert client.post("/api/sync/run", headers={"X-Fw-Role": "LEAD"}).status_code == 200


def test_sync_run_without_folders_says_so(client: TestClient) -> None:
    response = client.post("/api/sync/run", headers={"X-Fw-Role": "ADMIN"})
    assert response.status_code == 409
    assert response.json()["code"] == "SYNC_NOT_CONFIGURED"


def test_click_to_applied(sink: Path, tmp_path: Path) -> None:
    """DESIGN.md §9.2 M4: approve → outbox → fake core applies → re-import sees APPLIED."""
    client = _sync_client(sink, tmp_path)
    action_id = client.post("/api/recommendations/rec_round1/decision", json=APPROVE_ALL,
                            headers={"Idempotency-Key": "m4"}).json()["action_id"]
    assert client.get(f"/api/actions/{action_id}").json()["sync_status"] == "PENDING"
    assert [a["action_id"] for a in
            client.get("/api/actions?sync_status=PENDING").json()["items"]] == [action_id]

    run = client.post("/api/sync/run", headers={"X-Fw-Role": "ADMIN"}).json()

    assert run["status"] == "ok" and run["applied"] == [action_id]
    status = client.get(f"/api/actions/{action_id}").json()
    assert status["sync_status"] == "APPLIED" and status["exported_at"] and status["applied_at"]
    answers = [d for d in client.get("/api/decisions").json()["items"]
               if d["source_action_id"] == action_id]
    assert len(answers) == 1
    assert client.get("/api/sync/runs").json()[0]["id"] == run["id"]
    # A second run finds nothing to do and changes nothing.
    again = client.post("/api/sync/run", headers={"X-Fw-Role": "ADMIN"}).json()
    assert again["exported"] == [] and again["applied"] == []


def test_without_the_fake_core_the_action_waits(sink: Path, tmp_path: Path) -> None:
    client = _sync_client(sink, tmp_path, fake_core=False)
    action_id = client.post("/api/recommendations/rec_round1/decision", json=APPROVE_ALL,
                            headers={"Idempotency-Key": "m4b"}).json()["action_id"]
    client.post("/api/sync/run", headers={"X-Fw-Role": "ADMIN"})
    assert client.get(f"/api/actions/{action_id}").json()["sync_status"] == "EXPORTED"

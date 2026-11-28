# ruff: noqa: E501  (fixture rows stay one record per line)
"""A hosted chat model never sees what is not public (CLAUDE.md, design 27/10 section 8.4).

The catalog edges, the totals, the parents of a public row, the task manifest, the tools that
cannot filter rows, the earlier answers of the conversation: each was a way out before the fix.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from chat_index import make_idx  # noqa: F401
from flywheel.console.chat import common, llm, providers, registry, tools_round
from flywheel.console.index.catalog import totals as index_totals
from flywheel.console.paths import ConsolePaths

NEMO = "http://127.0.0.1:11435"
SECRET = "team-raw-old"


@pytest.fixture
def hosted_idx(idx: ConsolePaths) -> Iterator[ConsolePaths]:
    """The tiny index with every row public, plus one internal row linked as list edges are."""
    cat = json.loads((idx.index / "catalog.json").read_text(encoding="utf-8"))
    for r in cat["rows"]:
        r.update(data_class="public", group=r.get("group") or "s1", unique=r["id"] != "ALL")
        r.setdefault("hours", None)  # the index writes the key on every row
    ego = next(r for r in cat["rows"] if r["id"] == "egx_aaaa1111")
    ego.update(group="egocentric", parents=[SECRET], hours=0.01)
    cat["rows"].append({"id": SECRET, "name": SECRET, "title": "team video", "data_class": "internal",
                        "group": "egocentric", "data_type": "egocentric", "task": "two_table",
                        "status": "current", "episodes": 50, "hours": 1.0, "unique": True,
                        "parents": [], "children": ["egx_aaaa1111"]})  # fmt: skip
    cat["edges"].append([SECRET, "egx_aaaa1111"])
    cat["totals"] = index_totals(cat["rows"])
    (idx.index / "catalog.json").write_text(json.dumps(cat), encoding="utf-8")
    tasks = {"tasks": [{"id": "two_table", "catalog_task": "two_table",
                        "catalog_totals": index_totals([r for r in cat["rows"] if r["task"] == "two_table"]),
                        "catalog_rows": [{"id": r["id"], "group": r["group"], "episodes": r["episodes"]}
                                         for r in cat["rows"] if r["task"] == "two_table"]}]}  # fmt: skip
    (idx.index / "tasks.json").write_text(json.dumps(tasks), encoding="utf-8")
    tok = common.HOSTED.set(True)
    try:
        yield idx
    finally:
        common.HOSTED.reset(tok)


def test_hosted_catalog_drops_list_edges_parents_and_counts_of_internal_rows(
    hosted_idx: ConsolePaths,
) -> None:
    cat = common.catalog()
    assert SECRET not in json.dumps(cat)
    assert ["tray_s1_41899efb4b27", "ALL"] in cat["edges"]  # public edges stay
    assert cat["totals"]["egocentric"]["episodes"] == 3  # 50 internal episodes not counted
    res = registry.call("lineage", {"dataset_id": "egx_aaaa1111", "direction": "both"})
    assert SECRET not in json.dumps(res)
    common.HOSTED.set(False)
    assert SECRET in json.dumps(common.catalog())  # the local model keeps the whole catalog


def test_hosted_task_manifest_lists_and_totals_public_rows_only(hosted_idx: ConsolePaths) -> None:
    task = tools_round.manifest()["tasks"][0]
    assert SECRET not in json.dumps(task)
    assert task["catalog_totals"]["egocentric"]["episodes"] == 3


def test_chat_totals_match_the_index_totals(hosted_idx: ConsolePaths) -> None:
    rows = json.loads((hosted_idx.index / "catalog.json").read_text(encoding="utf-8"))["rows"]
    assert common.totals(rows) == index_totals(rows)


def test_local_only_tools_are_refused_and_never_offered_to_a_hosted_model(
    hosted_idx: ConsolePaths,
) -> None:
    for name in registry.LOCAL_ONLY:
        res = registry.call(name, {"job_id": "j-aaa111"}, {"route": "#/jobs"})
        assert not res["ok"] and "hosted" in res["model"], name
    for route in ("#/jobs", "#/qa", "#/runs", "#/home"):
        assert not set(registry.offered_names(route, "list the jobs")) & registry.LOCAL_ONLY
    assert registry.forced_tool("bao nhiêu clip video người đã xuất") is None
    common.HOSTED.set(False)
    assert registry.call("job_list", {}, {"route": "#/jobs"})["ok"]
    assert "job_list" in registry.offered_names("#/jobs", "list the jobs")


def test_loopback_alone_does_not_make_a_server_self_hosted(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("FW_CHAT_API_KEY", "FW_CHAT_NAME", "FW_CHAT_SELF_HOSTED"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("FW_CHAT_MODEL", "some-model")
    monkeypatch.setenv("FW_CHAT_BASE_URL", "http://127.0.0.1:8080/v1")  # any forward, any proxy
    p = providers.active(NEMO, "nemo")
    assert p.hosted and p.loopback and not llm.needs_tunnel(p)
    assert providers.problem(p) is None  # called as it is; the data rule applies through hosted
    monkeypatch.setenv("FW_CHAT_SELF_HOSTED", "1")
    assert not providers.active(NEMO, "nemo").hosted
    monkeypatch.setenv("FW_CHAT_BASE_URL", "http://nim.lan:8000/v1")  # a NIM of the team
    assert not providers.active(NEMO, "nemo").hosted
    monkeypatch.delenv("FW_CHAT_SELF_HOSTED")
    remote = providers.active(NEMO, "nemo")
    assert remote.hosted and "FW_CHAT_SELF_HOSTED" in str(providers.problem(remote))


def test_an_ollama_cloud_model_is_hosted_even_on_the_tunnel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FW_CHAT_SELF_HOSTED", raising=False)
    monkeypatch.delenv("FW_CHAT_BASE_URL", raising=False)
    assert providers.active(NEMO, "gpt-oss:120b-cloud").hosted
    assert not providers.active(NEMO, "nemotron:q4_k_m").hosted
    monkeypatch.setenv("FW_CHAT_BASE_URL", "http://127.0.0.1:11435/v1")
    monkeypatch.setenv("FW_CHAT_MODEL", "qwen3-coder:480b-cloud")
    p = providers.active(NEMO, "nemo")
    assert p.hosted and llm.needs_tunnel(p)


def test_refusal_says_which_model_answers() -> None:
    q = "send this dataset to chatgpt"
    local = providers.Provider("nemotron", "ollama", NEMO, "nemo", False, 11435, True)
    hosted = providers.Provider(
        "openrouter.ai", "openai", "https://openrouter.ai/api/v1", "m", True
    )
    assert llm.guard_check(q, local) == ("hosted_api", llm.GUARDS[3][2])
    why, text = llm.guard_check(q, hosted)
    assert why == "hosted_api" and "openrouter.ai" in str(text) and "Nemotron" not in str(text)


def test_a_hosted_turn_sets_the_rule_first_and_resets_it(
    idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    prov = providers.Provider(
        "openrouter.ai", "openai", "https://openrouter.ai/api/v1", "vendor/m", True
    )
    monkeypatch.setattr(llm, "provider", lambda: prov)
    monkeypatch.setenv("FW_CHAT_API_KEY", "k")
    monkeypatch.setenv("FW_CHAT_BASE_URL", "https://openrouter.ai/api/v1")  # the key's own host
    seen: list[tuple[Any, Any]] = []

    def fake_generate(msgs: Any, schemas: Any, deadline: float) -> Any:
        seen.append((msgs, schemas))
        yield "tok", "ok"
        yield "end", ("ok", [], 1, 1)

    monkeypatch.setattr(llm, "generate", fake_generate)
    body = {"messages": [{"role": "user", "content": "list the jobs"},
                         {"role": "assistant", "content": "j-aaa111 from the team video"},
                         {"role": "user", "content": "and the failed ones?"}],
            "context": {"route": "#/jobs"}}  # fmt: skip
    evs = list(llm.events(body))
    start = evs[0][1]
    assert start["model"] == "vendor/m"
    assert not set(start["tools_offered"]) & registry.LOCAL_ONLY
    msgs, schemas = seen[0]
    assert all(m["role"] != "assistant" for m in msgs)  # no earlier answer goes out
    assert not {s["function"]["name"] for s in schemas or []} & registry.LOCAL_ONLY
    assert common.HOSTED.get() is False  # reset when the turn ends


def test_a_request_body_cannot_declare_a_hosted_api_self_hosted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for k in ("FW_CHAT_BASE_URL", "FW_CHAT_SELF_HOSTED"):
        monkeypatch.delenv(k, raising=False)
    saved = dict(providers._RUNTIME_CFG)
    try:
        cfg = providers.set_runtime_config(
            {"base_url": "https://api.openai.com/v1", "model": "gpt-4.1", "self_hosted": True},
            persist=False,
        )
        assert cfg["hosted"] and not cfg["self_hosted"]
        assert providers.active(NEMO, "nemo").hosted
    finally:
        providers._RUNTIME_CFG.clear()
        providers._RUNTIME_CFG.update(saved)

"""The provider layer: which model answers, the message shape, the hosted-data rule."""

from __future__ import annotations

import json
from typing import Any

import pytest
from chat_index import make_idx  # noqa: F401
from flywheel.console.chat import bench, common, llm, providers, registry
from flywheel.console.paths import ConsolePaths

NEMO = "http://127.0.0.1:11435"


def test_default_provider_is_nemotron_over_the_tunnel(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("FW_CHAT_BASE_URL", "FW_CHAT_MODEL", "FW_CHAT_API_KEY", "FW_CHAT_NAME"):
        monkeypatch.delenv(k, raising=False)
    p = providers.active(NEMO, "nemo")
    assert (p.kind, p.hosted, p.model, p.port) == ("ollama", False, "nemo", 11435)
    assert providers.problem(p) is None and llm.needs_tunnel(p)


def test_hosted_provider_needs_https_a_model_and_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FW_CHAT_BASE_URL", "https://openrouter.ai/api/v1/")
    monkeypatch.delenv("FW_CHAT_MODEL", raising=False)
    monkeypatch.delenv("FW_CHAT_API_KEY", raising=False)
    p = providers.active(NEMO, "nemo")
    assert (p.kind, p.hosted, p.name) == ("openai", True, "openrouter.ai")
    assert p.base_url == "https://openrouter.ai/api/v1" and not llm.needs_tunnel(p)
    assert "FW_CHAT_MODEL" in str(providers.problem(p))
    monkeypatch.setenv("FW_CHAT_MODEL", "vendor/model:free")
    assert "FW_CHAT_API_KEY" in str(providers.problem(providers.active(NEMO, "nemo")))
    monkeypatch.setenv("FW_CHAT_API_KEY", "k")
    assert providers.problem(providers.active(NEMO, "nemo")) is None
    monkeypatch.setenv("FW_CHAT_BASE_URL", "http://example.com/v1")
    assert "https" in str(providers.problem(providers.active(NEMO, "nemo")))
    # the same Ollama through its OpenAI-protocol port is local and still behind the tunnel
    monkeypatch.setenv("FW_CHAT_BASE_URL", "http://127.0.0.1:11435/v1")
    local = providers.active(NEMO, "nemo")
    assert not local.hosted and llm.needs_tunnel(local) and providers.problem(local) is None


def test_messages_take_the_chat_completions_shape() -> None:
    msgs: list[dict[str, Any]] = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "a", "arguments": {"x": 1}}},
            {"function": {"name": "b", "arguments": {}}}]},
        {"role": "tool", "tool_name": "a", "content": "ra"},
        {"role": "tool", "tool_name": "b", "content": "rb"},
    ]  # fmt: skip
    out = providers.to_openai(msgs)
    calls = out[2]["tool_calls"]
    assert [c["id"] for c in calls] == ["call_0", "call_1"] and out[2]["content"] is None
    assert json.loads(calls[0]["function"]["arguments"]) == {"x": 1}
    assert [(m["tool_call_id"], m["content"]) for m in out[3:]] == [
        ("call_0", "ra"),
        ("call_1", "rb"),
    ]
    assert "tool_name" not in out[3]


def test_hosted_model_never_sees_rows_that_are_not_public(idx: ConsolePaths) -> None:
    cat = json.loads((idx.index / "catalog.json").read_text(encoding="utf-8"))
    cat["rows"][0]["data_class"] = "public"
    cat["rows"].append({"id": "secret-set", "data_class": "internal", "group": "egocentric",
                        "data_type": "egocentric", "status": "current", "episodes": 3})  # fmt: skip
    for r in cat["rows"][1:-1]:
        r["data_class"] = "public"
    (idx.index / "catalog.json").write_text(json.dumps(cat), encoding="utf-8")
    assert any(r["id"] == "secret-set" for r in common.catalog()["rows"])
    tok = common.HOSTED.set(True)
    try:
        assert all(r["id"] != "secret-set" for r in common.catalog()["rows"])
        assert not common.public_ds("secret-set") and common.ds_file("secret-set", "stats") is None
        res = registry.call("catalog_search", {"q": "secret"}, {"route": "#/data"})
        assert "secret-set" not in res["model"]
    finally:
        common.HOSTED.reset(tok)


def test_forced_lookup_never_contradicts_the_benchmark() -> None:
    """A question the bench expects another tool for must not be taken over by the forced lookup."""
    for item in bench.load_items():
        forced = registry.forced_tool(item["question"])
        expected = [e["name"] for e in item.get("expect_tools") or []]
        assert forced is None or forced in expected, (item["id"], forced, expected)


def test_openrouter_turns_reasoning_off_unless_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FW_CHAT_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("FW_CHAT_MODEL", "vendor/model:free")
    monkeypatch.delenv("FW_CHAT_REASONING", raising=False)
    p = providers.active(NEMO, "nemo")
    assert providers.reasoning_body(p) == {"reasoning": {"enabled": False}}
    monkeypatch.setenv("FW_CHAT_REASONING", "low")
    assert providers.reasoning_body(p) == {"reasoning": {"effort": "low"}}
    monkeypatch.setenv("FW_CHAT_REASONING", "default")
    assert providers.reasoning_body(p) is None
    monkeypatch.setenv("FW_CHAT_BASE_URL", "http://127.0.0.1:11435/v1")
    assert providers.reasoning_body(providers.active(NEMO, "nemo")) is None  # not OpenRouter


def test_runtime_api_config_keeps_key_in_ram_only_and_supports_presets(
    idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    for k in (
        "FW_CHAT_BASE_URL",
        "FW_CHAT_MODEL",
        "FW_CHAT_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(k, raising=False)
    providers.reset_runtime_config()
    try:
        pub = providers.set_runtime_config(
            {"preset": "deepseek", "model": "deepseek-reasoner", "api_key": "sk-secret-ram-only"}
        )
        assert pub["ready"] is True and pub["has_key"] is True
        assert "sk-secret-ram-only" not in json.dumps(pub)
        cfg_file = idx.console_dir / "config" / "chat_provider.json"
        assert cfg_file.is_file()
        assert "sk-secret-ram-only" not in cfg_file.read_text(encoding="utf-8")

        p = providers.active(NEMO, "nemo")
        assert (p.kind, p.hosted, p.model) == ("openai", True, "deepseek-reasoner")
        assert p.key == "sk-secret-ram-only" and providers.problem(p) is None

        # Anthropic preset maps to native Messages API
        providers.set_runtime_config(
            {"preset": "anthropic", "model": "claude-sonnet-4-20250514", "api_key": "sk-ant-test"}
        )
        pa = providers.active(NEMO, "nemo")
        assert (pa.kind, pa.hosted) == ("anthropic", True)
        sys_txt, anth_msgs = providers.to_anthropic(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "hi"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "qa_summary",
                                "arguments": {"dataset_id": "S70"},
                            }
                        }
                    ],
                },
                {"role": "tool", "tool_name": "qa_summary", "content": "425 pass"},
            ]
        )
        assert sys_txt == "sys"
        assert anth_msgs[1]["content"][0]["type"] == "tool_use"
        assert anth_msgs[2]["content"][0]["type"] == "tool_result"
    finally:
        providers.reset_runtime_config()

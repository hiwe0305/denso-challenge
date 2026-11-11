from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from chat_index import make_idx  # noqa: F401
from flywheel.console.chat import registry
from flywheel.console.chat.resolve import resolve_dataset
from flywheel.console.paths import ConsolePaths
from flywheel.console.server import runner


def snapshot(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*")}


def test_resolve_alias_s1(idx: ConsolePaths) -> None:
    assert resolve_dataset("S1") == ("ok", "cut-all-zone1")
    assert resolve_dataset("S70") == ("ok", "S70")
    assert resolve_dataset("all") == ("ok", "cut-all-zone1")
    assert resolve_dataset("nonexistent-zzz")[0] == "none"


def test_offered_names_cross_page(idx: ConsolePaths) -> None:
    names = registry.offered_names("runs", "loss của C_70 và lỗi QA của S70")
    assert "run_metrics" in names and "qa_summary" in names
    assert names[-1] == "open_page"


def test_offered_names_cap(idx: ConsolePaths) -> None:
    q = "loss của C_70, QA của S70, eval failure, job log, cost, cluster loop"
    for route in ("runs", "data", "home", "jobs", "qa"):
        assert len(registry.offered_names(route, q)) <= 8
    # a single-topic question keeps the page's own tools
    assert "run_list" in registry.offered_names("runs", "mấy run đang chạy")


def test_s1_question_offers_dataset_tools(idx: ConsolePaths) -> None:
    names = registry.offered_names("data/S70", "vì sao 68 lần sinh S1 thất bại?")
    assert "qa_summary" in names


def test_qa_status_from_rule_layer(idx: ConsolePaths) -> None:
    res = registry.call("qa_summary", {"dataset_id": "S70"}, {"route": "#/data"})
    assert res["ok"]
    raw: dict[str, Any] = res["raw"]
    assert raw["qa"]["decisions"] == {"pass": 425, "flag": 0, "reject": 0}
    gen = raw["generation_failures"]
    assert gen["failed"] == 68 and "L-ONE-HAND" in gen["reasons"]
    assert "NOT QA" in res["model"]
    # via the alias too
    assert registry.call("qa_summary", {"dataset_id": "S1"})["ok"]


def test_episode_frames_deid_only(idx: ConsolePaths) -> None:
    res = registry.call("episode_list", {"dataset_id": "egx_aaaa1111"})
    assert res["ok"]
    thumbs = [s for s in res["ui"]["items"] if s["type"] == "thumbs"]
    srcs = [t["src"] for s in thumbs for t in s["items"]]
    assert srcs == ["/data/ds/egx_aaaa1111/posters/ep_1.jpg"]
    from flywheel.console.chat.tools_data import deid_frame_source

    assert deid_frame_source("x/raw.mp4") is None
    assert deid_frame_source("x/a.deid.mp4") == Path("x/a.deid.mp4")


def test_propose_job_starts_nothing(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("propose_job must not start anything")

    for name in ("submit", "prepare", "make_job", "execute", "save"):
        monkeypatch.setattr(runner, name, boom)
    work = idx.fw_root / "pipeline" / "w1"
    work.mkdir(parents=True)
    before = snapshot(idx.fw_root)
    res = registry.call("propose_job", {"kind": "agentqa.run", "params": {"input": str(work)}})
    assert res["ok"], res["model"]
    ui = res["ui"]
    assert ui["type"] == "confirm" and ui["kind"] == "agentqa.run" and ui["argv_preview"]
    assert "not started" in res["model"]
    assert snapshot(idx.fw_root) == before
    bad = registry.call("propose_job", {"kind": "train.run", "params": {}})
    assert not bad["ok"]


def test_every_tool_is_read_only(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("a chat tool must not submit or write a job")

    for name in ("submit", "prepare", "make_job", "execute", "save", "cancel"):
        monkeypatch.setattr(runner, name, boom)
    work = idx.fw_root / "pipeline" / "w1"
    work.mkdir(parents=True)
    args: dict[str, dict[str, Any]] = {
        "dataset_stats": {"dataset_id": "S70"}, "episode_list": {"dataset_id": "S70"},
        "episode_get": {"dataset_id": "S70", "episode_id": "0"},
        "qa_summary": {"dataset_id": "S70"},
        "lineage": {"dataset_id": "S70"}, "run_metrics": {"run_id": "C_70"},
        "run_compare": {"run_ids": ["C_70", "C_70"]}, "log_tail": {"job_id": "j-aaa111"},
        "job_get": {"job_id": "j-aaa111"}, "open_page": {"route": "data/S70"},
        "propose_job": {"kind": "agentqa.run", "params": {"input": str(work)}},
    }  # fmt: skip
    before = snapshot(idx.fw_root)
    for name in registry.TOOLS:
        res = registry.call(name, args.get(name, {}), {"route": "#/data/S70"})
        assert {"ok", "ui", "model"} <= set(res), name
    assert snapshot(idx.fw_root) == before


def test_slash_describe_and_schemas(idx: ConsolePaths) -> None:
    d = registry.describe("#/runs")
    assert d[-1]["name"] == "open_page" and len(d) <= 6
    assert registry.schemas("runs")[0]["type"] == "function"

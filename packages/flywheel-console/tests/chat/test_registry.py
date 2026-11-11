from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from chat_index import make_idx  # noqa: F401
from flywheel.console.chat import registry
from flywheel.console.chat.resolve import resolve_dataset
from flywheel.console.paths import ConsolePaths
from flywheel.console.server import runner


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Every path under root with its size and mtime, so an in-place rewrite shows up too."""
    out: dict[str, tuple[int, int]] = {}
    for p in root.rglob("*"):
        st = p.stat()
        out[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns)
    return out


def test_resolve_alias_s1(idx: ConsolePaths) -> None:
    assert resolve_dataset("S1") == ("ok", "tray_s1_41899efb4b27")
    assert resolve_dataset("s70") == ("ok", "S70")
    assert resolve_dataset("all") == ("ok", "ALL")
    assert resolve_dataset("nonexistent-zzz")[0] == "none"


def test_offered_names_cross_page(idx: ConsolePaths) -> None:
    names = registry.offered_names("runs", "loss của C_70 và lỗi QA của S70")
    assert "run_metrics" in names and "qa_summary" in names
    assert names[-1] == "open_page"


def test_offered_names_union_needs_two_topics(idx: ConsolePaths) -> None:
    # route eval offers eval tools only; two topics (data, runs) pull in their pages' tools,
    # so catalog_search (data page only) is offered; without the union eval_summary would be.
    names = registry.offered_names("eval", "lỗi QA của S70 và loss của C_70")
    assert "catalog_search" in names and "eval_summary" not in names
    assert len(names) <= 8 and names[-1] == "open_page"
    single = registry.offered_names("eval", "loss của C_70")
    assert "eval_summary" in single


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
    res = registry.call("qa_summary", {"dataset_id": "T1"}, {"route": "#/data"})
    assert res["ok"]
    assert res["raw"]["qa"]["decisions"] == {"pass": 10, "flag": 2, "reject": 1}
    # a cut with generation failures: the batch is reported apart and marked NOT QA
    cut = registry.call("qa_summary", {"dataset_id": "S70"})
    raw: dict[str, Any] = cut["raw"]
    assert "decisions" not in raw.get("qa", {})
    gen = raw["generation_failures"]
    assert gen["failed"] == 68 and "L-ONE-HAND" in gen["reasons"]
    assert "NOT QA" in cut["model"]


def test_qa_summary_cut_reports_parent_decisions(idx: ConsolePaths) -> None:
    res = registry.call("qa_summary", {"dataset_id": "S70"})
    assert "parent tray_s1_41899efb4b27" in res["model"]
    assert "534 pass / 7 reject" in res["model"]
    assert "425 pass" not in res["model"]  # a cut never gets an invented pass count


def test_qa_summary_s1_reports_child_batch(idx: ConsolePaths) -> None:
    res = registry.call("qa_summary", {"dataset_id": "S1"})
    assert res["ok"]
    assert "generation batch recorded on ALL" in res["model"] and "NOT QA" in res["model"]
    assert res["raw"]["generation_failures"]["failed"] == 68
    assert "534 pass / 7 reject" in res["model"]  # the release's own QA note


def test_episode_frames_deid_only(idx: ConsolePaths) -> None:
    res = registry.call("episode_list", {"dataset_id": "egx_aaaa1111"})
    assert res["ok"]
    thumbs = [s for s in res["ui"]["items"] if s["type"] == "thumbs"]
    srcs = [t["src"] for s in thumbs for t in s["items"]]
    assert srcs == ["/data/ds/egx_aaaa1111/posters/ep_1.jpg"]  # missing file and /ego/ raw dropped
    for ep, want in (("ep_1", 1), ("ep_2", 0), ("ep_3", 0)):
        got = registry.call("episode_get", {"dataset_id": "egx_aaaa1111", "episode_id": ep})
        n = sum(len(s["items"]) for s in got["ui"]["items"] if s["type"] == "thumbs")
        assert n == want, ep


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

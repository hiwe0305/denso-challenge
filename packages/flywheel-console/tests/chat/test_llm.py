from __future__ import annotations

import json
import socket
import time
from typing import Any

import pytest
from chat_index import make_idx  # noqa: F401
from flywheel.console.chat import bench, llm
from flywheel.console.paths import ConsolePaths
from flywheel.console.server import runner


class FakeTunnel:
    def __init__(self, up: bool) -> None:
        self.up = up
        self.ensured = 0

    def tags(self, fresh: bool = False) -> list[Any] | None:
        return [] if self.up else None

    def ensure(self, timeout: float = 15) -> bool:
        self.ensured += 1
        return False


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_endpoint_is_loopback_tunnel() -> None:
    assert llm.ENDPOINT == "http://127.0.0.1:11435"
    assert llm.endpoint_ok()
    assert not llm.endpoint_ok("http://example.com:11435")
    assert not llm.endpoint_ok("https://127.0.0.1:11435")
    assert not llm.endpoint_ok("http://127.0.0.1:11434")
    assert (llm.NUM_CTX, llm.KEEP_ALIVE, llm.MAX_ROUNDS, llm.TURN_CAP_S) == (16384, "30m", 3, 20.0)


def test_stream_endpoint_down(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    port = closed_port()
    monkeypatch.setattr(llm, "ENDPOINT", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(llm, "LOOPBACK_PORT", port)
    monkeypatch.setattr(llm, "HTTP_TIMEOUT_S", 1.0)
    monkeypatch.setattr(runner, "TUNNEL", FakeTunnel(up=True))
    t0 = time.time()
    evs = list(llm.events({"messages": [{"role": "user", "content": "Thống kê tập S70"}],
                           "context": {"route": "#/data"}}))  # fmt: skip
    assert time.time() - t0 < 20
    assert evs[0][0] == "trace_start"
    assert evs[-1][0] == "error" and evs[-1][1]["fallback"] == "slash"
    # the SSE wrapper encodes the same events as bytes
    raw = b"".join(llm.stream({"messages": [{"role": "user", "content": "Thống kê tập S70"}]}))
    assert raw.rstrip().endswith(b"}") and b"event: error" in raw and b'"fallback"' in raw
    traces = llm.list_traces()
    assert traces and traces[0]["error"].startswith("model:")


def test_stream_tunnel_down(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    tun = FakeTunnel(up=False)
    monkeypatch.setattr(runner, "TUNNEL", tun)
    evs = list(llm.events({"messages": [{"role": "user", "content": "how many runs"}]}))
    assert evs[-1][0] == "error" and evs[-1][1]["fallback"] == "slash"
    assert tun.ensured == 1


def test_stream_guard_needs_no_model(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "TUNNEL", FakeTunnel(up=False))
    evs = list(llm.events({"messages": [{"role": "user", "content": "start training C+"}]}))
    assert evs[-1][0] == "done" and evs[-1][1]["guard"] == "training"


def test_ground_marks_unknown_numbers() -> None:
    ev = ["Thống kê tập S70", "QA of S70: 425 pass, 0 flag. generation 68 failed"]
    out = {
        n["text"]: n["grounded"]
        for n in llm.ground("S70 có 425 episode pass, 999 lỗi, 68 lần.", ev)
    }
    assert out["425"] is True and out["68"] is True and out["999"] is False


def test_parse_markup_calls() -> None:
    txt = '<|tool_call>call:qa_summary{dataset_id:<|"|>S70<|"|>,limit:3}<tool_call|>'
    assert llm.parse_markup_calls(txt) == [
        {"name": "qa_summary", "arguments": {"dataset_id": "S70", "limit": 3}}
    ]


def test_bench_items_and_scoring(idx: ConsolePaths) -> None:
    items = bench.load_items()
    ids = {i["id"] for i in items}
    assert len(items) == 49 and "b48" in ids and "b49" in ids
    assert any("vì sao 68 lần sinh S1 thất bại" in i["question"] for i in items)
    cross = next(i for i in items if i["id"] == "b49")
    ev: list[tuple[str, dict[str, Any]]] = [
        ("tool_start", {"name": "qa_summary", "args": {"dataset_id": "S70"}}),
        ("tool_start", {"name": "run_metrics", "args": {"run_id": "C_70"}}),
        ("token", {"text": "ok"}),
        ("done", {"numbers": [{"text": "1", "grounded": True}], "ms_total": 5}),
    ]
    r = bench.score(cross, ev)
    assert r["tool_ok"] and r["arg_ok"] and r["grounded"] == 1
    guard = next(i for i in items if i["group"] == "guard")
    g = bench.score(guard, [("token", {"text": "refused"}), ("done", {"guard": "x"})])
    assert g["no_action_ok"]
    leak = bench.score(guard, [("token", {"text": "<|tool_call"}), ("done", {})])
    assert leak["markup_leak"] and not leak["no_action_ok"]
    s = bench.summarize([r, g], [1.0, 2.0], "t")
    assert s["n"] == 2 and s["tool_accuracy"] == [1, 1] and s["guardrail_pass"] == [1, 1]
    assert {"by_group", "markup_leaks", "latency_p95_s", "no_tool_pass"} <= set(s)


def test_latest_bench_reads_written_summary(idx: ConsolePaths) -> None:
    summary = {"time": "t", "n": 2, "tool_accuracy": [1, 2], "arg_accuracy": [1, 2],
               "guardrail_pass": [1, 1], "grounded_numbers": [3, 4], "latency_p50_s": 1.5,
               "latency_p95_s": 2.0, "by_group": {"vi": [1, 2]}}  # fmt: skip
    idx.chat.mkdir(parents=True)
    (idx.chat / "bench-20261111-000000.json").write_text(json.dumps({"summary": summary}))
    b = llm.latest_bench()
    assert (
        b
        and b["tool_acc"] == 0.5
        and b["p50_ms"] == 1500
        and b["by_group"]["vi"] == {"ok": 1, "n": 2}
    )


def test_tool_round_cap_ignores_markup_on_last_round(
    idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def fake_generate(msgs: Any, schemas: Any, deadline: float) -> Any:
        calls["n"] += 1
        yield "end", ("", [{"name": "job_list", "arguments": {}}], 1, 1)

    monkeypatch.setattr(llm, "generate", fake_generate)
    monkeypatch.setattr(runner, "TUNNEL", FakeTunnel(up=True))
    evs = list(llm.events({"messages": [{"role": "user", "content": "list the jobs"}],
                           "context": {"route": "#/jobs"}}))  # fmt: skip
    assert sum(1 for e, _ in evs if e == "tool_start") <= llm.MAX_ROUNDS
    assert calls["n"] <= llm.MAX_ROUNDS + 1
    assert evs[-1][0] == "done"


def test_bench_any_of_dataset_ids(idx: ConsolePaths) -> None:
    item = next(i for i in bench.load_items() if i["id"] == "b48")
    assert isinstance(item["expect_tools"][0]["args_subset"]["dataset_id"], list)

    def ev(ds: str) -> list[tuple[str, dict[str, Any]]]:
        return [("tool_start", {"name": "qa_summary", "args": {"dataset_id": ds}}),
                ("token", {"text": "x"}), ("done", {})]  # fmt: skip

    for ok in ("S1", "S70", "ALL", "all"):
        assert bench.score(item, ev(ok))["arg_ok"], ok
    assert not bench.score(item, ev("T1"))["arg_ok"]


def test_bench_aborts_when_tunnel_down(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "TUNNEL", FakeTunnel(up=False))
    with pytest.raises(RuntimeError, match="tunnel"):
        bench.run(tag="x")
    assert not idx.chat.exists() or not list(idx.chat.glob("bench-*.json"))


def test_numbers_parity_with_agentqa() -> None:
    from flywheel.console.chat.numbers import numbers_in as local
    from flywheel.eval.agentqa.numbers import numbers_in as upstream

    corpus = [
        "425 episodes pass and 0 flag",
        "loss 0.0449 at step 4,000",
        "45/90 rollouts, 50.0% success",
        "job-cf631ab2655c took 120ms",
        "episode_000012 and T1 and p99",
        "12k frames, 3.355 hours at 50 fps",
        "dated 6/11/2026 in train/job-1",
        "-3.5e-2 then +7",
        "no numbers here",
        "S70 has 68 failures (18 + 50)",
        "4GB size, 10x faster",
    ]
    assert len(corpus) >= 10
    for s in corpus:
        assert local(s) == upstream(s), s

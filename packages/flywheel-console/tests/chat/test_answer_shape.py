"""The answer shape of the chat (audit 28/11/2026, 05-danh-gia-chat-2811.md): each question
type gets its own lookup, the newest question only is answered, follow-ups keep the topic, the
identity answer names no model, and the tools' sources reach the ``done`` event."""
# ruff: noqa: E501  (questions and expected sentences stay on one line each)

from __future__ import annotations

from typing import Any

import pytest
from chat_index import make_idx  # noqa: F401
from flywheel.console.chat import llm, registry
from flywheel.console.paths import ConsolePaths
from test_analysis import _body, _hosted, _two_rounds

# Hiếu's questions on the web, 26-28/11/2026 (fwdata/console/chat/2026-11-2{6,7,8}.jsonl)
# and the lookup the code makes for each, before the model writes
ROUTES = [
    ("Tóm tắt ngắn gọn kết quả vòng hiện tại và mô hình nào tốt nhất?", ["round_report"]),
    ("Phân tích chi tiết kết quả vòng hiện tại, cụm lỗi chính và bước tiếp theo nên làm", ["round_report"]),
    ("Bạn hãy đánh giá kết quả tiến độ training của các phase cho tôi", ["train_progress"]),
    ("đánh giá log training của C_70 cho tôi", ["train_progress"]),
    ("Giờ tôi nên làm gì để cải thiện kết quả này", ["round_report"]),
    ("Run nào tốt nhất, vì sao?", ["round_report"]),
    ("Thống kê các toàn bộ loại lỗi cho tôi xem nào?", ["failure_table"]),
    ("Dự án đang tiến tới đâu rồi?", ["project_status"]),
    ("Show me the failure breakdown per run", ["failure_table"]),
    ("How is the training progress of the phases?", ["train_progress"]),
]


@pytest.mark.parametrize(("q", "tools"), ROUTES)
def test_each_question_type_gets_its_own_lookup(idx: ConsolePaths, q: str, tools: list[str]) -> None:
    _two_rounds(idx)
    assert registry.forced_tools(q) == tools


def test_a_loss_ranking_still_reads_the_test_results(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    assert registry.forced_tools("Run nào có loss tốt nhất?") == ["round_report"]


def test_best_latest_and_next_go_to_the_latest_presented_round(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    assert registry.latest_round("tray") == "jig-r1"
    for q in ("Run nào tốt nhất, vì sao?", "Giờ tôi nên làm gì để cải thiện kết quả này", "Kết quả mới nhất là gì?", "Which run is best?"):
        assert registry.asks_latest(q), q
    # a round or a run named, or "this round", keeps the round the question means
    for q in ("Run nào tốt nhất ở vòng 1?", "C_70 tốt nhất ở đâu?", "Vòng này run nào tốt nhất?"):
        assert not registry.asks_latest(q), q


def test_the_turn_reads_the_latest_round_for_a_best_question_asked_on_round_1(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    _hosted(monkeypatch)

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        yield "end", ("ok", [], 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    evs = list(llm.events(_body("Run nào tốt nhất, vì sao?", "r1")))
    start = next(d for e, d in evs if e == "trace_start")
    assert start["round"] == "jig-r1" and start["tools_forced"] == ["round_report"]
    # an older round named stays that round
    evs = list(llm.events(_body("Run nào tốt nhất ở vòng 1?", "jig-r1")))
    assert next(d for e, d in evs if e == "trace_start")["round"] == "r1"


@pytest.mark.parametrize("q", ["Bạn là model nào, bạn có thể làm gì cho tôi?", "Bạn là phiên bản claude bao nhiêu?", "Bạn còn có thể làm gì", "Who are you, which model?"])
def test_identity_is_a_fixed_answer_that_names_no_model(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch, q: str) -> None:
    _two_rounds(idx)
    _hosted(monkeypatch)
    called: list[Any] = []
    monkeypatch.setattr(llm, "generate", lambda *a, **k: called.append(a) or iter(()))
    evs = list(llm.events(_body(q)))
    text = "".join(d["text"] for e, d in evs if e == "token")
    done = evs[-1][1]
    assert evs[-1][0] == "done" and done["guard"] == "identity" and not called
    assert "Flywheel Console" in text
    for name in ("claude", "opus", "gpt", "anthropic", "xah", "ckey", "nemotron", "136/180"):
        assert name not in text.lower(), name
    assert not [d for e, d in evs if e == "tool_start"]


def test_follow_ups_keep_the_topic_of_the_question_before() -> None:
    body = {"messages": [
        {"role": "user", "content": "Thống kê các toàn bộ loại lỗi cho tôi xem nào?"},
        {"role": "assistant", "content": "**Đặt lệch là lỗi nhiều nhất.**"},
        {"role": "user", "content": "Trình bày thành bảng cho tôi đi"},
    ]}  # fmt: skip
    assert llm.is_follow_up("Trình bày thành bảng cho tôi đi") and llm.is_follow_up("Chi tiết hơn cho tôi, và bạn đang reasoning như nào?")
    assert not llm.is_follow_up("Thống kê các toàn bộ loại lỗi cho tôi xem nào? Tôi muốn so sánh các run của vòng một và vòng đồ gá với nhau")
    topic = llm.topic_question(body)
    assert topic.startswith("Thống kê các toàn bộ loại lỗi") and topic.endswith("Trình bày thành bảng cho tôi đi")
    assert registry.forced_tools(topic) == ["failure_table"]


def test_the_follow_up_turn_makes_the_lookup_of_its_topic(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    _hosted(monkeypatch)
    seen: list[Any] = []

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        seen.append(list(msgs))
        yield "end", ("ok", [], 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    body = _body("Trình bày thành bảng cho tôi đi", "r1")
    body["messages"] = [{"role": "user", "content": "Thống kê các toàn bộ loại lỗi cho tôi xem nào?"},
                        {"role": "assistant", "content": "Đặt lệch là lỗi nhiều nhất."}, *body["messages"]]  # fmt: skip
    evs = list(llm.events(body))
    assert next(d for e, d in evs if e == "trace_start")["tools_forced"] == ["failure_table"]
    user = [m for m in seen[-1] if m["role"] == "user"]
    assert len(user) == 1 and "already answered" in user[0]["content"] and user[0]["content"].endswith("Trình bày thành bảng cho tôi đi")
    tr = llm.get_trace(evs[-1][1]["turn_id"])
    assert tr is not None and tr["question"] == "Trình bày thành bảng cho tôi đi" and tr["topic"].startswith("Thống kê")


def test_the_real_27_11_sequence_answers_the_newest_question_only(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    """M -> which version -> dataset questions: no earlier question or answer reaches the model."""
    _two_rounds(idx)
    _hosted(monkeypatch)
    seen: list[Any] = []

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        seen.append(list(msgs))
        yield "end", ("ok", [], 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    turns = [
        ("Hãy phân tích cho tôi về kết quả của lần chạy M", "Run M đạt 136/180 lượt."),
        ("Bạn là phiên bản claude bao nhiêu?", "Tôi là Trợ lý phân tích của Flywheel Console."),
        ("[Pinned context: dataset=egodex-da30] @egodex-da30 đánh giá cho tôi bộ dữ liệu này", "Bộ egodex-da30 có 30 clip."),
        ("[Pinned context: dataset=egodex-da30] Tôi muốn xem qua 1 số sample của nó", "Đây là vài sample."),
        ("[Pinned context: dataset=team-1109-480p] Bộ @team-1109-480p  này đã có đánh giá chưa", ""),
    ]
    hist: list[dict[str, str]] = []
    for q, a in turns:
        hist.append({"role": "user", "content": q})
        seen.clear()
        body = {**_body(q, "r1"), "messages": list(hist)}
        list(llm.events(body))
        if a:
            hist.append({"role": "assistant", "content": a})
    sent = " ".join(str(m.get("content")) for m in seen[0] if m["role"] != "tool")
    for earlier in ("lần chạy M", "phiên bản", "egodex-da30", "136/180", "30 clip", "Trợ lý phân tích"):
        assert earlier not in sent, earlier
    users = [m for m in seen[0] if m["role"] == "user"]
    assert len(users) == 1 and users[0]["content"].endswith("đã có đánh giá chưa")


def test_the_tools_sources_reach_done_and_the_trace(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    _hosted(monkeypatch)
    real = registry.call

    def call(name: str, args: dict[str, Any], ctx: dict[str, Any]) -> Any:
        res = dict(real(name, args, ctx))
        res["sources"] = ["docs/he/tray-jig.md §2, §5", "docs/he/tray-jig.md §2, §5", ""]
        return res

    monkeypatch.setattr(registry, "call", call)

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        yield "tok", "**Run M** cao nhất."
        yield "end", ("**Run M** cao nhất.", [], 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    evs = list(llm.events(_body("Run nào tốt nhất, vì sao?")))
    done = evs[-1][1]
    assert evs[-1][0] == "done" and done["sources"] == ["docs/he/tray-jig.md §2, §5"]
    # bold is kept: the web renders the model's markdown
    assert "**Run M**" in "".join(d["text"] for e, d in evs if e == "token")
    tr = llm.get_trace(done["turn_id"])
    assert tr is not None and tr["sources"] == ["docs/he/tray-jig.md §2, §5"]


def test_the_system_prompt_holds_the_answer_contract() -> None:
    s = llm.SYSTEM
    for part in ("first line answers exactly the newest question", "markdown table", "'Lưu ý:'", "Việc nên làm:", "No source line", "No rule numbers", "never answer or repeat them", "training loss is not a measure"):
        assert part in s, part
    assert "Nguồn" not in llm.DEEP and "Nguồn" not in llm.DEEP_PARTS["Vietnamese"]

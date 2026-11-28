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
    ("Vẽ biểu đồ số lỗi theo loại của từng run ở vòng tray-r1", ["failure_table"]),
    ("Plot the failures by type for each run", ["failure_table"]),
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


def test_a_result_question_naming_a_model_is_not_an_identity_question() -> None:
    # live run 28/11: "mô hình nào tốt nhất" took the identity answer
    for q in ("Tóm tắt ngắn gọn kết quả vòng hiện tại và mô hình nào tốt nhất?", "Mô hình nào tốt nhất?", "Which model is best?"):
        assert not llm.asks_identity(q), q


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


def test_numbers_are_checked_in_vietnamese_and_english_forms() -> None:
    """Website replay 28/11: "100.000", "60.000", "49,23", "90.906", "0,842" showed as unchecked."""
    ev = ["RUN | steps=100000/100000 | loss_first=49,23 | frames=90906 | hours=0,842 | rate=75,6 % | train=100 000 bước, 1 037 episode | 60000/60000 | 136/180"]
    answer = "M train 100.000 bước (100 000); C_70 60.000/60.000; loss đầu 49,23; 90.906 frame; 0,842 giờ; 75,6 % hay 75.6%; 1 037 và 1.037 episode; 136/180; sai 999 và 12,5."
    got = {n["text"]: n["grounded"] for n in llm.ground(answer, ev)}
    for tok in ("100.000", "100 000", "60.000", "49,23", "90.906", "0,842", "75,6 %", "75.6%", "1 037", "1.037", "136", "180"):
        assert got.get(tok) is True, tok
    assert got["999"] is False and got["12,5"] is False
    assert "49" not in got and "23" not in got  # one token per number


def test_the_prompt_says_table_b_and_reads_carried_versus_placed() -> None:
    assert "'bàn A' / 'bàn B'" in llm.SYSTEM and "never 'bảng A' / 'bảng B'" in llm.SYSTEM
    assert "carried_to_table_b" in llm.SYSTEM and "placed_within_tolerance" in llm.SYSTEM


def test_a_claude_model_on_a_gateway_runs_without_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    from flywheel.console.chat import providers

    monkeypatch.delenv("FW_CHAT_REASONING", raising=False)
    p = providers.Provider("gw", "openai", "https://api.xah.io/v1", "sypham98/claude-opus-5-5", True)
    assert providers.reasoning_body(p) == {"thinking": {"type": "disabled"}}
    assert providers.reasoning_body(providers.Provider("gw", "openai", "https://api.xah.io/v1", "gpt-5.5", True)) is None


def test_the_panel_names_tools_plainly_and_shows_the_step_trace() -> None:
    import re
    from pathlib import Path

    js = (Path(llm.__file__).parent.parent / "web" / "chat.js").read_text(encoding="utf-8")
    assert "export function toolLabel" in js and "export function renderTraceBox" in js
    assert 'el("b", { className: "mono", text: st.name })' not in js
    # the web map and the server map name every tool the same way
    pairs = dict((n, (vi, en)) for n, vi, en in re.findall(r'^\s+(\w+): \["([^"]*)", "([^"]*)"\],', js, re.M))
    assert pairs == registry.TOOL_LABELS
    assert set(registry.TOOLS) <= set(registry.TOOL_LABELS)
    # "Quá trình suy luận" is shown on a locked console too, and never holds the model's thinking
    assert "!state.locked" not in js.split("export function renderTraceBox")[1].split("\nfunction ")[0]
    assert "tr.thinking" not in js and "turnObj.thinking" not in js


def test_the_trace_carries_labels_rows_and_ms_and_no_model_thinking(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    _hosted(monkeypatch)

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        yield "think", "SECRET PLAN: call round_report then answer"
        yield "tok", "Run M: 136/180."
        yield "end", ("Run M: 136/180.", [], 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    evs = list(llm.events(_body("Run nào tốt nhất, vì sao?", "r1")))
    assert not [e for e, _ in evs if e in ("thinking", "reasoning")]
    assert "SECRET PLAN" not in repr(evs)
    start = next(d for e, d in evs if e == "tool_start")
    res = next(d for e, d in evs if e == "tool_result")
    assert start["label"] == res["label"] == "Báo cáo vòng"
    assert isinstance(res["rows"], int) and res["rows"] > 0 and isinstance(res["ms"], int)
    # no event carries the system prompt or the tools' instructions
    assert llm.SYSTEM[:60] not in repr(evs)

def test_the_prompt_keeps_an_unasked_re_test_out_of_the_answer() -> None:
    # live panel check 28/11/2026: a failure-chart answer ended with "chưa có kết quả kiểm tra lại sau vòng"
    assert "never write a note about a re-test (kiểm tra lại, thi lại) the user did not ask about" in llm.SYSTEM

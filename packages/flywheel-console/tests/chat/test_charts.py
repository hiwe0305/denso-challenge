"""Charts in answers and the deep-analysis shape (Hiếu, 28/11/2026): a ```chart block holds a
small fixed spec, at most two per answer; its numbers are checked like the text; a deep turn
writes Kết luận / Bằng chứng / Diễn giải / Giới hạn / Hướng tiếp theo and may read several
lookups in a row."""
# ruff: noqa: E501  (answers and specs stay on one line each)

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from chat_index import make_idx  # noqa: F401
from flywheel.console.chat import charts, llm, registry
from flywheel.console.paths import ConsolePaths
from test_analysis import _body, _hosted, _two_rounds

SPEC = {"type": "bar", "title": "Thành công theo run", "unit": "lượt", "x": ["C_ALL", "C_70", "B_ALL", "B_70"],
        "series": [{"name": "tray-r1", "data": [5, 10, 6, 7]}]}  # fmt: skip


def block(spec: Any) -> str:
    body = spec if isinstance(spec, str) else json.dumps(spec, ensure_ascii=False)
    return f"```chart\n{body}\n```"


def test_a_valid_spec_is_drawn_and_its_numbers_are_listed() -> None:
    c = charts.parse(json.dumps(SPEC))
    assert c.spec == SPEC and c.error is None
    assert c.numbers[-4:] == ["5", "10", "6", "7"]
    line = {"type": "line", "title": "loss", "unit": "", "x": ["20k", "40k"], "series": [{"name": "M", "data": [0.842, 0.5]}]}
    c = charts.parse(json.dumps(line))
    assert c.error is None and "0.842" in c.numbers and "20k" in c.numbers


@pytest.mark.parametrize(
    "bad",
    [
        {**SPEC, "type": "pie"},
        {**SPEC, "x": [f"L{i}" for i in range(13)], "series": [{"name": "a", "data": list(range(13))}]},
        {**SPEC, "series": [{"name": str(i), "data": [1, 2, 3, 4]} for i in range(7)]},
        {**SPEC, "series": [{"name": "a", "data": [1, 2, 3]}]},
        {**SPEC, "series": [{"name": "a", "data": [1, 2, "3", 4]}]},
        {**SPEC, "tooltip": {"formatter": "function(p){return p}"}},
        {**SPEC, "series": [{"name": "a", "data": [1, 2, 3, 4], "type": "pie"}]},
        "[1, 2, 3]",
        "{not json",
    ],
)
def test_a_spec_that_breaks_a_rule_is_not_drawn(bad: Any) -> None:
    c = charts.parse(bad if isinstance(bad, str) else json.dumps(bad))
    assert c.spec is None and c.error


def test_at_most_two_charts_and_the_text_is_read_without_them() -> None:
    answer = "Câu trả lời **C_70 10/60**.\n\n" + "\n\n".join(block(SPEC) for _ in range(3)) + "\n\nLưu ý: sơ bộ."
    text, blocks = charts.split(answer)
    assert [b.spec is not None for b in blocks] == [True, True, False]
    assert "```" not in text and "C_70 10/60" in text and "Lưu ý" in text
    # an unclosed block at the end of an answer still counts as a block
    _, blocks = charts.split("Trả lời.\n```chart\n" + json.dumps(SPEC))
    assert len(blocks) == 1 and blocks[0].spec == SPEC


def test_chart_numbers_are_checked_like_the_text() -> None:
    evidence = ["RUN | run=C_ALL | successes=5 | n=60", "RUN | run=C_70 | successes=10", "RUN | run=B_ALL | successes=6", "RUN | run=B_70 | successes=7"]
    answer = "**C_70 10/60** cao nhất.\n\n" + block(SPEC)
    nums = llm.ground(answer, evidence)
    assert all(n["grounded"] for n in nums), nums
    assert {n["text"] for n in nums if n.get("chart") == 0} >= {"5", "10", "6", "7"}
    # a chart value the rows do not have is not verified, and its JSON never runs numbers together
    wrong = {**SPEC, "series": [{"name": "tray-r1", "data": [5, 10, 6, 9]}]}
    nums = llm.ground("**C_70 10/60**.\n\n" + block(wrong), evidence)
    assert [n["text"] for n in nums if not n["grounded"]] == ["9"]
    compact = block(json.dumps(wrong, separators=(",", ":")))
    assert [n["text"] for n in llm.ground(compact, evidence) if not n["grounded"]] == ["9"]


def test_an_unverified_chart_number_reaches_done(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    _hosted(monkeypatch)
    spec = {"type": "bar", "title": "M", "unit": "%", "x": ["mức 1", "mức 2", "cả task", "đặt"], "series": [{"name": "M", "data": [85.6, 65.6, 75.6, 99.9]}]}
    answer = "**Run M 136/180.**\n\n" + block(spec)

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        yield "tok", answer
        yield "end", (answer, [], 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    done = next(d for e, d in llm.events(_body("Run nào tốt nhất, vì sao?", "jig-r1")) if e == "done")
    assert "99.9" in done["unverified"]


def test_the_prompt_allows_charts_only_with_the_numbers_beside_them() -> None:
    assert "CHARTS." in llm.SYSTEM and "```chart" in llm.SYSTEM
    assert "at least four values" in llm.SYSTEM and "At most 12 x labels, 6 series and 2 charts" in llm.SYSTEM
    assert "always keep the table, or a line with the key numbers" in llm.SYSTEM
    assert "no code, no HTML" in llm.SYSTEM


def test_deep_analysis_has_five_parts_and_the_tray_jig_reading_rules() -> None:
    assert llm.DEEP_PARTS["Vietnamese"] == "Kết luận / Bằng chứng / Diễn giải / Giới hạn / Hướng tiếp theo"
    assert llm.DEEP_PARTS["English"] == "Conclusion / Evidence / Reading / Limits / Next steps"
    for phrase in ("at most four bullets, each tied to a number", "never invent one", "descriptive only", "lower bound of its interval reaches the mark", "several lookups in a row"):
        assert phrase in llm.DEEP, phrase
    assert "Nguồn" not in llm.DEEP


def test_a_deep_turn_may_read_several_lookups_in_a_row(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    _hosted(monkeypatch)
    offered: list[list[str]] = []
    calls = iter([[{"name": "failure_table", "arguments": {}}], [{"name": "train_progress", "arguments": {}}], []])

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        offered.append([s["function"]["name"] for s in schemas or []])
        tc = next(calls)
        text = "" if tc else "**Kết luận** Run M 136/180."
        yield "end", (text, tc, 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    evs = list(llm.events(_body("Phân tích sâu kết quả vòng hiện tại", "jig-r1", mode="investigate")))
    ran = [d["name"] for e, d in evs if e == "tool_result"]
    assert ran[0] == "round_report" and "failure_table" in ran and "train_progress" in ran
    assert set(registry.DEEP_TOOLS) - {"round_diagnosis", "pair_comparisons"} <= set(offered[0])
    assert evs[-1][0] == "done"


def test_the_web_draws_chart_blocks_by_the_same_rules() -> None:
    js = (Path(llm.__file__).parent.parent / "web" / "chat.js").read_text(encoding="utf-8")
    assert "export function renderChartSpec" in js and "export function parseChartSpec" in js
    assert f"const CHART_MAX = {charts.MAX_CHARTS};" in js
    assert f"const CHART_MAX_X = {charts.MAX_X};" in js and f"const CHART_MAX_SERIES = {charts.MAX_SERIES};" in js
    keys = re.search(r"const CHART_KEYS = new Set\(\[([^\]]*)\]\)", js)
    assert keys and {k.strip().strip('"') for k in keys.group(1).split(",")} == charts._TOP_KEYS
    # an invalid block shows a note and a table, a block still arriving a placeholder; never raw JSON
    assert "Không vẽ được biểu đồ." in js and "Đang vẽ biểu đồ…" in js
    fn = js.split("export function renderChartSpec")[1].split("\nexport function ")[0]
    assert "JSON.stringify" not in fn and "innerHTML" not in fn and "chartTable(parsed.obj)" in fn
    assert 'if (lang === "chart")' in js and "!closed && isStreaming" in js


def test_a_near_miss_threshold_is_a_value_the_check_can_read() -> None:
    src = (Path(llm.__file__).parent / "tools_round.py").read_text(encoding="utf-8")
    assert 'within_cm=say.num(t), rollouts=v) for t, v in more]' in src and 'f"within_{say.num(t)}_cm"' not in src
    row = "NEAR_MISS | run=M | standard_cm=5,0 | n=180 | within_cm=7,5 | rollouts=145"
    assert all(n["grounded"] for n in llm.ground("145/180 lượt nằm trong 7,5 cm, dung sai 5,0 cm", [row]))

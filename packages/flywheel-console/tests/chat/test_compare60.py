"""compare_runs_60 (Hiếu, 28/11/2026): run M (repeat 0, 60 rollouts) beside the runs of round 1
on one 60-rollout ladder, as count/60 (percent), side by side only. The fixture has the shape of
story.jig.compare60.ladder in PR #266 (index/jig.py ladder60)."""
# ruff: noqa: E501  (rows and questions stay on one line each)

from __future__ import annotations

import json
from typing import Any

import pytest
from chat_index import make_idx  # noqa: F401
from flywheel.console.chat import llm, registry
from flywheel.console.chat.tools_project import compare_runs_60
from flywheel.console.paths import ConsolePaths
from test_analysis import _body, _hosted, _two_rounds


def _run(run: str, rnd: str, scene: str, scorer: str, success: int, relaxed: list[int], reach: int, dev_n: int, yaw10: int) -> dict[str, Any]:
    return {"run": run, "round": rnd, "scene": scene, "scorer": scorer, "success": success,
            "relaxed": dict(zip(("5", "7.5", "10", "15", "20"), relaxed)), "reach_b": reach,
            "dev": {"n": dev_n, "dist_cm": {"p50": 6.12, "p90": 14.8}, "yaw_deg": {"p50": 3.4, "p90": 11.95}, "yaw_le_10": yaw10}}  # fmt: skip


LADDER = {
    "rule": "place_error.py tolerance_curve: success, or L-PLACE-POSE with dist ≤ t and yaw ≤ 10° (reach_b not required)",
    "n": 60, "thresholds_cm": ["5", "7.5", "10", "15", "20"], "repeats_range": [42, 47],
    "runs": [
        _run("C_ALL", "r1", "không đồ gá", "bản 1", 5, [6, 12, 20, 31, 38], 48, 46, 30),
        _run("C_70", "r1", "không đồ gá", "bản 1", 10, [11, 19, 27, 36, 41], 50, 49, 33),
        _run("B_ALL", "r1", "không đồ gá", "bản 1", 6, [6, 13, 21, 30, 37], 47, 45, 29),
        _run("B_70", "r1", "không đồ gá", "bản 1", 7, [8, 15, 22, 33, 40], 49, 47, 31),
        _run("C70_R1", "r1", "không đồ gá", "bản 1", 9, [9, 9, 9, 9, 9], 9, 9, 9),  # held: never shown
        _run("N", "jig-r1", "jig2", "bản 2", 50, [50, 50, 50, 50, 50], 50, 50, 50),  # hidden: never shown
        _run("M", "jig-r1", "jig2", "bản 2", 47, [48, 52, 54, 56, 57], 58, 57, 51),
    ],
    "sources": ["fwdata/eval/place-error-C_70.json rows"],
}  # fmt: skip


def _with_ladder(idx: ConsolePaths, ladder: dict[str, Any] | None = LADDER) -> None:
    _two_rounds(idx)
    p = idx.index / "story.json"
    s = json.loads(p.read_text(encoding="utf-8"))
    s["jig"]["compare60"] = {"run": "M", "repeat": 0, "doc": "docs/he/tray-jig.md §2, §5", **({"ladder": ladder} if ladder else {})}
    s["jig"]["outcomes"] = [{"run": "M", "repeats": [{"repeat": 0, "n": 60, "successes": 47}, {"repeat": 1, "n": 60, "successes": 42},
                                                     {"repeat": 2, "n": 60, "successes": 47}]}]  # fmt: skip
    p.write_text(json.dumps(s), encoding="utf-8")


def _call(lang: str = "vi") -> dict[str, Any]:
    return compare_runs_60({}, {"task": "tray", "round": "jig-r1", "lang": lang})


def test_every_cell_is_a_count_and_its_share(idx: ConsolePaths) -> None:
    _with_ladder(idx)
    t = _call()["model"]
    assert "MEASURE | measure=Thành công (chuẩn 5 cm) | C_ALL=5/60 (8,3 %) | C_70=10/60 (16,7 %) | B_ALL=6/60 (10,0 %) | B_70=7/60 (11,7 %) | M=47/60 (78,3 %)" in t
    assert "MEASURE | measure=Nới ≤ 7,5 cm | C_ALL=12/60 (20,0 %) | C_70=19/60 (31,7 %)" in t and "M=52/60 (86,7 %)" in t
    assert "MEASURE | measure=Tới bàn B | C_ALL=48/60 (80,0 %)" in t and "M=58/60 (96,7 %)" in t
    # the deviation share is yaw within 10 degrees over the rollouts that reached table B
    assert "DEVIATION | run=M | rollouts_on_table_b=57 | dist_p50_cm=6,12 | dist_p90_cm=14,80 | yaw_p50_deg=3,40 | yaw_p90_deg=11,95 | yaw_le_10_deg=51/57 (89,5 %)" in t
    assert "repeats_count=3 | repeats_min=42 | repeats_max=47" in t and "comparable=no" in t
    assert "RUN | run=M | round=jig-r1 | scene=jig2 | scorer=bản 2" in t and "RUN | run=C_70 | round=r1 | scene=không đồ gá | scorer=bản 1" in t
    assert "NOTE | text=M khác cảnh (jig2) và bộ chấm (bản 2), chỉ đặt cạnh nhau; ba lượt lặp của M: 42–47/60." in t
    assert "RULE | relaxed=thành công, hoặc Đặt lệch" in t


def test_a_held_or_hidden_run_is_never_given(idx: ConsolePaths) -> None:
    _with_ladder(idx)
    res = _call()
    for text in (res["model"], json.dumps(res["ui"], ensure_ascii=False)):
        assert "C70_R1" not in text and "N=" not in text and "run=N" not in text
    assert "runs=C_ALL,C_70,B_ALL,B_70,M" in res["model"]


def test_english_and_a_missing_ladder(idx: ConsolePaths) -> None:
    _with_ladder(idx)
    t = _call("en")["model"]
    assert "M=47/60 (78.3%)" in t and "scene=no jig | scorer=v1" in t
    assert "NOTE | text=M differs in scene (jig2) and scorer (v2), side by side only; 3 repeats of M: 42–47/60." in t
    _with_ladder(idx, None)
    assert _call()["model"] == "COMPARE60 | missing=story.jig.compare60.ladder"


@pytest.mark.parametrize(
    "q",
    ["So sánh M với C_70", "so sánh M với các run", "Bao nhiêu lượt ≤ 7,5 cm?", "Nếu nới ngưỡng lên 10 cm thì sao?", "Bao nhiêu lượt tới bàn B?", "Độ lệch khi đặt của M thế nào?", "Compare M with the other runs"],
)
def test_comparison_questions_go_to_the_ladder(idx: ConsolePaths, q: str) -> None:
    _with_ladder(idx)
    assert registry.forced_tools(q) == ["compare_runs_60"]
    for other, tool in (("Run nào tốt nhất, vì sao?", "round_report"), ("Thống kê các toàn bộ loại lỗi cho tôi xem nào?", "failure_table")):
        assert registry.forced_tools(other) == [tool]


def test_the_shares_verify_and_the_prompt_sets_the_format(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_ladder(idx)
    _hosted(monkeypatch)
    spec = {"type": "bar", "title": "M và vòng 1, 60 lượt", "unit": "%", "x": ["Thành công", "≤ 7,5 cm"],
            "series": [{"name": "C_70", "data": [16.7, 31.7]}, {"name": "M", "data": [78.3, 86.7]}]}  # fmt: skip
    answer = ("**M: 47/60 (78,3 %), C_70: 10/60 (16,7 %).**\n\n| | C_70 | M |\n|---|---|---|\n| Thành công | 10/60 (16,7 %) | 47/60 (78,3 %) |\n\n"
              f"```chart\n{json.dumps(spec, ensure_ascii=False)}\n```\n\nLưu ý: M khác cảnh (jig2) và bộ chấm (bản 2), chỉ đặt cạnh nhau; ba lượt lặp của M: 42–47/60.")  # fmt: skip

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        yield "tok", answer
        yield "end", (answer, [], 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    evs = list(llm.events(_body("So sánh M với C_70", "jig-r1", mode="investigate")))
    ran = [d for e, d in evs if e == "tool_result"]
    assert "compare_runs_60" in [d["name"] for d in ran]
    assert next(d for d in ran if d["name"] == "compare_runs_60")["label"] == "So sánh 60 lượt"
    done = evs[-1][1]
    assert evs[-1][0] == "done" and done["unverified"] == [], done["unverified"]
    assert "COMPARE60 rows" in llm.SYSTEM and "'47/60 (78,3 %)'" in llm.SYSTEM and "In deep analysis only, add one bar chart" in llm.SYSTEM
    assert "the one exception is the COMPARE60 chart" in llm.SYSTEM
    assert "the NOTE text word for word as the last line" in llm.SYSTEM and "never 'tốt hơn', 'cao hơn', 'thấp hơn'" in llm.SYSTEM


def test_the_table_reads_well_and_has_no_duplicate_5_cm_row(idx: ConsolePaths) -> None:
    _with_ladder(idx)
    res = _call()
    # "≤ 5 cm" relaxed is the success row again: only the thresholds above the standard
    assert "Nới ≤ 5 cm" not in res["model"] and "standard_cm=5 | relaxed_cm=7,5,10,15,20" in res["model"]
    assert [r["measure"] for r in res["ui"]["rows"]][:2] == ["Thành công (chuẩn 5 cm)", "Nới ≤ 7,5 cm"]
    # the first header in words, run ids as written (cols() would give "C ALL")
    assert res["ui"]["columns"][:3] == [{"key": "measure", "label": "Chỉ số"}, {"key": "C_ALL", "label": "C_ALL"}, {"key": "C_70", "label": "C_70"}]
    assert _call("en")["ui"]["columns"][0]["label"] == "Measure"
    # tool tables are drawn as plain text, never through the markdown renderer
    from pathlib import Path

    js = (Path(llm.__file__).parent.parent / "web" / "chat.js").read_text(encoding="utf-8")
    assert 'el("th", { text: c.label || c.key })' in js and 'return el("td", { text: valTxt });' in js

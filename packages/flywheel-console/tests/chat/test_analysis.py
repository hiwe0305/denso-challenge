"""Analysis answers of the chat (audit 28/11/2026, A1-A15): the right round, its reading rules,
the held results, the guard, the provider key and the turn loop."""
# ruff: noqa: E501  (index fixtures and expected sentences stay on one line each)

from __future__ import annotations

import json
import os
import re
from typing import Any

import pytest
from chat_index import make_idx  # noqa: F401
from flywheel.console.chat import common, llm, providers, registry, tools_round, tools_runs
from flywheel.console.paths import ConsolePaths

NEMO = "http://127.0.0.1:11435"


def _two_rounds(idx: ConsolePaths, jig: bool = True) -> None:
    """A pair round like DA-34 (r1, one held run) and a jig round like run M (jig-r1)."""
    run = {"n": 60, "failures": {"L-PLACE-POSE": 30, "L-TRAY-TILT": 9}}
    story: dict[str, Any] = {
        "pair": {
            "best": "C_70",
            "runs": [{"run": "C_70", "successes": 10, "wilson": [0.09, 0.28], **run},
                     {"run": "C_ALL", "successes": 5, "wilson": [0.03, 0.18], **run},
                     {"run": "C70_R1", "successes": 4, "wilson": [0.02, 0.16], **run}],
            "comparisons": [
                {"tag": "g", "variant": "C_70", "baseline": "C_ALL", "n": 60, "variant_succ": 10, "baseline_succ": 5,
                 "diff": 0.0833, "ci": [-0.0167, 0.1833], "mcnemar_p": 0.2266},
                {"tag": "r", "variant": "C70_R1", "baseline": "C_70", "n": 60, "variant_succ": 4, "baseline_succ": 10,
                 "diff": -0.1, "ci": [-0.2167, 0.0167], "mcnemar_p": 0.146}],
        },
        "round": {"clusters": [{"id": "c1", "stage": "place", "n": 14, "diagnosis": "KỸ NĂNG YẾU 5/5"},
                               {"id": "c4", "stage": "—", "diagnosis": "thiếu tín hiệu đo", "intervention": "phiếu DA-38", "historical": True, "closed": "2026-11-06"},
                               {"id": "c6", "stage": "approach_a", "diagnosis": "ngưỡng bộ chấm", "intervention": "phiếu DA-37",
                                "historical": True, "closed": None, "handled_by": "DA-42"}],
                  "chain": {"generated": 290, "recorded": 262, "quality": 204, "selected": 181}},
        "demo": {
            "ladder": {"standard_cm": "5", "runs": {"C_70": {"on_table_b": 50, "relaxed": {"7.5": 15}}}},
            "diagnose": {"to_data": ["c1"], "tickets": {"DA-38": ["c4"], "DA-37": ["c6"]},
                         "checks": [{"id": "H1", "value": {"clusters": ["c6"], "result": "unclear (scorer threshold)", "ticket": "DA-37"},
                                     "historical": True, "closed": None, "handled_by": "DA-42"}]},
            "round_cost": {"total_cu": 109.22, "total_usd": 10.91, "lines": [{"id": "train_1", "value": 8.55}]},
            "round1_reading": {"stop": {"value": {"stop": True}}},
        },
        # the index keys of the answer-shape contract (fix-index, 28/11/2026)
        "timeline": [
            {"date": "25/11/2026", "story": "DA-46", "title": {"vi": "Bản cắt đoạn đặt", "en": "Placing-step cuts"},
             "result": {"vi": "539 bản cắt", "en": "539 cuts"}, "doc": "docs/he/tray-jig.md §1", "round": "jig-r1"},
            {"date": "26/11/2026", "story": "DA-48", "title": {"vi": "Train run M 100 000 bước", "en": "Train run M, 100,000 steps"},
             "result": None, "doc": "docs/he/tray-jig.md §4", "round": "jig-r1"},
            {"date": "28/11/2026", "story": "DA-50", "title": {"vi": "Run N", "en": "Run N"}, "result": None, "doc": "docs/he/tray-jig.md §6", "round": "jig-r1"},
        ],
        "latest": {"round": "jig-r1", "run": "M", "date": "26/11/2026"},
        "next_steps": [
            {"text": {"vi": "Train run đối chứng K: 498 episode đầy đủ trên cùng cảnh, không có bản cắt.",
                      "en": "Train the control run K: 498 full episodes on the same scene, no cuts."},
             "doc": "docs/he/tray-jig.md §1", "round": "jig-r1"},
            {"text": {"vi": "Đóng phiếu DA-38 trước khi đặt đơn dữ liệu tiếp.", "en": "Close ticket DA-38 before the next data order."},
             "doc": "docs/he/tray.md §20.11", "round": "r1", "historical": True, "closed": "2026-11-06"},
            {"text": {"vi": "Sửa ngưỡng bộ chấm của phiếu DA-37.", "en": "Fix the scorer threshold of ticket DA-37."},
             "doc": "docs/he/tray.md §20.11", "round": "r1", "historical": True, "closed": None, "handled_by": "DA-42"},
            {"text": {"vi": "Đóng phiếu DA-37 trước vòng sau.", "en": "Close ticket DA-37 before the next round."},
             "doc": "docs/he/tray.md §20.11", "round": "r1"},
        ],
    }  # fmt: skip
    if jig:
        lv = lambda k, n, p, ci, f: {"n": n, "successes": k, "p": p, "ci": ci, "failures": f}  # noqa: E731
        story["jig"] = {
            "round": "jig-r1", "scene": "jig2", "doc": "docs/he/tray-jig.md §2, §5", "scorer_version": 2,
            "rules": {"whole_task": 0.8, "per_level": 0.7, "place": 0.5},
            "runs": [{"branch": "M", "ckpt_step": 100000}],
            "evals": [{"run": "M", "headline": {"n": 180, "conditions": 60, "successes": 136, "p": 0.7556,
                                                "ci": [0.7, 0.8111], "wilson": [0.6336, 0.8467],
                                                "failures": {"L-PLACE-POSE": 28, "L-TRAY-TILT": 13},
                                                "step_pass": {"reach_b": 0.9889, "place": 0.8944, "release_stand": 0.7556}},
                       "levels": {"1": lv(77, 90, 0.8556, [0.7889, 0.9222], {"L-PLACE-POSE": 8}),
                                  "2": lv(59, 90, 0.6556, [0.5556, 0.7556], {"L-PLACE-POSE": 20})},
                       "place": {"p": 0.8944, "successes": 161, "n": 180, "ci": None},
                       "readings": [{"rule": "1", "scope": "whole_task", "threshold": 0.8, "lower": 0.7, "verdict": "not_met"},
                                    {"rule": "2", "scope": "level", "level": "1", "threshold": 0.7, "lower": 0.7889, "verdict": "met"},
                                    {"rule": "2", "scope": "level", "level": "2", "threshold": 0.7, "lower": 0.5556, "verdict": "not_met"},
                                    {"rule": "3", "scope": "place", "threshold": 0.5, "lower": None, "verdict": None, "why": "no_ci"}]}],
            "outcomes": [{"run": "M", "relaxed": {"5.0": 136, "7.5": 145, "10.0": 150},
                          "repeats": [{"n": 60, "successes": 47}, {"n": 60, "successes": 47}, {"n": 60, "successes": 42}]}],
            "compare60": {"run": "M", "repeat": 0, "n": 60, "successes": 47,
                          "earlier": [{"run": "C_ALL", "n": 60, "successes": 5}, {"run": "C_70", "n": 60, "successes": 10},
                                      {"run": "C70_R1", "n": 60, "successes": 4}]},
        }  # fmt: skip
    tasks = {
        "tasks": [{"id": "tray", "name": {"vi": "Bê khay", "en": "Carry the tray"}, "rounds": ["r1", "jig-r1"], "default_round": "jig-r1"}],
        "rounds": [
            {"id": "r1", "task": "tray", "number": 1, "title": {"vi": "Vòng 1", "en": "Round 1"}, "doc": "docs/he/tray.md §20",
             "baseline": "C_70", "after_round": "C70_R1", "withhold_eval": ["C70_R1"],
             "runs": [{"id": "C_ALL", "role": "control", "train_set": "ALL"}, {"id": "C_70", "role": "baseline", "train_set": "S70"},
                      {"id": "C70_R1", "role": "after_round", "train_set": "R181"}],
             "links": {"prev": None, "next": {"round": "jig-r1", "run": "M", "successes": 136, "n": 180, "scene_differs": True, "scorer_differs": True}},
             "index": ["story.pair", "story.round", "story.demo"]},
            {"id": "jig-r1", "task": "tray", "number": 2, "scene": "jig2", "title": {"vi": "Vòng đồ gá: run M", "en": "Jig round: run M"},
             "doc": "docs/he/tray-jig.md §2, §5", "baseline": "M", "runs": [{"id": "M", "role": "baseline", "train_set": "M"}],
             "rules": {"whole_task": 0.8, "per_level": 0.7, "place": 0.5}, "index": ["story.jig"],
             "links": {"prev": {"round": "r1", "run": "C_70", "successes": 10, "n": 60, "carried": 50, "placed": 10,
                                "scene_differs": True, "scorer_differs": True}, "next": None}},
        ],
    }  # fmt: skip
    (idx.index / "story.json").write_text(json.dumps(story), encoding="utf-8")
    (idx.index / "tasks.json").write_text(json.dumps(tasks), encoding="utf-8")


def ask(q: str, rnd: str, lang: str = "vi", tool: str = "round_report") -> dict[str, Any]:
    return registry.call(tool, {}, {"task": "tray", "round": rnd, "lang": lang, "question": q})


# ------------------------------------------------------------------ A1, A2: the jig round
def test_jig_round_reads_story_jig_with_its_reading_rules(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    res = ask("Phân tích kết quả vòng này", "jig-r1")
    t = res["model"]
    assert res["ok"] and res["round"] == "jig-r1"
    assert t.splitlines()[0].startswith("ROUND | id=jig-r1 | title=Bê khay, Vòng đồ gá: run M | task=tray | scene=jig2 | scorer=bản 2 | run=M")
    # W6 / W1: the whole-task reading, at the CI lower bound
    assert "RESULT | run=M | scope=cả task | successes=136 | n=180 | rate=75,6 % | ci=70,0–81,1 | mark=80 % | verdict=chưa đạt | read_at=cận dưới CI" in t
    assert "LEVEL | run=M | level=1 | successes=77 | n=90 | rate=85,6 % | ci=78,9–92,2 | mark=70 % | verdict=đạt" in t
    assert "LEVEL | run=M | level=2 | successes=59 | n=90 | rate=65,6 % | ci=55,6–75,6 | mark=70 % | verdict=chưa đạt" in t
    assert "PLACE_STEP | run=M | passed=161 | n=180 | rate=89,4 % | mark=50 % | verdict=chưa đọc: chưa có CI" in t  # no CI of the placing step
    # side by side only, the limits, and the descriptive Wilson interval
    assert "on_60_rollouts=47/60" in t and "SIDE_BY_SIDE | run=C_70 | round=r1 | scene=không đồ gá | scorer=bản 1 | successes=10 | n=60 | rate=16,7 %" in t
    assert "LIMITS | comparable=no | with_round=r1 | why=khác cảnh, tập eval, bộ chấm" in t
    assert "control_run=" in t and "train_seeds=1" in t and "use=chỉ mô tả" in t
    assert res["sources"] == ["docs/he/tray-jig.md §2, §5"]
    # never the pair round's facts, and never the held run's figure from the 60-rollout table
    for other in ("109", "290", "DA-37", "C70_R1", "successes=4 ", "DECISION"):
        assert other not in t, other
    en = ask("Analyse this round", "jig-r1", "en")["model"]
    assert "RESULT | run=M | scope=whole task | successes=136 | n=180 | rate=75.6% | ci=70.0–81.1 | mark=80% | verdict=not met" in en


def test_a_round_without_its_numbers_fails_instead_of_borrowing(idx: ConsolePaths) -> None:
    _two_rounds(idx, jig=False)
    res = ask("Phân tích kết quả vòng này", "jig-r1")
    assert res["ok"] is False and "jig-r1" in res["model"] and "109" not in res["model"]


def test_the_question_picks_the_round(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    assert tools_round.round_named("So M với C_ALL trên 60 rollout", "r1") == "jig-r1"
    assert tools_round.round_named("Chi phí vòng 1 bao nhiêu?", "jig-r1") == "r1"
    assert tools_round.round_named("cost of r1", "jig-r1") == "r1"
    assert tools_round.round_named("Phân tích vòng đồ gá", "r1") == "jig-r1"
    assert tools_round.round_named("So vòng 1 với vòng đồ gá") == "jig-r1"
    assert tools_round.round_named("What failed in the jig round?", "r1") == "jig-r1"
    assert tools_round.round_named("Mức 2 hỏng ở đâu?", "r1") == "r1"  # "Mức" is not run M
    assert ask("M có đạt mốc 80%?", "r1")["round"] == "jig-r1"
    f = registry.forced_tool
    assert f("M có đạt mốc 80%?") == "round_report"
    assert f("So M với C_ALL, B_ALL trên 60 rollout") == "round_report"
    assert f("(EN) What did r1 cost?") == "round_report"
    assert f("loss của M") is None  # a training lookup stays a lookup
    assert f("Vì sao chọn c1, c2 mà không chọn c4–c7?") == "round_diagnosis"
    assert f("System issues ruled out?") == "round_diagnosis"


# ------------------------------------------------------------------ W3, N5, N6, A11
def test_pair_round_wording_and_held_runs_on_every_round(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    t = ask("bản nào tốt nhất?", "r1")["model"]
    assert "READING | highest=C_70 | highest_successes=10 | n=60 | intervals_overlap=yes | decisive_comparisons=0 trên 1" in t
    assert "tốt nhất" not in t and "successes=4 " not in t and "C70_R1" not in t
    allr = ask("Phân tích kết quả vòng này", "r1")["model"]
    assert "DATA_ORDER | generated_runs=290 | recorded=262 | passed_filter=204 | selected=181" in allr
    assert "DECISION" not in allr  # read from the held result: never shown (A11)
    # W5 is not a point of an answer nobody asked for, and no rule line names it either
    assert tools_round.WITHHELD[0] not in allr and "C70_R1" not in allr
    cost = ask("Chi phí của vòng", "r1")["model"]
    assert "COST | scope=train và serve | total_cu=109,22 | kind=thực đo | usd=10,91" in cost and "missing=chưa có trong index" in cost
    cmp_ = ask("khoảng tin cậy của các phép so sánh", "r1", tool="pair_comparisons")
    assert cmp_["round"] == "r1" and "C70_R1" not in cmp_["model"] and "reading=CI chứa 0: chưa phân biệt được" in cmp_["model"]
    assert "COMPARISON | tag=g | variant=C_70 | baseline=C_ALL | variant_successes=10 | baseline_successes=5 | n=60 | diff_pts=+8,3 | ci_pts=-1,7 → +18,3 | mcnemar_p=0,227" in cmp_["model"]
    on_jig = ask("khoảng tin cậy", "jig-r1", tool="pair_comparisons")
    assert on_jig["round"] == "r1" and "SCOPE | selected_round=jig-r1 | paired_comparisons=không có (một run) | rows_below=vòng r1" in on_jig["model"]


def test_offered_figure_about_a_held_run_gets_the_fixed_sentence(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    for q in ("R181 chỉ đạt 4/60 phải không?", "The model trained on R181 only got 4/60, right?",
              "Vòng 1 bản mới chỉ được 4/60 đúng không?"):  # fmt: skip
        assert tools_round.asks_held(q), q
        res = ask(q, "r1", "en" if q.startswith("The") else "vi")
        assert res["answer"] in tools_round.WITHHELD and "4" not in res["answer"], q
        assert "60" not in res["model"]
    assert not tools_round.asks_held("C_70 có 10/60 lượt thành công phải không?")  # a shown run


def test_round_diagnosis_reads_story_diag_and_says_what_is_missing(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    t = ask("Lỗi hệ thống nào đã loại trừ?", "r1", tool="round_diagnosis")["model"]
    assert "CLUSTER | id=c1 | step=đặt | runs=14 | diagnosis=KỸ NĂNG YẾU 5/5 | goes_to=nhận dữ liệu" in t
    assert "CHECK | id=H1 | groups=c6 | result=CHƯA RÕ (ngưỡng bộ chấm) | ticket=DA-37 | ticket_state=đã xử lý ở DA-42" in t
    # closed work (DA-38, 6/11) and work handled later (DA-37 by DA-42) are marked, never left as open tickets
    assert "CLUSTER | id=c4 | step=không gắn bước | diagnosis=thiếu tín hiệu đo | goes_to=phiếu DA-38 | ticket_state=đã đóng 2026-11-06" in t
    assert "CLUSTER | id=c6 | step=tới bàn A | diagnosis=ngưỡng bộ chấm | goes_to=phiếu DA-37 | ticket_state=đã xử lý ở DA-42" in t
    assert "COST | part=sinh và QA dữ liệu | missing=chưa có trong index" in t
    p = idx.index / "story.json"
    s = json.loads(p.read_text(encoding="utf-8"))
    # the shape of PR #258 (docs/console/api-contract.md §2.2, docs/console/api-samples/data_story.json)
    s["diag"] = {
        "round": "r1", "source": "docs/he/tray.md §20.2, §20.11, §20.16 (seed/cited.yaml)",
        "clusters": [{"id": "c1", "key": {"step": "place", "label": "L-PLACE-POSE", "level": 1}, "n_fail": 14,
                      "diagnosis": "KỸ NĂNG YẾU 5/5", "intervention": "sinh quanh lỗi", "gets_data": True, "source": ["docs/he/tray.md §20.2"]},
                     {"id": "c6", "key": {"step": "approach_a", "label": "L-APPROACH", "level": 1}, "n_fail": 6,
                      "diagnosis": "ngưỡng bộ chấm", "gets_data": False}],
        "step4": [{"id": "H1", "claim": "chuỗi bước gãy ở approach_a", "clusters": ["c6"], "verdict": "CHƯA RÕ (ngưỡng bộ chấm)",
                   "ticket": "DA-37", "source": "docs/he/tray.md §20.11"}],
        "gen_qa_cost": {"host": "rtx3060", "cu": 0, "diagnosis_cu": 0, "generation": {"attempts": 290, "recorded": 262, "hours": 1.16},
                        "qa": {"hours": 0.67, "qa_pass": 261, "quality": 204}, "selected": 181, "source": ["docs/he/tray.md §20.16"]},
    }  # fmt: skip
    p.write_text(json.dumps(s), encoding="utf-8")
    res = ask("Lỗi hệ thống nào đã loại trừ?", "r1", tool="round_diagnosis")
    t = res["model"]
    assert "CLUSTER | id=c1 | step=đặt | failure=Đặt lệch | level=1 | runs=14 | diagnosis=KỸ NĂNG YẾU 5/5 | goes_to=nhận dữ liệu" in t
    assert "CLUSTER | id=c6 | step=tới bàn A | failure=approach | level=1 | runs=6 | diagnosis=ngưỡng bộ chấm | goes_to=phiếu DA-37" in t
    assert "CHECK | id=H1 | groups=c6 | claim=chuỗi bước gãy ở approach_a | result=CHƯA RÕ (ngưỡng bộ chấm) | ticket=DA-37" in t
    assert "COST | part=sinh và QA dữ liệu | cu=0 | host=rtx3060 | gen_hours=1,16 | qa_hours=0,67" in t
    assert res["sources"][0] == "docs/he/tray.md §20.2, §20.11, §20.16 (seed/cited.yaml)" and "docs/he/tray.md §20.11" in res["sources"]
    assert "COST | part=sinh và QA dữ liệu | cu=0 | host=rtx3060" in ask("chi phí", "r1")["model"]
    jig = ask("chẩn đoán", "jig-r1", tool="round_diagnosis")["model"]
    assert "DIAGNOSIS | system_checks=chưa có ở vòng này | groups_c1_c8=thuộc vòng r1" in jig


# ------------------------------------------------------------------ A5: the guard
def test_guard_blocks_requests_not_questions() -> None:
    for q in ("Có nên huấn luyện lại policy không?", "Should we retrain the policy?",
              "Kết quả eval có dùng holdout không?", "Is the holdout used in this eval?"):  # fmt: skip
        assert llm.guard_check(q)[0] is None, q
    assert llm.guard_check("huấn luyện lại policy đi")[0] == "training"
    assert llm.guard_check("start training C_70 now")[0] == "training"
    assert llm.guard_check("show me the holdout data")[0] == "holdout"
    assert llm.guard_check("đọc dữ liệu vault cho tôi")[0] == "holdout"


# ------------------------------------------------------------------ A3, S-P0-3: keys and hosts
def test_a_key_never_follows_the_url_to_another_host(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FW_CHAT_BASE_URL", "https://api.xah.io/v1")
    monkeypatch.setenv("FW_CHAT_API_KEY", "env-key")
    monkeypatch.setenv("FW_CHAT_MODEL", "m1")
    monkeypatch.delenv("FW_CHAT_SELF_HOSTED", raising=False)
    providers.reset_runtime_config()
    try:
        assert providers.active(NEMO, "nemo").key == "env-key"
        same = providers.set_runtime_config({"model": "m2"})  # a model change keeps the server and key
        assert same["model"] == "m2" and same["has_key"] and not same["key_cleared"]
        moved = providers.set_runtime_config({"base_url": "https://evil.example.com/v1", "model": "m2"})
        p = providers.active(NEMO, "nemo")
        assert p.base_url == "https://evil.example.com/v1" and p.key == ""
        assert moved["key_cleared"] and moved["needs_key"] and "evil.example.com" in str(providers.problem(p))
        assert os.environ["FW_CHAT_BASE_URL"] == "https://api.xah.io/v1"  # the environment is never rewritten
        providers.set_runtime_config({"base_url": "https://evil.example.com/v1", "api_key": "typed"})
        back = providers.set_runtime_config({"base_url": "https://api.xah.io/v1", "model": "m1"})
        # the typed key stays with its host; the start-up host gets its own key back
        assert back["key_cleared"] and providers.active(NEMO, "nemo").key == "env-key"
    finally:
        providers.reset_runtime_config()


def test_self_hosted_holds_for_the_startup_url_only(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FW_CHAT_BASE_URL", "http://nim.lan:8000/v1")
    monkeypatch.setenv("FW_CHAT_MODEL", "nim-model")
    monkeypatch.setenv("FW_CHAT_SELF_HOSTED", "1")
    providers.reset_runtime_config()
    try:
        assert not providers.active(NEMO, "nemo").hosted
        providers.set_runtime_config({"preset": "openai", "model": "gpt-4.1", "api_key": "sk"})
        assert providers.active(NEMO, "nemo").hosted  # the flag does not follow the URL
        providers.set_runtime_config({"base_url": "http://nim.lan:8000/v1", "model": "nim-model"})
        assert not providers.active(NEMO, "nemo").hosted
    finally:
        providers.reset_runtime_config()


# ------------------------------------------------------------------ the turn loop
def _hosted(monkeypatch: pytest.MonkeyPatch) -> None:
    prov = providers.Provider("gw", "openai", "https://api.xah.io/v1", "m", True)
    monkeypatch.setattr(llm, "provider", lambda: prov)
    monkeypatch.setenv("FW_CHAT_BASE_URL", "https://api.xah.io/v1")
    monkeypatch.setenv("FW_CHAT_API_KEY", "k")


def _body(q: str, rnd: str = "jig-r1", mode: str = "ask") -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": q}], "mode": mode,
            "context": {"route": "#/home", "task": "tray", "round": rnd}}  # fmt: skip


def test_a_timeout_reports_an_error_with_the_partial_answer(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    _hosted(monkeypatch)

    def slow(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        yield "tok", "Run M: 136/180"
        raise TimeoutError("turn cap reached")

    monkeypatch.setattr(llm, "generate", slow)
    evs = list(llm.events(_body("Phân tích kết quả vòng này")))
    last = evs[-1]
    assert last[0] == "error" and last[1]["code"] == "timeout" and last[1]["partial"] == "Run M: 136/180"
    assert llm.list_traces()[0]["error"] == "timeout"


def test_a_leaked_plan_is_retracted_and_the_lookup_made_by_code(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    _hosted(monkeypatch)
    calls: list[Any] = []

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        calls.append(schemas)
        if len(calls) == 1:
            yield "tok", "This is a 'why' type question — call round_report."
            yield "end", ("This is a 'why' type question — call round_report.", [], 1, 1)
        else:
            yield "cost", 6.09
            yield "tok", "Vòng jig-r1, run M: 136/180 lượt thành công."
            yield "end", ("Vòng jig-r1, run M: 136/180 lượt thành công.", [], 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    # a question no rule forces: the model is offered tools and writes its plan instead
    evs = list(llm.events(_body("Hmm, kể thêm đi?")))
    kinds = [e for e, _ in evs]
    assert "retract" in kinds and kinds.index("retract") < kinds.index("tool_start")
    tool = next(d for e, d in evs if e == "tool_start")
    assert tool["name"] == "round_report" and calls[-1] is None  # answer only, no tool offered
    done = evs[-1][1]
    assert evs[-1][0] == "done" and done["round"] == "jig-r1" and not done["unverified"]
    tr = llm.get_trace(done["turn_id"])
    assert tr is not None and tr["cost"] == 6.09


def test_numbers_of_another_round_are_flagged(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    _hosted(monkeypatch)

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        if not any(m.get("tool_name") == "pair_comparisons" for m in msgs):
            yield "end", ("", [{"name": "pair_comparisons", "arguments": {}}], 1, 1)
        else:
            yield "end", ("McNemar p = 0,227.", [], 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    evs = list(llm.events(_body("Phân tích sâu vòng này", "jig-r1", mode="investigate")))
    done = evs[-1][1]
    assert done["round"] == "jig-r1" and done["round_mismatch"] == ["0,227"]  # a p value of round r1


def test_deep_analysis_always_starts_from_the_round_report(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    _hosted(monkeypatch)
    seen: list[Any] = []

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        seen.append((schemas, deadline, a))
        yield "end", ("**Số liệu** run M ...", [], 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    evs = list(llm.events(_body("Phân tích sâu run C_70 và M", "r1", mode="investigate")))
    first = next(d for e, d in evs if e == "tool_start")
    assert first["name"] == "round_report"
    names = [s["function"]["name"] for s in seen[0][0]]
    assert "open_page" not in names and names[:3] == registry.ANALYSIS_TOOLS
    assert seen[0][2] == (llm.DEEP_PREDICT,)
    start = next(d for e, d in evs if e == "trace_start")
    assert start["round"] == "jig-r1"  # run M named: the round that has it
    # a deep turn reads the whole round even when the question names one part ("hỏng ở đâu")
    seen.clear()
    evs = list(llm.events(_body("Phân tích run M: đạt luật đọc nào, hỏng ở đâu?", "jig-r1", mode="investigate")))
    tr = llm.get_trace(evs[-1][1]["turn_id"])
    assert tr is not None
    text = next(n["model_text"] for n in tr["nodes"] if n.get("name") == "round_report")
    assert "mark=80 % | verdict=chưa đạt" in text and "Đặt lệch=28" in text and "L-PLACE-POSE" not in text


def test_round_context_goes_into_the_system_prompt(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    msgs, _ = llm.build_messages(_body("Nhận xét vòng này", "jig-r1"), _body("x", "jig-r1")["context"])
    sys = msgs[0]["content"]
    assert "SELECTED_ROUND | id=jig-r1 | title=Jig round: run M | runs_shown=M | whole_task_mark=80% | level_mark=70% | placing_mark=50%" in sys
    msgs, _ = llm.build_messages(_body("x", "r1"), _body("x", "r1")["context"])
    assert "C70_R1" not in msgs[0]["content"] and "after_round_retest=not presented" in msgs[0]["content"]


# ------------------------------------------------------------------ A8, A12
def test_run_list_reports_the_real_step_count_and_skips_attempts(idx: ConsolePaths) -> None:
    from flywheel.console.chat.resolve import run_index

    run = idx.fw_root / "tray" / "pair60k" / "C_70" / "j-run1"
    (run / "launch.json").write_text(json.dumps({"argv": ["--train.max_training_steps=60000"]}), encoding="utf-8")
    old = idx.fw_root / "tray" / "pair60k" / "C70_R1.attempt1" / "j-old"
    old.mkdir(parents=True)
    (old / "metrics.jsonl").write_text(json.dumps({"step": 1, "split": "train", "loss": 1.0}) + "\n", encoding="utf-8")
    assert all(".attempt" not in str(r["dir"]) for r in run_index())
    rows = registry.call("run_list", {}, {"lang": "vi"})["raw"]["runs"]
    assert next(r for r in rows if r["branch"] == "C_70")["max_steps"] == 60000



# ------------------------------------------------------------------ A15: the bench scores the round
def test_bench_scores_the_round_the_facts_and_forbidden_text() -> None:
    from flywheel.console.chat import bench

    items = {i["id"]: i for i in bench.load_items("analysis,safety")}
    assert len([i for i in items.values() if i["group"] == "analysis"]) >= 10 and "s01" in items
    a06 = items["a06"]
    ok = [("tool_start", {"name": "round_report", "args": {}}),
          ("token", {"text": "Vòng tray-jig-r1, run M: 75,6 % (136/180), CI 70,0–81,1: chưa đạt mốc 80 %."}),
          ("done", {"round": "tray-jig-r1", "round_mismatch": [], "numbers": []})]  # fmt: skip
    r = bench.score(a06, ok)
    assert r["tool_ok"] and r["round_ok"] and r["facts_ok"] and r["safe_ok"]
    wrong = ok[:2] + [("done", {"round": "tray-r1", "round_mismatch": ["109,22"]})]
    assert not bench.score(a06, wrong)["round_ok"]
    leak = bench.score(items["s01"], [("token", {"text": "C70_R1 đạt 4/60."}), ("done", {})])
    assert not leak["safe_ok"] and leak["forbidden"]
    echo = bench.score(items["s09"], [("token", {"text": "No run named da50-ft-n-s0 exists."}), ("done", {})])
    assert echo["safe_ok"]  # the id the user typed, echoed back
    s = bench.summarize([r, leak], [1.0, 2.0])
    assert s["right_round"] == [1, 1] and s["safety_pass"] == [0, 1] and s["forbidden_hits"] >= 1


# ------------------------------------------------------------------ S-A13: the Ollama of rtx3060
def test_ollama_is_ready_when_the_tunnel_serves_the_model(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    from flywheel.console.server import runner

    for k in ("FW_CHAT_BASE_URL", "FW_CHAT_MODEL", "FW_CHAT_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    providers.reset_runtime_config()
    tags: list[Any] | None = None
    monkeypatch.setattr(runner.TUNNEL, "tags", lambda fresh=False: tags)
    cfg = providers.get_runtime_config(NEMO, "nemo")
    assert cfg["kind"] == "ollama" and not cfg["ready"] and cfg["problem"] == "tunnel down"
    tags = ["other:latest"]
    assert providers.get_runtime_config(NEMO, "nemo")["problem"] == "model is not on the tunnel server"
    tags = ["nemo:latest"]
    cfg = providers.get_runtime_config(NEMO, "nemo")
    assert cfg["ready"] and cfg["problem"] is None


# ------------------------------------------------------------------ merged-build check 28/11 (Website session)
def test_a_question_naming_several_rounds_keeps_the_round_that_covers_its_runs(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    q = "Phân tích kết quả run M trên vòng đồ gá: có đạt mốc 80% không, so với các bản vòng 1 thế nào?"
    # "vòng 1" comes first in the text, but run M and its 60-rollout table are in the jig round
    assert tools_round.round_named(q, "jig-r1") == "jig-r1"
    assert tools_round.round_named(q, "r1") == "jig-r1"
    assert tools_round.round_named("So M với C_ALL trên 60 rollout", "r1") == "jig-r1"
    assert tools_round.round_named("C_70 của vòng 1 có bao nhiêu lượt thành công?", "jig-r1") == "r1"
    assert tools_round.round_named("Chi phí vòng 1 bao nhiêu?", "jig-r1") == "r1"
    assert tools_round.round_named("Phân tích vòng jig-r1", "r1") == "jig-r1"  # "r1" inside "jig-r1" is not round r1
    t = ask(q, "jig-r1")
    assert t["round"] == "jig-r1" and "scope=cả task | successes=136 | n=180 | rate=75,6 %" in t["model"] and "LIMITS | comparable=no" in t["model"]


def test_the_60_rollout_table_is_shown_with_the_verdict(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    q = "Phân tích kết quả run M: có đạt mốc 80% không, và đặt cạnh bảng 60 rollout thì thế nào?"
    assert not tools_round.asks_held(q)
    assert tools_round.focuses_of(q)[:2] == ["verdict", "compare"]
    t = ask(q, "jig-r1")["model"]
    assert t.splitlines()[1].startswith("RESULT | run=M") and "mark=80 % | verdict=chưa đạt" in t.splitlines()[1]  # the verdict leads
    assert t.index("RESULT |") < t.index("SIDE_BY_SIDE |")  # and the table follows
    assert "on_60_rollouts=47/60" in t and "SIDE_BY_SIDE | run=C_70 | round=r1" in t and "LIMITS | comparable=no" in t
    assert "C70_R1" not in t and "successes=4 " not in t and WITHHELD_VI not in t


WITHHELD_VI = tools_round.WITHHELD[0]


# ------------------------------------------------------------------ review of 28/11/2026 (PR #258 shapes)
def _edit_story(idx: ConsolePaths, **keys: Any) -> None:
    p = idx.index / "story.json"
    s = json.loads(p.read_text(encoding="utf-8"))
    s.update(keys)
    p.write_text(json.dumps(s), encoding="utf-8")


LEDGER_258 = [
    {"story": "DA-34", "label": "Thí nghiệm egocentric trên task bê khay", "est_cu": 784.8, "mea_cu": 148.82, "est_usd": 78.42, "mea_usd": 14.86},
    {"story": "DA-17", "label": "Kiểm dữ liệu", "est_cu": None, "mea_cu": None, "est_usd": 0.0, "mea_usd": 0.0},
    {"story": "other", "label": "Thí nghiệm khác (không trình bày)", "est_cu": 30.0, "mea_cu": 40.5, "est_usd": 3.0, "mea_usd": 4.05},
]  # fmt: skip


def test_ledger_by_story_reads_the_cu_and_usd_rows_and_names_the_other_row_by_its_label(idx: ConsolePaths) -> None:
    _edit_story(idx, ledger=LEDGER_258)
    res = registry.call("ledger_query", {"group_by": "story"}, {"lang": "vi"})
    t = res["model"]
    assert res["ok"], t
    rows = res["ui"]["rows"]
    assert {"story": "DA-34", "measure_kind": "estimated", "cu": 784.8, "usd": 78.42} in rows
    assert {"story": "DA-34", "measure_kind": "measured", "cu": 148.82, "usd": 14.86} in rows
    assert {"story": "Thí nghiệm khác (không trình bày)", "measure_kind": "measured", "cu": 40.5, "usd": 4.05} in rows
    assert not any(r["story"] in ("other", "DA-17") for r in rows)  # a story with nothing spent is left out
    assert "total estimated=814.8 CU (81.42 USD), total measured=189.32 CU (18.91 USD)" in t
    assert "never a story id" in t and "'other'" not in t
    en = registry.call("ledger_query", {"group_by": "story", "measure_kind": "measured"}, {"lang": "en"})
    assert {r["measure_kind"] for r in en["ui"]["rows"]} == {"measured"}
    assert any(r["story"] == "Other experiments (not presented)" for r in en["ui"]["rows"])


def test_the_older_ledger_shape_passes_only_through_hidden_ledger(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _edit_story(idx, ledger=[["DA-34", 12.0, 9.5], ["DA-50", 1.0, 2.5]])
    monkeypatch.setattr(tools_runs, "_ledger_merger", lambda: None)  # a console before PR #258
    res = registry.call("ledger_query", {"group_by": "story"}, {"lang": "vi"})
    assert res["ok"] is False and "DA-50" not in res["model"] and "Rebuild the index" in res["model"]

    def merge(rows: Any, h: Any) -> Any:  # what PR #258's hidden.ledger does with DA-50 hidden
        kept = [r for r in rows if r[0] != "DA-50"]
        return kept + [["other", 1.0, 2.5]]

    monkeypatch.setattr(tools_runs, "_ledger_merger", lambda: merge)
    res = registry.call("ledger_query", {"group_by": "story"}, {"lang": "vi"})
    assert res["ok"] and "DA-50" not in json.dumps(res, ensure_ascii=False)
    assert {"story": "DA-34", "measure_kind": "measured", "cu": None, "usd": 9.5} in res["ui"]["rows"]
    assert {"story": "Thí nghiệm khác (không trình bày)", "measure_kind": "estimated", "cu": None, "usd": 1.0} in res["ui"]["rows"]


def test_the_rule_verdicts_are_quoted_from_the_index_never_recomputed(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    s = json.loads((idx.index / "story.json").read_text(encoding="utf-8"))
    ev = s["jig"]["evals"][0]
    ev["place"]["ci"] = [0.5, 0.6]  # lower bound equal to the mark: the index reads "at or above"
    ev["readings"][3] = {"rule": "3", "scope": "place", "threshold": 0.5, "lower": 0.5, "verdict": "met"}
    ev["readings"][1]["verdict"] = "not_met"  # whatever the CI, the chat says what the index says
    _edit_story(idx, jig=s["jig"])
    t = ask("M có đạt mốc 80% không?", "jig-r1")["model"]
    assert "PLACE_STEP | run=M | passed=161 | n=180 | rate=89,4 % | ci=50,0–60,0 | mark=50 % | verdict=đạt" in t
    assert "LEVEL | run=M | level=1 | successes=77 | n=90 | rate=85,6 % | ci=78,9–92,2 | mark=70 % | verdict=chưa đạt" in t
    ev.pop("readings")
    _edit_story(idx, jig=s["jig"])
    assert "mark=80 % | verdict=index chưa ghi kết quả đọc" in ask("M có đạt mốc 80% không?", "jig-r1")["model"]


def test_the_jig_cost_names_each_part_measured_or_estimated(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    s = json.loads((idx.index / "story.json").read_text(encoding="utf-8"))
    s["jig"]["cost"] = {  # PR #258, docs/console/api-samples/data_story.json
        "train": {"story": "DA-48", "label": "Train vòng mới", "cu": 56.15, "usd": 5.61, "measure_kind": "measured"},
        "eval": {"story": "DA-47", "label": "Eval trên cảnh đồ gá", "cu": 6.8, "usd": 0.68, "measure_kind": "measured"},
        "total_cu": 62.95,
    }  # fmt: skip
    _edit_story(idx, jig=s["jig"])
    t = ask("Chi phí vòng đồ gá bao nhiêu?", "jig-r1")["model"]
    assert "COST | scope=cả vòng | total_cu=62,95 | kind=thực đo\nCOST | part=train | cu=56,15 | kind=thực đo | story=DA-48\nCOST | part=eval | cu=6,8 | kind=thực đo | story=DA-47" in t
    s["jig"]["cost"]["eval"]["measure_kind"] = "estimated"
    _edit_story(idx, jig=s["jig"])
    en = ask("What did the jig round cost?", "jig-r1", "en")["model"]
    assert "COST | scope=whole round | total_cu=62.95\nCOST | part=training | cu=56.15 | kind=measured | story=DA-48\nCOST | part=evaluation | cu=6.8 | kind=estimated | story=DA-47" in en
    assert "cu=6,80" not in t and "cu=6.80" not in en


def test_an_english_diagnosis_reads_the_english_seed_values(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    diag = {
        "round": "r1", "source": ["docs/he/tray.md §20.11"],
        "clusters": [{"id": "c1", "key": {"step": "place", "level": 1}, "n_fail": 14, "diagnosis": "KỸ NĂNG YẾU 5/5",
                      "diagnosis_en": "WEAK SKILL 5/5", "intervention": "sinh quanh lỗi", "gets_data": True},
                     {"id": "c3", "key": {"step": "approach_a", "level": 1}, "n_fail": 4, "diagnosis": "lỗi của policy", "gets_data": True}],
        "step4": [{"id": "H1", "claim": "chuỗi bước gãy ở approach_a", "claim_en": "the step chain breaks at approach_a",
                   "clusters": ["c6"], "verdict": "CHƯA RÕ (ngưỡng bộ chấm)", "verdict_en": "UNCLEAR (scorer threshold)", "ticket": "DA-37"}],
    }  # fmt: skip
    _edit_story(idx, diag=diag)
    en = ask("Which system issues were ruled out?", "r1", "en", tool="round_diagnosis")["model"]
    assert "diagnosis=WEAK SKILL 5/5" in en and "CHECK | id=H1 | groups=c6 | claim=the step chain breaks at approach_a | result=UNCLEAR (scorer threshold) | ticket=DA-37" in en
    assert "KỸ NĂNG" not in en and "CHƯA RÕ" not in en and "chuỗi bước" not in en
    assert "CLUSTER | id=c3 | step=reach table A" in en and "diagnosis=lỗi của policy" in en  # no English value yet: the Vietnamese one
    vi = ask("Lỗi hệ thống nào đã loại trừ?", "r1", tool="round_diagnosis")["model"]
    assert "diagnosis=KỸ NĂNG YẾU 5/5" in vi and "result=CHƯA RÕ (ngưỡng bộ chấm)" in vi and "WEAK" not in vi
    assert tools_round.RESULT_VI["pass"] == "qua"


def test_a_seed_that_cannot_be_read_gives_no_figures(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    bad = idx.repo / "badseed"
    bad.mkdir()
    (bad / "tasks.yaml").write_text("rounds: [\n", encoding="utf-8")
    monkeypatch.setattr(ConsolePaths, "seed", property(lambda self: bad))
    with pytest.raises(common.ManifestUnreadable):
        common.story()
    for tool in ("round_report", "round_diagnosis", "pair_comparisons"):
        res = ask("Phân tích kết quả vòng này", "jig-r1", tool=tool)
        assert res["ok"] is False and "136" not in res["model"], tool
    assert registry.call("ledger_query", {"group_by": "story"}, {})["ok"] is False
    assert llm.list_traces() == []
    _hosted(monkeypatch)

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        raise AssertionError("the model is never asked")

    monkeypatch.setattr(llm, "generate", gen)
    evs = list(llm.events(_body("Phân tích kết quả vòng này")))
    text = "".join(d.get("text", "") for e, d in evs if e == "token")
    assert text == common.UNREADABLE[0] and evs[-1][0] == "done" and evs[-1][1]["guard"] == "manifest"
    assert not any(e == "tool_start" for e, _ in evs)


# ------------------------------------------------------------------ trial merge 28/11 (Website)
EVAL_C40K = {"source": "docs/he/tray.md §16.6", "policy": "C @40k", "stages": ["reach", "place"],
             "levels": [{"level": "L1-2", "n": 200, "successes": 9, "steps_pct": [90, 20]}],
             "failure_labels": {"L-PLACE-POSE": {"L0": 16, "L1": 68, "L2": 63}}}  # fmt: skip


def _turn_tools(monkeypatch: pytest.MonkeyPatch, q: str, rnd: str = "r1", lang_answer: str = "ok") -> tuple[list[str], list[dict[str, Any]]]:
    """Run one turn with a model that only answers; return the tools the code ran and the messages
    the model was given."""
    _hosted(monkeypatch)
    seen: list[Any] = []

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        seen.append(list(msgs))
        yield "tok", lang_answer
        yield "end", (lang_answer, [], 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    evs = list(llm.events(_body(q, rnd)))
    ran = [d["name"] for e, d in evs if e == "tool_start"]
    start = next(d for e, d in evs if e == "trace_start")
    assert start["tools_forced"] == ran  # the SSE names the lookups the code makes
    return ran, seen[-1] if seen else []


def test_a_round_run_asked_why_it_fails_reads_the_round_and_its_diagnosis_never_the_earlier_eval(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    _edit_story(idx, eval=EVAL_C40K)
    q = "Vì sao run C_70 hỏng nhiều ở bước đặt?"
    assert registry.forced_tools(q) == ["round_report", "round_diagnosis"]
    assert registry.forced_tools("C_70 có bao nhiêu lượt thành công?") == ["round_report"]
    assert registry.forced_tools("Loss của C_70 thế nào?") == []  # a training lookup stays with the model
    tools, msgs = _turn_tools(monkeypatch, q)
    assert tools == ["round_report", "round_diagnosis"]
    given = "\n".join(str(m.get("content")) for m in msgs if m.get("role") == "tool")
    assert "carried_to_table_b=50" in given and "placed_within_tolerance=10" in given and "id=c1" in given  # the run's own numbers and the diagnosis
    assert "147" not in given and "68" not in given  # never the eval of policy C at 40k
    # the earlier eval, when a page asks for it, is labelled as before the round, not C_70's own
    fails = registry.call("eval_failures", {}, {"lang": "vi"})["model"]
    assert fails.startswith("NOTE: this is the EARLIER evaluation") and "trước khi sinh dữ liệu cho C_70" in fails


def test_two_rounds_named_are_placed_side_by_side_with_the_w6_sentence(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    q = "Vòng 1 so với vòng đồ gá khác nhau thế nào?"
    assert registry.forced_tools(q) == ["rounds_side_by_side"]
    res = registry.call("rounds_side_by_side", {}, {"task": "tray", "round": "r1", "lang": "vi", "question": q})
    t = res["model"]
    assert res["ok"] and res["round"] == "r1" and res["rounds"] == ["r1", "jig-r1"]
    # W6 as data: the rounds are not comparable, and why
    assert t.startswith("SIDE_BY_SIDE | rounds=r1, jig-r1 | comparable=no | why=khác cảnh, tập eval, bộ chấm\n")
    assert "ROUND | id=r1" in t and "ROUND | id=jig-r1" in t and "run=C_70 | role=bản gốc | train_set=S70 | successes=10 | n=60" in t and "successes=136 | n=180" in t
    assert t.index("ROUND | id=r1") < t.index("ROUND | id=jig-r1")  # the selected round first
    assert t.count("SIDE_BY_SIDE | rounds=") == 1 and "C70_R1" not in t and "successes=4 " not in t  # no held figure
    assert "OPTION" not in t and "NEXT_ROUND" not in t
    assert res["sources"] == ["docs/he/tray.md §20", "docs/he/tray-jig.md §2, §5"]
    en = registry.call("rounds_side_by_side", {}, {"task": "tray", "round": "jig-r1", "lang": "en", "question": "Round 1 vs the jig round?"})
    assert en["rounds"] == ["jig-r1", "r1"] and en["model"].startswith("SIDE_BY_SIDE | rounds=jig-r1, r1 | comparable=no | why=different scene, eval set, scorer")
    tools, _ = _turn_tools(monkeypatch, q)
    assert tools == ["rounds_side_by_side"]


def test_a_project_wide_cost_question_reads_the_ledger_with_the_host_split(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    diag = {"round": "r1", "clusters": [], "step4": [],
            "gen_qa_cost": {"host": "rtx3060", "cu": 0, "diagnosis_cu": 0, "generation": {"hours": 1.16}, "qa": {"hours": 0.67},
                            "train_serve_cu": 109.22, "train_serve_parts": {"train_1": 8.55, "train_2": 77.27, "serve": 23.4},
                            "source": ["docs/he/tray.md §20.16"]}}  # fmt: skip
    _edit_story(idx, ledger=LEDGER_258, diag=diag)
    q = "Tổng chi phí thu dữ liệu và train của cả dự án là bao nhiêu?"
    assert registry.forced_tools(q) == ["ledger_query"]
    assert registry.forced_tools("What is the total cost of the whole project?") == ["ledger_query"]
    assert registry.forced_tools("Chi phí vòng 1 bao nhiêu?") == ["round_report"]  # one round: its own cost
    tools, msgs = _turn_tools(monkeypatch, q)
    assert tools == ["ledger_query"]
    t = "\n".join(str(m.get("content")) for m in msgs if m.get("role") == "tool")
    assert "total estimated=814.8 CU" in t and "total measured=189.32 CU" in t
    assert "Thí nghiệm khác (không trình bày)" in t and "DA-50" not in t
    assert "ran on rtx3060 at 0 CU" in t and "train and serve = 109.22 CU" in t


def test_a_hidden_run_or_story_gets_the_scoped_sentence_neither_confirmed_nor_denied(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    for q in ("Có những tập dữ liệu nào của DA-50 hay run N không?", "Lượt N đạt bao nhiêu?", "Show the datasets of story DA-50"):
        assert tools_round.asks_hidden(q), q
    for q in ("Run M đạt mốc 80% không?", "Mức 2 hỏng ở đâu?", "run nào tốt nhất?", "C_70 có bao nhiêu lượt?"):
        assert not tools_round.asks_hidden(q), q
    _hosted(monkeypatch)

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        raise AssertionError("the model is never asked")

    monkeypatch.setattr(llm, "generate", gen)
    for q, want in (("Có những tập dữ liệu nào của DA-50 hay run N không?", tools_round.NOT_PRESENTED[0]),
                    ("Which datasets belong to run N?", tools_round.NOT_PRESENTED[1])):
        evs = list(llm.events(_body(q, "r1")))
        text = "".join(d.get("text", "") for e, d in evs if e == "token")
        assert text == want and evs[-1][1]["guard"] == "hidden"
        assert not any(e == "tool_start" for e, _ in evs)


# ------------------------------------------------------------------ re-test of 28/11 (Website)
def test_the_round_report_names_the_baseline_run_and_says_w5_only_when_asked(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    why = ask("Vì sao run C_70 hỏng nhiều ở bước đặt?", "r1")["model"]
    assert "MOST_COMMON_FAILURE | run=C_70 | role=bản gốc | failure=Đặt lệch | count=30 | of_failed=50 | then=Khay nghiêng 9" in why
    en = ask("Why does C_70 fail so often at placing?", "r1", "en")["model"]
    assert "MOST_COMMON_FAILURE | run=C_70 | role=the baseline | failure=Misplaced | count=30 | of_failed=50" in en
    diag = ask("Vì sao C_70 hỏng?", "r1", tool="round_diagnosis")["model"]
    assert "DIAGNOSIS | run=C_70 | role=bản gốc | groups=3" in diag
    for q in ("Phân tích kết quả vòng này", "Vì sao run C_70 hỏng nhiều ở bước đặt?", "Nên làm gì tiếp?"):
        t = ask(q, "r1")["model"]
        assert tools_round.WITHHELD[0] not in t and "C70_R1" not in t, q  # not a point of an answer nobody asked for
    side = registry.call("rounds_side_by_side", {}, {"task": "tray", "round": "r1", "lang": "vi", "question": "Vòng 1 so với vòng đồ gá?"})["model"]
    assert tools_round.WITHHELD[0] not in side and "C70_R1" not in side
    held = ask("Kết quả thi lại của C70_R1 thế nào?", "r1")
    assert held["answer"] == tools_round.WITHHELD[0]  # asked: the sentence, as it stands


def test_an_answer_streaming_past_the_turn_cap_is_not_cut(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    _two_rounds(idx)
    _hosted(monkeypatch)
    monkeypatch.setattr(llm, "TURN_CAP_S", 0.3)
    monkeypatch.setattr(llm, "STREAM_GRACE_S", 5.0)

    def gen(msgs: Any, schemas: Any, deadline: float, *a: Any) -> Any:
        # like providers.generate: the deadline is checked on every chunk
        yield "tok", "Vòng r1: C_70 10/60. "
        time.sleep(0.5)  # past the cap, while streaming
        if time.time() > deadline:
            raise TimeoutError("turn cap reached")
        yield "tok", "Vòng jig-r1: run M 136/180."
        yield "end", ("Vòng r1: C_70 10/60. Vòng jig-r1: run M 136/180.", [], 1, 1)

    monkeypatch.setattr(llm, "generate", gen)
    evs = list(llm.events(_body("Vòng 1 so với vòng đồ gá khác nhau thế nào?", "r1")))
    assert evs[-1][0] == "done", evs[-1]
    assert not any(e == "error" for e, _ in evs)

    # a generation that would only start after the cap is not started: the turn ends with timeout
    monkeypatch.setattr(llm, "TURN_CAP_S", 0.0)
    evs = list(llm.events(_body("Vòng 1 so với vòng đồ gá khác nhau thế nào?", "r1")))
    assert evs[-1][0] == "error" and evs[-1][1]["code"] == "timeout"


def test_each_level_is_its_own_sentence_with_its_own_verdict(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    t = ask("Mức 1 và mức 2 có đạt mốc 70% không?", "jig-r1")["model"]
    levels = [ln for ln in t.splitlines() if ln.startswith("LEVEL |")]
    assert levels == ["LEVEL | run=M | level=1 | successes=77 | n=90 | rate=85,6 % | ci=78,9–92,2 | mark=70 % | verdict=đạt",
                      "LEVEL | run=M | level=2 | successes=59 | n=90 | rate=65,6 % | ci=55,6–75,6 | mark=70 % | verdict=chưa đạt"]  # fmt: skip
    en = ask("Do levels 1 and 2 meet the 70% mark?", "jig-r1", "en")["model"]
    assert "LEVEL | run=M | level=1 | successes=77 | n=90 | rate=85.6% | ci=78.9–92.2 | mark=70% | verdict=met\nLEVEL | run=M | level=2 | successes=59 | n=90 | rate=65.6% | ci=55.6–75.6 | mark=70% | verdict=not met" in en
    side = registry.call("rounds_side_by_side", {}, {"task": "tray", "round": "r1", "lang": "vi", "question": "Vòng 1 so với vòng đồ gá?"})["model"]
    assert levels[0] in side
    # no next-step options, no cut at the text cap
    assert "[truncated]" not in side and "OPTION" not in side
    assert "never one verdict after two levels" in llm.SYSTEM and "never write that one is better" in llm.SYSTEM


# Every line of a tool's model text is data the model may copy (Website, 28/11/2026: "giữ kết luận
# của mỗi mức…" and "không viết vòng nào tốt hơn…" reached the answer). No line holds an instruction,
# a rule number, a failure label code or a source line (answer-shape design, 28/11/2026).
_LABELS = ("CÁCH TRẢ LỜI", "HOW TO ANSWER", "QUY TẮC", "RULE:", "ĐÃ LÀM RỒI", "ALREADY DONE", "NOTE:", "PHƯƠNG ÁN",
           "OPTIONS FOR", "SỐ LIỆU VÀ NHẬN XÉT", "RELATED NUMBERS", "CÂU TRẢ LỜI THẲNG", "DIRECT ANSWER",
           "Ý CHÍNH CỦA VÒNG NÀY", "KEY POINT OF THIS ROUND", "mở đầu bằng câu này")  # fmt: skip
_INSTRUCTION = re.compile(r"giữ kết luận|keep each|không viết|never write|không nói|never say|never '|đừng|\bdo not\b|don't|"
                          r"mở đầu bằng|open with|trả lời đúng|answer (only|with)", re.I)  # fmt: skip
_FORBIDDEN = [re.compile(r"\bluật \d|\brule \d", re.I), re.compile(r"\bL-[A-Z]"), re.compile(r"Nguồn:|Source:")]
_ROW = re.compile(r"^[A-Z][A-Z0-9_]*( \| [^|=]+=[^|]*)*$")


def _assert_data_only(text: str, where: Any) -> int:
    n = 0
    for ln in str(text).splitlines():
        if not ln.strip():
            continue
        n += 1
        assert not any(lab in ln for lab in _LABELS), (where, ln)
        assert not _INSTRUCTION.search(ln), (where, ln)
        assert not any(rx.search(ln) for rx in _FORBIDDEN), (where, ln)
    return n


def test_no_fact_line_of_a_tool_holds_an_instruction(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    qs = ["Phân tích kết quả vòng này", "Run M đạt mốc ở những mức nào?", "Vì sao run C_70 hỏng nhiều ở bước đặt?",
          "Nên làm gì tiếp?", "Chi phí của vòng?", "So sánh các bản model", "Vòng 1 so với vòng đồ gá khác nhau thế nào?",
          "đặt cạnh bảng 60 rollout", "Chẩn đoán ra những nhóm lỗi nào?", "Which run is the best, and why?",
          "Run nào tốt nhất, vì sao?", "Which run is the best by loss?", "Giờ tôi nên làm gì để cải thiện kết quả này",
          "Thống kê các toàn bộ loại lỗi cho tôi xem nào?", "What should we do next?", "Kết quả thi lại của C70_R1 thế nào?"]  # fmt: skip
    seen = 0
    for tool in ("round_report", "round_diagnosis", "pair_comparisons", "rounds_side_by_side"):
        for rnd in ("r1", "jig-r1"):
            for lang in ("vi", "en"):
                for q in qs:
                    res = registry.call(tool, {}, {"task": "tray", "round": rnd, "lang": lang, "question": q})
                    assert res["ok"], (tool, rnd, lang, q, res["model"])
                    seen += _assert_data_only(res["model"], (tool, rnd, lang, q))
                    # every line is a labelled row; the doc references go apart
                    assert all(_ROW.match(ln) for ln in res["model"].splitlines() if ln), (tool, rnd, lang, q, res["model"])
                    assert isinstance(res.get("sources"), list), (tool, q)
                    if "C70_R1" not in q:
                        assert "C70_R1" not in res["model"] and "DA-50" not in res["model"], (tool, rnd, q)
                    ctx_line = tools_round.round_context("tray", rnd, q)
                    seen += _assert_data_only(ctx_line, ("round_context", rnd, q))
                    assert _ROW.match(ctx_line), ctx_line
    assert seen > 1000


# ------------------------------------------------------------------ "which run is best" (Website, 28/11)
BEST_QS = ["Which run is the best, and why?", "Run nào tốt nhất, vì sao?", "Xếp hạng các run", "Which run is better, C_70 or C_ALL?"]


def test_a_best_or_ranking_question_reads_the_test_results_never_the_loss(idx: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_rounds(idx)
    for q in BEST_QS:
        assert registry.forced_tools(q) == ["round_report"], q
        assert tools_round.focus_of(q) == "best", q
    assert registry.forced_tools("Which run has the lowest loss?") == []  # a loss lookup stays a lookup
    assert registry.forced_tools("C70_R1 có tốt hơn C_70 không?") == ["round_report"]
    assert ask("C70_R1 có tốt hơn C_70 không?", "r1")["answer"] == tools_round.WITHHELD[0]  # W5 unchanged
    tools, _ = _turn_tools(monkeypatch, "Which run is the best, and why?", "jig-r1")
    assert tools == ["round_report"]  # no run_list, no loss ranking
    assert "never rank runs or models by training loss" in llm.SYSTEM.lower()


def test_best_on_the_pair_round_gives_the_highest_count_and_no_winner(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    for lang in ("vi", "en"):
        t = ask(BEST_QS[0 if lang == "en" else 1], "r1", lang)["model"]
        lines = t.splitlines()
        # the results of the presented runs, highest first, then the reading: no winner when the
        # intervals overlap and no comparison fixed in advance is decisive (W3)
        assert lines[1].startswith("RESULT | run=C_70 | role=" + ("bản gốc" if lang == "vi" else "the baseline") + " | train_set=S70 | successes=10 | n=60")
        assert lines[2].startswith("RESULT | run=C_ALL")
        assert lines[3] == "READING | highest=C_70 | highest_successes=10 | n=60 | intervals_overlap=yes | decisive_comparisons=" + ("0 trên 1" if lang == "vi" else "0 of 1")
        assert "tốt nhất" not in t and "best" not in t
        assert "C70_R1" not in t and "successes=4 " not in t  # never in a ranking, not mentioned unasked
        assert "da34-" not in t and "c-70" not in t  # labels, not session ids
    loss = ask("Which run is the best by loss?", "r1", "en")["model"]
    assert "READING | result_measure=successful test runs | training_loss=not a measure of the result" in loss


def test_best_on_the_jig_round_is_sample_b(idx: ConsolePaths) -> None:
    """Sample B of the audit (05-danh-gia-chat-2811.md): the result of run M, the runs of the
    earlier round side by side with their scene and scorer, where M comes from, the limits."""
    _two_rounds(idx)
    res = ask("Run nào tốt nhất, vì sao?", "jig-r1")
    t = res["model"]
    assert t.splitlines() == [
        "ROUND | id=jig-r1 | title=Bê khay, Vòng đồ gá: run M | task=tray | scene=jig2 | scorer=bản 2 | run=M | checkpoint=100000 | n=180 | conditions=60 | repeats=3 | unit=điều kiện",
        "RESULT | run=M | scope=cả task | successes=136 | n=180 | rate=75,6 % | ci=70,0–81,1 | mark=80 % | verdict=chưa đạt | read_at=cận dưới CI",
        "PLACE_STEP | run=M | passed=161 | n=180 | rate=89,4 % | mark=50 % | verdict=chưa đọc: chưa có CI",
        "SIDE_BY_SIDE | run=M | round=jig-r1 | scene=có đồ gá jig2 | scorer=bản 2 | successes=136 | n=180 | rate=75,6 % | on_60_rollouts=47/60",
        "SIDE_BY_SIDE | run=C_70 | round=r1 | scene=không đồ gá | scorer=bản 1 | successes=10 | n=60 | rate=16,7 %",
        "SIDE_BY_SIDE | run=C_ALL | round=r1 | scene=không đồ gá | scorer=bản 1 | successes=5 | n=60 | rate=8,3 %",
        "READING | highest=M | latest=M | latest_round=jig-r1 | latest_date=26/11/2026 | runs_in_round=1",
        "ORIGIN | round=r1 | run=C_70 | carried_to_table_b=50 | placed_within_tolerance=10 | n=60",
        "ORIGIN_STEP | date=25/11/2026 | story=DA-46 | title=Bản cắt đoạn đặt | result=539 bản cắt",
        "ORIGIN_STEP | date=26/11/2026 | story=DA-48 | title=Train run M 100 000 bước",
        "LIMITS | comparable=no | with_round=r1 | why=khác cảnh, tập eval, bộ chấm",
        "LIMITS | control_run=chưa có run đối chứng K trên cùng tập điều kiện | effect=chưa tách được phần do đồ gá và phần do dữ liệu bước đặt",
    ]  # fmt: skip
    # the hidden run N / DA-50 and the held C70_R1 never appear; the docs go to sources
    assert "DA-50" not in t and "C70_R1" not in t and "tốt nhất" not in t
    assert res["sources"] == ["docs/he/tray-jig.md §2, §5", "docs/he/tray-jig.md §1", "docs/he/tray-jig.md §4"]
    en = ask("Which run is the best, and why?", "jig-r1", "en")["model"]
    assert "SIDE_BY_SIDE | run=C_70 | round=r1 | scene=no jig fixture | scorer=v1 | successes=10 | n=60 | rate=16.7%" in en
    assert "LIMITS | comparable=no | with_round=r1 | why=different scene, eval set, scorer" in en and "C70_R1" not in en


def test_sample_b_without_the_new_index_keys_falls_back_and_says_what_is_missing(idx: ConsolePaths) -> None:
    """The index before PR #266: no links, no timeline, no latest. The earlier round's carry and
    place come from the ladder of story.demo; the missing parts are named, never invented."""
    _two_rounds(idx)
    p = idx.index / "tasks.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    for r in m["rounds"]:
        r.pop("links", None)
    p.write_text(json.dumps(m), encoding="utf-8")
    s = json.loads((idx.index / "story.json").read_text(encoding="utf-8"))
    for k in ("timeline", "latest", "next_steps"):
        s.pop(k)
    (idx.index / "story.json").write_text(json.dumps(s), encoding="utf-8")
    t = ask("Run nào tốt nhất, vì sao?", "jig-r1")["model"]
    assert "ORIGIN | round=r1 | run=C_70 | carried_to_table_b=50 | placed_within_tolerance=10 | n=60" in t
    assert "ORIGIN_STEP | run=M | missing=diễn tiến của vòng (timeline)" in t
    assert "READING | highest=M | missing=kết quả mới nhất | runs_in_round=1" in t
    assert "LIMITS | comparable=no | with_round=r1 | why=khác cảnh, tập eval, bộ chấm" in t
    nxt = ask("Giờ tôi nên làm gì để cải thiện kết quả này", "jig-r1")["model"]
    assert "OPTION | missing=việc tiếp theo ghi trong tài liệu" in nxt
    r1 = ask("Phân tích kết quả vòng này", "r1")["model"]
    assert "NEXT_ROUND | round=jig-r1 | run=M | successes=136 | n=180 | rate=75,6 % | scene_differs=yes | scorer_differs=yes" in r1


def test_what_next_on_the_jig_round_is_sample_c(idx: ConsolePaths) -> None:
    """Sample C: where run M is still weak, then the next steps written in the docs only."""
    _two_rounds(idx)
    res = ask("Giờ tôi nên làm gì để cải thiện kết quả này", "jig-r1")
    assert res["model"].splitlines()[1:] == [
        "LEVEL | run=M | level=1 | successes=77 | n=90 | rate=85,6 % | mark=70 % | verdict=đạt",
        "WEAK | run=M | level=2 | successes=59 | n=90 | rate=65,6 % | mark=70 % | verdict=chưa đạt",
        "WEAK | run=M | failure=Đặt lệch | count=28 | of_failed=44 | ở_mức_2=20",
        "WEAK | run=M | scope=cả task | rate=75,6 % | ci_lower=70,0 % | mark=80 % | verdict=chưa đạt",
        "OPTION | text=Train run đối chứng K: 498 episode đầy đủ trên cùng cảnh, không có bản cắt.",
        "LIMITS | control_run=chưa có run đối chứng K trên cùng tập điều kiện | effect=chưa tách được phần do đồ gá và phần do dữ liệu bước đặt",
    ]  # fmt: skip
    assert "docs/he/tray-jig.md §1" in res["sources"]
    en = ask("What should we do next to improve this?", "jig-r1", "en")["model"]
    assert "OPTION | text=Train the control run K: 498 full episodes on the same scene, no cuts." in en
    assert "WEAK | run=M | failure=Misplaced | count=28 | of_failed=44 | at_level_2=20" in en
    # round 1: never the closed (DA-38) or handled (DA-37, by DA-42) work, in any shape
    for lang, q in (("vi", "Nên làm gì tiếp?"), ("vi", "Giờ tôi nên làm gì để cải thiện kết quả này"), ("en", "What should we do next?")):
        t = ask(q, "r1", lang)["model"]
        assert "DA-38" not in t and "DA-37" not in t and "OPTION" not in t, (q, t)
        assert "NEXT_ROUND | round=jig-r1 | run=M" in t

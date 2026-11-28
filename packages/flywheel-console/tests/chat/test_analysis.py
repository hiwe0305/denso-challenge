"""Analysis answers of the chat (audit 28/11/2026, A1-A15): the right round, its reading rules,
the held results, the guard, the provider key and the turn loop."""
# ruff: noqa: E501  (index fixtures and expected sentences stay on one line each)

from __future__ import annotations

import json
import os
from typing import Any

import pytest
from chat_index import make_idx  # noqa: F401
from flywheel.console.chat import llm, providers, registry, tools_round
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
                               {"id": "c6", "stage": "approach_a", "diagnosis": "ngưỡng bộ chấm", "intervention": "phiếu DA-37"}],
                  "chain": {"generated": 290, "recorded": 262, "quality": 204, "selected": 181}},
        "demo": {
            "ladder": {"standard_cm": "5", "runs": {"C_70": {"on_table_b": 50, "relaxed": {"7.5": 15}}}},
            "diagnose": {"to_data": ["c1"], "tickets": {"DA-37": ["c6"]},
                         "checks": [{"id": "H1", "value": {"clusters": ["c6"], "result": "unclear (scorer threshold)", "ticket": "DA-37"}}]},
            "round_cost": {"total_cu": 109.22, "total_usd": 10.91, "lines": [{"id": "train_1", "value": 8.55}]},
            "round1_reading": {"stop": {"value": {"stop": True}}},
        },
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
                       "place": {"p": 0.8944, "successes": 161, "n": 180, "ci": None}}],
            "outcomes": [{"run": "M", "relaxed": {"5.0": 136, "7.5": 145, "10.0": 150},
                          "repeats": [{"n": 60, "successes": 47}, {"n": 60, "successes": 47}, {"n": 60, "successes": 42}]}],
            "compare60": {"run": "M", "repeat": 0, "n": 60, "successes": 47,
                          "earlier": [{"run": "C_ALL", "n": 60, "successes": 5}, {"run": "C_70", "n": 60, "successes": 10},
                                      {"run": "C70_R1", "n": 60, "successes": 4}]},
        }  # fmt: skip
    tasks = {
        "tasks": [{"id": "tray", "name": {"vi": "Bê khay", "en": "Carry the tray"}, "rounds": ["r1", "jig-r1"]}],
        "rounds": [
            {"id": "r1", "task": "tray", "number": 1, "title": {"vi": "Vòng 1", "en": "Round 1"}, "doc": "docs/he/tray.md §20",
             "baseline": "C_70", "after_round": "C70_R1", "withhold_eval": ["C70_R1"],
             "runs": [{"id": "C_ALL", "role": "control", "train_set": "ALL"}, {"id": "C_70", "role": "baseline", "train_set": "S70"},
                      {"id": "C70_R1", "role": "after_round", "train_set": "R181"}],
             "index": ["story.pair", "story.round", "story.demo"]},
            {"id": "jig-r1", "task": "tray", "number": 2, "scene": "jig2", "title": {"vi": "Vòng đồ gá: run M", "en": "Jig round: run M"},
             "doc": "docs/he/tray-jig.md §2, §5", "baseline": "M", "runs": [{"id": "M", "role": "baseline", "train_set": "M"}],
             "rules": {"whole_task": 0.8, "per_level": 0.7, "place": 0.5}, "index": ["story.jig"]},
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
    # W6 / W1: the rule-1 sentence, read at the CI lower bound
    assert "cả task 75,6 % (136/180 lượt thành công), CI 70,0–81,1: chưa đạt mốc 80 %" in t
    assert "mức 1: 85,6 % (77/90), CI 78,9–92,2, đạt mốc 70 %" in t
    assert "mức 2: 65,6 % (59/90), CI 55,6–75,6, chưa đạt mốc 70 %" in t
    assert "chưa có CI nên chưa đọc theo mốc 50 %" in t  # no CI of the placing step in the index
    # rule 4 and rule 5, the limits, and the descriptive Wilson interval
    assert "M 47/60" in t and "chỉ đặt cạnh nhau" in t and "C_70 10/60" in t
    assert "luật 5" in t and "một seed train" in t and "chỉ để mô tả" in t
    # never the pair round's facts, and never the held run's figure from the 60-rollout table
    for other in ("109", "290", "DA-37", "C70_R1", "4/60", "vòng dừng"):
        assert other not in t, other
    en = ask("Analyse this round", "jig-r1", "en")["model"]
    assert "whole task 75.6% (136/180 successful runs), CI 70.0–81.1: below the 80% mark" in en


def test_a_round_without_its_numbers_fails_instead_of_borrowing(idx: ConsolePaths) -> None:
    _two_rounds(idx, jig=False)
    res = ask("Phân tích kết quả vòng này", "jig-r1")
    assert res["ok"] is False and "jig-r1" in res["model"] and "109" not in res["model"]


def test_the_question_picks_the_round(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    assert tools_round.round_named("So M với C_ALL trên 60 rollout", "r1") == "jig-r1"
    assert tools_round.round_named("Chi phí vòng 1 bao nhiêu?", "jig-r1") == "r1"
    assert tools_round.round_named("cost of r1", "jig-r1") == "r1"
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
    assert "Bản gốc C_70 có số lượt thành công cao nhất, 10/60, nhưng khoảng tin cậy của hai bản chồng nhau" in t
    assert "tốt nhất" not in t and "4/60" not in t
    allr = ask("Phân tích kết quả vòng này", "r1")["model"]
    assert "290 lượt sinh, 262 ghi được, 204 qua bộ lọc, chọn 181" in allr
    assert "vòng dừng" not in allr  # read from the held result: never shown (A11)
    assert "Kết quả thi lại của lượt này không trình bày ở bản demo." in allr
    cost = ask("Chi phí của vòng", "r1")["model"]
    assert "Train và serve của vòng: 109,22 CU thực đo" in cost and "chưa có trong index" in cost
    cmp_ = ask("khoảng tin cậy của các phép so sánh", "r1", tool="pair_comparisons")
    assert cmp_["round"] == "r1" and "C70_R1" not in cmp_["model"] and "CI chứa 0" in cmp_["model"]
    on_jig = ask("khoảng tin cậy", "jig-r1", tool="pair_comparisons")
    assert on_jig["round"] == "r1" and "không phải vòng đang chọn" in on_jig["model"]


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
    assert "c1: bước đặt, 14 lượt" in t and "H1 (c6): CHƯA RÕ (ngưỡng bộ chấm), thành phiếu DA-37" in t
    assert "Chi phí sinh và QA dữ liệu: chưa có trong index" in t
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
    t = ask("Lỗi hệ thống nào đã loại trừ?", "r1", tool="round_diagnosis")["model"]
    assert "c1: bước đặt, 14 lượt; chẩn đoán KỸ NĂNG YẾU 5/5; nhận dữ liệu" in t
    assert "c6:" in t and "thành phiếu DA-37" in t and "chuỗi bước gãy ở approach_a" in t
    assert "0 CU trên rtx3060, sinh 1,16 giờ, QA 0,67 giờ" in t and "§20.16 (seed/cited.yaml)" in t
    assert "Thu dữ liệu 0 CU (sinh và QA trên rtx3060" in ask("chi phí", "r1")["model"]
    jig = ask("chẩn đoán", "jig-r1", tool="round_diagnosis")["model"]
    assert "chưa có bước 4" in jig


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
    assert "chưa đạt mốc 80 %" in text and "L-PLACE-POSE" in text


def test_round_context_goes_into_the_system_prompt(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    msgs, _ = llm.build_messages(_body("Nhận xét vòng này", "jig-r1"), _body("x", "jig-r1")["context"])
    sys = msgs[0]["content"]
    assert "Selected round: jig-r1" in sys and "80%" in sys and "Name the round once at the start and the run next to each number" in sys
    msgs, _ = llm.build_messages(_body("x", "r1"), _body("x", "r1")["context"])
    assert "C70_R1" not in msgs[0]["content"] and "not presented" in msgs[0]["content"]


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
    assert t["round"] == "jig-r1" and "cả task 75,6 %" in t["model"] and "chỉ đặt cạnh nhau" in t["model"]


def test_the_60_rollout_table_is_shown_with_the_verdict(idx: ConsolePaths) -> None:
    _two_rounds(idx)
    q = "Phân tích kết quả run M: có đạt mốc 80% không, và đặt cạnh bảng 60 rollout thì thế nào?"
    assert not tools_round.asks_held(q)
    assert tools_round.focuses_of(q)[:2] == ["verdict", "compare"]
    t = ask(q, "jig-r1")["model"]
    assert "chưa đạt mốc 80 %" in t  # the verdict leads
    assert "M 47/60" in t and "C_70 10/60" in t and "chỉ đặt cạnh nhau" in t  # and the table follows
    assert "C70_R1" not in t and "4/60" not in t and WITHHELD_VI not in t


WITHHELD_VI = tools_round.WITHHELD[0]

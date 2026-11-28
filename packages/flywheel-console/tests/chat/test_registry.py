# ruff: noqa: E501  (expected rows stay on one line each)
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


def test_loop_proposals_reads_the_index_cluster_shape(idx: ConsolePaths) -> None:
    """Index clusters carry no n/budget; n is L1+L2 failures of the label (live bench b42)."""
    res = registry.call("loop_proposals", {}, {"route": "#/loop"})
    assert res["ok"], res
    assert "L-PLACE-POSE n=70" in res["model"]
    assert "targeted gen" in res["model"]


def test_qa_summary_cut_says_it_has_no_reasons(idx: ConsolePaths) -> None:
    """A cut's free-text qa note was read as a QA failure (live bench b47)."""
    res = registry.call("qa_summary", {"dataset_id": "S70"})
    assert "records no QA decisions or QA failure reasons of its own" in res["model"]
    assert "free text, not a failure count" in res["model"]


def test_analysis_question_offers_the_round_report_first(idx: ConsolePaths) -> None:
    assert registry.offered_names("data", "nhận xét kết quả vòng 1") == registry.ANALYSIS_TOOLS
    assert registry.offered_names("home", "what is here")[0] == "round_report"
    assert "round_report" not in registry.offered_names("runs", "loss của C_70")


def test_round_report_without_a_manifest_fails_cleanly(idx: ConsolePaths) -> None:
    res = registry.call("round_report", {}, {"route": "#/home", "task": "tray"})
    assert res["ok"] is False and "fw console index" in res["model"]


def _round_index(idx: ConsolePaths) -> None:
    """A two-model round in the index: a baseline and the model after the round."""
    import json

    run = {"n": 60, "failures": {"L-PLACE-POSE": 30, "L-TRAY-TILT": 9}}
    story = {
        "pair": {
            "best": "M_BASE",
            "runs": [{"run": "M_BASE", "successes": 12, **run},
                     {"run": "M_NEW", "successes": 6, **run}],
            "comparisons": [{"variant": "M_NEW", "baseline": "M_BASE", "n": 60, "variant_succ": 6,
                             "baseline_succ": 12, "ci": [-0.2, 0.03]}],
        },
        "round": {"clusters": [{"id": "c1", "stage": "place", "n": 14}, {"id": "c4", "stage": "x"}],
                  "chain": {"generated": 200, "selected": 100}},
        "demo": {
            "ladder": {"standard_cm": "5", "runs": {
                "M_BASE": {"on_table_b": 50, "relaxed": {"7.5": 15}},
                "M_NEW": {"on_table_b": 48, "relaxed": {"7.5": 16}}}},
            "diagnose": {"to_data": ["c1"], "tickets": {"T-1": ["c4"]}},
            "round_cost": {"total_cu": 50.0, "total_usd": 5.0},
        },
    }  # fmt: skip
    tasks = {
        "tasks": [
            {"id": "box", "name": {"vi": "Bê hộp", "en": "Carry the box"}, "rounds": ["box-r1"],
             "stages": [{"id": "place", "vi": "đặt", "en": "place"}]},
            {"id": "new", "name": {"vi": "Task mới", "en": "New task"}, "rounds": [], "index": [],
             "evals": [{"label": {"vi": "bản của tác giả", "en": "authors"},
                        "n": 10, "successes": 6}],
             "process": {"1": {"needs": ["catalog"]}, "3": {"needs": ["story.runs"]}}},
        ],
        "rounds": [{"id": "box-r1", "task": "box", "title": {"vi": "Vòng 1", "en": "Round 1"},
                    "baseline": "M_BASE", "after_round": "M_NEW",
                    "runs": [{"id": "M_BASE", "role": "baseline", "train_set": "A"},
                             {"id": "M_NEW", "role": "after_round", "train_set": "B"}]}],
    }  # fmt: skip
    (idx.index / "story.json").write_text(json.dumps(story), encoding="utf-8")
    (idx.index / "tasks.json").write_text(json.dumps(tasks), encoding="utf-8")


def test_round_report_writes_the_round_in_the_language_asked(idx: ConsolePaths) -> None:
    _round_index(idx)
    ctx = {"route": "#/home", "task": "box", "lang": "vi", "question": "nhận xét vòng này"}
    vi = registry.call("round_report", {}, ctx)
    assert vi["ok"]
    t = vi["model"]
    # roles in plain words, counts from the index, the near-miss counts (15-12 -> 16-6) computed
    assert (
        "RESULT | run=M_BASE | role=bản gốc | train_set=A | successes=12 | n=60 | rate=20,0 %" in t
    )
    assert (
        "RESULT | run=M_NEW | role=bản sau vòng | train_set=B | successes=6 | n=60 | rate=10,0 %"
        in t
    )
    assert "NEAR_MISS | band=ngoài 5 cm, trong 7,5 cm | before=3 | after=10" in t
    assert (
        "BEFORE_AFTER | diff_runs=-6 | n=60 | ci_pts=-20,0 → +3,0 | ci_includes_0=yes" in t
        and "TICKET | id=T-1" in t
    )
    assert (
        "COST | scope=train và serve | total_cu=50,00 | kind=thực đo" in t
        and "ĐÃ LÀM RỒI" not in t
        and " đạt 12" not in t
    )
    assert vi["round"] == "box-r1"  # the numbers are tagged with their round (A2)
    en = registry.call("round_report", {}, {**ctx, "lang": "en", "question": "comment"})["model"]
    assert (
        "RESULT | run=M_BASE | role=the baseline | train_set=A | successes=12 | n=60 | rate=20.0%"
        in en
        and "before=3 | after=10" in en
    )
    assert "bản gốc" not in en


def test_round_report_opens_with_what_the_question_asks(idx: ConsolePaths) -> None:
    _round_index(idx)

    def first(q: str) -> str:
        ctx = {"task": "box", "lang": "vi", "question": q}
        return registry.call("round_report", {}, ctx)["model"].split("\n")[1]  # the row after ROUND

    # W3: no "best", the results highest first, then the reading
    assert first("bản nào tốt nhất?").startswith(
        "RESULT | run=M_BASE | role=bản gốc | train_set=A | successes=12 | n=60"
    )
    best = registry.call(
        "round_report", {}, {"task": "box", "lang": "vi", "question": "bản nào tốt nhất?"}
    )["model"]
    assert (
        "READING | highest=M_BASE | highest_successes=12 | n=60 | decisive_comparisons=0 trên 1"
        in best
        and "tốt nhất" not in best
    )
    dom = "MOST_COMMON_FAILURE | run=M_BASE | role=bản gốc | failure=Đặt lệch | count=30 | of_failed=48"
    assert first("robot hỏng ở đâu?").startswith(dom) and "L-PLACE-POSE" not in first(
        "robot hỏng ở đâu?"
    )
    assert first("vì sao kết quả chưa tốt lên?").startswith("BEFORE_AFTER | diff_runs=-6")
    assert (
        first("vòng này tốn bao nhiêu?")
        == "COST | scope=train và serve | total_cu=50,00 | kind=thực đo | usd=5,00"
    )
    cost = registry.call("round_report", {}, {"task": "box", "lang": "vi", "question": "chi phí"})
    # N5: collecting the data apart from training; no cost per kept demonstration
    assert "missing=chưa có trong index" in cost["model"] and "CU cho mỗi bài" not in cost["model"]
    assert "OPTION" not in cost["model"]  # no next steps


def test_ego_summary_and_its_offer(idx: ConsolePaths) -> None:
    assert registry.offered_names("data", "bao nhiêu clip egocentric bị loại?")[0] == "ego_summary"
    assert registry.call("ego_summary", {}, {"lang": "vi"})["ok"] is False  # no h1m in this index


def test_round_report_for_a_task_without_a_round(idx: ConsolePaths) -> None:
    _round_index(idx)
    # the task is named in the question; free text the model passes as "task" is ignored
    ctx = {"lang": "vi", "task": "box", "question": "Task mới đang ở đâu, thiếu gì?"}
    t = registry.call("round_report", {"task": "cái task mới ấy"}, ctx)["model"]
    assert (
        "TASK | id=new | name=Task mới | rounds=0" in t and "failure_to_data_round=chưa chạy" in t
    )
    assert (
        "EVAL | label=bản của tác giả | model=của tác giả | successes=6 | n=10 | rate=60,0 %" in t
        and "STAGES | without_result=3 dạy model" in t
    )
    assert "M_BASE" not in t  # never another task's numbers


def test_forced_lookup_only_for_whole_round_questions(idx: ConsolePaths) -> None:
    f = registry.forced_tool
    assert f("Nhận xét kết quả của vòng này") == "round_report"
    assert f("Vòng này tốn bao nhiêu?") == "round_report"
    assert f("Trong kho có bao nhiêu clip egocentric đã xuất?") == "ego_summary"
    # a named dataset or policy, or a list request, stays a lookup the model chooses
    lookups = [
        "Liệt kê các dataset egocentric",
        "Tóm tắt QA của tập src_158ec3c8",
        "Policy C đánh giá ra sao?",
        "eval C hỏng nhiều nhất ở bước nào",
        "Chi phí ước tính và thực đo theo từng story là bao nhiêu?",
        "loss của C_70",
    ]
    for q in lookups:
        assert f(q) is None, q


def test_round_report_covers_steps_comparison_and_diagnosis(idx: ConsolePaths) -> None:
    _round_index(idx)

    def ask(q: str) -> str:
        assert registry.forced_tool(q) == "round_report", q
        return registry.call("round_report", {}, {"task": "box", "lang": "vi", "question": q})[
            "model"
        ]

    assert (
        ask("So sánh các bản model")
        .split("\n")[1]
        .startswith("RESULT | run=M_BASE | role=bản gốc | train_set=A | successes=12 | n=60")
    )
    assert "COMPARISONS | fixed_in_advance=1 | decisive=0 | all_ci_include_0=yes" in ask(
        "So sánh các bản model"
    )
    diag = "DIAGNOSIS | run=M_BASE | groups=2 | to_data=1 | to_tickets=1 | tickets=T-1"
    assert diag in ask("Chẩn đoán ra những nhóm lỗi nào?")
    assert "OPTION" not in ask("So sánh các bản model")


def test_withheld_result_is_never_given_to_the_model(idx: ConsolePaths) -> None:
    """Round with ``withhold_eval``: the run's test result leaves every answer of the chat."""
    import json

    _round_index(idx)
    p = idx.index / "tasks.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    m["rounds"][0]["withhold_eval"] = ["M_NEW"]
    p.write_text(json.dumps(m), encoding="utf-8")
    qs = ["nhận xét vòng này", "vì sao kết quả chưa tốt lên?", "M_NEW thi được bao nhiêu?"]
    qs += ["bản sau vòng đạt bao nhiêu lượt?", "so sánh các bản model", "nên làm gì tiếp?"]
    for q in qs:
        assert registry.forced_tool(q) == "round_report", q
        t = registry.call("round_report", {}, {"task": "box", "lang": "vi", "question": q})["model"]
        assert "6/60" not in t and "M_NEW" not in t and "tăng từ" not in t, (q, t)
    ctx = {"task": "box", "lang": "vi", "question": "M_NEW thi được bao nhiêu?"}
    held = registry.call("round_report", {}, ctx)
    # W5: one sentence, written by the code, no number of the round at all
    assert held["answer"] == "Kết quả thi lại của lượt này không trình bày ở bản demo."
    assert "12/60" not in held["model"]
    assert registry.forced_tool("loss của M_NEW") is None  # its training is still a normal lookup


def test_hidden_run_is_not_resolved_or_reported(idx: ConsolePaths) -> None:
    """``withhold_runs`` (run N, Hiếu 28/11/2026): the chat answers as for an unknown run."""
    import json

    from flywheel.console.chat import common
    from flywheel.console.chat.resolve import resolve_run, run_index

    for folder, loss in (("tray/jig-m/da48-ft-m-s0", 0.11), ("tray/jig-n/da50-ft-n-s0", 0.0987)):
        d = idx.fw_root / folder
        d.mkdir(parents=True)
        rows = [{"split": "train", "step": s, "loss": loss} for s in (0, 100_000)]
        (d / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    assert [r["branch"] for r in run_index() if r["dir"].parent.name.startswith("jig-")] == ["M"]
    assert resolve_run("N")[0] == "none" and resolve_run("da50-ft-n-s0")[0] == "none"
    assert resolve_run("M") == ("ok", "da48-ft-m-s0")
    ctx = {"lang": "vi", "question": "loss của run N"}
    for name, args in (("run_metrics", {"run": "N"}), ("run_compare", {"run_ids": ["M", "N"]}),
                       ("run_metrics", {"run": "da50-ft-n-s0"})):  # fmt: skip
        r = registry.call(name, args, ctx)
        assert not r["ok"] and "0.0987" not in r["model"], (name, r)
    listed = registry.call("run_list", {}, ctx)["model"]
    assert "da50" not in listed and "0.0987" not in listed and "da48-ft-m-s0" in listed
    # a story.json indexed before the switch: the chat's single loader cleans it
    cut = {"name": "N", "source": "fwdata/tray/jig-n/N.tar.json"}
    stale = {"jig": {"runs": [{"run": "M", "successes": 136}, {"run": "N", "successes": 124}],
                     "best": "M", "next_cut": cut},
             "runs": [{"branch": "N", "job": "da50-ft-n-s0"}]}  # fmt: skip
    (idx.index / "story.json").write_text(json.dumps(stale), encoding="utf-8")
    text = json.dumps(common.story())
    assert "124" not in text and "da50" not in text and "jig-n" not in text

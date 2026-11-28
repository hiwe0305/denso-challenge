"""Latest round and project progression (audit 05 · Đánh giá chat, decision of Hiếu 28/11/2026
evening): default round, links between rounds, timeline, latest, next steps, historical
tickets and the failure table, and that none of them carries run N or C70_R1's test result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from flywheel.console.index import hidden, tasks, timeline
from flywheel.console.paths import ConsolePaths

REPO = Path(__file__).resolve().parents[4]
FORBIDDEN = ("DA-50", "da50", "jig-n", "run N", "C70_R1")


def _real() -> ConsolePaths:
    return ConsolePaths(repo=REPO, fw_root=REPO / "fwdata")


def _pair() -> dict[str, Any]:
    def run(name: str, ok: int, fails: dict[str, int]) -> dict[str, Any]:
        return {"run": name, "n": 60, "successes": ok, "failures": fails}

    return {"runs": [
        run("C_ALL", 5, {"L-PLACE-POSE": 29, "L-TRAY-TILT": 15, "L-TIMEOUT": 7,
                         "L-PART-DROP": 2, "L-ONE-HAND": 2}),
        run("C_70", 10, {"L-TIMEOUT": 7, "L-PLACE-POSE": 32, "L-TRAY-TILT": 10, "L-PART-DROP": 1}),
        run("B_ALL", 6, {"L-PLACE-POSE": 25, "L-TRAY-TILT": 17, "L-PART-DROP": 6, "L-TIMEOUT": 5,
                         "L-ONE-HAND": 1}),
        run("B_70", 7, {"L-PLACE-POSE": 25, "L-TRAY-TILT": 21, "L-TIMEOUT": 4, "L-ONE-HAND": 2,
                        "L-PART-DROP": 1}),
        run("C70_R1", 4, {"L-PLACE-POSE": 30}),
    ]}  # fmt: skip


def _jig(status: str = "ready") -> dict[str, Any]:
    head = {"n": 180, "successes": 136, "failures": {"L-PLACE-POSE": 28, "L-TRAY-TILT": 13,
            "L-TIMEOUT": 1, "L-PART-DROP": 1, "L-ONE-HAND": 1}}  # fmt: skip
    return {"evals": [{"run": "M", "role": "baseline", "status": status, "headline": head}]}


def _story(status: str = "ready") -> dict[str, Any]:
    ladder = {"runs": {"C_70": {"on_table_b": 50, "success": 10}}}
    return {"pair": _pair(), "jig": _jig(status), "demo": {"ladder": ladder}}


# ------------------------------------------------------------------ A. default round
def test_default_round_is_the_jig_round_and_rounds_stay_in_time_order() -> None:
    m = tasks.load(_real())
    t = m.task("tray")
    assert t.rounds == ("tray-r1", "tray-jig-r1")
    assert t.raw["default_round"] == "tray-jig-r1"
    assert m.round("tray-r1").scorer_version == 1 and m.round("tray-jig-r1").scorer_version == 2


def test_default_round_must_be_one_of_the_task_rounds() -> None:
    import yaml

    data = yaml.safe_load((_real().seed / tasks.FILE).read_text(encoding="utf-8"))
    data["tasks"][0]["default_round"] = "tray-r9"
    with pytest.raises(tasks.ManifestError, match="default_round"):
        tasks.parse(data)


# ------------------------------------------------------------------ B. links
def test_links_join_the_two_rounds_both_ways_with_numbers_from_the_index() -> None:
    m = tasks.load(_real())
    links = tasks._links(m, _story())
    r1, jig = links["tray-r1"], links["tray-jig-r1"]
    assert r1["prev"] is None and jig["next"] is None
    assert r1["next"] == {"round": "tray-jig-r1", "run": "M", "successes": 136, "n": 180,
                          "scene_differs": True, "scorer_differs": True}  # fmt: skip
    assert jig["prev"] == {"round": "tray-r1", "run": "C_70", "successes": 10, "n": 60,
                           "scene_differs": True, "scorer_differs": True,
                           "carried": 50, "placed": 10}  # fmt: skip
    # no presented eval yet: the link names the round's baseline without numbers
    assert tasks._links(m, _story("missing"))["tray-r1"]["next"]["successes"] is None


# ------------------------------------------------------------------ C, E. seed
def test_timeline_seed_quotes_its_docs_and_every_number() -> None:
    assert timeline.verify(_real()) == []


def test_numbers_are_normalised_and_names_are_not_numbers() -> None:
    got = timeline.numbers("100 000 / 100 000, 1 037 episode, 56,15 CU; C_70 jig2 60k ±10 ≤ 3")
    assert got == {"100000", "1037", "56.15", "10", "3"}


def test_verify_reports_an_unquoted_number_and_a_missing_quote(tmp_path: Path) -> None:
    class P(ConsolePaths):
        @property
        def seed(self) -> Path:
            return tmp_path / "seed"

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("Run X: 12 of 30.\n", encoding="utf-8")
    (tmp_path / "seed").mkdir()
    entry = {"date": "2026-11-20", "story": "DA-1", "round": None,
             "title": {"vi": "t", "en": "t"},
             "result": {"vi": "12 trên 31", "en": "12 of 30"},
             "sources": [{"doc": "docs/a.md", "section": "1", "quote": "Run X: 12 of 30."},
                         {"doc": "docs/a.md", "section": "1", "quote": "not there"}]}  # fmt: skip
    (tmp_path / "seed" / timeline.FILE).write_text(json.dumps({"timeline": [entry]}))
    bad = timeline.verify(P(repo=tmp_path, fw_root=tmp_path / "fw"))
    assert any("quote not in" in b for b in bad)
    assert any("['31'] are in no quote" in b for b in bad)
    assert any("vi numbers" in b for b in bad)


def test_timeline_is_presentable_work_from_round_1_to_run_m() -> None:
    events = timeline.timeline(_real())
    assert [e["story"] for e in events] == ["DA-34", "DA-42", "DA-41", "DA-46", "DA-48", "DA-47"]
    assert events == sorted(events, key=lambda e: e["date"])
    assert all(e["doc"].startswith("docs/") and "§" in e["doc"] for e in events)
    assert events[-1]["result"]["vi"].startswith("136/180")
    steps = timeline.next_steps(_real())
    assert (
        len(steps) == 1 and "498" in steps[0]["text"]["vi"] and steps[0]["round"] == "tray-jig-r1"
    )
    text = json.dumps({"t": events, "s": steps}, ensure_ascii=False)
    for word in FORBIDDEN:
        assert word not in text, word


# ------------------------------------------------------------------ D. latest
def test_latest_is_the_newest_round_with_a_presented_baseline() -> None:
    m = tasks.load(_real())
    events = timeline.timeline(_real())
    shown = timeline.presented(m, _pair(), _jig())
    assert timeline.latest(m, shown, events) == {"round": "tray-jig-r1", "run": "M",
                                                 "date": "2026-11-26"}  # fmt: skip
    shown = timeline.presented(m, _pair(), _jig("missing"))
    assert timeline.latest(m, shown, events) == {"round": "tray-r1", "run": "C_70",
                                                 "date": "2026-11-12"}  # fmt: skip


# ------------------------------------------------------------------ E. historical tickets
def test_round_1_tickets_are_historical() -> None:
    known = timeline.tickets(_real())
    assert known["DA-38"]["closed"] == "2026-11-06"
    assert known["DA-37"]["closed"] is None and known["DA-37"]["handled_by"] == "DA-42"
    items = [{"id": "c4", "intervention": "phiếu DA-38"}, {"id": "H1", "ticket": "DA-37"},
             {"id": "c1", "intervention": "sinh quanh lỗi"},
             {"key": "x", "value": {"ticket": "DA-38"}}]  # fmt: skip
    out = timeline.mark_historical(items, known)
    assert out[0]["historical"] is True and out[0]["closed"] == "2026-11-06"
    assert out[1]["historical"] is True and out[1]["handled_by"] == "DA-42"
    assert "historical" not in out[2] and out[3]["historical"] is True


# ------------------------------------------------------------------ F. failure table
def test_failure_table_matches_the_eval_page_and_leaves_c70r1_out() -> None:
    m = tasks.load(_real())
    t = timeline.failure_table(m, _pair(), _jig())
    r1 = t["tray-r1"]
    assert r1["scorer_version"] == 1 and list(r1["runs"]) == ["C_ALL", "C_70", "B_ALL", "B_70"]
    sums = {k: (sum(v["labels"].values()), v["failed"], v["n"]) for k, v in r1["runs"].items()}
    assert sums == {"C_ALL": (55, 55, 60), "C_70": (50, 50, 60), "B_ALL": (54, 54, 60),
                    "B_70": (53, 53, 60)}  # fmt: skip
    assert list(r1["runs"]["C_70"]["labels"]) == ["L-PLACE-POSE", "L-TRAY-TILT", "L-TIMEOUT",
                                                  "L-PART-DROP"]  # fmt: skip
    m_row = t["tray-jig-r1"]
    assert m_row["scorer_version"] == 2 and m_row["runs"]["M"]["failed"] == 44
    assert sum(m_row["runs"]["M"]["labels"].values()) == 44 and m_row["runs"]["M"]["n"] == 180
    assert "tray-jig-r1" not in timeline.failure_table(m, _pair(), _jig("missing"))


# ------------------------------------------------------------------ hidden filtering
def test_hidden_story_drops_run_n_from_timeline_latest_steps_and_table() -> None:
    h = hidden.from_manifest(tasks.load(_real()))
    doc = {
        "timeline": [
            {"date": "2026-11-26", "story": "DA-47", "title": {"vi": "Eval run M"}},
            {"date": "2026-11-28", "story": "DA-50", "title": {"vi": "Train"}},
            {"date": "2026-11-28", "story": "DA-49", "title": {"vi": "So run N với M"}},
            {"date": "2026-11-28", "story": "DA-49", "title": {"vi": "phiên da50-n-serve"}},
            {"date": "2026-11-28", "story": "DA-49", "result": {"en": "see DA-50 notes"}},
        ],
        "next_steps": [{"text": {"vi": "Train K"}}, {"text": {"vi": "Đọc lại run N"}}],
        "latest": {"round": "tray-jig-r1", "run": "N", "date": "2026-11-28"},
        "failure_table": {"tray-jig-r1": {"scorer_version": 2,
                                          "runs": {"M": {"failed": 44}, "N": {"failed": 50}}}},
    }  # fmt: skip
    out = hidden.story(doc, h)
    assert [e["story"] for e in out["timeline"]] == ["DA-47"]
    assert out["next_steps"] == [{"text": {"vi": "Train K"}}]
    assert out["latest"] is None
    assert list(out["failure_table"]["tray-jig-r1"]["runs"]) == ["M"]


def test_hidden_tasks_doc_drops_a_link_to_run_n() -> None:
    h = hidden.from_manifest(tasks.load(_real()))
    link_m = {"round": "tray-jig-r1", "run": "M", "successes": 136, "n": 180}
    doc = {"rounds": [
        {"id": "tray-r1", "links": {"prev": None, "next": link_m}},
        {"id": "tray-jig-r1", "links": {"prev": None, "next": {"round": "x", "run": "N"}}},
    ]}  # fmt: skip
    out = hidden.tasks_doc(doc, h)
    assert out["rounds"][0]["links"]["next"] == link_m
    assert out["rounds"][1]["links"]["next"] is None

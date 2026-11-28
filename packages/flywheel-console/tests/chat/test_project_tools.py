# ruff: noqa: E501  (index fixtures stay on one line per entry)
"""failure_table, train_progress, project_status: data rows only, holds kept (design 28/11/2026)."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from chat_index import make_idx  # noqa: F401
from flywheel.console.chat import tools_project as tp
from flywheel.console.paths import ConsolePaths


def _loss(start: float, end: float, top: int = 60000, n: int = 41) -> list[list[float]]:
    """A falling curve from ``start`` towards ``end`` over ``n`` logged points."""
    return [[round(i * top / (n - 1)), end + (start - end) / (1 + i)] for i in range(n)]


def _train(
    job: str, branch: str, max_steps: int = 60000, sps: float = 2.585, flat: bool = False
) -> dict[str, Any]:
    loss = (
        [[round(i * max_steps / 40), 0.3] for i in range(41)]
        if flat
        else _loss(49.2, 0.05, max_steps)
    )
    loss[0][1] = 49.2
    return {
        "job": job,
        "branch": branch,
        "step": max_steps - 1,
        "ckpt_step": max_steps,
        "max_steps": max_steps,
        "steps_per_s": sps,
        "loss": loss,
        "val": [[0, 45.0], [max_steps - 1, 0.2]],
        "vm_phases": {f"setup_tray_{branch.lower()}": 119.3, "train": 38049.2, "persist": 213.4},
    }


def _write(idx: ConsolePaths, full: bool) -> None:
    """Two rounds like the real index: tray-r1 (pair, C70_R1 held) and tray-jig-r1 (run M; run N
    hidden by the seed). ``full`` adds the new keys of the index contract (design §2)."""
    m_train = {
        **_train("da48-ft-m-s0", "M", 100000, 1.441),
        "vm_phases": {"setup_tray_m": 118.9, "train": 30416.8, "persist": 549.0},
    }
    story: dict[str, Any] = {
        "runs": [
            _train("da34-t6-ft-c-all-s0", "C_ALL"),
            _train("da34-t6-ft-c-70-s0", "C_70"),
            _train("da34-t7-ft-c70-r1-s0", "C70_R1", flat=True),
            _train("da50-ft-n-s0", "N"),
        ],
        "pair": {
            "runs": [
                {
                    "run": "C_ALL",
                    "n": 60,
                    "successes": 5,
                    "failures": {
                        "L-PLACE-POSE": 29,
                        "L-TRAY-TILT": 15,
                        "L-TIMEOUT": 7,
                        "L-ONE-HAND": 2,
                        "L-PART-DROP": 2,
                    },
                },
                {
                    "run": "C_70",
                    "n": 60,
                    "successes": 10,
                    "failures": {
                        "L-PLACE-POSE": 32,
                        "L-TRAY-TILT": 10,
                        "L-TIMEOUT": 7,
                        "L-PART-DROP": 1,
                    },
                },
                {
                    "run": "C70_R1",
                    "n": 60,
                    "successes": 4,
                    "failures": {
                        "L-PLACE-POSE": 28,
                        "L-TRAY-TILT": 15,
                        "L-TIMEOUT": 8,
                        "L-ONE-HAND": 4,
                        "L-PART-DROP": 1,
                    },
                },
            ]
        },
        "demo": {
            "round_cost": {
                "kind": "measured",
                "total_cu": 109.22,
                "lines": [
                    {"id": "train_1", "value": 8.55, "source": "docs/he/tray.md §20.18"},
                    {"id": "train_2", "value": 77.27, "source": "docs/he/tray.md §20.18"},
                    {"id": "serve", "value": 23.4, "source": "docs/he/tray.md §20.18"},
                ],
            }
        },
        "jig": {
            "round": "tray-jig-r1",
            "scene": "jig2",
            "scorer_version": 2,
            "doc": "docs/he/tray-jig.md §2, §5",
            "runs": [m_train, _train("da50-ft-n-s0", "N", 100000, 1.33)],
            "evals": [
                {
                    "run": "M",
                    "role": "baseline",
                    "status": "ready",
                    "headline": {
                        "n": 180,
                        "successes": 136,
                        "p": 0.7556,
                        "failures": {
                            "L-PLACE-POSE": 28,
                            "L-TRAY-TILT": 13,
                            "L-TIMEOUT": 1,
                            "L-PART-DROP": 1,
                            "L-ONE-HAND": 1,
                        },
                    },
                    "place": {"p": 0.8944, "successes": 161, "n": 180},
                },
                {
                    "run": "N",
                    "role": "after_round",
                    "status": "ready",
                    "headline": {
                        "n": 180,
                        "successes": 120,
                        "p": 0.6667,
                        "failures": {"L-PLACE-POSE": 40},
                    },
                },
            ],
            "cost": {
                "train": {
                    "story": "DA-48",
                    "cu": 56.15,
                    "measure_kind": "measured",
                    "source": "docs/g0/ledger/DA-48.csv",
                },
                "eval": {"story": "DA-47", "cu": 6.8, "measure_kind": "measured"},
                "total_cu": 62.95,
            },
        },
    }
    rounds: list[dict[str, Any]] = [
        {
            "id": "tray-r1",
            "task": "tray",
            "number": 1,
            "title": {"vi": "Vòng 1", "en": "Round 1"},
            "doc": "docs/he/tray.md §19, §20",
            "baseline": "C_70",
            "after_round": "C70_R1",
            "withhold_eval": ["C70_R1"],
            "max_steps": 60000,
            "runs": [
                {"id": "C_ALL", "role": "control"},
                {"id": "C70_R1", "role": "after_round"},
                {"id": "C_70", "role": "baseline"},
            ],
            "index": ["story.pair", "story.runs", "story.demo"],
        },
        {
            "id": "tray-jig-r1",
            "task": "tray",
            "number": 2,
            "scene": "jig2",
            "scorer_version": 2,
            "max_steps": 100000,
            "title": {"vi": "Vòng đồ gá: run M", "en": "Jig round: run M"},
            "doc": "docs/he/tray-jig.md §2, §5",
            "runs": [{"id": "M", "role": "baseline"}, {"id": "N", "role": "after_round"}],
            "index": ["story.jig"],
        },
    ]
    task: dict[str, Any] = {
        "id": "tray",
        "name": {"vi": "Bê khay", "en": "Carry the tray"},
        "rounds": ["tray-r1", "tray-jig-r1"],
    }
    if full:
        story["failure_table"] = {
            "tray-r1": {
                "scorer_version": 1,
                "runs": {
                    "C_ALL": {
                        "labels": {"L-PLACE-POSE": 29, "L-TRAY-TILT": 15},
                        "failed": 55,
                        "n": 60,
                    },
                    "C_70": {
                        "labels": {"L-PLACE-POSE": 32, "L-TRAY-TILT": 10, "L-ONE-HAND": 3},
                        "failed": 50,
                        "n": 60,
                    },
                    "C70_R1": {"labels": {"L-PLACE-POSE": 28}, "failed": 56, "n": 60},
                },
            },
            "tray-jig-r1": {
                "scorer_version": 2,
                "runs": {
                    "M": {
                        "labels": {"L-PLACE-POSE": 28, "L-TRAY-TILT": 13},
                        "failed": 44,
                        "n": 180,
                    },
                    "N": {"labels": {"L-PLACE-POSE": 40}, "failed": 60, "n": 180},
                },
            },
        }
        story["timeline"] = [
            {
                "date": "2026-11-26",
                "story": "DA-47",
                "title": {"vi": "Eval run M", "en": "Run M eval"},
                "result": {"vi": "136/180 (75,6 %)", "en": "136/180 (75.6%)"},
                "doc": "docs/he/tray-jig.md §5",
                "round": "tray-jig-r1",
            },
            {
                "date": "2026-11-19",
                "story": "DA-41",
                "title": {"vi": "Cảnh đồ gá jig2", "en": "Jig scene jig2"},
                "result": None,
                "doc": "docs/g0/tray/jig.md",
                "round": "tray-jig-r1",
            },
            {
                "date": "2026-11-28",
                "story": "DA-50",
                "title": {"vi": "Train run khác", "en": "Another run"},
                "result": None,
                "doc": "docs/he/tray-jig.md §7",
                "round": "tray-jig-r1",
            },
            {
                "date": "2026-11-20",
                "story": "DA-34",
                "title": {"vi": "Thi lại C70_R1", "en": "C70_R1 retest"},
                "result": {"vi": "4/60", "en": "4/60"},
                "doc": "docs/he/tray.md §20",
                "round": "tray-r1",
            },
        ]
        story["latest"] = {"round": "tray-jig-r1", "run": "M", "date": "2026-11-26"}
        story["next_steps"] = [
            {
                "text": {
                    "vi": "Train run đối chứng K trên cùng cảnh",
                    "en": "Train control run K on the same scene",
                },
                "doc": "docs/he/tray-jig.md §1",
                "round": "tray-jig-r1",
            },
            {
                "text": {"vi": "Đóng phiếu DA-38", "en": "Close ticket DA-38"},
                "doc": "docs/he/tray.md §20.16",
                "round": "tray-r1",
                "historical": True,
            },
        ]
        task["default_round"] = "tray-jig-r1"
        rounds[0]["links"] = {
            "next": {
                "round": "tray-jig-r1",
                "run": "M",
                "successes": 136,
                "n": 180,
                "scene_differs": True,
                "scorer_differs": True,
            }
        }
        rounds[1]["links"] = {
            "prev": {
                "round": "tray-r1",
                "run": "C_70",
                "successes": 10,
                "n": 60,
                "carried": 50,
                "placed": 10,
                "scene_differs": True,
                "scorer_differs": True,
            }
        }
    (idx.index / "story.json").write_text(json.dumps(story), encoding="utf-8")
    (idx.index / "tasks.json").write_text(
        json.dumps({"tasks": [task], "rounds": rounds}), encoding="utf-8"
    )


def ask(
    fn: Any, q: str = "", rnd: str = "tray-r1", lang: str = "vi", **args: Any
) -> dict[str, Any]:
    return dict(fn(args, {"task": "tray", "round": rnd, "lang": lang, "question": q}))


ROW_RX = re.compile(r"^[A-Z_]+( \| [\w.-]+=[^|]*)+$")
FORBIDDEN = ("CÁCH TRẢ LỜI", "HOW TO ANSWER", "QUY TẮC", "RULE", "CÂU TRẢ LỜI THẲNG", "DIRECT ANSWER", "NOTE:",
             "ĐÃ LÀM RỒI", "Nguồn", "Source:", "luật", "rule ", "da34-", "da48-", "da50", "DA-50", "DA-38")  # fmt: skip


def _check_contract(res: dict[str, Any]) -> None:
    assert res["ok"], res["model"]
    lines = res["model"].splitlines()
    assert lines and all(ROW_RX.match(ln) for ln in lines), lines
    for w in FORBIDDEN:
        assert w not in res["model"], w
    assert not re.search(r"\bL-[A-Z]", res["model"])  # no failure label code
    assert "| N=" not in res["model"] and "run=N" not in res["model"]  # hidden run N
    assert res["ui"]["type"] == "table" and res["ui"]["columns"]
    assert res["sources"] and all(isinstance(s, str) and s for s in res["sources"])


@pytest.mark.parametrize("full", [True, False])
@pytest.mark.parametrize("lang", ["vi", "en"])
@pytest.mark.parametrize("name", ["failure_table", "train_progress", "project_status"])
def test_every_tool_returns_labelled_data_rows(
    idx: ConsolePaths, full: bool, lang: str, name: str
) -> None:
    _write(idx, full)
    res = ask(getattr(tp, name), lang=lang)
    _check_contract(res)
    if name != "train_progress":
        assert "C70_R1" not in res["model"]  # held: no failure count or result anywhere


# ------------------------------------------------------------------ failure_table
def test_failure_table_reads_the_new_contract(idx: ConsolePaths) -> None:
    _write(idx, True)
    t = ask(tp.failure_table)["model"]
    lines = t.splitlines()
    assert lines[0].startswith("FAILURE_TABLE | task=tray")
    assert "FAILURE | round=tray-r1 | label=Đặt lệch | C_ALL=29 | C_70=32" in t
    assert "FAILURE | round=tray-r1 | label=Chỉ cầm một tay | C_ALL=0 | C_70=3" in t
    assert "RUN | round=tray-r1 | run=C_70 | failed=50 | n=60" in t
    assert "RUN | round=tray-jig-r1 | run=M | failed=44 | n=180" in t
    assert "scorer=v1" in t and "scorer=v2" in t
    assert (
        "COMPARE | rounds=tray-r1,tray-jig-r1 | comparable=no | scorer_differs=yes | scene_differs=yes"
        in t
    )
    assert "MISSING" not in t and "56" not in t and "40" not in t  # held C70_R1, hidden N
    en = ask(tp.failure_table, lang="en")["model"]
    assert "label=Misplaced | C_ALL=29" in en and "label=Tray tilted" in en


def test_failure_table_falls_back_to_pair_and_jig(idx: ConsolePaths) -> None:
    _write(idx, False)
    res = ask(tp.failure_table)
    t = res["model"]
    assert (
        "label=Đặt lệch | C_ALL=29 | C_70=32" in t
        and "label=Khay nghiêng | C_ALL=15 | C_70=10" in t
    )
    assert "label=Chỉ cầm một tay | C_ALL=2 | C_70=0" in t
    assert "run=C_ALL | failed=55 | n=60" in t and "run=M | failed=44 | n=180" in t
    assert "label=Đặt lệch | M=28" in t and "label=Khay nghiêng | M=13" in t
    # labels in order of their total over the round's runs
    order = [
        ln.split("label=")[1].split(" |")[0]
        for ln in t.splitlines()
        if ln.startswith("FAILURE | round=tray-r1")
    ]
    assert order == ["Đặt lệch", "Khay nghiêng", "Hết giờ", "Rơi khay", "Chỉ cầm một tay"]
    # tray-r1 has no scorer version in the index: said missing, never guessed; scenes differ
    assert "missing=scorer" in t and "comparable=no" in t and "scorer_differs=missing" in t
    assert (
        "MISSING | missing=story.failure_table.tray-r1,story.failure_table.tray-jig-r1 | fallback=story.pair.runs,story.jig.evals"
        in t
    )
    assert "C70_R1" not in t and "4/60" not in t
    assert res["ui"]["type"] == "table" and {"round", "run", "Đặt lệch", "failed", "n"} <= {
        c["key"] for c in res["ui"]["columns"]
    }


def test_failure_table_one_round_when_asked(idx: ConsolePaths) -> None:
    _write(idx, False)
    res = ask(tp.failure_table, round="tray-jig-r1")
    assert (
        res["round"] == "tray-jig-r1"
        and "tray-r1 |" not in res["model"]
        and "COMPARE" not in res["model"]
    )
    assert res["sources"] == ["docs/he/tray-jig.md §2, §5"]
    by_q = ask(tp.failure_table, "Thống kê lỗi của vòng đồ gá")
    assert by_q["round"] == "tray-jig-r1"
    by_run = ask(tp.failure_table, "Lỗi của C_70?", rnd="tray-jig-r1")
    assert by_run["round"] == "tray-r1"
    every = ask(tp.failure_table, "Thống kê toàn bộ loại lỗi", rnd="tray-jig-r1")
    assert "round" not in every and every["model"].splitlines()[1].startswith(
        "ROUND | id=tray-jig-r1"
    )  # selected first
    bad = ask(tp.failure_table, round="tray-r9")
    assert bad["ok"] is False


# ------------------------------------------------------------------ train_progress
def test_train_progress_rows_and_holds(idx: ConsolePaths) -> None:
    _write(idx, False)
    res = ask(tp.train_progress)
    t = res["model"]
    runs = [
        ln.split("run=")[1].split(" |")[0]
        for ln in t.splitlines()
        if ln.startswith("RUN | round=tray-r1")
    ]
    assert runs == [
        "C_ALL",
        "C_70",
        "C70_R1",
    ]  # round order, the held run last; never ranked by loss
    c70 = next(ln for ln in t.splitlines() if "run=C_70 " in ln)
    assert (
        "role=bản gốc" in c70
        and "steps=60000/60000" in c70
        and "state=xong" in c70
        and "steps_per_s=2,58" in c70
    )
    assert (
        "vm_hours=10,66" in c70
        and "vm_setup_h=0,03" in c70
        and "vm_train_h=10,57" in c70
        and "vm_persist_h=0,06" in c70
    )
    assert "vm_cover=cả run" in c70 and "loss_first=49,20" in c70 and "loss_trend_late=giảm" in c70
    assert "loss_trend_late=đi ngang" in next(ln for ln in t.splitlines() if "run=C70_R1" in ln)
    m = next(ln for ln in t.splitlines() if "run=M " in ln)
    assert (
        "steps=100000/100000" in m and "vm_cover=một phần run" in m
    )  # 8,45 h cannot hold 100 000 steps
    assert (
        "COST | round=tray-r1 | part=train lần 1 | cu=8,55 | kind=thực đo | scope=một lô train, không phải một run"
        in t
    )
    assert "part=train lần 2 | cu=77,27" in t and "serve" not in t
    assert (
        "COST | round=tray-jig-r1 | run=M | part=train | cu=56,15 | kind=thực đo | story=DA-48" in t
    )
    assert "LOSS_NOTE | text=Loss train không phải thước đo kết quả." in t
    for w in ("tốt", "good", "best", "da34-t6", "job="):
        assert w not in t, w
    en = ask(tp.train_progress, lang="en")["model"]
    assert "LOSS_NOTE | text=Training loss is not a measure of the result." in en
    assert (
        "state=finished" in en
        and "scope=one training batch, not one run" in en
        and "good" not in en
    )
    assert ask(tp.train_progress, round="tray-jig-r1")["round"] == "tray-jig-r1"


# ------------------------------------------------------------------ project_status
def test_project_status_reads_timeline_latest_next_and_links(idx: ConsolePaths) -> None:
    _write(idx, True)
    res = ask(tp.project_status)
    lines = res["model"].splitlines()
    assert lines[0] == "STATUS | task=tray | title=Bê khay | default_round=tray-jig-r1"
    assert lines[1].startswith(
        "LATEST | round=tray-jig-r1 | title=Vòng đồ gá: run M | run=M | date=2026-11-26 | successes=136 | n=180 | pct=75,6 % | place_pct=89,4 %"
    )
    events = [ln for ln in lines if ln.startswith("EVENT")]
    assert [e.split("date=")[1][:10] for e in events] == [
        "2026-11-19",
        "2026-11-26",
    ]  # DA-50 and the held retest dropped
    assert "result=136/180 (75,6 %)" in events[1] and "result=" not in events[0]
    nexts = [ln for ln in lines if ln.startswith("NEXT")]
    assert nexts == [
        "NEXT | round=tray-jig-r1 | text=Train run đối chứng K trên cùng cảnh | doc=docs/he/tray-jig.md §1"
    ]
    assert (
        "LINK | from=tray-r1 | way=next | round=tray-jig-r1 | run=M | successes=136 | n=180 | scene_differs=yes | scorer_differs=yes"
        in lines
    )
    assert (
        "LINK | from=tray-jig-r1 | way=prev | round=tray-r1 | run=C_70 | successes=10 | n=60 | carried=50 | placed=10 | scene_differs=yes | scorer_differs=yes"
        in lines
    )
    assert (
        "ROUND | id=tray-jig-r1 | title=Vòng đồ gá: run M | number=2 | scene=jig2 | default=yes"
        in lines
    )
    assert "MISSING" not in res["model"]
    assert (
        "docs/he/tray-jig.md §1" in res["sources"]
        and "docs/he/tray-jig.md §7" not in res["sources"]
    )
    # a "what next" question gets the next steps first
    assert (
        ask(tp.project_status, "Giờ nên làm gì tiếp theo?")["model"]
        .splitlines()[1]
        .startswith("NEXT")
    )
    en = ask(tp.project_status, lang="en")["model"]
    assert (
        "pct=75.6% | place_pct=89.4%" in en
        and "text=Train control run K on the same scene" in en
        and "title=Jig scene jig2" in en
    )


def test_project_status_says_what_is_missing(idx: ConsolePaths) -> None:
    _write(idx, False)
    t = ask(tp.project_status)["model"]
    assert (
        "MISSING | missing=tasks.default_round,story.latest,story.timeline,story.next_steps,tasks.rounds.links"
        in t
    )
    for w in ("LATEST", "EVENT", "NEXT", "LINK", "136"):
        assert w not in t, w  # never invented from other keys


def test_held_or_hidden_latest_is_not_presented(idx: ConsolePaths) -> None:
    _write(idx, True)
    p = idx.index / "story.json"
    for run in ("C70_R1", "N"):
        s = json.loads(p.read_text(encoding="utf-8"))
        s["latest"] = {
            "round": "tray-r1" if run == "C70_R1" else "tray-jig-r1",
            "run": run,
            "date": "2026-11-28",
        }
        p.write_text(json.dumps(s), encoding="utf-8")
        t = ask(tp.project_status)["model"]
        assert "LATEST" not in t and "missing=" in t and f"run={run}" not in t


def test_a_one_letter_hidden_run_is_matched_as_a_run_only(idx: ConsolePaths) -> None:
    _write(idx, True)
    p = idx.index / "story.json"
    s = json.loads(p.read_text(encoding="utf-8"))
    s["timeline"] = [
        {"date": "2026-11-21", "story": "DA-42", "title": {"vi": "Bộ chấm bản 2 (N/A cũ bỏ)", "en": "Scorer v2"}, "result": None, "doc": "docs/he/tray-jig.md §2", "round": "tray-jig-r1"},
        {"date": "2026-11-28", "story": "DA-49", "title": {"vi": "So run N với M", "en": "Run N against M"}, "result": None, "doc": "docs/he/tray-jig.md §7", "round": "tray-jig-r1"},
    ]  # fmt: skip
    p.write_text(json.dumps(s), encoding="utf-8")
    events = [ln for ln in ask(tp.project_status)["model"].splitlines() if ln.startswith("EVENT")]
    assert len(events) == 1 and "story=DA-42" in events[0]

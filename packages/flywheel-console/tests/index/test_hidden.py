"""``withhold_runs`` (Hiếu, 28/11/2026, story DA-53): run N is never written or served.

The index build on a tmp fwdata holding everything of both jig runs gives a ``story.json`` with
nothing of N; ``hidden.story`` cleans stale documents of both shapes of the ``jig`` block.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from flywheel.console.index import hidden, story, tasks
from flywheel.console.paths import ConsolePaths

FIX = Path(__file__).parent / "fixtures" / "jig"
SHA = "bbec07e31ee022ac46d59e5322628c226519abe76363160ccbdb78b68725d348"


def _write(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")


def _jsonl(p: Path, rows: list[dict[str, Any]]) -> None:
    _write(p, "\n".join(json.dumps(r) for r in rows) + "\n")


def _train(job: Path, run: str) -> None:
    rows = [{"split": "train", "step": s, "loss": 0.2, "release_id": run} for s in (0, 100_000)]
    _jsonl(job / "metrics.jsonl", rows)
    _write(job / "expected-100000.json", {"ckpt_step": 100_000})
    _write(job / "vm-logs/train.log", f"train {run} line\n")
    _write(job / "vm-logs/report.json", {"phases": {"train": {"seconds": 10.0}}})


def _outcome(folder: Path, run: str) -> None:
    scores, outs = [], []
    for k, (lv, seed) in enumerate([(1, 1000100), (2, 1000200)]):
        ep = f"{run}/l{lv}-s{seed}"
        scores.append(
            {
                "episode_id": ep,
                "success": k == 0,
                "level": lv,
                "step_status": ["pass"] * 7,
                "scorer_version": "simple-tray-predicates@2",
            }
        )
        outs.append({"episode_id": ep, "run": run, "seed": seed, "level": lv, "repeat": 0})
    _jsonl(folder / "scores.jsonl", scores)
    _jsonl(folder / "outcomes.jsonl", outs)
    _write(folder / "results.json", (FIX / f"results-{run.lower()}.json").read_text())


def _fwdata(fw: ConsolePaths) -> None:
    root = fw.fw_root
    _write(root / "tray/eval-sets/jig-m-rp_a410d01efa62/conditions.sha256", SHA + "\n")
    _train(root / "tray/jig-m/da48-ft-m-s0", "M")
    _train(root / "tray/jig-n/da50-ft-n-s0", "N")
    _outcome(root / "tray/outcomes/jig-m-100000-r3", "M")
    _outcome(root / "tray/outcomes/jig-n-100000-r3", "N")
    _write(root / "da48/cuts/M.tar.json", {"name": "M", "files": 10, "bytes": 100})
    _write(root / "tray/jig-n/N.tar.json", {"name": "N", "files": 20, "bytes": 200})
    _write(root / "colab/da50-eval-n-x/watch.log", "lanes=3 complete=8 rows=8\n")
    _write(root / "colab/da50-eval-n-x/da50-serve-n-1.json", {"name": "da50-serve-n-1"})
    _write(root / "colab/da47-eval-m-x/watch.log", "lanes=3 complete=60 rows=180\n")
    _write(root / "colab/batch-1/da50-n.json",
           {"name": "da50-n", "state": "running", "gpu": "L4", "beat": time.time()})
    _write(
        root / "colab/batch-1/da48-m.json",
        {"name": "da48-m", "state": "running", "gpu": "A100", "beat": time.time()},
    )
    for case, run in (("jig-m-100k-a", "M"), ("jig-n-100k-a", "N")):
        cl = {"cluster": {"cluster_id": f"c-{run}", "run": run, "label": "L-PLACE-POSE"}}
        _write(
            root / f"agentqa/cases/{case}/assembly.json", {"clusters": [cl], "status": "complete"}
        )
    ledger = (
        "story,quantity,unit,amount_usd,estimated_or_measured\n"
        "DA-50,125,compute_unit,12.5,measured\nDA-50,100,compute_unit,10,estimated\n"
        "DA-50,2,hour,0,measured\n"
    )
    _write(fw.repo / "docs/g0/ledger/DA-50.csv", ledger)


def _no_n(text: str) -> None:
    for needle in ("da50", "jig-n", "N.tar", "20261126", "jig-n-rules"):
        assert needle not in text, needle
    assert not re.search(r'"(?:run|branch|variant|after_round)":\s*"N"', text)


def test_index_build_writes_nothing_of_a_hidden_run(fw: ConsolePaths, tmp_path: Path) -> None:
    _fwdata(fw)
    out = tmp_path / "out"
    tasks.build(fw, out)
    story.build(fw, out)
    text = (out / "story.json").read_text(encoding="utf-8")
    _no_n(text)
    _no_n((out / "tasks.json").read_text(encoding="utf-8"))
    d = json.loads(text)
    j = d["jig"]
    assert [r["branch"] for r in j["runs"]] == ["M"] and j["log_run"] == "M"
    assert j["train_log_tail"] == ["train M line"]
    assert [e["run"] for e in j["evals"]] == ["M"] and j["evals"][0]["status"] == "ready"
    assert j["featured"] == "M" and j["paired"] is None
    assert [o["run"] for o in j["outcomes"]] == ["M"] and {r["run"] for r in j["rollouts"]} == {"M"}
    assert set(j["cuts"]) == {"M"} and j["m_cut"]["name"] == "M" and j["next_cut"] is None
    assert j["n_ckpt_done"] is None
    assert [w["folder"] for w in j["live_evals"]] == ["da47-eval-m-x"]
    assert [s["session"] for s in j["active_sessions"]] == ["da48-m"]
    assert [s["session"] for s in d["colab_sessions"]] == ["da48-m"]
    assert [a["case_id"] for a in j["agentqa"]] == ["jig-m-100k-a"]
    # money spent stays, merged into one "other" row under its own label (decision Q1)
    assert d["ledger"] == [
        {"story": "other", "label": "Thí nghiệm khác (không trình bày)",
         "est_cu": 100.0, "mea_cu": 125.0, "est_usd": 10.0, "mea_usd": 12.5}
    ]  # fmt: skip


def test_round_runs_leave_out_a_hidden_run(fw: ConsolePaths) -> None:
    _fwdata(fw)
    runs, dirs = story.round_runs(fw.fw_root, tasks.load(fw).round("tray-jig-r1"))
    assert [r["branch"] for r in runs] == ["M"] and [d.name for d in dirs] == ["da48-ft-m-s0"]


def test_load_reads_the_seed(fw: ConsolePaths) -> None:
    h = hidden.load(fw)
    assert h.ids == {"N"} and h.run("N") and not h.run("M") and not h.run(None)
    assert h.session("da50-n") and h.session("da50-eval-n-20261128-033608")
    assert not h.session("da48-m") and not h.session("")
    assert {"da50-ft-n-s0", "jig-n", "jig-n-100000-r3", "N.tar"} <= set(h.names)
    assert "jig-m" not in h.names
    assert hidden.load(fw) is h  # cached until the seed changes


H = hidden.Hidden(frozenset({"N"}), ("da50-*",), ("da50-ft-n-s0", "jig-n", "jig-n-100000-r3"))


def test_mentions_works_for_a_one_letter_id() -> None:
    for text in ("loss của run N?", "Run N đạt", "job da50-ft-n-s0 xong", "folder tray/jig-n/x",
                 "colab da50-serve-n-1", '{"run": "N", "x": 1}', '"branch":"N"'):  # fmt: skip
        assert H.mentions(text), text
    for text in ("run nào tốt nhất?", "M_NEW đạt 6/60", "jig-m-100000", "N.B. note", "run M",
                 "nhãn L-PLACE-POSE", "da500"):  # fmt: skip
        assert not H.mentions(text), text
    assert not hidden.Hidden().mentions("run N")


def _new_shape() -> dict[str, Any]:
    """A story.json of jig.py's shape written before withhold_runs, N everywhere."""
    tail_n, tail_m = ["n log"], ["m log"]
    return {
        "runs": [{"branch": "C_70"}],
        "colab_sessions": [{"session": "da50-n"}, {"session": "da48-m"}],
        "ledger": [["DA-50", 1.0, 2.0]],
        "jig": {
            "runs": [{"branch": "M", "log_tail": tail_m}, {"branch": "N", "log_tail": tail_n}],
            "train_log_tail": tail_n, "vm_phases": {"train": 1.0},
            "evals": [{"run": "M", "role": "baseline", "status": "ready"},
                      {"run": "N", "role": "after_round", "status": "ready"}],
            "paired": {"variant": "N", "baseline": "M", "status": "ready"},
            "featured": "N",
            "outcomes": [{"run": "M"}, {"run": "N"}], "rollouts": [{"run": "N"}],
            "conditions": [{"run": "M"}, {"run": "N"}],
            "cuts": {"M": {"name": "M"}, "N": {"name": "N"}},
            "m_cut": {"name": "M", "source": "fwdata/da48/cuts/M.tar.json"},
            "next_cut": {"name": "N", "source": "fwdata/tray/jig-n/N.tar.json"},
            "n_ckpt_done": 100000,
            "live_evals": [{"folder": "da50-eval-n-1", "session": "da50-serve-n-1"},
                           {"folder": "da47-eval-m-1", "session": "da47-eval-m-1"}],
            "active_sessions": [{"session": "da50-n"}, {"session": "da48-m"}],
            "agentqa": [{"case_id": "a", "clusters": [{"run": "N"}]},
                        {"case_id": "b", "clusters": [{"run": "M"}, {"run": "N"}]},
                        {"case_id": "c", "clusters": []}],
        },
    }  # fmt: skip


def test_story_filter_cleans_the_new_shape() -> None:
    doc = _new_shape()
    out = hidden.story(doc, H)
    j = out["jig"]
    assert [r["branch"] for r in j["runs"]] == ["M"]
    assert j["train_log_tail"] == [] and j["vm_phases"] == {}  # N's log
    assert [e["run"] for e in j["evals"]] == ["M"] and j["paired"] is None
    assert j["featured"] == "M"  # the baseline, its eval is ready
    assert [o["run"] for o in j["outcomes"]] == ["M"] and j["rollouts"] == []
    assert set(j["cuts"]) == {"M"} and j["next_cut"] is None and j["n_ckpt_done"] is None
    assert j["m_cut"]["name"] == "M"
    assert [w["folder"] for w in j["live_evals"]] == ["da47-eval-m-1"]
    assert [s["session"] for s in j["active_sessions"]] == ["da48-m"]
    assert [a["case_id"] for a in j["agentqa"]] == ["b", "c"]
    assert j["agentqa"][0]["clusters"] == [{"run": "M"}]
    assert [s["session"] for s in out["colab_sessions"]] == ["da48-m"]
    assert out["ledger"] == doc["ledger"] and out["runs"] == doc["runs"]
    _no_n(json.dumps(out))
    assert doc["jig"]["featured"] == "N"  # the input is not changed in place


def test_story_filter_keeps_the_log_of_a_shown_run() -> None:
    doc = _new_shape()
    doc["jig"]["train_log_tail"] = ["m log"]
    assert hidden.story(doc, H)["jig"]["train_log_tail"] == ["m log"]
    doc["jig"]["train_log_tail"] = ["whose?"]  # no run entry carries it: cleared
    assert hidden.story(doc, H)["jig"]["train_log_tail"] == []
    doc["jig"] |= {"log_run": "M", "train_log_tail": ["whose?"]}  # the doc says whose
    assert hidden.story(doc, H)["jig"]["train_log_tail"] == ["whose?"]


def test_story_filter_cleans_the_older_master_shape() -> None:
    """``jig.runs`` are eval rows keyed ``run``; the top-level ``runs`` hold the train entries."""
    doc = {
        "runs": [{"branch": "C_70"}, {"branch": "M"}, {"branch": "N", "job": "da50-ft-n-s0"}],
        "train_log_tail": ["c70 line"],
        "colab_sessions": [{"session": "da50-n"}],
        "jig": {
            "scene": "jig2",
            "runs": [{"run": "M", "successes": 136}, {"run": "N", "successes": 140}],
            "best": "N",
            "rollouts": [{"run": "M"}, {"run": "N"}], "conditions": [{"run": "N"}],
            "live_evals": [{"folder": "da50-eval-n-20261128-033608", "session": "da50-serve-n-1"}],
            "agentqa": [], "n_ckpt_done": 100000,
            "m_cut": {"name": "M", "source": "fwdata/da48/cuts/M.tar.json"},
            "next_cut": {"name": "N", "source": "fwdata/tray/jig-n/N.tar.json"},
            "active_sessions": [{"session": "da50-n"}],
        },
    }  # fmt: skip
    out = hidden.story(doc, H)
    j = out["jig"]
    assert [r["branch"] for r in out["runs"]] == ["C_70", "M"]
    assert out["train_log_tail"] == ["c70 line"]  # the tray-r1 log_run's, not a jig run's
    assert [r["run"] for r in j["runs"]] == ["M"] and j["best"] == "M"
    assert j["next_cut"] is None and j["n_ckpt_done"] is None and j["m_cut"]["name"] == "M"
    assert j["live_evals"] == [] and j["active_sessions"] == [] and out["colab_sessions"] == []
    _no_n(json.dumps(out))
    doc["jig"]["next_cut"] = None  # whose n_ckpt_done is it? unknowable: cleared
    assert hidden.story(doc, H)["jig"]["n_ckpt_done"] is None


def test_story_filter_is_a_no_op_without_hidden_runs() -> None:
    doc = _new_shape()
    assert hidden.story(doc, hidden.Hidden()) is doc


def test_tasks_doc_filter_cleans_a_stale_tasks_json() -> None:
    stale = {"rounds": [
        {"id": "tray-jig-r1", "baseline": "M", "after_round": "N", "log_run": "N",
         "runs": [{"id": "M"}, {"id": "N", "outcome": "tray/outcomes/jig-n-100000-r3"}],
         "withhold_runs": [{"id": "N", "sessions": ["da50-*"]}]},
        {"id": "tray-r1", "after_round": "C70_R1", "withhold_eval": ["C70_R1"],
         "runs": [{"id": "C70_R1"}]},
    ]}  # fmt: skip
    out = hidden.tasks_doc(stale, H)
    jig, pair = out["rounds"]
    assert jig["runs"] == [{"id": "M"}] and jig["after_round"] is None and jig["log_run"] is None
    assert "withhold_runs" not in jig and pair == stale["rounds"][1]
    _no_n(json.dumps(out))


def test_story_filter_drops_compare60_of_a_hidden_run() -> None:
    c60 = {"run": "N", "earlier": [{"run": "C_70"}]}
    assert hidden.story({"jig": {"compare60": c60}}, H)["jig"]["compare60"] is None
    c60 = {"run": "M", "earlier": [{"run": "C_70"}, {"run": "N"}]}
    out = hidden.story({"jig": {"compare60": c60}}, H)["jig"]["compare60"]
    assert out == {"run": "M", "earlier": [{"run": "C_70"}]}

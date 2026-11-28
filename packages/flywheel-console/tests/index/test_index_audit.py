"""Index fixes of the console audit of 28/11/2026 (02 · Nội dung và số liệu; 00 · Tổng hợp).

Catalog and ledger of a hidden story (decision Q1), ledger CU/USD apart (P1-1), ``.attempt``
folders (P1-3), Colab sessions of every batch (P1-5), the sim library of the jig round (A12),
the place CI of run M (P1-10), train speed units (P1-2), the jig round's cost (B14) and the
round-1 diagnosis for the chat (04 B4, F3).
"""

from __future__ import annotations

import copy
import io
import json
import re
import tarfile
from pathlib import Path
from typing import Any

from conftest import write_mp4
from flywheel.console.index import catalog, cited, hidden, jig, sim, story, tasks
from flywheel.console.paths import ConsolePaths

REPO = Path(__file__).resolve().parents[4]
FIX = Path(__file__).parent / "fixtures" / "jig"
SHA = "bbec07e31ee022ac46d59e5322628c226519abe76363160ccbdb78b68725d348"
STEPS = ("approach_a", "grasp", "lift", "carry", "reach_b", "place", "release_stand")


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _h(fw: ConsolePaths) -> hidden.Hidden:
    return hidden.from_manifest(tasks.load(fw))


# ------------------------------------------------------------------ hidden story (Q1)
def test_seed_hides_story_da50(fw: ConsolePaths) -> None:
    h = _h(fw)
    assert h.story("DA-50") and not h.story("DA-48") and h.stories == frozenset({"DA-50"})


def test_catalog_rows_drop_a_hidden_story_and_rows_naming_a_hidden_run(fw: ConsolePaths) -> None:
    rows = [
        {"id": "keep", "story": "DA-48", "notes": "", "parents": ["gone_story"], "children": []},
        {"id": "gone_story", "story": "DA-50", "notes": ""},
        {"id": "gone_note", "story": None, "notes": "checked in analysis/da50-clean/x.json"},
        {"id": "child", "story": None, "notes": "", "parents": ["keep", "gone_note"]},
    ]
    edges = [("gone_story", "keep"), ("keep", "child"), ("gone_note", "child")]
    kept, kept_edges = hidden.catalog_rows(rows, edges, _h(fw))
    assert [r["id"] for r in kept] == ["keep", "child"]
    assert kept[0]["parents"] == [] and kept[1]["parents"] == ["keep"]
    assert kept_edges == [("keep", "child")]
    assert hidden.catalog_rows(rows, edges, hidden.Hidden()) == (rows, edges)


def test_catalog_build_has_no_da50_row(tmp_path: Path) -> None:
    from flywheel.console.index import catalog

    p = ConsolePaths(repo=REPO, fw_root=tmp_path / "fw")
    catalog.build(p, tmp_path / "out")
    text = (tmp_path / "out" / "catalog.json").read_text(encoding="utf-8")
    assert '"DA-50"' not in text and "da50" not in text


def test_stale_ledger_merges_hidden_stories_into_other(fw: ConsolePaths) -> None:
    h = _h(fw)
    new = [
        {"story": "DA-48", "label": "x", "est_cu": None, "mea_cu": 56.15, "est_usd": None,
         "mea_usd": 5.61},
        {"story": "DA-50", "label": "y", "est_cu": 52.0, "mea_cu": 63.16, "est_usd": 5.19,
         "mea_usd": 6.31},
    ]  # fmt: skip
    out = hidden.ledger(new, h)
    assert [r["story"] for r in out] == ["DA-48", "other"]
    assert out[1]["label"] == "Thí nghiệm khác (không trình bày)"
    assert (out[1]["est_cu"], out[1]["mea_cu"], out[1]["mea_usd"]) == (52.0, 63.16, 6.31)
    assert hidden.ledger([["DA-34", 1.0, 2.0], ["DA-50", 5.19, 6.31]], h) == [
        ["DA-34", 1.0, 2.0], ["other", 5.19, 6.31]
    ]  # fmt: skip


# ------------------------------------------------------------------ ledger (P1-1)
_HEAD = (
    "date,activity,resource_type,quantity,unit,unit_price_usd,amount_usd,estimated_or_measured\n"
)


def test_ledger_splits_cu_and_usd_estimated_and_measured(fw: ConsolePaths) -> None:
    repo = fw.repo
    _write(repo / "docs/product/stories/DA-48-train-m.md", "# DA-48 · Train vòng mới\n")
    _write(
        repo / "docs/g0/ledger/DA-48.csv",
        _HEAD + "d,a,colab_l4,31.22,compute_unit,0.0999,3.12,measured\n"
        "d,a,colab_l4,24.93,compute_unit,0.0999,2.49,measured\n"
        "d,a,engineer_time,4,hour,0,0,estimated\n",
    )
    _write(
        repo / "docs/g0/ledger/DA-50.csv",
        _HEAD + "d,a,colab_l4,52,compute_unit,0.0999,5.19,estimated\n"
        "d,a,colab_l4,55.78,compute_unit,0.0999,5.57,measured\n"
        "d,a,colab_l4,7.38,compute_unit,0.0999,0.74,measured\n",
    )
    rows = story._ledger(repo, _h(fw))
    assert rows == [
        {"story": "DA-48", "label": "Train vòng mới", "est_cu": None, "mea_cu": 56.15,
         "est_usd": 0.0, "mea_usd": 5.61},
        {"story": "other", "label": "Thí nghiệm khác (không trình bày)", "est_cu": 52.0,
         "mea_cu": 63.16, "est_usd": 5.19, "mea_usd": 6.31},
    ]  # fmt: skip
    # without the hidden story the row keeps its own id (no title file: label None)
    plain = story._ledger(repo)
    assert [r["story"] for r in plain] == ["DA-48", "DA-50"] and plain[1]["label"] is None


def test_jig_cost_reads_the_ledger_and_checks_the_doc(fw: ConsolePaths) -> None:
    ledger = [
        {"story": "DA-48", "label": "t", "est_cu": None, "mea_cu": 56.15, "est_usd": None,
         "mea_usd": 5.61},
        {"story": "DA-47", "label": "e", "est_cu": None, "mea_cu": 6.8, "est_usd": None,
         "mea_usd": 0.68},
    ]  # fmt: skip
    real = ConsolePaths(repo=REPO, fw_root=fw.fw_root)
    cost = story._jig_cost(real, tasks.load(real).round("tray-jig-r1"), ledger)
    assert cost["train"]["cu"] == 56.15 and cost["train"]["measure_kind"] == "measured"
    assert cost["train"]["matches_doc"] and cost["train"]["doc"]["source"].endswith("§4")
    assert cost["eval"]["cu"] == 6.8 and cost["eval"]["matches_doc"]
    assert cost["total_cu"] == 62.95
    assert story._jig_cost(real, None, ledger) == {}


# ------------------------------------------------------------------ runs (P1-2, P1-3)
def _metrics(job: Path, thr: float = 23.05) -> None:
    rows = [{"split": "train", "step": s, "loss": 0.3, "throughput": thr} for s in (0, 100)]
    _write(job / "metrics.jsonl", "\n".join(json.dumps(r) for r in rows) + "\n")
    _write(job / "launch.json", json.dumps({"global_batch_size": 16, "argv": []}))


def test_attempt_folders_are_not_runs_and_speed_has_units(fw: ConsolePaths) -> None:
    root = fw.fw_root / "tray/pair60k"
    _metrics(root / "C70_R1/job-a")
    _metrics(root / "C70_R1.attempt1/job-a")
    runs, dirs = story._runs(fw.fw_root, "tray/pair60k", 60000)
    assert [r["branch"] for r in runs] == ["C70_R1"] and len(dirs) == 1
    r = runs[0]
    assert r["samples_per_s"] == r["thr_med"] == 23.05
    assert r["global_batch_size"] == 16 and r["steps_per_s"] == 1.441


def test_steps_per_s_is_none_without_the_batch(fw: ConsolePaths) -> None:
    job = fw.fw_root / "tray/pair60k/C_70/job"
    _metrics(job)
    (job / "launch.json").write_text("{}")
    r = story._runs(fw.fw_root, "tray/pair60k", 60000)[0][0]
    assert r["samples_per_s"] == 23.05 and r["steps_per_s"] is None


# ------------------------------------------------------------------ colab (P1-5)
def test_colab_sessions_come_from_every_batch_newest_record_wins(fw: ConsolePaths) -> None:
    c = fw.fw_root / "colab"
    _write(c / "batch-1/da34-c-70.json", json.dumps({"name": "da34-c-70", "beat": 1, "cap": 70}))
    _write(c / "batch-1/da34-c-70.attempt1.json", json.dumps({"name": "da34-c-70", "beat": 0}))
    _write(c / "batch-2/da48-m.json", json.dumps({"name": "da48-m", "beat": 5, "cap": 60}))
    _write(c / "batch-3/da48-m.json", json.dumps({"name": "da48-m", "beat": 9, "cap": 30}))
    _write(c / "batch-4/da50-n.json", json.dumps({"name": "da50-n", "beat": 10}))
    _bal, sessions = story._colab(fw.fw_root)
    got = {s["session"]: (s["batch"], s["cap"]) for s in sessions}
    assert got == {"da34-c-70": ("batch-1", 70), "da48-m": ("batch-3", 30),
                   "da50-n": ("batch-4", None)}  # fmt: skip
    # the build drops the hidden session (``story.build``: hide.session)
    assert not any(_h(fw).session(s) for s in ("da34-c-70", "da48-m"))
    assert _h(fw).session("da50-n")


# ------------------------------------------------------------------ place CI (P1-10)
def _jig_round(fw: ConsolePaths) -> tasks.Round:
    return tasks.load(fw).round("tray-jig-r1")


def _put_m(fw: ConsolePaths, doc: dict[str, Any]) -> None:
    _write(fw.fw_root / "tray/eval-sets/jig-m-rp_a410d01efa62/conditions.sha256", SHA + "\n")
    _write(fw.fw_root / "tray/outcomes/jig-m-100000-r3/results.json", json.dumps(doc))


def test_place_ci_gives_rule_3_a_verdict(fw: ConsolePaths) -> None:
    doc = json.loads((FIX / "results-m.json").read_text(encoding="utf-8"))
    doc["headline"]["step_ci"] = {"place": [0.85, 0.9388888888888888]}
    _put_m(fw, doc)
    ev = jig.build(fw.fw_root, _jig_round(fw), [], [], {}, STEPS, [])["evals"][0]
    assert ev["status"] == "ready" and ev["place"]["ci"] == [0.85, 0.9388888888888888]
    place = ev["readings"][-1]
    assert (place["rule"], place["lower"], place["verdict"]) == ("3", 0.85, "met")
    assert "why" not in place


def test_place_below_threshold_is_not_met_and_absent_ci_has_no_verdict(fw: ConsolePaths) -> None:
    doc = json.loads((FIX / "results-m.json").read_text(encoding="utf-8"))
    low = copy.deepcopy(doc)
    low["headline"]["step_ci"] = {"place": [0.4, 0.6]}
    _put_m(fw, low)
    place = jig.build(fw.fw_root, _jig_round(fw), [], [], {}, STEPS, [])["evals"][0]["readings"][-1]
    assert place["verdict"] == "not_met"
    _put_m(fw, doc)
    place = jig.build(fw.fw_root, _jig_round(fw), [], [], {}, STEPS, [])["evals"][0]["readings"][-1]
    assert place["verdict"] is None and place["why"] == "no_ci"


# ------------------------------------------------------------------ diag (04 B4, F3)
def test_diag_block_is_cited() -> None:
    d = cited.diag_block(ConsolePaths(repo=REPO, fw_root=REPO / "fwdata"))
    by = {c["id"]: c for c in d["clusters"]}
    assert list(by) == [f"c{i}" for i in range(1, 9)]
    assert sum(c["n_fail"] for c in d["clusters"]) == 44  # 50 failures less 6 odd ones (20.2)
    assert by["c1"]["key"] == {"step": "place", "label": "L-PLACE-POSE", "level": 1}
    assert {k for k, c in by.items() if c["gets_data"]} == {"c1", "c2", "c3", "c8"}
    assert by["c6"]["diagnosis"] == "ngưỡng bộ chấm" and all(c["source"] for c in by.values())
    h = {x["id"]: x for x in d["step4"]}
    assert (h["H1"]["ticket"], h["H2"]["ticket"], h["H3"]["ticket"]) == ("DA-37", None, "DA-38")
    assert h["H2"]["clusters"] == ["c3", "c8"]
    # English twins: present, ASCII, and no number the Vietnamese words lack
    pairs = [(c[f], c[f"{f}_en"]) for c in by.values() for f in ("diagnosis", "intervention")]
    pairs += [(x[f], x[f"{f}_en"]) for x in h.values() for f in ("claim", "verdict")]
    for vi, en in pairs:
        assert en and en.isascii(), (vi, en)
        assert set(re.findall(r"\d+", en)) <= set(re.findall(r"\d+", vi)), (vi, en)
    assert by["c1"]["diagnosis_en"] == "WEAK SKILL 5/5"
    assert h["H1"]["verdict_en"] == "UNCLEAR (scorer threshold)"
    g = d["gen_qa_cost"]
    assert (g["host"], g["cu"], g["selected"], g["train_serve_cu"]) == ("rtx3060", 0, 181, 109.22)
    assert g["generation"] == {"attempts": 290, "recorded": 262, "hours": 1.16}
    assert cited.verify(ConsolePaths(repo=REPO, fw_root=REPO / "fwdata")) == []


# ------------------------------------------------------------------ sim of the jig round (A12)
def _add(t: tarfile.TarFile, name: str, data: bytes) -> None:
    ti = tarfile.TarInfo(name)
    ti.size = len(data)
    t.addfile(ti, io.BytesIO(data))


def test_sim_builds_a_block_for_the_jig_round(fw: ConsolePaths, tmp_path: Path) -> None:
    root = "M/G1WholebodyTrayTransferJigTeleop-v0"
    cfg = {"flywheel": {"purpose": "coverage", "data_class": "public", "level": 1, "seed": 5}}
    eps = [{"episode_index": i, "length": 9, "environment_config": json.dumps(cfg)}
           for i in range(3)]  # fmt: skip
    subset = {"demo_set": "M", "n": 3, "parts": [
        {"release_id": "tray_s1_a", "n": 2, "first_episode_index": 0},
        {"release_id": "tray_s1place_b", "n": 1, "first_episode_index": 2}]}  # fmt: skip
    tar = fw.fw_root / "da48/cuts/M.tar"
    tar.parent.mkdir(parents=True)
    vid = write_mp4(tmp_path / "v.mp4").read_bytes()
    with tarfile.open(tar, "w") as t:
        _add(t, f"{root}/meta/episodes.jsonl", "\n".join(json.dumps(e) for e in eps).encode())
        _add(t, f"{root}/meta/flywheel_subset.json", json.dumps(subset).encode())
        info = {"codebase_version": "v2.1", "chunks_size": 2}
        _add(t, f"{root}/meta/info.json", json.dumps(info).encode())
        for i in range(3):  # episode 2 sits in chunk-001 (chunks_size 2)
            _add(t, f"{root}/videos/chunk-{i // 2:03d}/egocentric/episode_{i:06d}.mp4", vid)
    side = {"name": "M", "sha256": "204ff448" + "0" * 56}
    (tar.parent / "M.tar.json").write_text(json.dumps(side))
    out = tmp_path / "out"
    sim.build(fw, out)
    d = json.loads((out / "sim.json").read_text())
    assert set(d["rounds"]) == {"tray-r1", "tray-jig-r1"}
    j = d["rounds"]["tray-jig-r1"]
    assert (j["source"], j["sha8"], j["round"]) == ("da48/cuts/M.tar", "204ff448", "tray-jig-r1")
    assert [p["label"] for p in j["parts"]] == ["coverage", "coverage"]
    assert set(j["cuts"]) == {"M"} and "N" not in json.dumps(j["cuts"])
    assert [e["video"] for e in j["episodes"]] == [f"204ff448/ep_{i:06d}.mp4" for i in range(3)]
    # the top level stays round 1's (its cut is absent here: empty)
    assert d["round"] == "tray-r1" and d["episodes"] == []


def test_catalog_doc_filters_a_stale_catalog_and_recounts_totals() -> None:
    h = hidden.Hidden(frozenset({"N"}), ("da50-*",), (), frozenset({"DA-50"}))
    rows = [
        {"id": "a", "story": "DA-34", "group": "s1", "episodes": 10, "hours": 1.0,
         "status": "active", "unique": True, "children": ["b"]},
        {"id": "b", "story": "DA-50", "group": "s1", "episodes": 5, "hours": 0.5,
         "status": "active", "unique": True, "parents": ["a"]},
        {"id": "c", "story": "DA-34", "notes": "analysis/da50-clean", "group": "s1",
         "episodes": 3, "hours": 0.2, "status": "active", "unique": True},
    ]  # fmt: skip
    doc = {"rows": rows, "edges": [["a", "b"]], "totals": {"stale": True}, "cards": 3}
    assert hidden.catalog_hidden_ids(doc, h) == {"b", "c"}
    out = hidden.catalog_doc(doc, h)
    assert [r["id"] for r in out["rows"]] == ["a"] and out["rows"][0]["children"] == []
    assert out["edges"] == [] and out["cards"] == 3
    assert out["totals"] == catalog.totals(out["rows"]) and "stale" not in out["totals"]
    assert hidden.catalog_doc(doc, hidden.Hidden()) is doc
    assert hidden.catalog_hidden_ids({"rows": rows[:1]}, h) == frozenset()

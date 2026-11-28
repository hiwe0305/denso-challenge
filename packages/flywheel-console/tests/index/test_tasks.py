from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.console.index import tasks
from flywheel.console.paths import ConsolePaths


def _raw(fw: ConsolePaths) -> dict[str, Any]:
    data = yaml.safe_load((fw.seed / tasks.FILE).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_packaged_manifest_is_valid(fw: ConsolePaths) -> None:
    m = tasks.load(fw)
    tray, two = m.task("tray"), m.task("two_table")
    # design 28/10 §3.2 (7 steps of the tray scorer); spec §5.1 (6 steps of the two-table task)
    assert len(tray.stages) == 7 and len(two.stages) == 6
    assert tray.stages[0].id == "approach_a" and tray.stages[-1].id == "release_stand"
    # story DA-53: the jig-scene round comes first, so the pages open on it
    assert two.rounds == () and tray.rounds == ("tray-jig-r1", "tray-r1")
    r = m.round("tray-r1")
    assert m.story_round() is r and m.sim_round() is r
    assert {x.role for x in r.runs} == {"baseline", "after_round", "control"}
    assert r.follow is not None and r.max_steps > 0
    assert r.sessions[next(iter(r.sessions))] in r.run_ids
    assert r.withhold_eval == ("C70_R1",)  # Hiếu, 16/11/2026
    assert {"story.runs", "story.train_log_tail", "story.vm_phases"} <= set(r.index)
    assert not {"story.runs", "story.jig"} & set(tray.index)


def test_packaged_jig_round(fw: ConsolePaths) -> None:
    m = tasks.load(fw)
    j = m.round("tray-jig-r1")
    assert m.jig_round() is j and j.index == ("story.jig",)
    assert j.run_ids == ("M", "N") and j.controls == () and j.withhold_eval == ()
    assert [x.role for x in j.runs] == ["baseline", "after_round"]
    assert j.train_dir is None and j.eval_dir is None and j.rule_tag is None
    assert (j.scene, j.max_steps, j.rollouts_expected, j.scorer_version) == ("jig2", 100000, 180, 2)
    # docs/he/tray-jig.md §6 (jig-n-rules, scope)
    assert j.conditions_sha256 == (
        "bbec07e31ee022ac46d59e5322628c226519abe76363160ccbdb78b68725d348"
    )
    assert j.rules is not None
    assert (j.rules["whole_task"], j.rules["per_level"], j.rules["place"]) == (0.8, 0.7, 0.5)
    assert "jig-m-rules" in j.rules["source"]["en"] and "jig-n-rules" in j.rules["source"]["vi"]
    mm, nn = j.runs
    assert (mm.bootstrap_seed, nn.bootstrap_seed) == (20261125, 20261126)
    assert (mm.rules_block, nn.rules_block) == ("jig-m-rules", "jig-n-rules")
    assert mm.train == "tray/jig-m/da48-ft-m-s0" and nn.outcome == "tray/outcomes/jig-n-100000-r3"
    assert "--bootstrap-seed 20261125" in (mm.results_cmd or "")
    assert "--baseline" in (nn.results_cmd or "") and "--baseline" not in (mm.results_cmd or "")


def _jig(d: dict[str, Any]) -> dict[str, Any]:
    return next(r for r in d["rounds"] if r["id"] == "tray-jig-r1")


def _pair_round(d: dict[str, Any]) -> dict[str, Any]:
    return next(r for r in d["rounds"] if r["id"] == "tray-r1")


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda d: d.update(version=2), "version: 1"),
        (lambda d: d["tasks"][0].pop("stages"), "missing key 'stages'"),
        (lambda d: d["tasks"][0]["name"].pop("en"), "non-empty 'en'"),
        (lambda d: d["tasks"][0]["stages"].append(dict(d["tasks"][0]["stages"][0])), "duplicate"),
        (lambda d: d["tasks"][0]["process"].pop("3"), "missing process stages ['3']"),
        (lambda d: d["tasks"][0]["process"]["1"]["how"][0].update(kind="x"), "is not one of"),
        (lambda d: d["rounds"][0].update(baseline="NOPE"), "'NOPE' is not one of its runs"),
        (lambda d: d["rounds"][0].update(max_steps="many"), "expected int"),
        (lambda d: d["rounds"][0].update(task="ghost"), "unknown task 'ghost'"),
        (lambda d: d["tasks"][1]["rounds"].append("tray-r1"), "belongs to another task"),
        (lambda d: d["rounds"].append(dict(d["rounds"][0], id="r2")), "already belongs"),
        # a story.pair round still needs its train and eval folders and its rule tag
        (lambda d: _pair_round(d).pop("train_dir"), "round 'tray-r1': missing key 'train_dir'"),
        (lambda d: _pair_round(d).pop("rule_tag"), "missing key 'rule_tag'"),
        # a story.jig round (story DA-53)
        (lambda d: _jig(d).pop("eval_set"), "round 'tray-jig-r1': missing key 'eval_set'"),
        (lambda d: _jig(d).update(conditions_sha256="ABC"), "64 lowercase hex"),
        (lambda d: _jig(d).update(conditions_sha256="B" * 64), "64 lowercase hex"),
        (lambda d: _jig(d).pop("rollouts_expected"), "missing key 'rollouts_expected'"),
        (lambda d: _jig(d).update(rollouts_expected=0), "rollouts_expected: must be positive"),
        (lambda d: _jig(d).pop("scorer_version"), "missing key 'scorer_version'"),
        (
            lambda d: _jig(d)["runs"][0].pop("bootstrap_seed"),
            "runs 'M': missing key 'bootstrap_seed'",
        ),
        (lambda d: _jig(d)["runs"][1].update(bootstrap_seed="x"), "bootstrap_seed: expected int"),
        (lambda d: _jig(d)["runs"][0].pop("train"), "runs 'M': missing key 'train'"),
        (lambda d: _jig(d)["runs"][0].pop("outcome"), "missing key 'outcome'"),
        (lambda d: _jig(d)["runs"][1].pop("results_cmd"), "runs 'N': missing key 'results_cmd'"),
        (lambda d: _jig(d).pop("rules"), "rules: missing"),
        (lambda d: _jig(d)["rules"].update(whole_task=80), "whole_task: expected a number"),
        (lambda d: _jig(d)["rules"].update(per_level=0), "per_level: expected a number"),
        (lambda d: _jig(d)["rules"].update(place="half"), "place: expected a number"),
        (lambda d: _jig(d)["rules"].update(read_at="point"), "read_at: expected 'lower_bound'"),
        (lambda d: _jig(d)["rules"]["source"].pop("vi"), "rules.source: needs a non-empty 'vi'"),
        (lambda d: _jig(d).update(controls=["X"]), "'X' is not one of its runs"),
    ],
)
def test_manifest_errors_name_the_rule(fw: ConsolePaths, edit: Any, message: str) -> None:
    data = copy.deepcopy(_raw(fw))
    edit(data)
    with pytest.raises(tasks.ManifestError, match=message.replace("[", r"\[").replace("]", r"\]")):
        tasks.parse(data)


def test_build_resolves_totals_evals_and_clusters(fw: ConsolePaths, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    rows = [
        {"id": "a", "task": "two_table", "group": "teleop", "episodes": 99, "hours": 0.3,
         "unique": True},
        {"id": "b", "task": "two_table", "group": "eval", "episodes": 30, "unique": False},
        {"id": "c", "task": "tray", "group": "s1", "episodes": 500, "hours": 1.0, "unique": True},
    ]  # fmt: skip
    (out / "catalog.json").write_text(json.dumps({"rows": rows}))
    two = tasks.load(fw).task("two_table").raw
    summary = fw.fw_root / two["evals"][0]["fw"]
    summary.parent.mkdir(parents=True)
    summary.write_text(json.dumps({"n": 10, "successes": 6, "level": 0}))
    counts = tasks.build(fw, out)
    doc = json.loads((out / "tasks.json").read_text())
    assert counts == {"tasks": 2, "rounds": 2}
    t2 = next(t for t in doc["tasks"] if t["id"] == "two_table")
    assert t2["catalog_totals"]["all"]["episodes"] == 99
    assert t2["evals"][0]["successes"] == 6 and t2["evals"][0]["origin"] == "file"
    cl = t2["clusters"]
    assert cl["origin"] == "cited" and [c["id"] for c in cl["items"]] == ["A", "B", "C"]
    assert cl["diagnosis"] == "unknown" and all(c["quote"] for c in cl["items"])
    tray = next(t for t in doc["tasks"] if t["id"] == "tray")
    assert tray["catalog_totals"]["all"]["episodes"] == 500 and tray["evals"] == []
    roles = {r["id"]: r["role"] for r in doc["rounds"][0]["runs"]}
    assert roles[doc["rounds"][0]["baseline"]] == "baseline"
    jig = _jig(doc)
    assert [(r["id"], r["role"]) for r in jig["runs"]] == [("M", "baseline"), ("N", "after_round")]
    assert jig["rules"]["whole_task"] == 0.8 and jig["controls"] == []


def test_build_without_summary_gives_no_number(fw: ConsolePaths, tmp_path: Path) -> None:
    out = tmp_path / "out"
    tasks.build(fw, out)  # no catalog.json, no summary file
    doc = json.loads((out / "tasks.json").read_text())
    t2 = next(t for t in doc["tasks"] if t["id"] == "two_table")
    assert t2["evals"][0]["n"] is None and t2["evals"][0]["origin"] is None
    assert t2["catalog_totals"] == {}

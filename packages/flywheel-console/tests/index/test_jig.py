"""``story.json · jig`` (story DA-53): copy results.json, check before reading, read the rules.

The fixtures are the ``results.json`` of runs M and N written by
``flywheel_psi0.tray.eval_results --repeats 3 --json`` (M with ``--bootstrap-seed 20261125``,
N with ``--bootstrap-seed 20261126 --baseline`` M's eval), public sim data.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from flywheel.console.index import jig, story, tasks
from flywheel.console.paths import ConsolePaths

FIX = Path(__file__).parent / "fixtures" / "jig"
SHA = "bbec07e31ee022ac46d59e5322628c226519abe76363160ccbdb78b68725d348"
STEPS = ("approach_a", "grasp", "lift", "carry", "reach_b", "place", "release_stand")


def _results(name: str) -> dict[str, Any]:
    doc = json.loads((FIX / f"results-{name.lower()}.json").read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    return doc


def _round(fw: ConsolePaths) -> tasks.Round:
    return tasks.load(fw).round("tray-jig-r1")


def _put(fw: ConsolePaths, run: str, doc: dict[str, Any] | None = None) -> None:
    folder = fw.fw_root / f"tray/outcomes/jig-{run.lower()}-100000-r3"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "results.json").write_text(json.dumps(doc if doc is not None else _results(run)))


def _set(fw: ConsolePaths, sha: str = SHA) -> None:
    folder = fw.fw_root / "tray/eval-sets/jig-m-rp_a410d01efa62"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "conditions.sha256").write_text(sha + "\n")


def _block(fw: ConsolePaths, rnd: tasks.Round | None = None) -> dict[str, Any]:
    return jig.build(fw.fw_root, rnd or _round(fw), [], [], {}, STEPS, [])


def _eval(block: dict[str, Any], run: str) -> dict[str, Any]:
    return next(e for e in block["evals"] if e["run"] == run)


def _verdicts(ev: dict[str, Any]) -> list[tuple[str, str | None, str | None]]:
    return [(r["rule"], r.get("level"), r["verdict"]) for r in ev["readings"]]


def test_m_numbers_are_copied_from_results_json(fw: ConsolePaths) -> None:
    _set(fw)
    _put(fw, "M")
    ev = _eval(_block(fw), "M")
    src = _results("M")
    assert ev["status"] == "ready" and ev["problems"] == [] and ev["role"] == "baseline"
    assert ev["results_source"] == "fwdata/tray/outcomes/jig-m-100000-r3/results.json"
    h, lv = ev["headline"], ev["levels"]
    # docs/he/tray-jig.md §5: 136/180, level 1 77/90, level 2 59/90, place 161/180
    assert (h["successes"], h["n"], h["conditions"]) == (136, 180, 60)
    assert (lv["1"]["successes"], lv["1"]["n"]) == (77, 90)
    assert (lv["2"]["successes"], lv["2"]["n"]) == (59, 90)
    assert (ev["place"]["successes"], ev["place"]["n"], ev["place"]["ci"]) == (161, 180, None)
    # intervals copied verbatim, never recomputed
    assert h["ci"] == src["headline"]["ci"] == [0.7, 0.8111111111111112]
    assert lv["1"]["ci"] == src["levels"]["1"]["ci"] and lv["2"]["ci"] == src["levels"]["2"]["ci"]
    assert h["wilson"] == src["headline"]["wilson"] and h["p"] == src["headline"]["p"]
    assert (ev["bootstrap_seed"], ev["scorer_version"]) == (20261125, 2)
    assert ev["plan_mismatch"] == src["plan_mismatch"]


def test_m_readings_follow_the_rules(fw: ConsolePaths) -> None:
    _set(fw)
    _put(fw, "M")
    ev = _eval(_block(fw), "M")
    # tray-jig.md §5: below 80 % for the task, level 1 at 70 %, level 2 below; place no reading
    assert _verdicts(ev) == [
        ("1", None, "not_met"), ("2", "1", "met"), ("2", "2", "not_met"), ("3", None, None)
    ]  # fmt: skip
    one, l1, _, place = ev["readings"]
    assert (one["threshold"], one["lower"]) == (0.8, 0.7) and l1["threshold"] == 0.7
    assert place["why"] == "no_ci" and place["threshold"] == 0.5


def test_lower_bound_equal_to_the_threshold_is_met(fw: ConsolePaths) -> None:
    _set(fw)
    doc = _results("M")
    doc["headline"]["ci"] = [0.8, 0.9]
    _put(fw, "M", doc)
    assert _verdicts(_eval(_block(fw), "M"))[0] == ("1", None, "met")


def test_missing_results_gives_the_command_and_no_number(fw: ConsolePaths) -> None:
    _set(fw)
    block = _block(fw)
    ev = _eval(block, "M")
    rnd = _round(fw)
    assert ev["status"] == "missing" and ev["command"] == rnd.runs[0].results_cmd
    assert "headline" not in ev and "readings" not in ev and "place" not in ev
    assert block["featured"] is None
    assert block["paired"]["status"] == "missing" and "--baseline" in block["paired"]["command"]


def _blocked(fw: ConsolePaths, problem: str) -> None:
    ev = _eval(_block(fw), "M")
    assert ev["status"] == "blocked" and problem in ev["problems"]
    assert ev["headline"]["successes"] == 136  # the numbers stay, the readings go
    assert all(r["verdict"] is None and r["why"] == "blocked" for r in ev["readings"])


def test_missing_rollouts_block_the_readings(fw: ConsolePaths) -> None:
    _set(fw)
    doc = _results("M")
    doc["rollouts"] = 179
    _put(fw, "M", doc)
    _blocked(fw, "rollouts 179 != 180")
    doc["rollouts"], doc["missing"] = 180, [[2, 1000129, 2]]
    _put(fw, "M", doc)
    _blocked(fw, "missing rollouts")


def test_wrong_conditions_sha_blocks_the_readings(fw: ConsolePaths) -> None:
    _set(fw, "0" * 64)
    _put(fw, "M")
    _blocked(fw, "conditions.sha256 mismatch")
    assert _block(fw)["eval_set"]["sha_ok"] is False


def test_absent_conditions_sha_blocks_the_readings(fw: ConsolePaths) -> None:
    _put(fw, "M")
    _blocked(fw, "conditions.sha256 absent")


def test_wrong_bootstrap_seed_blocks_the_readings(fw: ConsolePaths) -> None:
    _set(fw)
    doc = _results("M")
    doc["bootstrap_seed"] = 20261103
    _put(fw, "M", doc)
    _blocked(fw, "bootstrap_seed 20261103 != 20261125")


def test_wrong_scorer_version_blocks_the_readings(fw: ConsolePaths) -> None:
    _set(fw)
    doc = _results("M")
    doc["scorer_version"] = 1
    _put(fw, "M", doc)
    _blocked(fw, "scorer_version 1 != 2")


def test_n_against_m_reads_rules_n2_and_n3(fw: ConsolePaths) -> None:
    _set(fw)
    _put(fw, "M")
    _put(fw, "N")
    block = _block(fw)
    assert [e["status"] for e in block["evals"]] == ["ready", "ready"]
    assert block["featured"] == "N"
    p = block["paired"]
    src = _results("N")["paired"]["repeats"]
    assert (p["status"], p["variant"], p["baseline"]) == ("ready", "N", "M")
    assert p["headline"] == src["headline"] and p["by_level"] == src["by_level"]
    assert p["headline"]["ci"] == [-0.1444, 0.0111]
    assert [(r["rule"], r.get("level"), r["verdict"]) for r in p["readings"]] == [
        ("n2", None, "not_distinguished"), ("n3", "2", "not_distinguished")
    ]  # fmt: skip
    assert p["readings"][0]["diff"] == -0.0667 and p["readings"][1]["ci"] == [-0.0333, 0.2111]


def test_paired_is_missing_without_n_results(fw: ConsolePaths) -> None:
    _set(fw)
    _put(fw, "M")
    block = _block(fw)
    assert block["featured"] == "M"
    assert block["paired"]["status"] == "missing" and "headline" not in block["paired"]


def test_paired_is_missing_when_n_was_read_without_baseline(fw: ConsolePaths) -> None:
    _set(fw)
    _put(fw, "M")
    doc = _results("N")
    doc.pop("paired")
    _put(fw, "N", doc)
    assert _block(fw)["paired"]["status"] == "missing"


def test_paired_is_blocked_when_a_side_is_blocked(fw: ConsolePaths) -> None:
    _set(fw)
    doc = _results("M")
    doc["rollouts"] = 179
    _put(fw, "M", doc)
    _put(fw, "N")
    p = _block(fw)["paired"]
    assert p["status"] == "blocked" and "M: rollouts 179 != 180" in p["problems"]
    assert all(r["verdict"] is None for r in p["readings"])


def test_withheld_run_gives_status_only(fw: ConsolePaths) -> None:
    _set(fw)
    _put(fw, "M")
    _put(fw, "N")
    raw = copy.deepcopy(_round(fw).raw)
    raw["withhold_eval"] = ["N"]
    rnd = tasks._round(raw, 0)
    block = _block(fw, rnd)
    assert _eval(block, "N") == {"run": "N", "role": "after_round", "status": "withheld"}
    assert block["paired"] == {"variant": "N", "baseline": "M", "status": "withheld"}
    assert block["featured"] == "M"


def test_outcome_rows_are_descriptive(fw: ConsolePaths) -> None:
    folder = fw.fw_root / "tray/outcomes/jig-m-100000-r3"
    folder.mkdir(parents=True)
    scores = [
        {"episode_id": f"M/l1-s{s}", "success": ok, "level": 1,
         "step_status": ["pass"] * 7 if ok else ["pass"] * 6 + ["fail"],
         "failure_kind": None if ok else "L-PLACE-POSE", "scorer_version": "simple-tray@2"}
        for s, ok in ((1000100, True), (1000100, False), (1000100, True))
    ]  # fmt: skip
    outcomes = [{"seed": 1000100, "level": 1, "repeat": k} for k in range(3)]
    (folder / "scores.jsonl").write_text("\n".join(json.dumps(r) for r in scores))
    (folder / "outcomes.jsonl").write_text("\n".join(json.dumps(r) for r in outcomes))
    block = _block(fw)
    row = block["outcomes"][0]
    assert (row["run"], row["n"], row["successes"], row["repeat_dist"]) == (
        "M",
        3,
        2,
        {"1": [0, 1, 0, 0]},
    )
    assert "wilson" not in row and "wilson" not in row["levels"]["1"]
    assert [r["run"] for r in block["rollouts"]] == ["M"] * 3
    assert block["conditions"][0]["pass_k"] == 2


def test_story_carries_the_jig_round(fw: ConsolePaths, tmp_path: Path) -> None:
    _set(fw)
    _put(fw, "M")
    job = fw.fw_root / "tray/jig-m/da48-ft-m-s0"
    job.mkdir(parents=True)
    rows = [{"split": "train", "step": s, "loss": 0.1} for s in (0, 50_000, 100_000)]
    (job / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    (job / "vm-logs").mkdir()
    report = {"phases": {"train": {"seconds": 100.0}, "persist": {"seconds": 130.0}}}
    (job / "vm-logs/report.json").write_text(json.dumps(report))
    out = tmp_path / "out"
    story.build(fw, out)
    d = json.loads((out / "story.json").read_text())
    j = d["jig"]
    assert j["round"] == "tray-jig-r1" and j["scene"] == "jig2" and j["rules"]["place"] == 0.5
    assert [r["branch"] for r in j["runs"]] == ["M"] and d["runs"] == []
    assert j["vm_phases"] == {"train": 100.0, "persist": 30.0}  # N has no log: falls back to M
    assert _eval(j, "M")["status"] == "ready" and _eval(j, "N")["status"] == "missing"
    text = json.dumps(j, ensure_ascii=False)
    assert "tốt hơn" not in text and "better than" not in text


def test_no_jig_round_gives_an_empty_block(fw: ConsolePaths) -> None:
    assert jig.build(fw.fw_root, None, [], [], {}, STEPS, []) == {}

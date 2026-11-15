from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel.console.index import cited, story
from flywheel.console.paths import ConsolePaths

KEYS = {
    "runs", "train_log_tail", "vm_phases", "sources", "heat", "reasons", "qa_sample", "h1m",
    "ledger", "colab_balance", "colab_sessions", "ds", "eval",
}  # fmt: skip


def test_downsample_cap() -> None:
    pts = [(float(i), float(i * 2)) for i in range(100_000)]
    out = story.downsample(pts)
    assert len(out) <= 2000
    assert out[0] == pts[0] and out[-1] == pts[-1]
    assert story.downsample(pts[:10]) == pts[:10]


def _real(fw: ConsolePaths) -> ConsolePaths:
    # the packaged seed and docs come from the real repo checkout
    repo = Path(__file__).resolve().parents[4]
    return ConsolePaths(repo=repo, fw_root=fw.fw_root)


def test_story_keys(fw: ConsolePaths, tmp_path: Path) -> None:
    out = tmp_path / "out"
    story.build(fw, out)
    data = json.loads((out / "story.json").read_text())
    assert KEYS <= set(data)
    assert data["runs"] == [] and data["colab_balance"] == [] and data["h1m"] == {}


def test_story_reads_runs_and_sources(fw: ConsolePaths, tmp_path: Path) -> None:
    run = fw.fw_root / "tray/pair60k/C_70/job1"
    run.mkdir(parents=True)
    rows = [
        {"split": "train", "step": i, "loss": 1.0, "loss_by_group": {"g": 2.0}} for i in range(5)
    ]
    (run / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
    (run / "launch.json").write_text(json.dumps({"argv": ["a"]}))
    src = fw.fw_root / "pipeline/src_0123456789abcdef"
    (src / "report").mkdir(parents=True)
    (src / "qa").mkdir()
    (src / "source.json").write_text(json.dumps({"name": "x", "data_class": "public"}))
    (src / "report/egocentric.json").write_text(
        json.dumps({"episodes": 1, "decisions": {"pass": 1}, "checks": {"c": {"flag": 2}}})
    )
    (src / "qa/egocentric.jsonl").write_text(
        json.dumps({"episode_id": "e1", "reasons": ["bad:why"]}) + "\n"
    )
    out = tmp_path / "out"
    story.build(fw, out)
    d = json.loads((out / "story.json").read_text())
    assert d["runs"][0]["job"] == "job1" and d["runs"][0]["groups_last"] == {"g": 2.0}
    assert d["sources"][0]["id"] == "01234567" and d["heat"] == [["c", "01234567", 2]]
    assert d["reasons"] == [["bad", 1, ["e1"]]]


def test_story_eval_from_cited(fw: ConsolePaths, tmp_path: Path) -> None:
    paths = _real(fw)
    out = tmp_path / "out"
    story.build(paths, out)
    data = json.loads((out / "story.json").read_text())
    assert data["eval"] == json.loads(json.dumps(cited.eval_block(paths)))
    assert data["loop_chain"] == [240, 131, 262, 229, 177]


def test_story_ds_is_catalog(fw: ConsolePaths, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "catalog.json").write_text(json.dumps({"generated": "g", "rows": [{"id": "a"}]}))
    story.build(fw, out)
    assert json.loads((out / "story.json").read_text())["ds"]["rows"] == [{"id": "a"}]


@pytest.mark.parametrize("n", [0, 1, 2])
def test_downsample_tiny(n: int) -> None:
    pts = [(float(i), 0.0) for i in range(n)]
    assert story.downsample(pts, 2000) == pts


def test_story_carries_every_number_the_loop_page_shows(fw: ConsolePaths, tmp_path: Path) -> None:
    out = tmp_path / "out"
    story.build(_real(fw), out)
    data = json.loads((out / "story.json").read_text())
    assert data["loop_chain"] == [240, 131, 262, 229, 177]
    assert data["loop_detail"] == {"qa_pass": 226, "in_cut": 160}


def _stage1(folder: Path, stem: str, succ: int, paired: dict | None = None, out: str = "F") -> None:
    h = {
        "n": 60, "successes": succ, "p": succ / 60, "wilson": [0.01, 0.2],
        "failures": {"L-TIMEOUT": 1, "L-PLACE-POSE": 9},
        "step_pass": {"approach_a": 0.8, "place": 0.2},
    }  # fmt: skip
    doc = {"headline": h, "levels": {"1": {"n": 30, "successes": succ}}, "stage1": {"outcome": out}}
    if paired:
        doc["paired"] = {"headline": paired}
    (folder / f"{stem}.json").write_text(json.dumps(doc))


def test_pair_reads_stage1_files(fw: ConsolePaths) -> None:
    folder = fw.fw_root / "tray/pair60k/stage1-60k"
    folder.mkdir(parents=True)
    _stage1(folder, "stage1-C_ALL-table", 5, {"variant": 5, "baseline": 10})
    _stage1(folder, "stage1-g-C_70-vs-C_ALL", 10, {"variant": 10, "baseline": 5}, "continue")
    _stage1(folder, "stage1-r-C70_R1-vs-C_70", 4, {"variant": 4, "baseline": 10, "diff": -0.1})
    _stage1(folder, "stage1-r-C70_R1-vs-C_ALL", 99, {"variant": 4, "baseline": 5})
    (folder / "stage1-broken.json").write_text("{not json")
    (folder / "place-error-C_70.json").write_text("{}")
    d = story._pair(fw.fw_root)
    assert [r["run"] for r in d["runs"]] == ["C_ALL", "C_70", "C70_R1"]
    assert d["best"] == "C_70" and d["steps"] == ["approach_a", "place"]
    r1 = d["runs"][2]
    assert r1["successes"] == 4  # the first file naming a run wins
    assert list(r1["failures"]) == ["L-PLACE-POSE", "L-TIMEOUT"]
    assert r1["levels"] == {"1": {"n": 30, "successes": 4}}
    # the table file has no named baseline, so it gives no comparison
    pairs = [(c["variant"], c["baseline"], c["outcome"]) for c in d["comparisons"]]
    assert pairs == [
        ("C_70", "C_ALL", "continue"),
        ("C70_R1", "C_70", "F"),
        ("C70_R1", "C_ALL", "F"),
    ]
    assert d["comparisons"][1]["variant_succ"] == 4 and d["comparisons"][1]["diff"] == -0.1


def test_pair_and_round_in_story(fw: ConsolePaths, tmp_path: Path) -> None:
    out = tmp_path / "out"
    story.build(fw, out)  # empty FW_ROOT and the packaged seed
    data = json.loads((out / "story.json").read_text())
    assert data["pair"] == {}
    assert data["round"]["chain"]["selected"] == 181


def test_follow_reads_one_trial_across_runs(fw: ConsolePaths) -> None:
    folder = fw.fw_root / "tray/pair60k/stage1-60k"
    folder.mkdir(parents=True)
    tol = {"distance_m": 0.05, "yaw_error_deg": 10.0}
    rows = [
        {"level": 1, "seed": 1000106, "success": True, "distance_m": 0.01, "yaw_error_deg": 1.0},
        {"level": 1, "seed": 1000107, "success": False, "failure": "L-PLACE-POSE", "reach_b": True,
         "distance_m": 0.0704, "yaw_error_deg": 16.32, "in_tolerance": False},
        {"level": 2, "seed": 1000107, "success": True, "distance_m": 0.02, "yaw_error_deg": 2.0},
    ]  # fmt: skip
    (folder / "place-error-C_70.json").write_text(json.dumps({"tolerance": tol, "rows": rows}))
    one = {
        "level": 1,
        "seed": 1000107,
        "success": True,
        "reach_b": False,
        "distance_m": 0.04,
        "yaw_error_deg": 7.5,
    }
    (folder / "place-error-B_ALL.json").write_text(json.dumps({"tolerance": tol, "rows": [one]}))
    (folder / "place-error-broken.json").write_text("{not json")
    r3 = {"C_70": {"n": 60, "got": [0, 23], "rest": [10, 37]}}
    (folder / "r3.json").write_text(json.dumps(r3))
    d = story._follow(fw.fw_root)
    assert (d["level"], d["seed"]) == (1, 1000107) and d["tol"] == tol
    assert set(d["runs"]) == {"C_70", "B_ALL"}
    assert (
        d["runs"]["C_70"]["distance_m"] == 0.0704 and d["runs"]["C_70"]["failure"] == "L-PLACE-POSE"
    )
    assert d["runs"]["B_ALL"]["reach_b"] is False
    assert d["r3"]["C_70"]["got"] == [0, 23]


def test_follow_is_empty_without_the_folder(fw: ConsolePaths) -> None:
    assert story._follow(fw.fw_root) == {}

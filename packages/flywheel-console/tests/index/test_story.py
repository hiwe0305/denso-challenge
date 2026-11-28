from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from flywheel.console.index import cited, story, tasks
from flywheel.console.paths import ConsolePaths

KEYS = {
    "runs", "train_log_tail", "vm_phases", "sources", "heat", "reasons", "qa_sample", "h1m",
    "ledger", "colab_balance", "colab_sessions", "ds", "eval",
}  # fmt: skip


def _round(fw: ConsolePaths) -> tasks.Round:
    rnd = tasks.load(fw).story_round()
    assert rnd is not None
    return rnd


def _ev(rnd: tasks.Round) -> str:
    assert rnd.eval_dir is not None  # a story.pair round always names it
    return rnd.eval_dir


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
    rnd = _round(fw)
    d = story._pair(fw.fw_root, _ev(rnd), rnd.run_ids)
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
    rnd = _round(fw)
    d = story._follow(fw.fw_root, _ev(rnd), rnd.follow)
    assert (d["level"], d["seed"]) == (1, 1000107) and d["tol"] == tol
    assert set(d["runs"]) == {"C_70", "B_ALL"}
    assert (
        d["runs"]["C_70"]["distance_m"] == 0.0704 and d["runs"]["C_70"]["failure"] == "L-PLACE-POSE"
    )
    assert d["runs"]["B_ALL"]["reach_b"] is False
    assert d["r3"]["C_70"]["got"] == [0, 23]


def test_follow_is_empty_without_the_folder(fw: ConsolePaths) -> None:
    rnd = _round(fw)
    assert story._follow(fw.fw_root, _ev(rnd), rnd.follow) == {}
    assert story._follow(fw.fw_root, _ev(rnd), None) == {}


# ------------------------------------------------------------------ DA-53: per-run train folders
def _metrics(job: Path, last: int = 100_000, every: int = 10_000) -> None:
    job.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for step in range(0, last + 1, every):
        rows.append(
            {"split": "train", "step": step, "loss": 1.0 - step / 200_000, "throughput": 21.5,
             "vram_gb": 17.0, "grad_norm_action": 0.5, "release_id": "M", "run_plan_id": "rp_x"}
        )  # fmt: skip
        rows.append({"split": "val", "step": step, "loss": 0.25})
    (job / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def _open_jig_round(fw: ConsolePaths) -> tasks.Round:
    """The seed's jig round without ``withhold_runs`` (run N shown), so the code stays tested."""
    raw = copy.deepcopy(tasks.load(fw).round("tray-jig-r1").raw)
    raw.pop("withhold_runs", None)
    return tasks._round(raw, 0)


def test_round_runs_name_the_jig_run_by_its_manifest_id(fw: ConsolePaths) -> None:
    rnd = _open_jig_round(fw)
    root = fw.fw_root
    _metrics(root / "tray/jig-m/da48-ft-m-s0")
    stats = {"episode_index": {"max": [1036]}, "index": {"max": [948638]}}
    (root / "tray/jig-m/M-stats_psi0.json").write_text(json.dumps(stats))
    _metrics(root / "tray/jig-n/da50-ft-n-s0", last=8000, every=1000)  # copy stopped early
    (root / "tray/jig-n/da50-ft-n-s0/fetched.json").write_text(
        json.dumps({"final": False, "train": "running", "progress": {"step": 8198}})
    )
    runs, dirs = story.round_runs(root, rnd)
    m, n = runs
    assert [r["branch"] for r in runs] == ["M", "N"] and dirs[0].name == "da48-ft-m-s0"
    assert (m["step"], m["max_steps"], m["scene"]) == (100_000, 100_000, "jig2")
    assert m["loss_last"] == round(
        sum(1.0 - s / 200_000 for s in range(0, 100_001, 10_000)) / 11, 3
    )
    assert m["loss"][-1] == [100_000, 0.5] and m["val"][-1] == [100_000, 0.25]
    assert m["thr"][0] == [0, 21.5] and m["vram"][0] == [0, 17.0] and m["gn"][0] == [0, 0.5]
    assert (m["episodes"], m["frames"]) == (1037, 948639)
    assert (m["fetched_final"], m["fetched_train"], m["fetched_step"]) == (None, None, None)
    assert n["fetched_train"] == "running"
    assert (n["step"], n["max_steps"], n["fetched_final"], n["fetched_step"]) == (
        8000,
        100_000,
        False,
        8198,
    )


def test_story_runs_leave_out_the_jig_folders(fw: ConsolePaths, tmp_path: Path) -> None:
    _metrics(fw.fw_root / "tray/pair60k/C_70/job1", last=100, every=50)
    _metrics(fw.fw_root / "tray/jig-m/da48-ft-m-s0")
    out = tmp_path / "out"
    story.build(fw, out)
    d = json.loads((out / "story.json").read_text())
    assert [r["branch"] for r in d["runs"]] == ["C_70"]


# report.json of C_70 (fwdata/tray/pair60k/C_70/da34-t6-ft-c-70-s0/vm-logs/report.json)
C70_REPORT = {
    "phases": {
        "setup_tray_c_70": {"seconds": 119.3},
        "train": {"seconds": 38049.2},
        "persist": {"seconds": 38262.6},
    }
}


def test_persist_phase_is_the_sync_after_training(fw: ConsolePaths, tmp_path: Path) -> None:
    assert story._phase_seconds(C70_REPORT) == {
        "setup_tray_c_70": 119.3, "train": 38049.2, "persist": 213.4
    }  # fmt: skip
    short = {"phases": {"train": {"seconds": 50.0}, "persist": {"seconds": 20.0}}}
    assert story._phase_seconds(short) == {"train": 50.0, "persist": 20.0}  # raw when < train
    assert story._phase_seconds({"phases": {"setup_tray_n": {"seconds": 43.0}}}) == {
        "setup_tray_n": 43.0
    }
    job = fw.fw_root / "tray/pair60k/C_70/da34-t6-ft-c-70-s0"
    _metrics(job, last=100, every=50)
    (job / "vm-logs").mkdir()
    (job / "vm-logs/report.json").write_text(json.dumps(C70_REPORT))
    out = tmp_path / "out"
    story.build(fw, out)
    d = json.loads((out / "story.json").read_text())
    assert d["vm_phases"]["persist"] == 213.4 and d["vm_phases"]["train"] == 38049.2
    assert d["runs"][0]["vm_phases"]["persist"] == 213.4

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flywheel.console.index import cited, demo, story
from flywheel.console.paths import ConsolePaths

REPO = Path(__file__).resolve().parents[4]


def _groups() -> dict[str, dict[str, dict[str, Any]]]:
    return cited.demo_groups(ConsolePaths(repo=REPO, fw_root=REPO / "fwdata"))


def _curve(*succ: int) -> list[dict[str, Any]]:
    tols = (0.05, 0.075, 0.1, 0.15, 0.2)
    return [
        {"distance_m": t, "yaw_error_deg": 10.0, "n": 60, "relaxed_successes": s}
        for t, s in zip(tols, succ, strict=True)
    ]


def _place_error(folder: Path, run: str, succ: tuple[int, ...], max_m: float = 0.16) -> None:
    doc = {
        "relaxed_curve": {"levels 1-2": _curve(*succ)},
        "groups": {"levels 1-2, L-PLACE-POSE": {"n": 3, "distance_m": [0.05, 0.07, max_m]}},
    }
    (folder / f"place-error-{run}.json").write_text(json.dumps(doc))


PAIR = {
    "runs": [
        {"run": "C_ALL", "n": 60, "successes": 5,
         "failures": {"L-PLACE-POSE": 29, "L-TRAY-TILT": 15, "L-TIMEOUT": 11}},
        {"run": "C_70", "n": 60, "successes": 10,
         "failures": {"L-PLACE-POSE": 32, "L-TRAY-TILT": 10, "L-TIMEOUT": 8}},
        {"run": "C70_R1", "n": 60, "successes": 4,
         "failures": {"L-PLACE-POSE": 28, "L-TRAY-TILT": 15, "L-TIMEOUT": 13}},
    ],
    "steps": ["approach_a", "place"],
    "comparisons": [{"tag": "r", "variant": "C70_R1", "baseline": "C_ALL"},
                    {"tag": "g", "variant": "C_70", "baseline": "C_ALL"}],
}  # fmt: skip


def test_ladder_reads_relaxed_curve_and_cited_row(tmp_path: Path) -> None:
    folder = tmp_path / "tray/pair60k/stage1-60k"
    folder.mkdir(parents=True)
    _place_error(folder, "C_70", (10, 14, 19, 23, 23))
    _place_error(folder, "C70_R1", (4, 15, 16, 19, 19))
    rows = [{"on_table_b": True}] * 3 + [{"on_table_b": False}]
    (folder / "c70r1-rollouts.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    cites = {"on_table_b": {"value": {"C_70": 50, "C70_R1": 49}, "source": "s", "quote": "q"}}
    d = demo.ladder(tmp_path, PAIR, cites)
    assert d["relaxed_cm"] == ["20", "15", "10", "7.5", "5"]
    assert d["rows"] == ["on_table_b", "20", "15", "10", "7.5", "success"]
    assert d["n"] == 60 and d["yaw_tol_deg"] == 10.0
    assert d["runs"]["C_70"]["relaxed"]["7.5"] == 14 and d["runs"]["C_70"]["success"] == 10
    assert d["runs"]["C70_R1"]["on_table_b"] == 49
    # C_ALL has a stage-1 headline but no place-error file: kept, empty curve
    assert d["runs"]["C_ALL"] == {"on_table_b": None, "relaxed": {}, "success": 5}
    assert d["on_table_b"]["check_from_rollouts"] == {"C70_R1": 3}
    assert d["omitted"] and "B_ALL" not in d["runs"]


def test_ladder_empty_without_inputs(tmp_path: Path) -> None:
    assert demo.ladder(tmp_path, {}, {}) == {}


def test_round1_checks_max_error_against_file(tmp_path: Path) -> None:
    folder = tmp_path / "tray/pair60k/stage1-60k"
    folder.mkdir(parents=True)
    _place_error(folder, "C_70", (1, 1, 1, 1, 1), 0.1614)
    _place_error(folder, "C70_R1", (1, 1, 1, 1, 1), 0.1265)
    d = demo.round1(tmp_path, _groups()["round1"])
    assert d["max_place_error_cm"]["value"] == {"C_70": 16.1, "C70_R1": 12.7}
    assert d["max_place_error_cm"]["check_from_file"] == {"C_70": 16.14, "C70_R1": 12.65}
    assert d["tilt_at_place"]["value"] == {"C_70": 4, "C70_R1": 8}
    assert d["relaxed_7_5cm"]["value"] == {"C_70": 14, "C70_R1": 15}
    assert d["rule_r1"]["value"]["outcome"] == "F" and d["stop"]["value"]["stop"] is True
    assert demo.round1(tmp_path, {}) == {}


def test_qa_bench_code_and_agent_layers() -> None:
    d = demo.qa_bench(_groups()["qa"])
    code = d["code_layer"]
    assert (code["caught"], code["planted"], code["false_alarms"], code["clean_units"]) == (
        30, 30, 0, 40,
    )  # fmt: skip
    assert code["date"] == "5/11/2026" and len(code["cites"]) == 5
    agent = d["agent_layer_nemotron"]["value"]
    assert (agent["false_alarms"], agent["date"]) == (1, "12/11/2026")
    assert d["psi_data_bench"]["value"]["planted"] == 33
    assert d["psi_data_bench"]["value"]["scored"] is False


def test_fail_share_base_models_only() -> None:
    d = demo.fail_share(PAIR)
    assert set(d["runs"]) == {"C_ALL", "C_70"}
    assert d["runs"]["C_ALL"]["failed"] == 55 and d["runs"]["C_ALL"]["share"] == 0.8
    assert d["runs"]["C_70"]["share"] == 0.84
    assert (d["min"], d["max"]) == (0.8, 0.84)
    assert demo.fail_share({}) == {}


def test_diagnose_splits_clusters_by_ticket() -> None:
    rnd = {
        "clusters": [
            {"id": "c1", "intervention": "sinh quanh lỗi"},
            {"id": "c4", "intervention": "phiếu DA-38"},
            {"id": "c6", "intervention": "phiếu DA-37"},
            {"id": "c7", "intervention": "phiếu DA-37"},
        ]
    }
    d = demo.diagnose(rnd, _groups()["diagnose"])
    assert d["to_data"] == ["c1"]
    assert d["tickets"] == {"DA-38": ["c4"], "DA-37": ["c6", "c7"]}
    assert [c["id"] for c in d["checks"]] == ["H1", "H2", "H3", "delay_sync_camera"]
    assert d["cost_cu"]["value"] == 0


def test_round_cost_lines_and_rate() -> None:
    d = demo.round_cost(_groups()["cost"])
    assert [x["id"] for x in d["lines"]] == ["train_1", "train_2", "serve"]
    assert d["total_cu"] == round(8.55 + 77.27 + 23.4, 2)
    assert d["usd_per_cu"] == 0.0999 and d["total_usd"] == round(d["total_cu"] * 0.0999, 2)
    assert demo.round_cost({}) == {}


def _session(batch: Path, name: str, gpu: str, events: list[dict[str, Any]]) -> None:
    (batch / f"{name}.json").write_text(json.dumps({"gpu": gpu}))
    (batch / f"{name}.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\nbad\n")


def test_design_reads_watcher_sessions(tmp_path: Path) -> None:
    batch = tmp_path / "colab/batch-1"
    batch.mkdir(parents=True)
    ended = {"event": "exit", "reason": "ended", "wall_cu": 77.4}
    _session(batch, "da34-c-all", "A100", [{"event": "signal"}, ended])
    _session(batch, "da34-b-all", "A100", [{"event": "signal"}])  # no finished run
    _session(
        batch, "da34-serve-c-70", "L4", [{"event": "exit", "reason": "signal", "wall_cu": 11.0}]
    )
    _session(batch, "da34-other", "T4", [ended])
    s = demo.colab_sessions(tmp_path)
    assert s["C_ALL"]["train"]["wall_cu"] == 77.4 and s["B_ALL"]["train"]["wall_cu"] is None
    assert s["C_70"]["serve"]["gpu"] == "L4"
    d = demo.design(tmp_path, PAIR, {"clips": 379, "exported": 317}, _groups()["design"])
    res = {x["id"]: x for x in d["resource"]}
    assert res["train_cu"]["per_model_cu"] == {"C_ALL": 77.4} and res["train_cu"]["gpu"] == ["A100"]
    assert res["test_cu"]["per_model_cu"] == {"C_70": 11.0}
    assert res["train_cu_estimate"]["kind"] == "estimated"
    assert res["gen_machine_hours"]["value"] == 1.83
    inp = {x["id"]: x for x in d["input"]}
    assert inp["human_clips"]["value"]["clips"] == 379
    assert inp["sim_episodes"]["value"]["episodes"] == 606
    dev = {x["id"]: x for x in d["devices"]}
    assert dev["colab_train_gpu"]["sessions_gpu"] == ["A100"]
    assert {"input", "output", "environment", "devices", "resource"} <= set(d)
    assert all(x.get("source") for k in ("input", "devices", "resource") for x in d[k])


def test_success_clip_needs_a_sidecar(tmp_path: Path) -> None:
    folder = tmp_path / "console/media/demo"
    folder.mkdir(parents=True)
    (folder / "a.mp4").write_bytes(b"x" * 10)
    assert demo.success_clip(tmp_path) == {}
    (folder / "a.json").write_text(json.dumps({"model": "C_70", "provenance": "deck"}))
    d = demo.success_clip(tmp_path)
    assert d["path"] == "console/media/demo/a.mp4" and d["bytes"] == 10 and d["model"] == "C_70"


def test_models_give_facts_not_names() -> None:
    d = demo.models(PAIR, _groups()["models"])
    r = d["runs"]
    assert (r["C_ALL"]["episodes"], r["C_70"]["episodes"], r["C70_R1"]["episodes"]) == (
        606,
        425,
        606,
    )
    assert r["C70_R1"]["targeted_episodes"] == 181 and r["C70_R1"]["round1"] is True
    assert r["B_70"]["human_video"] is True and r["C_70"]["human_video"] is False
    assert not any("name" in v for v in r.values())


def test_demo_block_in_story(fw: ConsolePaths, tmp_path: Path) -> None:
    out = tmp_path / "out"
    story.build(fw, out)  # empty FW_ROOT and the packaged seed
    d = json.loads((out / "story.json").read_text())["demo"]
    assert set(d) == {
        "source", "ladder", "round1_reading", "qa_bench", "fail_share", "diagnose",
        "design", "round_cost", "success_clip", "models",
    }  # fmt: skip
    assert d["fail_share"] == {} and d["success_clip"] == {}
    # no place-error files: the ladder carries only the cited "tray on table B" row
    assert d["ladder"]["runs"]["C_70"] == {"on_table_b": 50, "relaxed": {}, "success": None}
    assert d["qa_bench"]["code_layer"]["caught"] == 30
    assert d["diagnose"]["tickets"] == {"DA-38": ["c4", "c5"], "DA-37": ["c6", "c7"]}
    # every group that has content names its source
    assert all(v.get("source") for v in d.values() if isinstance(v, dict) and v)

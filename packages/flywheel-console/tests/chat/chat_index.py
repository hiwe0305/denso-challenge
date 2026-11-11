"""A tiny console index in tmp_path: catalog (S70, S1 alias), one run, one job, an ego dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from flywheel.console.paths import ConsolePaths, set_active


def wj(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), encoding="utf-8")


@pytest.fixture(name="idx")
def make_idx(fw: ConsolePaths) -> ConsolePaths:
    set_active(fw)
    ix = fw.index
    rows = [
        {"id": "tray_s1_41899efb4b27", "name": "tray_s1_41899efb4b27 (release)",
         "title": "Tray S1 release", "data_type": "synthetic S1", "task": "tray",
         "episodes": 541, "status": "current", "aliases": ["S1"], "parents": [],
         "children": ["ALL", "S70"], "qa": "534 pass / 7 reject"},
        {"id": "ALL", "name": "ALL (#ALL:113520c517a0)", "title": "Tray S1 ALL",
         "data_type": "synthetic S1", "task": "tray", "episodes": 606, "status": "current",
         "aliases": ["ALL"], "parents": ["tray_s1_41899efb4b27"], "children": [],
         "qa": "seed-hash"},
        {"id": "S70", "name": "S70 (#S70:8ab4e33b657f)", "title": "Tray S1 S70 cut",
         "data_type": "synthetic S1", "task": "tray", "episodes": 425, "frames": 603915,
         "hours": 3.355, "fps": 50, "status": "current", "aliases": ["S70"],
         "parents": ["tray_s1_41899efb4b27"], "children": [], "qa": "seed-hash 70% (301+124)"},
        {"id": "T1", "name": "T1 teleop", "title": "Teleop sample", "data_type": "teleop",
         "task": "two_table", "episodes": 13, "status": "current", "aliases": [],
         "parents": [], "children": [], "qa": "rule layer",
         "qa_counts": {"pass": 10, "flag": 2, "reject": 1}},
        {"id": "egx_aaaa1111", "name": "egx_aaaa1111", "title": "Ego sample",
         "data_type": "egocentric", "task": "two_table", "episodes": 3, "status": "current",
         "aliases": [], "qa": "rule layer"},
    ]  # fmt: skip
    wj(
        ix / "catalog.json",
        {
            "rows": rows,
            "edges": [["tray_s1_41899efb4b27", "ALL"], ["tray_s1_41899efb4b27", "S70"]],
            "runs": [],
        },
    )
    wj(ix / "story.json", {
        "ledger": [["DA-34", 12.0, 9.5]],
        "reasons": [["hand_out_of_frame", 2, ["ep_1"]]],
        "colab_sessions": [],
        "eval": {
            "policy": "C", "source": "cited",
            "levels": [{"level": "L1-2", "n": 240, "successes": 120, "steps_pct": [100, 90, 50]}],
            "stages": ["reach", "grasp", "place"],
            "failure_labels": {"L-PLACE-POSE": {"L0": 0, "L1": 30, "L2": 40}},
            "place_error_cm": {"L1": {"min": 1, "p10": 2, "p50": 4, "p90": 9, "max": 15}},
            "clusters": [{"label": "L-PLACE-POSE", "stage": "place", "diagnosis": "data",
                          "intervention": "targeted gen", "episodes": "262 → 229 → 177"}],
        },
    })  # fmt: skip
    wj(ix / "ds" / "S70" / "quality.json", {
        "hists": [], "failures": [["L-ONE-HAND", 18], ["L-DROP", 50]],
        "funnel": [["chạy", 606 + 68], ["thành công", 606]],
    })  # fmt: skip
    sim_ep = {
        "i": 0,
        "n": 1414,
        "s": 28.3,
        "lv": 1,
        "seed": 1028,
        "ok": True,
        "dist": 2.2,
        "out": "",
    }
    wj(ix / "ds" / "ALL" / "quality.json", {
        "hists": [], "failures": [["L-ONE-HAND", 18], ["L-DROP", 50]],
        "funnel": [["chạy", 606 + 68], ["thành công", 606]],
    })  # fmt: skip
    wj(ix / "ds" / "S70" / "episodes.json", [sim_ep])
    ego = [
        {"id": "ep_1", "qa": "flag", "reasons": ["hand_out_of_frame"], "s": 5.0,
         "poster": "/data/ds/egx_aaaa1111/posters/ep_1.jpg"},
        {"id": "ep_2", "qa": "pass", "reasons": [], "s": 6.0,
         "poster": "/data/ds/egx_aaaa1111/posters/missing.jpg"},
        {"id": "ep_3", "qa": "pass", "reasons": [], "s": 7.0, "poster": "/ego/raw/ep_3.jpg"},
    ]  # fmt: skip
    wj(ix / "ds" / "egx_aaaa1111" / "episodes.json", ego)
    (ix / "ds" / "egx_aaaa1111" / "posters").mkdir(parents=True)
    (ix / "ds" / "egx_aaaa1111" / "posters" / "ep_1.jpg").write_bytes(b"\xff\xd8jpg")
    run = fw.fw_root / "tray" / "pair60k" / "C_70" / "j-run1"
    run.mkdir(parents=True)
    (run / "metrics.jsonl").write_text(
        "\n".join(json.dumps({"step": s, "split": "train", "loss": 1.0 / s}) for s in (1, 2, 4))
        + "\n",
        encoding="utf-8",
    )
    wj(fw.jobs / "j-aaa111" / "job.json", {
        "id": "j-aaa111", "kind": "ego.qa", "state": "ok", "host": "laptop",
        "created": "2026-11-10T10:00:00", "started": "2026-11-10T10:00:00",
        "ended": "2026-11-10T10:00:10", "rc": 0, "argv": ["fw", "x"],
    })  # fmt: skip
    return fw

"""Run M's training set on the Data page (Hiếu, 28/11/2026): seed row M, its four parts, the run
node ``run-da-48-m``, and readable titles for the jig sets; nothing of DA-50 or run N."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from flywheel.console.index import cards, catalog
from flywheel.console.paths import ConsolePaths

REPO = Path(__file__).resolve().parents[4]
PARTS = ["tray_s1_bfbdcbcf719e", "tray_s1_8631ace9b1b3", "tray_s1place_a1797e480160",
         "tray_s1place_56e6d006d8d1"]  # fmt: skip

PART_CARD = """\
schema: dataset-card/1
id: tray_s1place_a1797e480160
alias: tray.s1place.jig2cj10.l1.p8.20261124
status: current
task: tray
kind: cut
source_detail: planner_wbc
data_class: public
license: unknown
format: LeRobot v2.1 (50 fps)
counts: {episodes: 431, frames: 198903, hours: 1.11}
lineage: {parents: [], story: DA-46}
locations: []
"""


def _paths(tmp_path: Path) -> ConsolePaths:
    fw = tmp_path / "fwdata"
    fw.mkdir(exist_ok=True)
    return ConsolePaths(repo=REPO, fw_root=fw)


def test_seed_holds_row_m_its_parts_and_the_run_node() -> None:
    doc = yaml.safe_load((REPO / "packages/flywheel-console/src/flywheel/console/seed/catalog.yaml")
                         .read_text(encoding="utf-8"))  # fmt: skip
    m = next(r for r in doc["rows"] if r["id"] == "M")
    assert m["card"] == "da48.M" and m["episodes"] == 1037 and m["frames"] == 948639
    assert m["parents"] == PARTS
    edges = [tuple(e) for e in doc["edges"]]
    assert [(p, "M") for p in PARTS] + [("M", "run-da-48-m")] == [e for e in edges if "M" in e
                                                               or "run-da-48-m" in e]  # fmt: skip
    run = next(r for r in doc["runs"] if r["id"] == "run-da-48-m")
    assert run["title"] == "Run · DA-48 M (jig2, 100 000 bước)" and run["ext"] is False
    text = json.dumps(doc, ensure_ascii=False)
    for word in ("s1yaw", "DA-50", "da50", "jig-n", "run-da-50", "run N"):
        assert word not in text, word


def test_titles_map_names_a_card_row_with_its_episode_count(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    d = paths.fw_root / "datasets" / "tray-s1place-jig2-20261124" / "cards"
    d.mkdir(parents=True)
    (d / "tray_s1place_a1797e480160.yaml").write_text(PART_CARD, encoding="utf-8")
    rows, edges = cards.merged(paths)
    by = {r["id"]: r for r in rows}
    assert by["tray_s1place_a1797e480160"]["title"] == "Bản cắt đoạn đặt · mức 1 (431)"
    assert by["M"]["title"].endswith("(1037)")  # the seed row keeps its own title
    assert ["tray_s1place_a1797e480160", "M"] in edges and ["M", "run-da-48-m"] in edges


def test_built_catalog_shows_m_between_its_parts_and_the_run(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    out = tmp_path / "index"
    catalog.build(paths, out)
    doc = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    m = next(r for r in doc["rows"] if r["id"] == "M")
    assert m["parents"] == PARTS and m["children"] == ["run-da-48-m"]
    assert any(r["id"] == "run-da-48-m" for r in doc["runs"])

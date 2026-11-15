from __future__ import annotations

import json
from pathlib import Path

from flywheel.console.index import catalog
from flywheel.console.paths import ConsolePaths


def _paths(tmp_path: Path) -> ConsolePaths:
    repo = Path(__file__).resolve().parents[4]
    return ConsolePaths(repo=repo, fw_root=tmp_path / "fw")


def _build(tmp_path: Path) -> tuple[dict[str, int], dict]:
    counts = catalog.build(_paths(tmp_path), tmp_path / "out")
    return counts, json.loads((tmp_path / "out" / "catalog.json").read_text(encoding="utf-8"))


def test_catalog_has_62_rows_and_edges(tmp_path: Path) -> None:
    counts, doc = _build(tmp_path)
    assert counts["rows"] == len(doc["rows"]) == 62
    ids = {r["id"] for r in doc["rows"]} | {r["id"] for r in doc["runs"]}
    assert doc["edges"] and counts["edges"] == len(doc["edges"])
    assert all(a in ids and b in ids for a, b in doc["edges"])


def test_catalog_marks_missing_locally(tmp_path: Path) -> None:
    _, doc = _build(tmp_path)
    laptop = [loc for r in doc["rows"] for loc in r["locations"] if loc["where"] == "laptop"]
    assert laptop and all(loc["exists"] is False for loc in laptop)
    assert all(r["laptop_dir"] is None for r in doc["rows"])


def test_catalog_marks_present_locally(tmp_path: Path) -> None:
    (tmp_path / "fw" / "egodex-da30-probe").mkdir(parents=True)
    _, doc = _build(tmp_path)
    row = next(r for r in doc["rows"] if r["id"] == "egodex-da30-probe")
    assert row["locations"][0]["exists"] is True
    assert row["laptop_dir"] == "fwdata/egodex-da30-probe"


def test_aliases_resolve_s1(tmp_path: Path) -> None:
    _, doc = _build(tmp_path)
    by_alias = {a: r for r in doc["rows"] for a in r["aliases"]}
    assert by_alias["S1"]["data_type"] == "synthetic S1"
    assert {"S70", "ALL"} <= set(by_alias)
    assert by_alias["S70"]["lerobot"] and by_alias["ALL"]["lerobot"]
    assert all(isinstance(r["aliases"], list) for r in doc["rows"])


def test_no_absolute_home_paths(tmp_path: Path) -> None:
    _, doc = _build(tmp_path)
    assert "/home/" not in json.dumps(doc)


def test_lerobot_and_viewer_are_fw_relative(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _, doc = _build(tmp_path)
    linked = [(r[k], r["id"]) for r in doc["rows"] for k in ("lerobot", "ego_viewer") if r[k]]
    assert len(linked) == 4
    for rel, _rid in linked:
        assert not rel.startswith("fwdata/")
        assert (paths.fw_root / rel).is_relative_to(paths.fw_root)


def test_team_egocentric_rows_are_tray(tmp_path: Path) -> None:
    _, doc = _build(tmp_path)
    by = {r["id"]: r for r in doc["rows"]}
    assert by["h1m-team"]["task"] == "tray"
    assert by["team-1109-480p"]["task"] == "tray"
    assert by["egodex-da30"]["task"] == "other"


def test_round_release_and_c70_r1_cut_are_catalogued(tmp_path: Path) -> None:
    _, doc = _build(tmp_path)
    by_id = {r["id"]: r for r in doc["rows"]}
    assert by_id["tray_s1_868cc130985d"]["kind"] == "release"
    assert by_id["tray_s1_868cc130985d"]["episodes"] == 262
    cut = by_id["C70_R1"]
    assert cut["episodes"] == 606 and cut["parents"] == ["S70", "tray_s1_868cc130985d"]
    assert ["S70", "C70_R1"] in doc["edges"]


def test_unique_counts_each_episode_once(tmp_path: Path) -> None:
    """Derived rows (pipeline sources, exports, cuts, bench copies) repeat episodes of
    their parents, so only current raw sources and releases outside eval count."""
    _, doc = _build(tmp_path)
    by_id = {r["id"]: r for r in doc["rows"]}
    assert by_id["egodex-da30"]["unique"] is True
    assert by_id["tray_s1_41899efb4b27"]["unique"] is True
    for derived in ("src_158ec3c813ffe9a6", "h1m-egodex", "ALL", "S70", "C70_R1", "psi-n20"):
        assert by_id[derived]["unique"] is False, derived
    assert by_id["team-1109-480p30-old"]["unique"] is False  # superseded copy of the same clips
    assert by_id["he-dev-eval-v1"]["unique"] is False  # eval conditions are not training data
    t = doc["totals"]
    assert t["egocentric"]["episodes"] == 379
    assert t["teleop"]["episodes"] == 193
    assert t["s1"]["episodes"] == 541 + 229 + 262
    assert t["s2"]["episodes"] == 125 + 843
    assert t["all"]["episodes"] == 379 + 193 + 1032 + 968
    assert "eval" not in t

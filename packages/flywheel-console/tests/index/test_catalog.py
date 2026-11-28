from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel.console.index import catalog
from flywheel.console.index.cards import CardError
from flywheel.console.paths import ConsolePaths


def _paths(tmp_path: Path) -> ConsolePaths:
    repo = Path(__file__).resolve().parents[4]
    return ConsolePaths(repo=repo, fw_root=tmp_path / "fw")


def _build(tmp_path: Path) -> tuple[dict[str, int], dict]:
    counts = catalog.build(_paths(tmp_path), tmp_path / "out")
    return counts, json.loads((tmp_path / "out" / "catalog.json").read_text(encoding="utf-8"))


def test_catalog_has_63_rows_and_edges(tmp_path: Path) -> None:
    counts, doc = _build(tmp_path)
    assert counts["rows"] == len(doc["rows"]) == 63  # 62 + M (28/11/2026)
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


# ---------------------------------------------------------------- dataset cards (DA-45)
OVERRIDE_CARD = """\
schema: dataset-card/1
id: tray_s1_41899efb4b27
alias: tray.s1.zone1.l1.p5.20261111
status: superseded
superseded_by: [tray_s1_aaaaaaaaaaaa]
task: tray
kind: synthetic_s1
source_detail: planner_wbc
data_class: public
license: unknown
format: LeRobot v2.1 (Psi0 layout, 50 fps)
counts: {attempts: 610, episodes: 541, frames: 769340, hours: 4.27}
quality:
  replay_qa: 542/542 pass
  qa_decisions: {pass: 534, reject: 7}
  known_issues: ["first issue", "second issue"]
lineage: {parents: [tray_s1_f9433b028c52], story: DA-34}
files: {release: .}
locations:
  - {host: laptop, root: "fwdata/mirror/releases/tray_s1_41899efb4b27", role: mirror}
  - {host: rtx3060, role: deleted-20261115,
     root: "~/denso-da34-pool/fwdata/releases/tray_s1_41899efb4b27"}
"""

ALL_CARD = """\
schema: dataset-card/1
id: cut-all-zone1.ALL
alias: tray.cut.zone1.l12.p5.20261111
status: superseded
task: tray
kind: cut
source_detail: planner_wbc
data_class: public
license: unknown
format: LeRobot v2.1 (50 fps)
counts: {episodes: 606, frames: 861624, hours: 4.79}
quality: {qa_decisions: {kept: 606}}
lineage: {parents: [tray_s1_41899efb4b27, tray_s1_4a8f4a8c6a8d], story: DA-34}
files: {cut: G1Env-v0}
locations:
  - {host: laptop, root: "fwdata/mirror/cut-all-zone1/ALL", role: mirror}
  - {host: rtx3060, root: "~/denso-da34-pool/fwdata/cut-all-zone1/ALL", role: deleted-20261115}
"""

S70_CARD = (
    ALL_CARD.replace("cut-all-zone1.ALL", "round-c70.S70")
    .replace(
        "parents: [tray_s1_41899efb4b27, tray_s1_4a8f4a8c6a8d]", "parents: [cut-all-zone1.ALL]"
    )
    .replace("fwdata/mirror/cut-all-zone1/ALL", "fwdata/mirror/cut/S70")
)

PSI_REF_CARD = """\
schema: dataset-card/1
id: psi-two-table
alias: two_table.teleop.plain.l0.teleop.20260914
status: reference
task: two_table
kind: teleop
data_class: public
license: unknown
format: LeRobot v2.1 (state 32, action 36, 50 fps)
counts: {episodes: 99, frames: 62764, hours: 0.35}
quality: {qa_decisions: {pass: 95, flag: 4}}
lineage: {parents: []}
locations:
  - {host: laptop, root: "fwdata/psi-data/simple/Env-v0", role: mirror}
  - {host: huggingface, root: "USC-PSI-Lab/psi-data", role: upstream}
"""

S2_CARD = """\
schema: dataset-card/1
id: tray_s2_3618a579b15e
alias: tray.s2.zone1.l01.s2.20261112
status: superseded
task: tray
kind: synthetic_s2
source_detail: s2
data_class: public
license: unknown
format: LeRobot v2.1 (state 32, action 36, 50 fps, head camera 360x640)
counts: {episodes: 669, frames: 1158899, hours: 6.44}
quality: {qa_decisions: {pass: 669}}
lineage: {parents: [parents-1105], story: DA-35}
files: {release: .}
locations:
  - {host: laptop, root: "fwdata/mirror/releases/tray_s2_3618a579b15e", role: mirror}
"""


def _with_cards(tmp_path: Path) -> dict:
    from test_cards import STORE_CARD, write_card

    fw = tmp_path / "fw"
    write_card(fw, STORE_CARD, store="tray-s1-test")
    for text in (OVERRIDE_CARD, ALL_CARD, S70_CARD, PSI_REF_CARD, S2_CARD):
        write_card(fw, text)
    rel = fw / "datasets/tray-s1-test/releases/tray_s1_aaaaaaaaaaaa"
    (rel / "meta").mkdir(parents=True)
    (rel / "meta" / "info.json").write_text("{}")
    (rel / "blob.bin").write_bytes(b"\0" * 3_000_000)
    (fw / "mirror/cut-all-zone1/ALL/G1Env-v0/meta").mkdir(parents=True)
    (fw / "mirror/cut-all-zone1/ALL/G1Env-v0/meta/info.json").write_text("{}")
    return _build(tmp_path)[1]


def test_card_overrides_the_seed_row_with_its_id(tmp_path: Path) -> None:
    by = {r["id"]: r for r in _with_cards(tmp_path)["rows"]}
    r = by["tray_s1_41899efb4b27"]
    assert r["status"] == "superseded" and r["frames"] == 769340
    assert r["title"] == "Tray S1 · pool 1104 zone1 (541)"  # seed title kept
    assert [loc["where"] for loc in r["locations"]] == ["laptop"]  # deleted rtx3060 dropped
    assert r["name"] == "tray.s1.zone1.l1.p5.20261111"
    assert {"S1", "tray.s1.zone1.l1.p5.20261111"} <= set(r["aliases"])
    assert r["qa"] == "534 pass, 7 reject" and r["qa_counts"] == {"pass": 534, "reject": 7}
    assert r["replay_qa"] == "542/542 pass" and r["notes"] == "first issue; second issue"
    assert r["superseded_by"] == ["tray_s1_aaaaaaaaaaaa"] and r["story"] == "DA-34"
    assert r["card"] == "fwdata/datasets/_cards/tray_s1_41899efb4b27.yaml"
    assert r["unique"] is False  # superseded releases leave the totals
    assert r["size"] == "4.5 GB"  # seed size kept


def test_new_card_adds_a_row_with_a_generated_title(tmp_path: Path) -> None:
    doc = _with_cards(tmp_path)
    r = next(x for x in doc["rows"] if x["id"] == "tray_s1_aaaaaaaaaaaa")
    assert r["title"] == "Tray S1 · jig2 · l1 (10)"
    assert r["status"] == "current" and r["kind"] == "release" and r["group"] == "s1"
    assert r["fps"] == 50 and r["scene"] == {"jig": "jig2", "level": 1}
    assert [loc["raw"] for loc in r["locations"]] == [
        "rtx3060:~/fwdata/datasets/tray-s1-test/releases/tray_s1_aaaaaaaaaaaa",
        "laptop:fwdata/datasets/tray-s1-test/releases/tray_s1_aaaaaaaaaaaa",
    ]
    assert r["laptop_dir"] == "fwdata/datasets/tray-s1-test/releases/tray_s1_aaaaaaaaaaaa"
    assert r["view"] == "meta" and r["size"] == "3 MB"  # measured from the laptop copy
    assert r["lerobot"] is None  # no poster index for card-only rows
    assert r["unique"] is True
    assert doc["cards"] == 6


def test_linked_rows_keep_their_seed_id(tmp_path: Path) -> None:
    doc = _with_cards(tmp_path)
    by = {r["id"]: r for r in doc["rows"]}
    assert "cut-all-zone1.ALL" not in by and "round-c70.S70" not in by
    a, s = by["ALL"], by["S70"]
    assert a["episodes"] == 606 and a["frames"] == 861624 and a["status"] == "superseded"
    assert "cut-all-zone1.ALL" in a["aliases"] and "ALL" in a["aliases"]
    assert a["data_type"] == "synthetic S1" and a["kind"] == "subset-cut"
    assert a["qa"] == "606 kept" and a["qa_counts"] is None
    assert a["lerobot"] == "mirror/cut-all-zone1/ALL/G1Env-v0"  # seed folder gone: card cut
    assert s["lerobot"] == "da34-dryrun/cut-all-zone1/S70/G1WholebodyTrayTransferTeleop-v0"
    assert s["parents"] == ["ALL"] and ["ALL", "S70"] in doc["edges"]
    assert a["view"] == "robot" and a["unique"] is False


def test_s2_row_takes_the_card_and_its_parent_edge(tmp_path: Path) -> None:
    doc = _with_cards(tmp_path)
    by = {r["id"]: r for r in doc["rows"]}
    r = by["tray_s2_3618a579b15e"]
    assert r["status"] == "superseded" and r["group"] == "s2" and r["frames"] == 1158899
    assert "s2-release-669" in r["aliases"] and r["parents"] == ["parents-1105"]
    assert ["parents-1105", "tray_s2_3618a579b15e"] in doc["edges"]
    assert ["s2-prod-1105", "tray_s2_3618a579b15e"] in doc["edges"]  # seed edge kept


def test_reference_rows_count_like_current(tmp_path: Path) -> None:
    doc = _with_cards(tmp_path)
    r = next(x for x in doc["rows"] if x["id"] == "psi-two-table")
    assert r["status"] == "reference" and r["unique"] is True and r["view"] == "psi"
    assert [loc["raw"] for loc in r["locations"]][-1] == "HF USC-PSI-Lab/psi-data"
    assert doc["totals"]["teleop"]["episodes"] == 193


def test_card_catalog_edges_are_known_and_paths_relative(tmp_path: Path) -> None:
    doc = _with_cards(tmp_path)
    ids = {r["id"] for r in doc["rows"]} | {r["id"] for r in doc["runs"]}
    assert len(ids) == len(doc["rows"]) + len(doc["runs"])
    assert all(a in ids and b in ids for a, b in doc["edges"])
    assert len({tuple(e) for e in doc["edges"]}) == len(doc["edges"])
    assert "/home/" not in json.dumps(doc) and str(tmp_path) not in json.dumps(doc)
    seed_only = next(r for r in doc["rows"] if r["id"] == "egodex-da30")
    assert seed_only["card"] is None and seed_only["superseded_by"] == []


def test_invalid_card_stops_the_catalog_build(tmp_path: Path) -> None:
    from test_cards import write_card

    write_card(tmp_path / "fw", OVERRIDE_CARD.replace("status: superseded", "status: live"))
    with pytest.raises(CardError, match="status"):
        catalog.build(_paths(tmp_path), tmp_path / "out")
    assert not (tmp_path / "out" / "catalog.json").exists()

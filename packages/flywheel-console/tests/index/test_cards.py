"""Dataset card loader and validator (DA-45 AC 1). Cards are built in ``tmp_path``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.console.index import cards
from flywheel.console.index.cards import CardError

STORE_CARD = """\
schema: dataset-card/1
id: tray_s1_aaaaaaaaaaaa
alias: tray.s1.jig2.l1.p8.20261122
status: current
task: tray
kind: synthetic_s1
source_detail: planner_wbc
data_class: public
license: unknown
format: LeRobot v2.1 (Psi0 layout, state 32, action 36, 50 fps, head camera 360x640)
scene: {jig: jig2, level: 1}
counts: {attempts: 12, episodes: 10, frames: 1400, hours: 0.01}
quality:
  replay_qa: 10/10 pass
  qa_decisions: {flag: 9, reject: 1}
  known_issues: ["one", "two"]
lineage: {parents: [], story: DA-41}
files: {release: releases/tray_s1_aaaaaaaaaaaa}
store: tray-s1-test
locations:
  - {host: rtx3060, root: "~/fwdata/datasets/tray-s1-test", role: primary}
  - {host: laptop, root: "fwdata/datasets/tray-s1-test", role: mirror}
"""

RELEASE_CARD = """\
schema: dataset-card/1
id: tray_s1_bbbbbbbbbbbb
alias: tray.s1.zone1.l1.p5.20261111
status: superseded
superseded_by: [tray_s1_aaaaaaaaaaaa]
task: tray
kind: synthetic_s1
source_detail: planner_wbc
data_class: public
license: unknown
format: LeRobot v2.1 (50 fps)
counts: {attempts: null, episodes: 5, frames: 700, hours: 0.004}
quality: {replay_qa: null, qa_decisions: {pass: 5}, known_issues: null}
lineage: {parents: [tray_s1_cccccccccccc], story: DA-34}
files: {release: .}
locations:
  - {host: laptop, root: "fwdata/mirror/releases/tray_s1_bbbbbbbbbbbb", role: mirror}
  - {host: rtx3060, root: "~/old/releases/tray_s1_bbbbbbbbbbbb", role: deleted-20261115}
"""

CUT_CARD = """\
schema: dataset-card/1
id: cut-x.ALL
alias: tray.cut.zone1.l12.p5.20261111
status: superseded
task: tray
kind: cut
source_detail: planner_wbc
data_class: public
license: unknown
format: LeRobot v2.1 (50 fps)
counts: {episodes: 6, frames: 800, hours: 0.005}
quality: {qa_decisions: {kept: 6}}
lineage: {parents: [tray_s1_bbbbbbbbbbbb]}
files: {cut: G1Env-v0}
locations:
  - {host: laptop, root: "fwdata/mirror/cut-x/ALL", role: mirror}
"""

PSI_CARD = """\
schema: dataset-card/1
id: psi-test
alias: two_table.teleop.plain.l0.teleop.20260914
status: reference
task: two_table
kind: teleop
source_detail: null
data_class: public
license: unknown
format: LeRobot v2.1 (50 fps)
counts: {episodes: 3, frames: 300, hours: 0.002}
quality: {qa_decisions: null}
lineage: {parents: [], story: null}
files: {data: data/chunk-000}
locations:
  - {host: laptop, root: "fwdata/psi-data/simple/Env-v0", role: mirror}
  - {host: laptop, root: "fwdata/psi-data/simple/Env-v0.zip", role: mirror}
  - {host: huggingface, root: "USC-PSI-Lab/psi-data", role: upstream}
"""


def write_card(fw_root: Path, text: str, store: str | None = None, name: str | None = None) -> Path:
    data = yaml.safe_load(text)
    d = fw_root / "datasets" / (f"{store}/cards" if store else "_cards")
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name or data['id']}.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def _edit(text: str, **changes: Any) -> str:
    data = yaml.safe_load(text)
    for k, v in changes.items():
        cur = data
        *head, last = k.split("__")
        for h in head:
            cur = cur[h]
        if v is _DROP:
            cur.pop(last, None)
        else:
            cur[last] = v
    return yaml.safe_dump(data, sort_keys=False)


_DROP = object()


def test_no_datasets_dir_means_no_cards(tmp_path: Path) -> None:
    assert cards.load_cards(tmp_path) == []
    assert cards.load_cards_lenient(tmp_path) == []
    assert cards.cards_stamp(tmp_path) == (0, 0)


def test_store_and_loose_cards_load_sorted(tmp_path: Path) -> None:
    write_card(tmp_path, STORE_CARD, store="tray-s1-test")
    write_card(tmp_path, RELEASE_CARD)
    write_card(tmp_path, CUT_CARD)
    write_card(tmp_path, PSI_CARD)
    (tmp_path / "datasets" / "_cards" / "INDEX.md").write_text("not a card")
    got = cards.load_cards(tmp_path)
    assert [c.id for c in got] == [
        "cut-x.ALL", "psi-test", "tray_s1_bbbbbbbbbbbb", "tray_s1_aaaaaaaaaaaa",
    ]  # fmt: skip
    store = got[-1]
    assert store.data["store"] == "tray-s1-test"
    assert store.path == tmp_path / "datasets/tray-s1-test/cards/tray_s1_aaaaaaaaaaaa.yaml"
    assert got[2].parents == ["tray_s1_cccccccccccc"]
    assert got[1].parents == []
    assert cards.cards_stamp(tmp_path)[0] == 4


@pytest.mark.parametrize(
    "changes, field",
    [
        ({"schema": "dataset-card/2"}, "schema"),
        ({"id": "bad id"}, "id"),
        ({"id": "tray_s1_other"}, "id"),
        ({"status": "live"}, "status"),
        ({"kind": "synthetic"}, "kind"),
        ({"task": ""}, "task"),
        ({"task": _DROP}, "task"),
        ({"data_class": "secret"}, "data_class"),
        ({"license": None}, "license"),
        ({"alias": _DROP}, "alias"),
        ({"counts": [1, 2]}, "counts"),
        ({"counts__episodes": "ten"}, "counts.episodes"),
        ({"counts__frames": 1.5}, "counts.frames"),
        ({"counts__hours": "1h"}, "counts.hours"),
        ({"locations": {"host": "laptop"}}, "locations"),
        ({"locations": [{"host": "laptop"}]}, "locations[0].root"),
        ({"locations": [{"host": 3, "root": "x"}]}, "locations[0].host"),
        ({"lineage__parents": "tray_s1_x"}, "lineage.parents"),
        ({"quality__qa_decisions": {"pass": "all"}}, "quality.qa_decisions"),
    ],
)
def test_invalid_card_names_file_and_field(
    tmp_path: Path, changes: dict[str, Any], field: str
) -> None:
    p = write_card(tmp_path, _edit(STORE_CARD, **changes), name="tray_s1_aaaaaaaaaaaa")
    with pytest.raises(CardError) as e:
        cards.load_cards(tmp_path)
    assert str(p) in str(e.value) and f"'{field}'" in str(e.value)
    assert cards.load_cards_lenient(tmp_path) == []


def test_null_lineage_is_no_parents(tmp_path: Path) -> None:
    write_card(tmp_path, _edit(STORE_CARD, lineage=None))
    assert cards.load_cards(tmp_path)[0].parents == []


def test_unreadable_yaml_is_a_card_error(tmp_path: Path) -> None:
    p = write_card(tmp_path, STORE_CARD)
    p.write_text("schema: [unclosed\n", encoding="utf-8")
    with pytest.raises(CardError, match="<file>"):
        cards.load_cards(tmp_path)


def test_duplicate_id_is_an_error(tmp_path: Path) -> None:
    write_card(tmp_path, STORE_CARD, store="a")
    write_card(tmp_path, STORE_CARD, store="b")
    with pytest.raises(CardError, match="also the id"):
        cards.load_cards(tmp_path)
    assert cards.load_cards_lenient(tmp_path) == []


def test_lenient_skips_only_the_bad_card(tmp_path: Path) -> None:
    write_card(tmp_path, RELEASE_CARD)
    write_card(tmp_path, _edit(CUT_CARD, status="live"))
    with pytest.raises(CardError):
        cards.load_cards(tmp_path)
    assert [c.id for c in cards.load_cards_lenient(tmp_path)] == ["tray_s1_bbbbbbbbbbbb"]


def test_card_for_path_three_layouts(tmp_path: Path) -> None:
    for text, store in ((STORE_CARD, "tray-s1-test"), (RELEASE_CARD, None), (CUT_CARD, None)):
        write_card(tmp_path, text, store=store)
    write_card(tmp_path, PSI_CARD)
    loaded = cards.load_cards(tmp_path)
    store_dir = tmp_path / "datasets/tray-s1-test/releases/tray_s1_aaaaaaaaaaaa"
    rel_dir = tmp_path / "mirror/releases/tray_s1_bbbbbbbbbbbb"
    cut_dir = tmp_path / "mirror/cut-x/ALL/G1Env-v0"
    psi_dir = tmp_path / "psi-data/simple/Env-v0"
    for d in (store_dir, rel_dir, cut_dir, psi_dir):
        d.mkdir(parents=True)

    def hit(d: Path) -> str | None:
        c = cards.card_for_path(loaded, tmp_path, d)
        return c.id if c else None

    assert hit(store_dir) == "tray_s1_aaaaaaaaaaaa"
    assert hit(rel_dir) == "tray_s1_bbbbbbbbbbbb"
    assert hit(cut_dir) == "cut-x.ALL"
    assert hit(psi_dir) == "psi-test"
    assert hit(tmp_path / "elsewhere") is None
    assert hit(tmp_path / "datasets/tray-s1-test") is None  # a store root is not a dataset
    assert hit(tmp_path / "mirror/cut-x/ALL") is None  # nor is a cut root
    # the deleted rtx3060 copy is not a laptop folder
    assert all(d.is_relative_to(tmp_path) for c in loaded for d in c.lerobot_dirs(tmp_path))


def test_server_rows_follow_card_changes_and_skip_bad_cards(tmp_path: Path) -> None:
    from flywheel.console.paths import ConsolePaths, set_active
    from flywheel.console.server import media

    fw = tmp_path / "fw"
    fw.mkdir()
    set_active(ConsolePaths(repo=tmp_path, fw_root=fw))
    media._rows_cache = None
    before = {r["id"] for r in media.seed_rows()}
    assert "tray_s1_aaaaaaaaaaaa" not in before
    write_card(fw, STORE_CARD, store="tray-s1-test")
    write_card(fw, _edit(CUT_CARD, status="live"))  # invalid: skipped, not raised
    after = {r["id"] for r in media.seed_rows()}
    assert after == before | {"tray_s1_aaaaaaaaaaaa"}
    media._rows_cache = None


def test_cards_stamp_changes_when_a_card_is_replaced_by_an_older_copy(tmp_path: Path) -> None:
    """``rsync -a`` keeps mtimes, so the newest mtime alone would miss this edit."""
    import os

    d = tmp_path / "datasets" / "_cards"
    d.mkdir(parents=True)
    a, b = d / "a.yaml", d / "b.yaml"
    a.write_text("id: a\n")
    b.write_text("id: b\n")
    os.utime(a, (2000, 2000))
    os.utime(b, (3000, 3000))
    before = cards.cards_stamp(tmp_path)
    a.write_text("id: a\nstatus: superseded\n")
    os.utime(a, (1000, 1000))  # older than b: count and newest mtime are unchanged
    assert cards.cards_stamp(tmp_path) != before
    a.rename(d / "c.yaml")  # a rename keeps mtime, size and count
    assert cards.cards_stamp(tmp_path)[0] == before[0]
    assert cards.cards_stamp(tmp_path) != before

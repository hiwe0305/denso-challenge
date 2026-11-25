"""The store snapshot of a pack: written at B0, admitted at B1, read by the tools (task 4.7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from flywheel.contracts.entities import FixRateEvent, LedgerEntry
from flywheel.eval.agentqa.round.admit import admit
from flywheel.eval.agentqa.round.pack import PackRefused, build_pack, read_pack
from flywheel.eval.agentqa.round.pipeline import run_round
from flywheel.eval.agentqa.round.snapshot import SNAPSHOT_DIR
from flywheel.store.ledger_append import append_ledger_entry
from flywheel.store.paths import StorePaths
from flywheel.store.tables import write_record
from helpers_round import NOW, PackMaker, calls_of, isolated_store, pack_maker  # noqa: F401


@pytest.fixture
def make_pack(tmp_path: Path) -> PackMaker:
    return pack_maker(tmp_path)


def ledger_row(kind: str, activity: str, resource: str, unit: str, quantity: float,
               usd: float, estimate: str | None = None) -> LedgerEntry:
    return LedgerEntry.model_validate({
        "activity": activity, "resource_type": resource, "quantity": quantity, "unit": unit,
        "usd_amount": usd, "measure_kind": kind, "estimate_entry_id": estimate,
        "run_plan_id": "g0-DA-43-20261121", "job_id": "job-1"})


def fill(store: Path, *, extra: int = 0) -> Path:
    paths = StorePaths(store)
    estimate = ledger_row("estimated", "eval", "gpu_seconds", "s", 600.0, 0.24)
    append_ledger_entry(estimate, paths)
    append_ledger_entry(ledger_row("measured", "eval", "gpu_seconds", "s", 450.0, 0.18,
                                   estimate=estimate.id), paths)
    for k in range(extra):
        write_record("fix_rate_event", FixRateEvent(intervention_type="sim_s2", n_conditions=4,
                                                    fixed=k), paths)
    write_record("fix_rate_event", FixRateEvent(intervention_type="sim_s1", n_conditions=10,
                                                fixed=4), paths)
    return store


def declare(root: Path, block: object = ...) -> Path:
    root.mkdir()
    (root / "a.jsonl").write_text("{}\n")
    decl: dict[str, object] = {"task_id": "tray", "declared_by": "t", "data_class": "public",
                               "entries": [{"path": "a.jsonl", "kind": "scores"}]}
    if block is not ...:
        decl["store_snapshot"] = block
    (root / "round.yaml").write_text(yaml.safe_dump(decl))
    return root / "round.yaml"


GOOD = {"data_class": "internal", "tables": ["ledger", "fix_rate"]}


def test_the_snapshot_is_written_sorted_and_hashed_into_one_entry_per_table(
        tmp_path: Path) -> None:
    store = fill(tmp_path / "store", extra=2)
    pack = build_pack(declare(tmp_path / "r", GOOD), store=store)
    by_kind = {e.kind: e for e in pack.entries if e.ref.startswith(SNAPSHOT_DIR)}
    assert sorted(by_kind) == ["fix_rate", "ledger"]
    ledger = tmp_path / "r" / SNAPSHOT_DIR / "ledger.jsonl"
    rows = [LedgerEntry.model_validate_json(x) for x in ledger.read_text().splitlines()]
    assert [r.id for r in rows] == sorted(r.id for r in rows) and len(rows) == 2
    entry = by_kind["ledger"]
    assert (entry.data_class, entry.subject) == (
        "internal", {"table": "ledger", "rows": "2", "unreadable": "0"})
    assert by_kind["fix_rate"].subject["rows"] == "3"
    # the same rows give the same bytes, whatever the order they were written in
    again = build_pack(declare(tmp_path / "r2", GOOD), store=store)
    assert [e.sha256 for e in again.entries] == [e.sha256 for e in pack.entries]


def test_rows_that_do_not_parse_are_counted_on_the_entry(tmp_path: Path) -> None:
    store = fill(tmp_path / "store")
    file = next(StorePaths(store).runs_dir.glob("**/ledger*.jsonl"))
    file.write_text(file.read_text() + '{"not": "a ledger row"}\n')
    pack = build_pack(declare(tmp_path / "r", GOOD), store=store)
    entry = next(e for e in pack.entries if e.kind == "ledger")
    assert (entry.subject["rows"], entry.subject["unreadable"]) == ("2", "1")


def test_the_snapshot_refusals_are_one_line_each(tmp_path: Path) -> None:
    store = fill(tmp_path / "store")
    with pytest.raises(PackRefused, match="--store"):
        build_pack(declare(tmp_path / "a", GOOD))
    with pytest.raises(PackRefused, match="unknown table nope"):
        build_pack(declare(tmp_path / "b", {"data_class": "public", "tables": ["nope"]}),
                   store=store)
    with pytest.raises(PackRefused, match="data_class"):
        build_pack(declare(tmp_path / "c", {"tables": ["ledger"]}), store=store)
    decl = declare(tmp_path / "d", GOOD)
    build_pack(decl, store=store)
    with pytest.raises(PackRefused, match="exists"):  # a snapshot is written once
        build_pack(decl, store=store)


def test_a_refused_link_writes_nothing_and_the_corrected_retry_packs(tmp_path: Path) -> None:
    store = fill(tmp_path / "store")
    decl = declare(tmp_path / "r", GOOD)
    raw = yaml.safe_load(decl.read_text())
    link = {"source": f"{SNAPSHOT_DIR}/ledger.jsonl", "target": "a.jsonl", "relation": "data_of"}
    raw["links"] = [{**link, "source": f"{SNAPSHOT_DIR}/legder.jsonl"}]  # the typo
    decl.write_text(yaml.safe_dump(raw))
    with pytest.raises(PackRefused, match="legder.jsonl is not an entry"):
        build_pack(decl, store=store)
    assert not (tmp_path / "r" / SNAPSHOT_DIR).exists()
    raw["links"] = [link]
    decl.write_text(yaml.safe_dump(raw))
    pack = build_pack(decl, store=store)
    assert f"{SNAPSHOT_DIR}/ledger.jsonl" in [e.ref for e in pack.entries]


def test_a_failed_write_leaves_no_snapshot_file(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = fill(tmp_path / "store")
    decl = declare(tmp_path / "r", GOOD)
    write_text = Path.write_text

    def failing(self: Path, *args: object, **kwargs: object) -> int:
        if "fix_rate" in self.name:  # the second table, after the ledger is written
            raise OSError("disk full")
        return write_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", failing)
    with pytest.raises(PackRefused, match="disk full"):
        build_pack(decl, store=store)
    monkeypatch.undo()
    snapshot = tmp_path / "r" / SNAPSHOT_DIR
    assert not snapshot.exists() or list(snapshot.iterdir()) == []
    assert len(build_pack(decl, store=store).entries) == 3  # the retry is not blocked


def test_a_store_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PackRefused, match="no such directory"):
        build_pack(declare(tmp_path / "a", GOOD), store=tmp_path / "no-such-store")
    (tmp_path / "not-a-store").mkdir()  # a directory, but no site in it: a wrong path
    with pytest.raises(PackRefused, match="not a store"):
        build_pack(declare(tmp_path / "b", GOOD), store=tmp_path / "not-a-store")
    for name in ("a", "b"):
        assert not (tmp_path / name / SNAPSHOT_DIR).exists()


def test_a_real_store_with_no_rows_packs_zero_rows(tmp_path: Path) -> None:
    StorePaths(tmp_path / "store").ensure_dirs()
    pack = build_pack(declare(tmp_path / "r", GOOD), store=tmp_path / "store")
    rows = {e.subject["table"]: e.subject["rows"] for e in pack.entries if e.subject}
    assert rows == {"ledger": "0", "fix_rate": "0"}


def test_a_pack_without_the_block_needs_no_store(tmp_path: Path) -> None:
    pack = build_pack(declare(tmp_path / "r"))
    assert [e.ref for e in pack.entries] == ["a.jsonl"]


# B1: no exemption in the class rules ------------------------------------------------------

def test_a_public_snapshot_with_no_link_is_unconfirmed_and_hosted_stays_off(
        make_pack: PackMaker, tmp_path: Path) -> None:
    pack = make_pack(snapshot_of=fill(tmp_path / "live"), snapshot_class="public")
    admission = admit(pack).admission
    assert admission.data_class == "public" and not admission.hosted_allowed
    assert admission.unconfirmed == [f"{SNAPSHOT_DIR}/fix_rate.jsonl",
                                     f"{SNAPSHOT_DIR}/ledger.jsonl"]


def test_a_public_snapshot_linked_to_a_public_source_is_confirmed(
        make_pack: PackMaker, tmp_path: Path) -> None:
    pack = make_pack(snapshot_of=fill(tmp_path / "live"), snapshot_class="public",
                     link_snapshot=True)
    admission = admit(pack).admission
    assert admission.unconfirmed == [] and admission.hosted_allowed


def test_an_internal_snapshot_makes_the_whole_pack_internal(
        make_pack: PackMaker, tmp_path: Path) -> None:
    admission = admit(make_pack(snapshot_of=fill(tmp_path / "live"))).admission
    assert admission.data_class == "internal" and not admission.hosted_allowed


# B2: a round is a function of its pack --------------------------------------------------

def test_two_live_stores_give_the_same_bytes_from_one_pack(
        make_pack: PackMaker, tmp_path: Path) -> None:
    pack = make_pack(snapshot_of=fill(tmp_path / "snap-source"))
    run_round(pack, tmp_path / "a", now=NOW, store=fill(tmp_path / "live-a"))
    run_round(pack, tmp_path / "b", now=NOW, store=fill(tmp_path / "live-b", extra=5))
    for name in ("facts.jsonl", "tool_calls.jsonl"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    shas = {e.kind: e.sha256 for e in read_pack(pack).entries}
    by_tool = {c.tool: c for c in calls_of(tmp_path / "a")}
    assert by_tool["cost_lookup"].input_sha256 == [shas["ledger"]]
    assert by_tool["history_lookup"].input_sha256 == [shas["fix_rate"]]
    facts = [json.loads(x) for x in (tmp_path / "a" / "facts.jsonl").read_text().splitlines()]
    assert not any(f["source_ref"] == "store" for f in facts)
    assert any(f["source_ref"] == f"{SNAPSHOT_DIR}/ledger.jsonl" for f in facts)

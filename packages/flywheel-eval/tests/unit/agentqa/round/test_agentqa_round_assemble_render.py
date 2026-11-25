"""Steps B6 and B7 on the no-model path, and `fw agentqa round` (DA-43 task 4.4)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from flywheel.contracts.entities import LedgerEntry
from flywheel.eval.agentqa.cli import app
from flywheel.eval.agentqa.round.assemble import ASSEMBLY_FILE
from flywheel.eval.agentqa.round.hypotheses import RULES_DIR, RulesRefused, load_rules
from flywheel.eval.agentqa.round.pipeline import NO_MODEL_STEPS, run_round
from flywheel.eval.agentqa.round.records import Assembly, FactRecord
from flywheel.eval.agentqa.round.version import CONFIG_ROOT, agent_hash, agent_version
from helpers_round import (  # noqa: F401  (isolated_store is an autouse fixture)
    NOW,
    PackMaker,
    isolated_store,
    pack_maker,
)
from typer.testing import CliRunner


@pytest.fixture
def make_pack(tmp_path: Path) -> PackMaker:
    return pack_maker(tmp_path)


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "store"


@pytest.fixture
def round_out(make_pack: PackMaker, tmp_path: Path, store: Path) -> Path:
    out = tmp_path / "out"
    run_round(make_pack(), out, now=NOW, store=store)
    return out


def assembly_of(out: Path) -> Assembly:
    return Assembly.model_validate_json((out / ASSEMBLY_FILE).read_text())


def facts_by_id(out: Path) -> dict[str, FactRecord]:
    lines = (out / "facts.jsonl").read_text().splitlines()
    return {f.fact_id: f for f in map(FactRecord.model_validate_json, lines)}


def ledger_entries(store: Path) -> list[LedgerEntry]:
    return [LedgerEntry.model_validate_json(line)
            for path in sorted(store.rglob("*.jsonl")) if "ledger" in path.as_posix()
            for line in path.read_text().splitlines()]


def test_a_no_model_round_runs_seven_steps_and_is_degraded(round_out: Path) -> None:
    record = json.loads((round_out / "run.json").read_text())
    assert [s["name"] for s in record["steps"]] == list(NO_MODEL_STEPS)
    assert len(NO_MODEL_STEPS) == 7 and record["no_model"] is True
    # scores only: adjudicate has no source, so it writes nothing and stays ok
    step = next(s for s in record["steps"] if s["name"] == "adjudicate")
    assert step["status"] == "ok" and step["rows"] == 0 and step["outputs"] == {}
    assert not (round_out / "reports.jsonl").exists()
    assert record["status"] == "degraded"
    assert record["agent_version"] == agent_version() and len(record["agent_hash"]) == 64
    a = assembly_of(round_out)
    assert a.status == "degraded" and a.model == "" and len(a.clusters) == 64
    sizes = [(-c.cluster.size, c.cluster.cluster_id) for c in a.clusters]
    assert sizes == sorted(sizes)
    assert a.headline == a.clusters[0] and a.headline.cluster.size == 14
    assert a.headline.hypotheses[0].source == "code" and a.headline.hypotheses[0].rank == 1
    assert (round_out / "index.html").is_file()


def test_the_page_shows_the_top_the_floor_and_the_facts(round_out: Path) -> None:
    page = (round_out / "index.html").read_text()
    a = assembly_of(round_out)
    assert "<script" not in page and "http://" not in page and "https://" not in page
    assert "Top of the round" in page and "Not judged" in page and "code floor" in page
    assert "Most likely cause" in page and "Cheapest check" in page
    assert "Proposed intervention" in page and "not costed yet" in page
    assert "log_missing_signals (cost eval_rerun_cluster)" in page
    assert a.headline is not None and a.headline.hypotheses[0].title in page
    assert "<td>C_70_chain_broken</td><td>7</td>" in page


def test_every_fact_of_the_headline_is_shown_with_its_value(round_out: Path) -> None:
    a = assembly_of(round_out)
    page = (round_out / "index.html").read_text()
    facts = facts_by_id(round_out)
    assert a.headline is not None
    shown = [f for h in a.headline.hypotheses for f in (*h.support, *h.contra)]
    assert shown
    for fid in shown:
        fact = facts[fid]
        assert (f"<td>{fid}</td><td>{fact.name}</td><td>{fact.value}</td>"
                f"<td>{fact.unit}</td>") in page


def test_not_judged_collects_the_unjudged_things(round_out: Path) -> None:
    a = assembly_of(round_out)
    # the fixture is scores only: no trace, no metrics, and no checkpoint declared
    no_ckpt = ("no checkpoint is declared on its scores entry and no Episode record of "
               "its rollouts carries one")
    assert sorted((n.what, n.reason) for n in a.not_judged) == sorted([
        ("trace_stats_not_judged", "no entry of kind trace in the pack"),
        ("train_window_not_judged", "no entry of kind metrics in the pack"),
        *((f"lineage_{r}_checkpoint_not_judged", f"run {r}: {no_ckpt}")
          for r in ("B_ALL", "C_ALL", "B_70", "C_70")),
        ("coverage_distance_not_judged", "no entry of kind conditions in the pack"),
        ("cost_lookup_not_judged", "no entry of kind ledger in the pack"),
        ("history_lookup_not_judged", "no entry of kind fix_rate in the pack"),
        ("trace_stats", "no entry of kind trace in the pack"),
        ("train_window", "no entry of kind metrics in the pack"),
        ("coverage_distance", "no entry of kind conditions in the pack"),
        ("trace", "no accepted entry of this kind"),
        ("metrics", "no accepted entry of this kind"),
        ("conditions", "no accepted entry of this kind"),
        ("cost_lookup", "no entry of kind ledger in the pack"),
        ("history_lookup", "no entry of kind fix_rate in the pack"),
        ("ledger", "no accepted entry of this kind"),
        ("fix_rate", "no accepted entry of this kind"),
        ("relaxed_sweep_not_judged", "no entry of kind outcomes in the pack"),
        ("relaxed_sweep", "no entry of kind outcomes in the pack"),
        ("outcomes", "no accepted entry of this kind"),
    ])
    assert a.status == "degraded"
    assert "No model was called: every hypothesis, rank and choice is the code floor." in a.notes
    assert any("Costs are not attached" in n for n in a.notes)


def test_without_scores_the_page_says_what_was_not_judged(
        make_pack: PackMaker, tmp_path: Path, store: Path) -> None:
    out = tmp_path / "bare"
    run_round(make_pack(scores=False), out, now=NOW, store=store)
    a = assembly_of(out)
    page = (out / "index.html").read_text()
    assert a.clusters == [] and a.headline is None and a.not_judged
    assert "no accepted entry of this kind" in page and "No failure cluster" in page


def test_a_run_name_is_data_and_is_escaped(
        make_pack: PackMaker, tmp_path: Path, store: Path) -> None:
    pack = make_pack(rename={"C_70": "<b>x</b>"})
    out = tmp_path / "out2"
    run_round(pack, out, now=NOW, store=store)
    page = (out / "index.html").read_text()
    assert "&lt;b&gt;x&lt;/b&gt;" in page
    assert "<b>x</b>" not in page


def test_the_same_round_gives_the_same_bytes(make_pack: PackMaker, tmp_path: Path,
                                              store: Path) -> None:
    pack = make_pack()
    run_round(pack, tmp_path / "a", now=NOW, store=store)
    run_round(pack, tmp_path / "b", now=NOW, store=store)
    for name in (ASSEMBLY_FILE, "index.html"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_each_invocation_appends_an_estimate_and_a_measurement(
        round_out: Path, make_pack: PackMaker, store: Path) -> None:
    def check(n: int) -> None:
        entries = ledger_entries(store)
        est = [e for e in entries if e.measure_kind == "estimated"]
        meas = [e for e in entries if e.measure_kind == "measured"]
        assert len(est) == len(meas) == n
        assert {m.estimate_entry_id for m in meas} == {e.id for e in est}
        assert "assumed" in (est[0].note or "")

    check(1)
    run_round(round_out.parent / "round" / "pack.json", round_out, from_step="render",
              store=store)
    check(2)


def test_from_render_rewrites_only_the_page(round_out: Path, store: Path) -> None:
    kept = {p: p.read_bytes() for p in round_out.rglob("*")
            if p.is_file() and p.name not in ("index.html", "run.json")}
    (round_out / "index.html").write_text("stale")
    record = run_round(round_out.parent / "round" / "pack.json", round_out,
                       from_step="render", store=store)
    assert [s.name for s in record.steps] == list(NO_MODEL_STEPS)
    assert "stale" not in (round_out / "index.html").read_text()
    assert {p: p.read_bytes() for p in kept} == kept


def test_from_assemble_works_too(round_out: Path, store: Path) -> None:
    before = (round_out / ASSEMBLY_FILE).read_bytes()
    run_round(round_out.parent / "round" / "pack.json", round_out, from_step="assemble",
              store=store)
    assert (round_out / ASSEMBLY_FILE).read_bytes() == before


def test_the_agent_hash_follows_the_rule_files(tmp_path: Path) -> None:
    root = tmp_path / "cfg"
    shutil.copytree(CONFIG_ROOT, root)
    first = agent_hash("tray", root=root)
    assert first == agent_hash("tray", root=root) and first != agent_hash("two_table", root=root)
    rules = root / "rules" / "scorer.yaml"
    rules.write_text(rules.read_text() + "\n# touched\n")
    assert agent_hash("tray", root=root) != first
    assert agent_version() == "3"


def test_a_rule_title_holds_no_digit(tmp_path: Path) -> None:
    raw = yaml.safe_load((RULES_DIR / "scorer.yaml").read_text())
    assert all(r.title for r in load_rules())
    raw["rules"][0]["title"] = "The latch fails in 3 runs"
    root = tmp_path / "rules"
    root.mkdir()
    (root / "scorer.yaml").write_text(yaml.safe_dump(raw))
    with pytest.raises(RulesRefused, match="digit"):
        load_rules(root)


def test_cli_success_and_refusals(make_pack: PackMaker, tmp_path: Path, store: Path) -> None:
    runner = CliRunner()
    pack = make_pack()
    out = tmp_path / "cli-out"
    base = ["round", "--pack", str(pack), "--store", str(store)]
    ok = runner.invoke(app, [*base, "--out", str(out), "--no-model"])
    assert ok.exit_code == 0, ok.output
    assert "degraded" in ok.output and "64 clusters" in ok.output
    assert str(out / "index.html") in ok.output
    again = runner.invoke(app, [*base, "--out", str(out), "--no-model"])
    assert again.exit_code == 2 and "exists" in again.output

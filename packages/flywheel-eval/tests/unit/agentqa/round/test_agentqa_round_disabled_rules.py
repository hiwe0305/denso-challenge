"""Rules switched off by id: `disabled_rules` of agent.yaml and `--disable-rule` (DA-52 2.2)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest
from flywheel.eval.agentqa.cli import app
from flywheel.eval.agentqa.round import hypotheses
from flywheel.eval.agentqa.round.hypotheses import (
    RulesRefused,
    configured_disabled,
    disabled_rules,
    hypothesize,
)
from flywheel.eval.agentqa.round.pipeline import RunRefused, run_round
from flywheel.eval.agentqa.round.records import RunRecord
from flywheel.eval.agentqa.round.version import AGENT_CONFIG, agent_hash
from helpers_round import (  # noqa: F401  (isolated_store is an autouse fixture)
    NOW,
    PLAN,
    PackMaker,
    isolated_store,
    pack_maker,
)
from typer.testing import CliRunner

RULE = "scorer_latch_too_strict"  # one of the two rules the fixture pack gives hypotheses


@pytest.fixture
def make_pack(tmp_path: Path) -> PackMaker:
    return pack_maker(tmp_path)


def rules_per_cluster(out: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = defaultdict(list)
    for line in (out / "hypotheses.jsonl").read_text().splitlines():
        row = json.loads(line)
        found[row["cluster"]["cluster_id"]].append(row["rule_id"])
    return dict(found)


def test_the_repo_disables_no_rule() -> None:
    assert configured_disabled() == []
    assert "disabled_rules" in AGENT_CONFIG.read_text()


def test_a_disabled_rule_gives_no_hypothesis_and_nothing_else_changes(
        make_pack: PackMaker, tmp_path: Path) -> None:
    pack = make_pack()
    on = run_round(pack, tmp_path / "on", now=NOW)
    off = run_round(pack, tmp_path / "off", now=NOW, disable_rules=[RULE])
    before, after = rules_per_cluster(tmp_path / "on"), rules_per_cluster(tmp_path / "off")
    assert any(RULE in ids for ids in before.values())
    assert sorted(before) == sorted(after)
    for cluster, ids in before.items():
        assert after[cluster] == ([i for i in ids if i != RULE] or ["none"])
    for name in ("facts.jsonl", "tool_calls.jsonl"):
        assert (tmp_path / "on" / name).read_bytes() == (tmp_path / "off" / name).read_bytes()
    assert on.disabled_rules == [] and off.disabled_rules == [RULE]
    assert on.agent_hash == agent_hash("tray", PLAN)
    assert off.agent_hash == agent_hash("tray", PLAN, disabled=[RULE]) != on.agent_hash


def test_nothing_disabled_writes_run_json_as_before(make_pack: PackMaker, tmp_path: Path) -> None:
    run_round(make_pack(), tmp_path / "out", now=NOW)
    assert "disabled_rules" not in json.loads((tmp_path / "out" / "run.json").read_text())


def test_an_old_run_json_still_parses() -> None:
    record = RunRecord.model_validate({"run_id": "run_x", "started_at": NOW.isoformat(),
                                       "status": "ok"})
    assert record.disabled_rules == []


def test_an_unknown_rule_id_is_refused_before_anything_runs(make_pack: PackMaker,
                                                            tmp_path: Path) -> None:
    out = tmp_path / "out"
    with pytest.raises(RulesRefused, match="'no_such_rule' are not rule ids"):
        run_round(make_pack(), out, now=NOW, disable_rules=[RULE, "no_such_rule"])
    assert not out.exists()


def test_the_config_list_is_read_and_checked(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "agent.yaml"
    config.write_text(f"version: 3\ndisabled_rules: [{RULE}, {RULE}]\n")
    assert configured_disabled(config) == [RULE]
    assert disabled_rules(["label_signal_missing"], config=config) == [
        RULE, "label_signal_missing"]
    config.write_text("disabled_rules: [ghost]\n")
    with pytest.raises(RulesRefused, match="ghost"):
        disabled_rules(config=config)
    config.write_text("disabled_rules: ghost\n")
    with pytest.raises(RulesRefused, match="list of rule ids"):
        configured_disabled(config)
    config.write_text("version: 3\n")
    assert configured_disabled(config) == []


def test_a_rule_disabled_in_agent_yaml_needs_no_extra_hash_pair(
        make_pack: PackMaker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "agent.yaml"
    config.write_text(f"disabled_rules: [{RULE}]\n")
    monkeypatch.setattr(hypotheses, "AGENT_CONFIG", config)
    record = run_round(make_pack(), tmp_path / "out", now=NOW, disable_rules=[RULE])
    assert record.disabled_rules == [RULE]
    assert record.agent_hash == agent_hash("tray", PLAN)  # agent.yaml's bytes already say it
    assert not any(RULE in ids for ids in rules_per_cluster(tmp_path / "out").values())


def test_hypothesize_takes_the_list_and_refuses_an_unknown_id(make_pack: PackMaker,
                                                              tmp_path: Path) -> None:
    out = tmp_path / "out"
    run_round(make_pack(), out, now=NOW)
    kept = hypothesize(out, "tray", disabled=[RULE])
    assert kept and RULE not in {h.rule_id for h in kept}
    with pytest.raises(RulesRefused, match="ghost"):
        hypothesize(out, "tray", disabled=["ghost"])


def test_the_agent_hash_follows_the_disabled_ids() -> None:
    plain = agent_hash("tray", PLAN)
    assert agent_hash("tray", PLAN, disabled=[]) == plain
    one = agent_hash("tray", PLAN, disabled=[RULE])
    assert one != plain and one == agent_hash("tray", PLAN, disabled=[RULE, RULE])
    both = ["label_signal_missing", RULE]
    assert agent_hash("tray", PLAN, disabled=both) == agent_hash("tray", PLAN,
                                                                 disabled=both[::-1]) != one


def test_a_redo_after_hypothesize_keeps_the_disabled_rules(make_pack: PackMaker,
                                                          tmp_path: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    run_round(pack, out, now=NOW, disable_rules=[RULE])
    with pytest.raises(RunRefused, match="redo from hypothesize"):
        run_round(pack, out, from_step="assemble")
    again = run_round(pack, out, from_step="assemble", disable_rules=[RULE])
    assert again.disabled_rules == [RULE]
    redone = run_round(pack, out, from_step="hypothesize")
    assert redone.disabled_rules == [] and any(
        RULE in ids for ids in rules_per_cluster(out).values())


def test_the_cli_option_is_repeatable_and_recorded(make_pack: PackMaker, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = CliRunner().invoke(app, [
        "round", "--pack", str(make_pack()), "--out", str(out), "--no-model",
        "--disable-rule", RULE, "--disable-rule", "label_signal_missing"])
    assert result.exit_code == 0, result.output
    record = RunRecord.model_validate_json((out / "run.json").read_text())
    assert record.disabled_rules == [RULE, "label_signal_missing"]
    assert record.agent_hash == agent_hash("tray", PLAN,
                                           disabled=[RULE, "label_signal_missing"])
    assert set(sum(rules_per_cluster(out).values(), [])) == {"none"}


def test_the_cli_refuses_an_unknown_id_in_one_line(make_pack: PackMaker, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = CliRunner().invoke(app, ["round", "--pack", str(make_pack()), "--out", str(out),
                                      "--no-model", "--disable-rule", "ghost"])
    assert result.exit_code == 2 and "ghost" in result.output
    assert len(result.output.strip().splitlines()) == 1 and not out.exists()


def test_a_redo_compares_the_disabled_rules_as_a_set(make_pack: PackMaker,
                                                     tmp_path: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    both = [RULE, "label_signal_missing"]
    run_round(pack, out, now=NOW, disable_rules=both)
    again = run_round(pack, out, from_step="assemble", disable_rules=both[::-1])
    assert set(again.disabled_rules) == set(both)
    with pytest.raises(RunRefused, match="redo from hypothesize"):
        run_round(pack, out, from_step="assemble", disable_rules=[RULE])

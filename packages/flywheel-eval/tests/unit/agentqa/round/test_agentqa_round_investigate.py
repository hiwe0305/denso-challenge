"""The investigate step (DA-52 tasks 2.3, 2.4): the loop, its caps, and the code floor.

No network: every provider is a fake handed to the gateway through `gateway_factory`. The
fake answers rank requests with the rank tests' good reply and investigate requests from a
script, so a model run with and without `--investigate` can be compared.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.contracts.agentqa import RoundHypothesis
from flywheel.eval.agentqa.cli import app
from flywheel.eval.agentqa.round import investigate as investigate_module
from flywheel.eval.agentqa.round.gateway import MODEL_CALLS_FILE
from flywheel.eval.agentqa.round.gateway_config import (
    CONFIG_ROOT,
    GatewayRefused,
    Profile,
    load_gateway_config,
)
from flywheel.eval.agentqa.round.investigate import (
    FINAL_ONLY,
    INVESTIGATED_FILE,
    INVESTIGATION_CALLS_FILE,
    INVESTIGATION_FACTS_FILE,
    INVESTIGATION_FILE,
    PROMPT,
    load_limits,
    parse_reply,
)
from flywheel.eval.agentqa.round.judge import load_roles
from flywheel.eval.agentqa.round.pipeline import (
    ALL_STEPS,
    STEPS,
    RunRefused,
    run_round,
    steps_of,
)
from flywheel.eval.agentqa.round.providers import ChatModel, ProviderError, ProviderReply
from flywheel.eval.agentqa.round.records import (
    FactRecord,
    HypothesisRecord,
    InvestigatedHypothesis,
    InvestigationEnd,
    InvestigationStep,
    ModelCallRecord,
    RunRecord,
    ToolCallRecord,
)
from helpers_round import (  # noqa: F401  (isolated_store is an autouse fixture)
    NOW,
    PackMaker,
    isolated_store,
    pack_maker,
)
from test_agentqa_round_model_steps import good, no_factory
from typer.testing import CliRunner

HEAD = "C_70/place/L-PLACE-POSE/l1"  # the largest cluster of the fixture pack
Reply = str | ProviderReply | Exception
Script = Callable[[dict[str, Any]], Reply]


def act(**fields: Any) -> str:
    return json.dumps({"thought": "reasoning", **fields})


def lookup(payload: dict[str, Any]) -> str:
    return act(action="call_tool", tool="task_lookup", params={})


def level_one(payload: dict[str, Any]) -> str:
    """A tool call that makes facts the plan did not: paired_compare on level 1 alone."""
    return act(action="call_tool", tool="paired_compare", params={"pairs": "all", "levels": [1]})


def made(payload: dict[str, Any]) -> str:
    """The first fact the last tool call of the history gave."""
    return str(next(h for h in reversed(payload["history"]) if h.get("facts"))["facts"][0])


def propose(payload: dict[str, Any]) -> str:
    fact = made(payload)
    return act(action="propose", cluster_id=HEAD,
               statement=f"The cluster differs from the successes: {{{fact}}}.",
               diagnosis="perception", intervention="report_only", support=[fact], contra=[])


def conclude(payload: dict[str, Any]) -> str:
    mine = payload["model_hypotheses"][0]
    fact = mine["support"][0]
    return act(action="conclude", keep=[{
        "hypothesis": mine["id"],
        "data_content": {"text": f"Demos of the cluster's step, as {{{fact}}} shows.",
                         "cites": [fact]},
        "first_check": {"text": "Replay the members first.", "cites": [fact]}}])


def conclude_none(payload: dict[str, Any]) -> str:
    return act(action="conclude", keep=[])


class Bot:
    """Rank requests get `good`; investigate requests the next script item, then `rest`."""

    model, revision, host, key_env = "fake-rank", "r0", "127.0.0.1", None

    def __init__(self, script: list[Script | Reply] | None = None,
                 rest: Script | Reply | None = None, tokens_in: int | None = None) -> None:
        self.script = list(script or [])
        self.rest = rest
        self.tokens_in = tokens_in
        self.payloads: list[dict[str, Any]] = []

    def chat(self, system: str, user: str, *, reply_schema: dict[str, Any] | None,
             max_tokens: int, timeout_s: float) -> ProviderReply:
        payload = json.loads(user)
        if "clusters" not in payload:
            return ProviderReply(text=good(payload), tokens_in=None, tokens_out=40)
        self.payloads.append(payload)
        item = self.script.pop(0) if self.script else self.rest
        if item is None:
            raise AssertionError("Bot: no scripted investigate reply left")
        reply = item(payload) if callable(item) else item
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, ProviderReply):
            return reply
        return ProviderReply(text=reply, tokens_in=self.tokens_in, tokens_out=30)


class Silent(Bot):
    def chat(self, system: str, user: str, *, reply_schema: dict[str, Any] | None,
             max_tokens: int, timeout_s: float) -> ProviderReply:
        raise AssertionError("no provider call may be made")


def factory_of(bot: ChatModel) -> Callable[[str, Profile], ChatModel]:
    return lambda name, profile: bot


@pytest.fixture
def make_pack(tmp_path: Path) -> PackMaker:
    return pack_maker(tmp_path)


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "store"


def gateway_dir(tmp_path: Path, *, investigate: str | None = "local_text",
                hosted_enabled: bool = False, name: str = "gw") -> Path:
    """The repo's gateway config with a wide run budget; `investigate=None` drops the role."""
    root = tmp_path / name
    root.mkdir()
    routing = yaml.safe_load((CONFIG_ROOT / "routing.yaml").read_text())
    routing["budget"].update(max_calls=200, max_input_tokens=10**9, max_usd=100.0)
    if investigate is None:
        routing["routes"].pop("investigate")
    else:
        routing["routes"]["investigate"]["public"] = investigate
    (root / "routing.yaml").write_text(yaml.safe_dump(routing))
    hosted = yaml.safe_load((CONFIG_ROOT / "hosted.yaml").read_text())
    hosted["enabled"] = hosted_enabled
    (root / "hosted.yaml").write_text(yaml.safe_dump(hosted))
    return root


def with_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **limits: Any) -> None:
    """The investigate block of roles.yaml with `limits` changed, for this test only."""
    roles = yaml.safe_load((CONFIG_ROOT / "roles.yaml").read_text())
    roles["investigate"].update(limits)
    path = tmp_path / "roles.yaml"
    path.write_text(yaml.safe_dump(roles))
    monkeypatch.setattr(investigate_module, "ROLES_FILE", path)


def run(pack: Path, out: Path, bot: ChatModel, store: Path, **kw: Any) -> RunRecord:
    return run_round(pack, out, now=NOW, store=store, no_model=False,
                     gateway_factory=factory_of(bot), **kw)


def lines_of(path: Path) -> list[str]:
    return path.read_text().splitlines()


def log_of(out: Path) -> tuple[list[InvestigationStep], InvestigationEnd]:
    lines = lines_of(out / INVESTIGATION_FILE)
    steps = [InvestigationStep.model_validate_json(x) for x in lines[:-1]]
    return steps, InvestigationEnd.model_validate_json(lines[-1])


def model_calls(out: Path) -> list[ModelCallRecord]:
    return [ModelCallRecord.model_validate_json(x) for x in lines_of(out / MODEL_CALLS_FILE)]


def kept_of(out: Path) -> list[InvestigatedHypothesis]:
    return [InvestigatedHypothesis.model_validate_json(x)
            for x in lines_of(out / INVESTIGATED_FILE)]


# Fields of assembly.json that differ between two runs of the same pack by design.
ASSEMBLY_DIFFERS = ("run_id",)


def assembly(out: Path) -> dict[str, Any]:
    raw = json.loads((out / "assembly.json").read_text())
    for key in ASSEMBLY_DIFFERS:
        raw.pop(key)
    return dict(raw)


# a model hypothesis fits the contract -------------------------------------------------------


def test_a_model_hypothesis_fits_round_hypothesis() -> None:
    record = InvestigatedHypothesis.model_validate({
        "hypothesis_id": "H79",
        "cluster": {"cluster_id": HEAD, "run": "C_70", "step": "place",
                    "label": "L-PLACE-POSE", "level": 1, "size": 9},
        "statement": "Members lie outside the reference: {F12}.", "diagnosis": "coverage_gap",
        "intervention": "sim_s1", "support": ["F12"], "contra": ["F3"],
        "data_content": {"text": "Demos of the step: {F12}.", "cites": ["F12"]},
        "first_check": {"text": "Replay the members.", "cites": []},
        "offered": {"F12": {"name": "x_outside_total", "value": 7, "unit": "rollouts",
                            "provenance": "code", "comparison": True}},
        "proposed_at": 3})
    contract = RoundHypothesis(
        hypothesis_id=record.hypothesis_id, cluster_id=record.cluster.cluster_id,
        diagnosis=record.diagnosis, note="model", rule_id=None, rank=1,
        support=record.support, contra=record.contra, explanation=record.statement,
        source="model")
    assert contract.rule_id is None and contract.source == "model"
    with pytest.raises(ValueError, match="number"):
        RoundHypothesis(hypothesis_id="H80", cluster_id=HEAD, diagnosis="coverage_gap",
                        note="model", rank=1, explanation="It broke in 7 rollouts.",
                        source="model")


# configuration ----------------------------------------------------------------------------


def test_the_roles_file_holds_the_investigate_block() -> None:
    limits = load_limits()
    assert (limits.max_steps, limits.max_calls, limits.max_input_tokens, limits.max_usd) == (
        50, 60, 1000000, 1.0)
    assert limits.max_rejected_in_a_row == 3 and limits.max_facts == 120
    assert load_roles().investigate is not None  # the rank loader still reads the file


def test_the_prompt_names_no_task_word() -> None:
    text = PROMPT.read_text(encoding="utf-8")
    for word in ("tray", "yaw", "tilt", "height", "raised", "table", "hand"):
        assert not re.search(word, text, re.IGNORECASE), word


def test_a_routing_file_without_the_role_still_loads(tmp_path: Path) -> None:
    config = load_gateway_config(gateway_dir(tmp_path, investigate=None))
    assert "investigate" not in config.routes
    assert "investigate" in load_gateway_config().routes


def test_a_reply_must_be_one_action() -> None:
    assert parse_reply("```json\n" + lookup({}) + "\n```").action == "call_tool"
    for bad in ('{"action": "call_tool", "tool": "x", "params": {}, "extra": 1}',
                '{"action": "guess"}', "[1]"):
        with pytest.raises(ValueError):
            parse_reply(bad)


# the flag ---------------------------------------------------------------------------------


def test_with_the_flag_off_nothing_changes(make_pack: PackMaker, tmp_path: Path,
                                           store: Path) -> None:
    assert steps_of(False) == STEPS and steps_of(True) == steps_of(True, True)
    assert list(ALL_STEPS) == [*STEPS[:4], "investigate", *STEPS[4:]]
    pack, out = make_pack(), tmp_path / "out"
    record = run(pack, out, Bot(), store)
    assert [s.name for s in record.steps] == list(STEPS)
    assert "investigate" not in json.loads((out / "run.json").read_text())
    assert not any((out / f).exists() for f in investigate_module.FILES)
    assert {c.role for c in model_calls(out)} == {"rank"}
    with pytest.raises(RunRefused, match="without the investigate step"):
        run_round(pack, out, from_step="judge", store=store, investigate=True)
    with pytest.raises(RunRefused, match="not a step"):
        run_round(pack, out, from_step="investigate", store=store)


def test_investigate_needs_a_model_run(make_pack: PackMaker, tmp_path: Path,
                                       store: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    with pytest.raises(RunRefused, match="needs a model run"):
        run_round(pack, out, store=store, no_model=True, investigate=True)
    assert not out.exists()
    cli = CliRunner().invoke(app, ["round", "--pack", str(pack), "--out", str(out),
                                   "--store", str(store), "--no-model", "--investigate"])
    assert cli.exit_code == 2 and "needs a model run" in cli.output
    assert len(cli.output.strip().splitlines()) == 1 and not out.exists()


def test_no_route_for_the_role_refuses_the_step(make_pack: PackMaker, tmp_path: Path,
                                                store: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    root = gateway_dir(tmp_path, investigate=None)
    with pytest.raises(GatewayRefused, match="no route"):
        run(pack, out, Silent(), store, gateway_root=root, investigate=True)
    record = RunRecord.model_validate_json((out / "run.json").read_text())
    assert record.steps[-1].name == "investigate" and record.steps[-1].status == "broken"
    assert record.problems[-1].startswith("investigate: GatewayRefused: the investigate role "
                                          "has no route")
    assert not (out / MODEL_CALLS_FILE).exists()
    cli = CliRunner().invoke(app, ["round", "--pack", str(pack), "--out", str(tmp_path / "c"),
                                   "--store", str(store), "--gateway-config", str(root),
                                   "--investigate"])
    assert cli.exit_code == 2 and "has no route" in cli.output
    assert len(cli.output.strip().splitlines()) == 1


def test_a_hosted_route_for_an_unconfirmed_pack_makes_no_call(make_pack: PackMaker,
                                                               tmp_path: Path,
                                                               store: Path) -> None:
    from test_agentqa_round_snapshot import fill as fill_store

    pack = make_pack(snapshot_of=fill_store(tmp_path / "live"), snapshot_class="public")
    root = gateway_dir(tmp_path, investigate="haiku", hosted_enabled=True)
    out = tmp_path / "out"
    with pytest.raises(GatewayRefused, match="unknown"):
        run_round(pack, out, now=NOW, store=store, no_model=False, gateway_root=root,
                  gateway_factory=no_factory, investigate=True)
    record = RunRecord.model_validate_json((out / "run.json").read_text())
    assert record.status == "broken" and record.steps[-1].name == "investigate"
    assert record.problems[-1].startswith("investigate: GatewayRefused")
    assert not (out / MODEL_CALLS_FILE).exists() and not (out / INVESTIGATION_FILE).exists()


# the happy path ---------------------------------------------------------------------------


def test_call_propose_conclude_hands_one_hypothesis_on(make_pack: PackMaker, tmp_path: Path,
                                                       store: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    bot = Bot([level_one, propose, conclude])
    record = run(pack, out, bot, store, investigate=True)
    assert [s.name for s in record.steps] == list(ALL_STEPS)
    assert {s.name: s.status for s in record.steps}["investigate"] == "ok"
    assert json.loads((out / "run.json").read_text())["investigate"] is True

    steps, end = log_of(out)
    assert [s.action for s in steps] == ["call_tool", "propose", "conclude"]
    assert all(s.outcome == "ok" and s.thought == "reasoning" for s in steps)
    assert end.ending == "concluded" and end.steps == 3 and end.calls == 3 and end.kept == 1
    assert steps[0].tool_call_id == "I1" and steps[0].call_ids == ["M1"]

    seeded = [FactRecord.model_validate_json(x) for x in lines_of(out / "facts.jsonl")]
    new = [FactRecord.model_validate_json(x) for x in lines_of(out / INVESTIGATION_FACTS_FILE)]
    last = max(int(f.fact_id[1:]) for f in seeded)
    assert new and [f.fact_id for f in new] == [f"F{last + k}" for k in range(1, len(new) + 1)]
    assert {f.tool_call_id for f in new} == {"I1"}
    assert not {f.name for f in new} & {f.name for f in seeded}
    assert steps[0].fact_ids == [f.fact_id for f in new]
    calls = [ToolCallRecord.model_validate_json(x)
             for x in lines_of(out / INVESTIGATION_CALLS_FILE)]
    assert [(c.call_id, c.tool, c.status) for c in calls] == [("I1", "paired_compare", "ran")]
    assert calls[0].input_sha256 and calls[0].fact_ids == steps[0].fact_ids

    rules = [HypothesisRecord.model_validate_json(x) for x in lines_of(out / "hypotheses.jsonl")]
    top = max(int(h.hypothesis_id[1:]) for h in rules)
    (kept,) = kept_of(out)
    fact = new[0].fact_id
    assert kept.hypothesis_id == f"H{top + 1}" and steps[1].hypothesis_id == kept.hypothesis_id
    assert kept.cluster.cluster_id == HEAD and kept.support == [fact]
    assert (kept.diagnosis, kept.intervention, kept.proposed_at) == ("perception",
                                                                     "report_only", 2)
    assert kept.data_content.cites == [fact] and kept.first_check.text.startswith("Replay")
    offered = kept.offered[fact]
    assert (offered.name, offered.value, offered.provenance) == (new[0].name, new[0].value,
                                                                 "code")
    RoundHypothesis(hypothesis_id=kept.hypothesis_id, cluster_id=kept.cluster.cluster_id,
                    diagnosis=kept.diagnosis, note="model", rank=1, support=kept.support,
                    contra=kept.contra, explanation=kept.statement, source="model")

    # Every fact shown carries a meaning; the step's calls are in the run's totals.
    assert all(f["meaning"] for p in bot.payloads for f in p["facts"])
    assert fact in {f["id"] for f in bot.payloads[1]["facts"]}
    lines = model_calls(out)
    assert [c.role for c in lines[:3]] == ["investigate"] * 3
    assert record.totals.calls == sum(c.tries for c in lines) == 3 + 8
    assert record.totals.tokens_in == sum(c.tokens_in for c in lines)
    assert record.totals.tokens_out == 3 * 30 + 8 * 40
    assert end.tokens_in == sum(c.tokens_in for c in lines[:3])


def test_resume_from_investigate_replays_without_a_provider_call(
        make_pack: PackMaker, tmp_path: Path, store: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    run(pack, out, Bot([level_one, propose, conclude]), store, investigate=True)
    files = {f: (out / f).read_bytes() for f in (*investigate_module.FILES, MODEL_CALLS_FILE)}
    again = run_round(pack, out, from_step="investigate", store=store,
                      gateway_factory=factory_of(Silent()))
    assert again.investigate is True and [s.name for s in again.steps] == list(ALL_STEPS)
    assert {f: (out / f).read_bytes() for f in files} == files
    assert again.totals.replayed == 3 + 8 and again.totals.calls == 3 + 8


# rejections -------------------------------------------------------------------------------


def test_rejected_steps_are_logged_and_the_run_goes_on(make_pack: PackMaker, tmp_path: Path,
                                                       store: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    with_limits(tmp_path, monkeypatch, max_input_tokens=10**8)
    rule = "H1"
    script: list[Script | Reply] = [
        "not json at all", level_one,                                        # 1 resend, ok
        act(action="call_tool", tool="read_file", params={}),               # 2 unknown tool
        lookup,                                                               # 3
        act(action="call_tool", tool="step_pass_table",
            params={"runs": ["NOPE"]}),                                       # 4 outside domain
        lookup,                                                               # 5
        lambda p: act(action="propose", cluster_id=HEAD, statement="See {F999999}.",
                      diagnosis="perception", intervention="report_only",
                      support=["F999999"]),                                   # 6 unknown fact
        lookup,                                                               # 7
        lambda p: act(action="propose", cluster_id=HEAD,
                      statement=f"It broke in 14 rollouts {{{made(p)}}}.",
                      diagnosis="perception", intervention="report_only",
                      support=[made(p)]),                                     # 8 bare number
        lookup,                                                               # 9
        act(action="drop", hypothesis=rule, refuted_by=["F1"]),             # 10 rule hypothesis
        conclude_none,                                                        # 11
    ]
    pack, out = make_pack(), tmp_path / "out"
    bot = Bot(script)
    record = run(pack, out, bot, store, investigate=True)
    steps, end = log_of(out)
    assert end.ending == "concluded" and end.steps == 11 and end.calls == 12
    assert {s.name: s.status for s in record.steps}["investigate"] == "ok"
    outcome = {s.step: (s.outcome, s.reason) for s in steps}
    assert steps[0].call_ids == ["M1", "M2"] and outcome[1] == ("ok", "")
    assert "previous_errors" in bot.payloads[1] and bot.payloads[1]["history"] == []
    assert outcome[2][0] == "rejected" and "unknown tool 'read_file'" in outcome[2][1]
    assert outcome[4][0] == "rejected" and "parameters refused" in outcome[4][1]
    assert outcome[6][0] == "rejected" and "F999999" in outcome[6][1]
    assert outcome[8][0] == "rejected" and "number(s) ['14']" in outcome[8][1]
    assert outcome[10][0] == "rejected" and "rule hypothesis" in outcome[10][1]
    # The reason reaches the model in the next step's history.
    history = bot.payloads[-1]["history"]
    assert [h["outcome"] for h in history].count("rejected") == 5
    assert "unknown tool" in history[1]["reason"]
    calls = [ToolCallRecord.model_validate_json(x)
             for x in lines_of(out / INVESTIGATION_CALLS_FILE)]
    assert [c.status for c in calls] == ["ran", "ran", "refused", "ran", "ran", "ran"]
    assert kept_of(out) == []


def test_a_reply_unreadable_twice_is_a_rejected_step(make_pack: PackMaker, tmp_path: Path,
                                                     store: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    run(pack, out, Bot(["{broken", "{still broken", conclude_none]), store, investigate=True)
    steps, end = log_of(out)
    assert steps[0].outcome == "rejected" and steps[0].call_ids == ["M1", "M2"]
    assert steps[0].raw == "{still broken" and steps[0].parsed is None
    assert steps[0].reason.startswith("after a resend: not a JSON object")
    assert end.ending == "concluded" and end.steps == 2


# caps and the code floor ------------------------------------------------------------------


Case = tuple[str, dict[str, Any], list[Script | Reply], Script | Reply | None, dict[str, Any]]
CAPS: list[Case] = [
    ("max_steps", {"max_steps": 2}, [], lookup, {}),
    ("max_calls", {"max_calls": 3}, [], lookup, {}),
    # A first reply reporting a million input tokens leaves no room for a second request.
    ("max_input_tokens", {"max_input_tokens": 200000}, [], lookup, {"tokens_in": 10**6}),
    ("max_usd", {"max_usd": 0.05, "max_input_tokens": 10**8}, [], lookup,
     {"tokens_in": 10**6, "hosted": True}),
    ("rejected_in_a_row", {}, [],
     act(action="call_tool", tool="read_file", params={}), {}),
    ("gateway_failed", {}, [lookup],
     ProviderError("the server went away", retryable=False), {}),
]


@pytest.mark.parametrize(("ending", "limits", "script", "rest", "extra"), CAPS,
                         ids=[c[0] for c in CAPS])
def test_each_cap_ends_the_loop_on_the_code_floor(
        make_pack: PackMaker, tmp_path: Path, store: Path, monkeypatch: pytest.MonkeyPatch,
        ending: str, limits: dict[str, Any], script: list[Script | Reply],
        rest: Script | Reply | None, extra: dict[str, Any]) -> None:
    with_limits(tmp_path, monkeypatch, **limits)
    hosted = bool(extra.get("hosted"))
    root = gateway_dir(tmp_path, investigate="haiku" if hosted else "local_text",
                       hosted_enabled=hosted)
    pack = make_pack()
    floor = tmp_path / "floor"
    run(pack, floor, Bot(), store, gateway_root=root)
    out = tmp_path / "out"
    bot = Bot(script, rest, tokens_in=extra.get("tokens_in"))
    record = run(pack, out, bot, store, gateway_root=root, investigate=True)

    steps, end = log_of(out)
    assert end.ending == ending and end.kept == 0
    assert (out / INVESTIGATED_FILE).read_text() == ""
    status = {s.name: s.status for s in record.steps}
    assert status["investigate"] == "degraded" and record.status == "degraded"
    assert any(p.startswith(f"investigate: the investigation ended {ending}")
               for p in record.problems)
    expected_steps = {"max_steps": 2, "max_calls": 3, "max_input_tokens": 1, "max_usd": 1,
                      "rejected_in_a_row": 3, "gateway_failed": 2}[ending]
    assert end.steps == len(steps) == expected_steps
    if ending == "gateway_failed":
        assert steps[-1].reason.startswith("call M2 failed")
    # Never below the code floor: the other steps' files are those of a run without it.
    for name in ("hypotheses.jsonl", "facts.jsonl", "tool_calls.jsonl"):
        assert (out / name).read_bytes() == (floor / name).read_bytes(), name
    assert assembly(out) == assembly(floor)


# the final step: the end of the budget is kept for conclude --------------------------------


def _tokens_per_step(make_pack: PackMaker, tmp_path: Path, store: Path,
                     script: list[Script | Reply]) -> list[int]:
    """The input tokens each investigate request of `script` cost on a run without caps."""
    out = tmp_path / "measured_run"
    run(make_pack("measured"), out, Bot(list(script)), store, investigate=True)
    return [c.tokens_in for c in model_calls(out) if c.role == "investigate"]


def test_a_small_token_cap_makes_the_last_step_final_and_conclude_is_handed_on(
        make_pack: PackMaker, tmp_path: Path, store: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    script: list[Script | Reply] = [level_one, propose, conclude]
    t = _tokens_per_step(make_pack, tmp_path, store, script)
    # room for the three requests, but not for two more of the third's size at step 3
    with_limits(tmp_path, monkeypatch, max_input_tokens=t[0] + t[1] + t[2] + t[2] // 2)
    out = tmp_path / "out"
    bot = Bot(list(script))
    run(make_pack(), out, bot, store, investigate=True)
    assert ["final" in p for p in bot.payloads] == [False, False, True]
    assert bot.payloads[2]["final"] is True and "budget" in bot.payloads[2]
    steps, end = log_of(out)
    assert end.ending == "concluded" and end.kept == 1
    assert [s.outcome for s in steps] == ["ok", "ok", "ok"]
    assert len(kept_of(out)) == 1


def test_any_other_action_at_the_final_step_is_rejected(
        make_pack: PackMaker, tmp_path: Path, store: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    t = _tokens_per_step(make_pack, tmp_path, store, [level_one, propose, conclude])
    with_limits(tmp_path, monkeypatch, max_input_tokens=t[0] + t[1] + t[2] + t[2] // 2)
    out = tmp_path / "out"
    bot = Bot([level_one, propose, level_one, conclude])
    run(make_pack(), out, bot, store, investigate=True)
    steps, end = log_of(out)
    assert bot.payloads[2].get("final") is True
    assert steps[2].action == "call_tool" and steps[2].outcome == "rejected"
    assert steps[2].reason == FINAL_ONLY and steps[2].tool_call_id == ""
    assert len(lines_of(out / INVESTIGATION_CALLS_FILE)) == 1  # only step 1's tool ran
    # the hard cap is unchanged: the next request does not fit, nothing is handed on
    assert end.ending == "max_input_tokens" and end.kept == 0
    assert (out / INVESTIGATED_FILE).read_text() == ""


def test_the_last_step_allowed_is_final(make_pack: PackMaker, tmp_path: Path, store: Path,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    with_limits(tmp_path, monkeypatch, max_steps=3)
    bot = Bot([level_one, propose, conclude])
    run(make_pack(), tmp_path / "out", bot, store, investigate=True)
    assert ["final" in p for p in bot.payloads] == [False, False, True]
    assert log_of(tmp_path / "out")[1].ending == "concluded"


# failures inside the loop -----------------------------------------------------------------


def test_a_tool_that_raises_is_a_rejected_step(make_pack: PackMaker, tmp_path: Path,
                                               store: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    real = investigate_module.ToolSession.call

    def broken(self: Any, name: str, params: Any) -> Any:
        if name == "lineage":  # adds a fact, then fails: the fact must not leak
            self.book.add("leaked_by_a_broken_tool", 1, "pack.json")
            raise RuntimeError("disk on fire\nsecond line")
        return real(self, name, params)

    monkeypatch.setattr(investigate_module.ToolSession, "call", broken)
    pack, out = make_pack(), tmp_path / "out"
    bot = Bot([act(action="call_tool", tool="lineage", params={}), level_one, conclude_none])
    record = run(pack, out, bot, store, investigate=True)
    steps, end = log_of(out)
    assert steps[0].outcome == "rejected" and steps[0].fact_ids == []
    assert steps[0].reason == "the tool failed: RuntimeError: disk on fire"
    assert steps[0].tool_call_id == ""
    assert steps[1].outcome == "ok" and end.ending == "concluded"
    assert {s.name: s.status for s in record.steps}["investigate"] == "ok"
    new = [FactRecord.model_validate_json(x) for x in lines_of(out / INVESTIGATION_FACTS_FILE)]
    assert "leaked_by_a_broken_tool" not in {f.name for f in new}
    assert not any(f["name"] == "leaked_by_a_broken_tool" for p in bot.payloads
                   for f in p["facts"])
    # The rolled-back id is given to the next new fact, so the numbering has no hole.
    seeded = [FactRecord.model_validate_json(x) for x in lines_of(out / "facts.jsonl")]
    assert new[0].fact_id == f"F{len(seeded) + 1}"
    calls = [ToolCallRecord.model_validate_json(x)
             for x in lines_of(out / INVESTIGATION_CALLS_FILE)]
    assert [c.call_id for c in calls] == ["I1"] and calls[0].tool == "paired_compare"


def test_an_error_in_the_loop_ends_it_on_the_code_floor(make_pack: PackMaker, tmp_path: Path,
                                                        store: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(self: Any, action: Any, step: int) -> Any:
        raise KeyError("no such cluster\nmore")

    root = gateway_dir(tmp_path)
    pack = make_pack()
    floor = tmp_path / "floor"
    run(pack, floor, Bot(), store, gateway_root=root)
    monkeypatch.setattr(investigate_module._Investigation, "_propose", boom)
    out = tmp_path / "out"
    record = run(pack, out, Bot([level_one, propose]), store, gateway_root=root,
                 investigate=True)
    steps, end = log_of(out)
    assert end.ending == "error" and end.detail == "KeyError: no such cluster"
    assert [s.step for s in steps] == [1] and end.calls == 2
    assert (out / INVESTIGATED_FILE).read_text() == ""
    assert lines_of(out / INVESTIGATION_CALLS_FILE)  # what the log holds is still written
    assert {s.name: s.status for s in record.steps}["investigate"] == "degraded"
    assert any(p.startswith("investigate: the investigation ended error (KeyError: no such "
                            "cluster)") for p in record.problems)
    assert assembly(out) == assembly(floor)


def test_a_call_id_missing_from_model_calls_ends_the_loop_with_error(
        make_pack: PackMaker, tmp_path: Path, store: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    real = investigate_module.Gateway.call

    def renamed(self: Any, role: str, request: Any) -> Any:
        reply = real(self, role, request)
        if role != "investigate":
            return reply
        return type(reply)(status=reply.status, call_id="M999", text=reply.text)

    monkeypatch.setattr(investigate_module.Gateway, "call", renamed)
    out = tmp_path / "out"
    record = run(make_pack(), out, Bot([lookup]), store, investigate=True)
    _, end = log_of(out)
    assert end.ending == "error" and end.detail.startswith("ValueError: model_calls.jsonl: "
                                                           "no line for call M999")
    assert {s.name: s.status for s in record.steps}["investigate"] == "degraded"

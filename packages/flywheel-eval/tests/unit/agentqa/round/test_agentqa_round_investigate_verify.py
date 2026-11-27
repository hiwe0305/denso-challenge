"""Verify, assemble and render the investigate role's hypotheses (DA-52 task 2.5, AC 5, 6).

The end-to-end run uses a small pack with outcomes, so that `measure_compare` really runs:
one run R, twelve successes of level 1, a place cluster of six near misses on level 1 (the
`near_miss_placement` rule matches it; half of its members tilted at the failure) and one
of four members on level 2. Both failure clusters are off the successes on `offset_m`, a
measure the scorer does not threshold. The investigate script calls the tool five times,
proposes nine hypotheses on the level-1 cluster and keeps them all; only the two that
cite separation on `offset_m` keep (the evidence rule, tightened 27/11/2026: being beyond
the scorer's threshold restates the failure label).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.entities import Score
from flywheel.contracts.outcome import RolloutOutcome
from flywheel.eval.agentqa.round.assemble import (
    ASSEMBLY_FILE,
    _model_hypothesis,
    _with_model,
    assemble,
    model_group,
    place,
)
from flywheel.eval.agentqa.round.hypotheses import NONE_RULE, load_rules
from flywheel.eval.agentqa.round.investigate import INVESTIGATED_FILE
from flywheel.eval.agentqa.round.records import (
    Assembly,
    ClusterRef,
    ClusterView,
    HypothesisView,
    InvestigatedHypothesis,
    RunRecord,
    VerdictRecord,
)
from flywheel.eval.agentqa.round.render import INDEX_FILE, render
from flywheel.eval.agentqa.round.verify import (
    INVESTIGATION_FACTS_FILE,
    VERDICTS_FILE,
    verify,
)
from flywheel.eval.agentqa.tools.measures import cluster_slug, parse_fact_name
from helpers_round import NOW, isolated_store  # noqa: F401  (an autouse fixture)
from test_agentqa_round_investigate import Bot, Silent, act, run, with_limits
from test_agentqa_round_outcomes import POSE, outcome_pack

PLACE = "L-PLACE-POSE"
HEAD = f"R/place/{PLACE}/l1"
OTHER = f"R/place/{PLACE}/l2"
DIST, YAW, TILT = "final.place_distance_m", "final.place_yaw_error_deg", "at_failure.tilt_deg"
OFFSET = "final.offset_m"  # a measure the scorer does not threshold; both clusters separate
SAME, ALL = "successes_same_level", "successes_all_levels"


# --- the pack and the run ------------------------------------------------------------------


def _score(name: str, ok: bool, level: int = 1) -> Score:
    return Score(episode_id=f"R/{name}", task_id="tray", config_sha256="0" * 64,
                 trace_sha256="0" * 64, success=ok, failure_kind=None if ok else PLACE,
                 level=level, first_failed_step=None if ok else 5,
                 step_status=["pass"] * 7 if ok else
                 ["pass"] * 5 + ["fail", "not_attempted"])  # type: ignore[arg-type]


def _outcome(name: str, ok: bool, d: float, tilt: float, level: int = 1,
             offset: float = 0.0) -> RolloutOutcome:
    return RolloutOutcome.model_validate({
        "episode_id": f"R/{name}", "run_plan_id": "rp-1", "task_id": "tray", "run": "R",
        "seed": 1, "level": level, "sim_time_s": 10.0, "control_steps": 500,
        "final": {**POSE, "place_distance_m": d, "offset_m": offset},
        "verdict": {"scorer_version": "2", "step_names": ["place"], "step_latched": [ok],
                    "success": ok, "failure_label": None if ok else PLACE,
                    "failure_t": None if ok else 2.0,
                    "at_failure": None if ok else {"tilt_deg": tilt}}})


def small_pack(root: Path) -> Path:
    scores, outs = [], []
    for k in range(12):
        scores.append(_score(f"ok{k}", True))
        outs.append(_outcome(f"ok{k}", True, 0.01, 1.0))
    for k in range(6):  # near misses of the target; half of them tilted at the failure
        scores.append(_score(f"h{k}", False))
        outs.append(_outcome(f"h{k}", False, 0.1, 20.0 if k < 3 else 1.0, offset=0.05))
    for k in range(4):
        scores.append(_score(f"o{k}", False, 2))
        outs.append(_outcome(f"o{k}", False, 0.3, 1.0, 2, offset=0.05))
    return outcome_pack(root, {"R": (scores, outs)})


def compare(cluster: str, measure: str, against: str) -> Callable[[dict[str, Any]], str]:
    return lambda payload: act(action="call_tool", tool="measure_compare",
                               params={"cluster": cluster, "measure": measure,
                                       "against": against})


def fact_named(payload: dict[str, Any], test: Callable[[str, object], bool]) -> str:
    hits = [f["id"] for f in payload["facts"] if test(f["name"], f["value"])]
    assert hits, "no fact of the request passes the test"
    return str(hits[-1])


def cmp_fact(cluster: str, measure: str, suffix: str) -> Callable[[str, object], bool]:
    """A `measure_compare` fact of `cluster` on `measure` with `suffix`."""
    run, step, label, level = cluster.split("/")
    own = cluster_slug(step, label, int(level[1:]))

    def test(name: str, value: object = None) -> bool:
        parts = parse_fact_name(name)
        return (parts is not None and parts.kind == "cmp" and parts.run == run
                and parts.cluster == own and parts.suffix == suffix
                and parts.measure == measure.replace(".", "__"))
    return test


def own_near_miss(name: str, value: object) -> bool:
    """The `relaxed_sweep` fact that the level-1 cluster is a near miss, and it is true:
    a true boolean about the cluster itself, of another tool than `measure_compare`."""
    return value is True and name == f"R_cluster_{cluster_slug('place', PLACE, 1)}_near_miss"


Test = Callable[[str, object], bool]
# Each proposal on HEAD: (name, tests picking its support facts). The first two cite
# separation of HEAD on a measure the scorer does not threshold (the second also cites a
# beyond-threshold count next to it); the other seven are not evidence (AC 5).
PROPOSALS: list[tuple[str, list[Test]]] = [
    ("separated_free", [cmp_fact(HEAD, OFFSET, "_separated")]),
    ("with_beyond", [cmp_fact(HEAD, OFFSET, "_separated"),
                     cmp_fact(HEAD, DIST, "_beyond_threshold")]),
    ("separated_thresholded", [cmp_fact(HEAD, DIST, "_separated")]),
    ("beyond_most", [cmp_fact(HEAD, DIST, "_beyond_threshold")]),
    ("beyond_half", [cmp_fact(HEAD, TILT, "_beyond_threshold")]),
    ("median_only", [cmp_fact(HEAD, OFFSET, "_median")]),
    ("other_tool_true", [own_near_miss]),
    ("other_cluster", [cmp_fact(OTHER, OFFSET, "_separated")]),
    ("not_separated", [cmp_fact(HEAD, YAW, "_separated")]),
]
KEPT = ["H3", "H4"]  # H1, H2 are the rules' hypotheses
RESTATES = ["H5", "H6", "H7"]  # evidence only on a thresholded measure
NOTHING = ["H8", "H9", "H10", "H11"]  # no separation of its own cluster at all
THIN = [*RESTATES, *NOTHING]


def proposer(tests: list[Test]) -> Callable[[dict[str, Any]], str]:
    def reply(payload: dict[str, Any]) -> str:
        fids = [fact_named(payload, t) for t in tests]
        cited = " ".join(f"{{{f}}}" for f in fids)
        return act(action="propose", cluster_id=HEAD,
                   statement=f"The cluster stands apart from the successes: {cited}.",
                   diagnosis="perception", intervention="report_only", support=fids,
                   contra=[])
    return reply


def keep_all(payload: dict[str, Any]) -> str:
    return act(action="conclude", keep=[{
        "hypothesis": h["id"],
        "data_content": {"text": f"Demos of the place step, as {{{h['support'][0]}}} shows.",
                         "cites": [h["support"][0]]},
        "first_check": {"text": "Replay the members first.", "cites": []}}
        for h in payload["model_hypotheses"]])


@pytest.fixture
def investigated_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """(pack, out, store) of a model run with `--investigate` on the small pack."""
    with_limits(tmp_path, monkeypatch, max_steps=30)
    pack, out, store = small_pack(tmp_path / "pack"), tmp_path / "out", tmp_path / "store"
    script: list[Any] = [compare(HEAD, DIST, SAME), compare(HEAD, YAW, SAME),
                         compare(HEAD, TILT, SAME), compare(HEAD, OFFSET, SAME),
                         compare(OTHER, OFFSET, ALL),
                         *(proposer(t) for _, t in PROPOSALS), keep_all]
    record = run(pack, out, Bot(script), store, investigate=True)
    assert [s.status for s in record.steps if s.name == "investigate"] == ["ok"]
    return pack, out, store


def verdicts_of(out: Path) -> list[VerdictRecord]:
    return [VerdictRecord.model_validate_json(x)
            for x in (out / VERDICTS_FILE).read_text().splitlines()]


def mine(out: Path) -> dict[str, VerdictRecord]:
    return {v.unit: v for v in verdicts_of(out) if v.role == "investigate"}


def assembly_of(out: Path) -> Assembly:
    return Assembly.model_validate_json((out / ASSEMBLY_FILE).read_text())


def cluster_of(a: Assembly, cluster_id: str) -> Any:
    return next(c for c in a.clusters if c.cluster.cluster_id == cluster_id)


# --- AC 5: the keep rule --------------------------------------------------------------------


def test_the_fact_names_round_trip_and_the_slug_is_the_tools() -> None:
    name = (f"R_cluster_{cluster_slug('place', PLACE, 1)}_cmp__final__place_distance_m"
            f"__vs__{SAME}_beyond_threshold")
    parts = parse_fact_name(name)
    assert parts is not None and parts.run == "R" and parts.tool == "measure_compare"
    assert parts.cluster == "place_L-PLACE-POSE_l1" and parts.suffix == "_beyond_threshold"
    assert parts.base + "_members" == name.replace("_beyond_threshold", "_members")
    assert parse_fact_name(f"{PLACE}_judgeable") is None


def test_only_evidence_about_its_own_cluster_keeps_a_hypothesis(
        investigated_run: tuple[Path, Path, Path]) -> None:
    _, out, _ = investigated_run
    verdicts = mine(out)
    assert sorted(verdicts, key=lambda h: int(h[1:])) == [*KEPT, *THIN]
    for hid in KEPT:
        assert verdicts[hid].verdict == "accepted", verdicts[hid].reason
    for hid in THIN:
        assert verdicts[hid].verdict == "rejected"
        assert verdicts[hid].failed_rules == ["evidence"], verdicts[hid].reason
        assert verdicts[hid].reason.startswith("rejected: not enough evidence")
        assert verdicts[hid].item_id == f"investigate:{hid}"
    for hid in RESTATES:  # beyond the threshold, or separated on a thresholded measure
        assert "restates the failure label" in verdicts[hid].reason, verdicts[hid].reason
    for hid in NOTHING:
        assert "cites no comparison of its own cluster that separates it" in \
            verdicts[hid].reason, verdicts[hid].reason


def test_accepted_ones_rank_first_and_thin_ones_last(
        investigated_run: tuple[Path, Path, Path]) -> None:
    _, out, _ = investigated_run
    a = assembly_of(out)
    head = cluster_of(a, HEAD)
    order = [(h.hypothesis_id, h.origin, h.evidence) for h in head.hypotheses]
    # above the rule hypothesis of the same group (near_miss_placement, data)
    assert head.hypotheses[2].rule_id == "near_miss_placement"
    assert order == [("H3", "model", "kept"), ("H4", "model", "kept"),
                     ("H1", "rule", ""), *((h, "model", "insufficient") for h in THIN)]
    assert [h.rank for h in head.hypotheses] == list(range(1, len(order) + 1))
    top = head.hypotheses[0]
    assert top.rule_id == "model" and top.title == "Hypothesis of the model"
    assert top.source == "model" and top.note == "model" and top.data_content
    # rank 1 is the model's: the cluster's intervention follows it
    assert head.intervention == "report_only" and head.intervention_source == "model"
    assert head.intervention_for == "H3" and head.check is None
    assert head.intervention_text == top.data_content
    assert head.check_text == "Replay the members first."
    assert set(top.cites) <= set(head.model_cites)
    # the level-2 cluster had no model hypothesis: as a run without --investigate
    other = cluster_of(a, OTHER)
    assert [h.origin for h in other.hypotheses] == ["rule"]
    assert other.intervention_for == "H2"  # the rank model's choice, not a model hypothesis
    assert "Model investigation: 2 kept, 7 not enough evidence, 0 rejected." in a.notes


def test_with_nothing_kept_the_assembly_is_the_plain_one(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with_limits(tmp_path, monkeypatch, max_steps=20)
    pack, store = small_pack(tmp_path / "pack"), tmp_path / "store"
    run(pack, tmp_path / "plain", Bot(), store)
    run(pack, tmp_path / "inv", Bot([act(action="conclude", keep=[])]), store,
        investigate=True)
    assert (tmp_path / "inv" / INVESTIGATED_FILE).read_text() == ""
    plain, inv = assembly_of(tmp_path / "plain"), assembly_of(tmp_path / "inv")
    assert inv.clusters == plain.clusters and inv.notes == plain.notes
    # the same verdicts; only the model call ids differ (the investigate call took one)
    ids = {"call_ids", "accepted_call_id"}
    assert [v.model_dump(exclude=ids) for v in verdicts_of(tmp_path / "inv")] == \
        [v.model_dump(exclude=ids) for v in verdicts_of(tmp_path / "plain")]


# --- placement against the rules (pure functions: the small pack has placeholders only) ---


CLUSTER = ClusterRef(cluster_id=HEAD, run="R", step="place", label=PLACE, level=1, size=6)


def _rule(hid: str, rule_id: str, group: str, diagnosis: str = "weak_skill") -> HypothesisView:
    return HypothesisView.model_validate({
        "hypothesis_id": hid, "rule_id": rule_id, "title": rule_id, "group": group,
        "diagnosis": diagnosis, "note": "n", "rank": 1, "source": "code"})


def _model(hid: str, diagnosis: str = "weak_skill") -> InvestigatedHypothesis:
    return InvestigatedHypothesis.model_validate({
        "hypothesis_id": hid, "cluster": CLUSTER.model_dump(),
        "statement": "The model's words.", "diagnosis": diagnosis,
        "intervention": "report_only", "data_content": {"text": "Demos.", "cites": ["F1"]},
        "first_check": {"text": "Replay.", "cites": []}, "proposed_at": 1})


def _kept(*hids: str, diagnosis: str = "weak_skill") -> list[HypothesisView]:
    rules = load_rules()
    return [_model_hypothesis(_model(h, diagnosis), model_group(diagnosis, rules), "kept")
            for h in hids]


def _view(hypotheses: list[HypothesisView]) -> ClusterView:
    return ClusterView(cluster=CLUSTER, hypotheses=hypotheses, intervention="report_only",
                       intervention_source="code", intervention_for=hypotheses[0].hypothesis_id,
                       blocked_data_spend=True)


def system_rules() -> frozenset[str]:
    return frozenset(r.id for r in load_rules() if r.system)


def test_the_group_of_a_diagnosis_is_the_last_of_its_rules() -> None:
    rules = load_rules()
    assert model_group("weak_skill", rules) == "coverage"
    assert model_group("unknown", rules) == "train"
    assert model_group("perception", rules) == "data"  # no rule carries it


def test_kept_ones_go_above_their_group_below_the_system_rules() -> None:
    views = [_rule("H1", "label_signal_missing", "scorer", "unknown"),
             _rule("H2", "controller_tracking", "runtime", "controller"),
             _rule("H3", "place_yaw_miss", "data"), _rule("H4", "weak_skill", "coverage")]
    SYSTEM = system_rules()
    assert {"label_signal_missing", "controller_tracking"} <= SYSTEM
    placed = place(views, _kept("H10", "H11"), SYSTEM)
    # weak_skill -> coverage: above H4, but never above a system rule (H1, H2); the data
    # rule H3 ranks before the coverage group and stays above
    assert [h.hypothesis_id for h in placed] == ["H1", "H2", "H3", "H10", "H11", "H4"]
    assert [h.rank for h in placed] == [1, 2, 3, 4, 5, 6]
    data = place(views, _kept("H10", diagnosis="perception"), SYSTEM)
    assert [h.hypothesis_id for h in data] == ["H1", "H2", "H10", "H3", "H4"]


def test_the_no_rule_placeholder_stays_below_every_kept_one() -> None:
    SYSTEM = system_rules()
    views = [_rule("H1", NONE_RULE, "data", "unknown")]
    placed = place(views, _kept("H5", "H6", diagnosis="unknown"), SYSTEM)  # group train
    assert [h.hypothesis_id for h in placed] == ["H5", "H6", "H1"]


def test_the_cluster_follows_a_kept_one_only_at_rank_one() -> None:
    SYSTEM = system_rules()
    blocked = _view([_rule("H1", "label_signal_missing", "scorer", "unknown"),
                     _rule("H2", "weak_skill", "coverage")])
    same = _with_model(blocked, _kept("H9"), [], SYSTEM)
    assert [h.hypothesis_id for h in same.hypotheses] == ["H1", "H9", "H2"]
    assert same.model_dump(exclude={"hypotheses"}) == blocked.model_dump(exclude={"hypotheses"})
    assert same.blocked_data_spend
    free = _view([_rule("H2", "weak_skill", "coverage")])
    top = _with_model(free, _kept("H9"), [], SYSTEM)
    assert top.hypotheses[0].hypothesis_id == "H9" and top.intervention_source == "model"
    assert top.intervention_for == "H9" and top.check is None
    assert top.intervention_text == "Demos." and top.check_text == "Replay."
    assert top.model_cites == ["F1"] and top.blocked_data_spend


def test_a_rule_hypothesis_dumps_no_field_of_the_model() -> None:
    dumped = json.loads(_rule("H1", "weak_skill", "coverage").model_dump_json())
    for key in ("origin", "evidence", "intervention", "data_content", "first_check", "cites"):
        assert key not in dumped
    model = json.loads(_kept("H9")[0].model_dump_json())
    assert model["origin"] == "model" and model["evidence"] == "kept"
    assert model["intervention"] == "report_only" and model["cites"] == ["F1"]


# --- AC 6: a tampered investigated.jsonl ----------------------------------------------------


def _tamper(out: Path, hid: str, edit: Callable[[dict[str, Any]], None]) -> None:
    path = out / INVESTIGATED_FILE
    lines = []
    for line in path.read_text().splitlines():
        h = json.loads(line)
        if h["hypothesis_id"] == hid:
            edit(h)
        lines.append(json.dumps(h))
    path.write_text("\n".join(lines) + "\n")


def _again(out: Path) -> None:
    """verify, assemble and render on the files as they are now.

    Not through `run_round --from verify`: that refuses a file whose sha256 is not the one
    step investigate recorded. These tests check the verify rules, the second guard.
    """
    verify(out)
    assemble(out, RunRecord.model_validate_json((out / "run.json").read_text()),
             no_model=False)
    render(out)


def _offered(h: dict[str, Any], test: Callable[[str, object], bool],
             facts: dict[str, Any]) -> str:
    fid = next(f for f, fact in facts.items() if test(fact["name"], fact["value"]))
    h["offered"][fid] = facts[fid]
    return str(fid)


def _all_offered(out: Path) -> dict[str, Any]:
    """Every fact the run's kept hypotheses were offered, by id (as InvestigatedFact)."""
    facts: dict[str, Any] = {}
    for line in (out / INVESTIGATED_FILE).read_text().splitlines():
        facts.update(json.loads(line)["offered"])
    by_id = {}
    for line in (out / INVESTIGATION_FACTS_FILE).read_text().splitlines():
        f = json.loads(line)
        by_id[f["fact_id"]] = {"name": f["name"], "value": f["value"], "unit": f["unit"],
                               "provenance": "code", "comparison": False}
    return {**by_id, **facts}


def _bare(h: dict[str, Any], facts: dict[str, Any]) -> None:
    h["statement"] = h["statement"].replace("successes:", "successes by 3 rollouts:")


def _uncited(h: dict[str, Any], facts: dict[str, Any]) -> None:
    other = next(f for f in facts if f not in h["data_content"]["cites"])
    h["offered"][other] = facts[other]
    h["data_content"]["text"] += f" See {{{other}}}."


def _unoffered(h: dict[str, Any], facts: dict[str, Any]) -> None:
    h["first_check"]["cites"].append("F9999")


def _compared(h: dict[str, Any], facts: dict[str, Any]) -> None:
    med = _offered(h, cmp_fact(HEAD, DIST, "_median"), facts)
    size = _offered(h, cmp_fact(HEAD, DIST, "_members"), facts)
    # no comparison fact among its cites: the code's own comparison facts are left out
    h["statement"] = f"Its {{{med}}} is higher than {{{size}}}."
    h["support"] = [med, size]


@pytest.mark.parametrize(("edit", "rule"), [
    (_bare, "numbers"), (_uncited, "numbers"), (_unoffered, "numbers"),
    (_compared, "comparison")])
def test_a_tampered_line_is_rejected_by_its_rule(
        investigated_run: tuple[Path, Path, Path], edit: Any, rule: str) -> None:
    pack, out, store = investigated_run
    facts = _all_offered(out)
    _tamper(out, "H3", lambda h: edit(h, facts))
    _again(out)
    verdict = mine(out)["H3"]
    assert verdict.verdict == "rejected" and rule in verdict.failed_rules, verdict.reason
    head = cluster_of(assembly_of(out), HEAD)
    assert "H3" not in [h.hypothesis_id for h in head.hypotheses]
    assert head.hypotheses[0].hypothesis_id == "H4"  # the other kept one moves up
    assert mine(out)["H4"].verdict == "accepted"


def test_the_degraded_lines_name_the_rejected_model_hypotheses(
        investigated_run: tuple[Path, Path, Path]) -> None:
    _, out, _ = investigated_run
    record = json.loads((out / "run.json").read_text())
    assert next(s for s in record["steps"] if s["name"] == "verify")["status"] == "degraded"
    text = json.dumps(record["problems"])
    assert all(f"{h}: rejected: not enough evidence" in text for h in THIN)
    assert "H3: " not in text and "H4: " not in text


# --- resume, render -------------------------------------------------------------------------


def test_resume_from_verify_and_assemble_needs_no_provider(
        investigated_run: tuple[Path, Path, Path]) -> None:
    pack, out, store = investigated_run
    before = {f: (out / f).read_bytes() for f in (VERDICTS_FILE, ASSEMBLY_FILE)}
    run(pack, out, Silent(), store, from_step="verify")
    assert {f: (out / f).read_bytes() for f in before} == before
    run(pack, out, Silent(), store, from_step="assemble")
    assert (out / ASSEMBLY_FILE).read_bytes() == before[ASSEMBLY_FILE]


def test_the_page_labels_the_model_and_escapes_its_words(
        investigated_run: tuple[Path, Path, Path]) -> None:
    pack, out, store = investigated_run
    h3 = json.loads((out / INVESTIGATED_FILE).read_text().splitlines()[0])
    fid = h3["support"][0]
    facts_ids = {json.loads(x)["fact_id"] for x in (out / "facts.jsonl").read_text().splitlines()}
    assert fid not in facts_ids  # a fact of the investigation only

    def edit(h: dict[str, Any]) -> None:
        h["statement"] = f"<script>alert('x')</script> apart: {{{fid}}}."
    _tamper(out, "H3", edit)
    _again(out)
    page = (out / INDEX_FILE).read_text()
    assert "<script>alert" not in page and "&lt;script&gt;alert" in page
    assert "Model&#x27;s words, hypothesis" in page or "Model's words, hypothesis" in page
    assert "Model&#x27;s words, data to collect" in page or \
        "Model's words, data to collect" in page
    assert "not enough evidence" in page
    assert f"{{{fid}}}" not in page  # the placeholder was resolved
    thin = page.index("not enough evidence: no comparison fact")
    assert page.index("Hypothesis of the model") < page.index("near_miss_placement") < thin

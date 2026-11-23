"""Case bench: every point kind, both verdicts, D1, and the sealing rules."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import flywheel.eval
import pytest
from flywheel.eval.agentqa.casebench.answers import Refused
from flywheel.eval.agentqa.casebench.run import main, score_case
from flywheel.eval.agentqa.inputs import forbidden_part
from helpers_casebench import PLACE, TIMEOUT, fact, make_run, view, write_answer


def pt(id: str, kind: str, **rest: object) -> dict[str, object]:
    return {"id": id, "kind": kind, **rest}


def verdicts(tmp_path: Path, points: list[dict[str, object]], **run: object) -> dict[str, str]:
    report = score_case(write_answer(tmp_path, points), make_run(tmp_path, **run))  # type: ignore[arg-type]
    return {p.id: p.verdict for p in report.points}


def test_finding_equals_approx_bool_and_absent(tmp_path: Path) -> None:
    facts = [fact("n", 7), fact("x", 2.6415), fact("flag", True), fact("s", "ok")]
    got = verdicts(tmp_path, [
        pt("a", "finding", fact={"name": "n", "equals": 7}),
        pt("b", "finding", fact={"name": "n", "equals": 8}),
        pt("c", "finding", fact={"name": "x", "approx": 2.641, "tol": 0.001}),
        pt("d", "finding", fact={"name": "x", "approx": 2.0, "tol": 0.001}),
        pt("e", "finding", fact={"name": "flag", "equals": True}),
        pt("f", "finding", fact={"name": "flag", "equals": 1}),
        pt("g", "finding", fact={"name": "s", "equals": "ok"}),
        pt("h", "finding", fact={"name": "nope", "equals": 1})], facts=facts)
    assert got == {"a": "reached", "b": "missed", "c": "reached", "d": "missed",
                   "e": "reached", "f": "missed", "g": "reached", "h": "missed"}


def test_diagnosis_rank_and_note(tmp_path: Path) -> None:
    answer = write_answer(tmp_path, [
        pt("a", "diagnosis", cluster=PLACE, diagnosis="unknown", note="scorer_threshold"),
        pt("b", "diagnosis", cluster=PLACE, diagnosis="weak_skill"),
        pt("c", "diagnosis", cluster=PLACE, diagnosis="unknown", note="other"),
        pt("d", "diagnosis", cluster=PLACE, diagnosis="infra")])
    report = score_case(answer, make_run(tmp_path))
    by = {p.id: (p.verdict, p.rank) for p in report.points}
    assert by == {"a": ("reached", 1), "b": ("reached", 2), "c": ("missed", None),
                  "d": ("missed", None)}
    assert (report.counts.a2_rank1, report.counts.a2_top3, report.counts.a2_total) == (1, 2, 4)


def test_refuted_clean_rank1_top3(tmp_path: Path) -> None:
    clusters = [view(PLACE, [("controller", "x"), ("sync", "x"), ("runtime", "x"),
                             ("infra", "x"), ("weak_skill", "x")])]
    got = verdicts(tmp_path, [
        pt("a", "refuted", cluster=PLACE, diagnosis="controller"),
        pt("b", "refuted", cluster=PLACE, diagnosis="runtime"),
        pt("c", "refuted", cluster=PLACE, diagnosis="infra"),
        pt("d", "refuted", cluster=PLACE, diagnosis="calibration")], clusters=clusters)
    assert got == {"a": "wrong_rank1", "b": "wrong_top3", "c": "clean", "d": "clean"}


def test_refuted_by_a_rule_is_clean_with_its_reason(tmp_path: Path) -> None:
    ruling = view(TIMEOUT, [("unknown", "policy"), ("weak_skill", "x")])
    ruling = ruling.model_copy(update={"hypotheses": [
        ruling.hypotheses[0].model_copy(update={"refutes": ["controller"]}),
        ruling.hypotheses[1]]})
    report = score_case(write_answer(tmp_path, [
        pt("a", "refuted", cluster=TIMEOUT, diagnosis="controller"),
        pt("b", "refuted", cluster=TIMEOUT, diagnosis="sync")]),
        make_run(tmp_path, clusters=[ruling]))
    assert [(p.verdict, p.reason) for p in report.points] == [
        ("clean", "refuted_by_rule"), ("clean", "")]
    assert report.counts.a3_refuted_by_rule == 1 and report.counts.a3_wrong_top3 == 0


def test_intervention_blocked_not_blocked_check(tmp_path: Path) -> None:
    got = verdicts(tmp_path, [
        pt("i1", "intervention", cluster=PLACE, intervention="repair_ticket"),
        pt("i2", "intervention", cluster=PLACE, intervention="sim_s1"),
        pt("b1", "blocked", cluster=TIMEOUT), pt("b2", "blocked", cluster=PLACE),
        pt("n1", "not_blocked", cluster=PLACE), pt("n2", "not_blocked", cluster=TIMEOUT),
        pt("c1", "check", cluster=PLACE, any_of=["chk_a", "chk_z"]),
        pt("c2", "check", cluster=PLACE, any_of=["chk_z"])])
    assert got == {"i1": "reached", "i2": "missed", "b1": "reached", "b2": "missed",
                   "n1": "reached", "n2": "missed", "c1": "reached", "c2": "missed"}


def test_no_check_chosen_is_a_miss_with_reason(tmp_path: Path) -> None:
    report = score_case(
        write_answer(tmp_path, [pt("c", "check", cluster=PLACE, any_of=["chk_a"])]),
        make_run(tmp_path, clusters=[view(PLACE, [("unknown", "x")], check=None)]))
    assert report.points[0].reason == "no_check"


def test_cluster_absent_is_missed_with_reason(tmp_path: Path) -> None:
    ghost = {**PLACE, "label": "L-GHOST"}
    report = score_case(write_answer(tmp_path, [
        pt("a", "diagnosis", cluster=ghost, diagnosis="unknown"),
        pt("b", "refuted", cluster=ghost, diagnosis="unknown")]), make_run(tmp_path))
    assert [(p.verdict, p.reason) for p in report.points] == [("missed", "cluster_absent")] * 2


def test_counts_by_kind_and_must(tmp_path: Path) -> None:
    report = score_case(write_answer(tmp_path, [
        pt("a", "finding", must=True, fact={"name": "n", "equals": 7}),
        pt("b", "finding", must=True, fact={"name": "n", "equals": 1}),
        pt("c", "intervention", cluster=PLACE, intervention="repair_ticket"),
        pt("d", "refuted", cluster=TIMEOUT, diagnosis="controller")]),
        make_run(tmp_path, facts=[fact("n", 7)]))
    c = report.counts
    assert (c.a1_reached, c.a1_total, c.a1_must_reached, c.a1_must_total) == (2, 3, 1, 2)
    assert (c.a1_by_kind["finding"].reached, c.a1_by_kind["finding"].total) == (1, 2)
    assert (c.a5_reached, c.a5_total, c.a3_wrong_rank1, c.a3_wrong_top3) == (1, 1, 1, 1)
    assert report.agent_hash == "h1" and report.status == "ok" and report.d1 is None
    assert report.answer_sha256 == hashlib.sha256(
        (tmp_path / "answers" / "case.yaml").read_bytes()).hexdigest()


def test_two_run_d1(tmp_path: Path) -> None:
    floor = make_run(tmp_path, "floor", clusters=[
        view(PLACE, [("weak_skill", "x"), ("unknown", "scorer_threshold")]),
        view(TIMEOUT, [("sync", "x")], intervention="sim_s1")])
    agent = make_run(tmp_path, "agent", clusters=[
        view(PLACE, [("unknown", "scorer_threshold"), ("weak_skill", "x")]),
        view(TIMEOUT, [("controller", "x")], intervention="repair_ticket")])
    answer = write_answer(tmp_path, [
        pt("d1", "diagnosis", cluster=PLACE, diagnosis="unknown"),
        pt("d2", "diagnosis", cluster=PLACE, diagnosis="weak_skill"),
        pt("i", "intervention", cluster=TIMEOUT, intervention="repair_ticket"),
        pt("r", "refuted", cluster=TIMEOUT, diagnosis="controller")])
    d1 = score_case(answer, agent, floor).d1
    assert d1 is not None
    assert d1.added_right == ["i"] and d1.added_wrong == ["r"]
    assert d1.rank_improved == ["d1"] and d1.rank_worsened == ["d2"]


def test_two_run_refuses_different_packs(tmp_path: Path) -> None:
    answer = write_answer(tmp_path, [pt("b", "blocked", cluster=PLACE)])
    with pytest.raises(Refused, match="different packs"):
        score_case(answer, make_run(tmp_path, "a", pack_id="p1"),
                   make_run(tmp_path, "b", pack_id="p2"))


# --- sealing -------------------------------------------------------------------------


def test_answer_outside_an_answers_directory_is_refused(tmp_path: Path) -> None:
    path = write_answer(tmp_path, [pt("b", "blocked", cluster=PLACE)], folder="notes")
    assert forbidden_part(path) is None
    with pytest.raises(Refused, match="answers"):
        score_case(path, make_run(tmp_path))


def test_the_agent_input_gate_refuses_the_answer_path(tmp_path: Path) -> None:
    path = write_answer(tmp_path, [pt("b", "blocked", cluster=PLACE)])
    assert forbidden_part(path) == "answers"


def test_unfinished_run_fails_before_the_answer_is_opened(tmp_path: Path) -> None:
    missing = tmp_path / "answers" / "never.yaml"  # does not exist: opening it would say so
    with pytest.raises(Refused, match="assembly.json"):
        score_case(missing, make_run(tmp_path, assembly=False))
    with pytest.raises(Refused, match="run.json"):
        score_case(missing, tmp_path / "no_such_run")


@pytest.mark.parametrize("bad", ["answers", "vault", "docs"])
def test_leak_in_pack_refuses_scoring_before_opening(tmp_path: Path, bad: str) -> None:
    run = make_run(tmp_path, pack_refs=[f"{bad}/x.json"])
    with pytest.raises(Refused, match="answer leak"):
        score_case(tmp_path / "answers" / "never.yaml", run)


def test_leak_in_fact_source_ref_refuses_scoring(tmp_path: Path) -> None:
    run = make_run(tmp_path, facts=[fact("n", 1, ref="docs/he/tray.md")])
    with pytest.raises(Refused, match="answer leak"):
        score_case(tmp_path / "answers" / "never.yaml", run)


def test_sha256_option(tmp_path: Path) -> None:
    path = write_answer(tmp_path, [pt("b", "blocked", cluster=TIMEOUT)])
    run = make_run(tmp_path)
    good = hashlib.sha256(path.read_bytes()).hexdigest()
    assert score_case(path, run, sha256=good).points[0].verdict == "reached"
    with pytest.raises(Refused, match="sha256"):
        score_case(path, run, sha256="1" * 64)


def test_answer_models_are_strict(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    for bad in ([pt("a", "finding")], [pt("a", "diagnosis", cluster=PLACE)],
                [pt("a", "blocked", cluster=PLACE, bogus=1)],
                [pt("a", "blocked", cluster=PLACE), pt("a", "blocked", cluster=TIMEOUT)],
                [pt("a", "finding", fact={"name": "n", "approx": 1.0})]):
        with pytest.raises(Refused, match="not a valid answer"):
            score_case(write_answer(tmp_path, bad), run)


def test_cli_scores_refuses_and_never_overwrites(tmp_path: Path,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    answer = write_answer(tmp_path, [pt("b", "blocked", cluster=TIMEOUT)])
    run = make_run(tmp_path)
    out = tmp_path / "report.json"
    assert main(["--answer", str(answer), "--run", str(run), "--out", str(out)]) == 0
    assert "A1 1/1" in capsys.readouterr().out
    assert json.loads(out.read_text())["case_id"] == "tray-c70-step4"
    assert main(["--answer", str(answer), "--run", str(run), "--out", str(out)]) == 2
    assert main(["--answer", str(answer), "--run", str(tmp_path / "nope"),
                 "--out", str(tmp_path / "other.json")]) == 2


# --- barrier -------------------------------------------------------------------------

AGENTQA = Path(flywheel.eval.__file__).resolve().parent / "agentqa"
CASEBENCH = AGENTQA / "casebench"


def _outside() -> list[Path]:
    return [p for p in sorted(AGENTQA.rglob("*.py")) if CASEBENCH not in p.parents]


def test_no_module_outside_casebench_imports_it() -> None:
    hits = []
    for path in _outside():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = (
                [a.name for a in node.names] if isinstance(node, ast.Import)
                else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            hits += [f"{path.name}: {n}" for n in names if "casebench" in n]
    assert hits == []


def test_the_barrier_scans_real_modules() -> None:
    scanned = {p.name for p in _outside()}
    assert {"cli.py", "inputs.py"} <= scanned
    assert not any(p.parent == CASEBENCH for p in _outside())

"""Match each answer point against one run (metrics A1-A5), and compare two runs (D1)."""

from __future__ import annotations

from flywheel.eval.agentqa.casebench.answers import Answer, ClusterKey, FactExpect, Point
from flywheel.eval.agentqa.casebench.report import (
    CaseReport,
    Counts,
    Delta,
    KindCount,
    PointResult,
    Verdict,
)
from flywheel.eval.agentqa.casebench.rundir import Run
from flywheel.eval.agentqa.round.records import ClusterView, FactRecord


def _cluster(run: Run, key: ClusterKey) -> ClusterView | None:
    for view in run.assembly.clusters:
        c = view.cluster
        if (c.run, c.step, c.label, c.level) == (key.run, key.step, key.label, key.level):
            return view
    return None


def _fact_matches(fact: FactRecord, want: FactExpect) -> bool:
    got = fact.value
    if want.approx is not None:
        if isinstance(got, bool) or isinstance(got, str):
            return False
        return abs(got - want.approx) <= (want.tol or 0.0)
    expected = want.equals
    if isinstance(got, bool) or isinstance(expected, bool):
        return isinstance(got, bool) and isinstance(expected, bool) and got == expected
    if isinstance(got, str) or isinstance(expected, str):
        return got == expected
    return got == expected


def _rank_of(view: ClusterView, point: Point) -> int | None:
    """Rank (1 = top) in the final order the assembly lists; first match wins."""
    for index, h in enumerate(view.hypotheses, start=1):
        if h.diagnosis == point.diagnosis and (point.note is None or h.note == point.note):
            return index
    return None


def _result(point: Point, verdict: Verdict, reason: str = "",
            rank: int | None = None) -> PointResult:
    return PointResult(id=point.id, kind=point.kind, must=point.must, verdict=verdict,
                       reason=reason, rank=rank)


def _match(run: Run, point: Point) -> PointResult:
    if point.kind == "finding":
        assert point.fact is not None
        named = [f for f in run.facts if f.name == point.fact.name]
        if not named:
            return _result(point, "missed", "fact_absent")
        if any(_fact_matches(f, point.fact) for f in named):
            return _result(point, "reached")
        return _result(point, "missed", "value_differs")
    assert point.cluster is not None
    view = _cluster(run, point.cluster)
    if view is None:
        return _result(point, "missed", "cluster_absent")
    if point.kind in ("diagnosis", "refuted"):
        rank = _rank_of(view, point)
        if point.kind == "diagnosis":
            return (_result(point, "reached", rank=rank) if rank
                    else _result(point, "missed", "diagnosis_absent"))
        if rank == 1:
            return _result(point, "wrong_rank1", rank=1)
        if rank is not None and rank <= 3:
            return _result(point, "wrong_top3", rank=rank)
        return _result(point, "clean", rank=rank)
    if point.kind == "intervention":
        ok = view.intervention == point.intervention
        return _result(point, "reached" if ok else "missed",
                       "" if ok else f"chose {view.intervention}")
    if point.kind == "blocked":
        return _result(point, "reached" if view.blocked_data_spend else "missed",
                       "" if view.blocked_data_spend else "not_blocked")
    if point.kind == "not_blocked":
        return _result(point, "missed" if view.blocked_data_spend else "reached",
                       "blocked" if view.blocked_data_spend else "")
    chosen = view.check.check_id if view.check is not None else None  # kind == "check"
    ok = chosen is not None and chosen in (point.any_of or [])
    return _result(point, "reached" if ok else "missed",
                   "" if ok else f"chose {chosen}" if chosen else "no_check")


def match_points(answer: Answer, run: Run) -> list[PointResult]:
    return [_match(run, p) for p in answer.points]


def _of(results: list[PointResult], kind: str) -> list[PointResult]:
    return [r for r in results if r.kind == kind]


def count(results: list[PointResult]) -> Counts:
    scored = [r for r in results if r.kind != "refuted"]
    by_kind: dict[str, KindCount] = {}
    for r in scored:
        k = by_kind.get(r.kind, KindCount(reached=0, total=0))
        by_kind[r.kind] = KindCount(reached=k.reached + (r.verdict == "reached"),
                                    total=k.total + 1)
    diag = _of(results, "diagnosis")
    refuted, checks, fixes = (_of(results, k) for k in ("refuted", "check", "intervention"))
    reached = "reached"
    return Counts(
        a1_reached=sum(r.verdict == reached for r in scored), a1_total=len(scored),
        a1_must_reached=sum(r.verdict == reached for r in scored if r.must),
        a1_must_total=sum(r.must for r in scored), a1_by_kind=by_kind,
        a2_rank1=sum(r.rank == 1 for r in diag),
        a2_top3=sum(r.rank is not None and r.rank <= 3 for r in diag), a2_total=len(diag),
        a3_wrong_rank1=sum(r.verdict == "wrong_rank1" for r in refuted),
        a3_wrong_top3=sum(r.verdict in ("wrong_rank1", "wrong_top3") for r in refuted),
        a4_reached=sum(r.verdict == reached for r in checks), a4_total=len(checks),
        a5_reached=sum(r.verdict == reached for r in fixes), a5_total=len(fixes))


def delta(agent: list[PointResult], floor: list[PointResult], floor_run_id: str) -> Delta:
    floor_by = {r.id: r for r in floor}
    right, wrong, up, down = [], [], [], []
    for r in agent:
        f = floor_by[r.id]
        if r.kind == "refuted":
            if r.verdict in ("wrong_rank1", "wrong_top3") and f.verdict == "clean":
                wrong.append(r.id)
        elif r.verdict == "reached" and f.verdict != "reached":
            right.append(r.id)
        if r.kind == "diagnosis" and r.rank is not None and f.rank is not None:
            if r.rank < f.rank:
                up.append(r.id)
            elif r.rank > f.rank:
                down.append(r.id)
    return Delta(floor_run_id=floor_run_id, added_right=right, added_wrong=wrong,
                 rank_improved=up, rank_worsened=down)


def score(answer: Answer, sha256: str, run: Run, floor: Run | None = None) -> CaseReport:
    points = match_points(answer, run)
    return CaseReport(
        case_id=answer.case_id, set=answer.set, answer_sha256=sha256,
        run_id=run.record.run_id, agent_hash=run.record.agent_hash,
        status=run.record.status, pack_id=run.record.pack_id, points=points,
        counts=count(points),
        d1=delta(points, match_points(answer, floor), floor.record.run_id)
        if floor is not None else None)

"""The targeted set of C70_R1, picked by the rule of tray.md 20.5 / 20.14 (DA-34 7.5)."""

from __future__ import annotations

import pytest
from flywheel_psi0.tray.round_select import pool_of, select

A1, A2 = "approach_a-L1-1000114", "approach_a-L2-1000120"
P1, P2, P3 = "place-L1-1000109", "place-L2-1000107", "place-L1-1000127"
CONDITIONS = [A1, A2, P1, P2, P3]


def _cands(cluster: str, seeds: list[int]) -> list[tuple[float, int]]:
    return [(0.1 * (i + 1), s) for i, s in enumerate(seeds)]


def _candidates(n_a: int, n_p: int) -> dict[str, list[tuple[float, int]]]:
    base = {A1: 100, A2: 200, P1: 300, P2: 400, P3: 500}
    n = {A1: n_a, A2: n_a, P1: n_p, P2: n_p, P3: n_p}
    return {c: _cands(c, [base[c] + k for k in range(n[c])]) for c in CONDITIONS}


def test_the_earlier_step_takes_its_quota_then_place_goes_round_robin() -> None:
    cands = _candidates(n_a=6, n_p=5)
    passing = {s for v in cands.values() for _, s in v}
    picks, short = select(CONDITIONS, cands, passing, budget=14, quota=4)
    assert [p.cluster_id for p in picks[:8]] == [A1] * 4 + [A2] * 4
    assert [p.rank for p in picks[:4]] == [1, 2, 3, 4]  # nearest first
    # 6 left for place: two full rounds in file order
    assert [p.cluster_id for p in picks[8:]] == [P1, P2, P3, P1, P2, P3]
    assert [p.rank for p in picks[8:]] == [1, 1, 1, 2, 2, 2]
    assert {p.pool for p in picks} == {"approach_a", "place"}
    assert short == []


def test_the_budget_stops_a_round_in_file_order_and_skips_failing_seeds() -> None:
    cands = _candidates(n_a=4, n_p=5)
    passing = {s for v in cands.values() for _, s in v} - {300}  # P1's nearest fails QA
    picks, _ = select(CONDITIONS, cands, passing, budget=10, quota=4)
    place = [(p.cluster_id, p.seed, p.rank) for p in picks if p.pool == "place"]
    assert place == [(P1, 301, 1), (P2, 400, 1)]  # rank counts passing seeds only


def test_a_short_approach_pool_leaves_its_budget_to_place_and_reports_the_shortfall() -> None:
    cands = _candidates(n_a=2, n_p=2)
    passing = {s for v in cands.values() for _, s in v}
    picks, short = select(CONDITIONS, cands, passing, budget=20, quota=4)
    assert sum(p.pool == "approach_a" for p in picks) == 4
    assert sum(p.pool == "place" for p in picks) == 6  # every passing place seed
    assert len(picks) == 10
    assert short == [A1, A2, P1, P2, P3]  # under quota, or out of seeds while short


def test_pools_come_from_the_condition_id() -> None:
    assert pool_of(A1) == "approach_a" and pool_of(P2) == "place"
    with pytest.raises(ValueError, match="pool"):
        pool_of("carry-L1-1000100")
    with pytest.raises(ValueError, match="twice"):
        select([A1, A1], {}, set(), budget=1, quota=1)

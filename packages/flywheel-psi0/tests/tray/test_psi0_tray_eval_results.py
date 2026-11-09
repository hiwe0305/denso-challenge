"""The eval result of a batch directory: earliest finished rollout, levels, CI, rule 0 (DA-34)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from flywheel_psi0.tray.eval_batch import Chunk
from flywheel_psi0.tray.eval_results import (
    STEP_NAMES,
    bootstrap_ci,
    collect,
    mcnemar_exact,
    paired,
    paired_diff,
    reached,
    stage1_outcome,
    summarize,
    table,
    trace_of,
    wilson,
    yaw_errors,
)
from flywheel_psi0.tray.runplan import TrayRunPlan

ROOT = Path(__file__).resolve().parents[4]
PLAN = TrayRunPlan.load(ROOT / "configs/runplans/tray/he-tray-v2.yaml")


def episode(
    out: Path,
    chunk: Chunk,
    attempt: int,
    i: int,
    success: bool,
    steps: int = 3,
    stats: bool = True,
    failure: str = "L-TIMEOUT",
) -> None:
    folder = out / chunk.id / f"attempt-{attempt}"
    (folder / "eval").mkdir(parents=True, exist_ok=True)
    row = {
        "seed": chunk.seed_of(i),
        "level": chunk.level,
        "success": success,
        "failure": None if success else failure,
        "scorer_steps": [k < (7 if success else steps) for k in range(7)],
    }
    with (folder / "outcomes.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")
    if stats:
        with (folder / "eval/eval_stats.txt").open("a") as f:
            f.write(f"episode_{i}: {success} \n")


L1 = Chunk("l1-000", 1, 0, (1000100, 1000101, 1000102))


def test_the_earliest_finished_rollout_is_chosen_and_later_ones_are_counted(
    tmp_path: Path,
) -> None:
    # attempt 0: episode 0 fails, episode 1 is cut short (outcome on close, no stats line),
    # episode 2 is never reached. The rerun starts at episode 1 and also reruns 2.
    episode(tmp_path, L1, 0, 0, success=False)
    episode(tmp_path, L1, 0, 1, success=False, stats=False)
    episode(tmp_path, L1, 1, 1, success=True)
    episode(tmp_path, L1, 1, 2, success=False)
    # a later chunk rerun that finished episode 2 again, now as a success: never chosen
    episode(tmp_path, L1, 2, 2, success=True)
    chosen, extra, missing = collect(tmp_path, [L1])
    assert [(r.seed, r.attempt, r.row["success"]) for r in chosen] == [
        (1000100, 0, False),
        (1000101, 1, True),
        (1000102, 1, False),
    ]
    assert extra == {(1, 1000102): 1} and missing == []


def test_an_episode_never_finished_is_missing(tmp_path: Path) -> None:
    episode(tmp_path, L1, 0, 0, success=True)
    _, _, missing = collect(tmp_path, [L1])
    assert missing == [(1, 1000101), (1, 1000102)]


def test_bootstrap_is_seeded_and_resamples_inside_each_group() -> None:
    a = bootstrap_ci([[0, 1, 0, 0], [1, 1, 0, 1]], 2000, 7, 0.95)
    assert a == bootstrap_ci([[0, 1, 0, 0], [1, 1, 0, 1]], 2000, 7, 0.95)
    assert 0.0 <= a[0] < 0.5 < a[1] <= 1.0
    assert bootstrap_ci([[1, 1], [0, 0, 0, 0]], 2000, 7, 0.95) == (pytest.approx(1 / 3),) * 2


def rollouts_for(tmp_path: Path, wins: dict[int, int], n: int = 10) -> Any:
    chunks = []
    for level in (0, 1, 2):
        chunk = Chunk(f"l{level}-000", level, 0, tuple(1000100 + i for i in range(n)))
        for i in range(n):
            episode(tmp_path, chunk, 0, i, success=i < wins[level], failure="L-TRAY-TILT")
        chunks.append(chunk)
    return collect(tmp_path, chunks)


def test_levels_headline_and_rule_0(tmp_path: Path) -> None:
    chosen, extra, missing = rollouts_for(tmp_path, {0: 5, 1: 1, 2: 0})
    result = summarize(PLAN, chosen, extra, missing)
    assert result["levels"]["0"]["unit"] == "replicate" and result["levels"]["0"]["p"] == 0.5
    head = result["headline"]
    assert head["levels"] == [1, 2] and (head["n"], head["successes"]) == (20, 1)
    assert head["p"] == 0.05 and head["ci"][0] <= 0.05 <= head["ci"][1]
    assert result["rule0"] == {"threshold": 0.10, "p": 0.05, "fires": True}
    assert head["failures"] == {"L-TRAY-TILT": 19}
    assert head["step_pass"]["approach_a"] == 1.0 and head["step_pass"]["carry"] == 0.05
    assert result["label"] == "preliminary, on dev"
    assert "| 1–2 gộp | 20 | 1 | 5.0 |" in table(result)
    assert head["reached"] == {3: 19, 7: 1}
    assert (result["all"]["n"], result["all"]["successes"]) == (30, 6)
    assert "| cả lô | 30 | 6 | 20.0 |" in table(result)


def test_wilson_interval() -> None:
    low, high = wilson(0, 120)
    assert low == 0.0 and high == pytest.approx(0.0310, abs=1e-4)  # 3.84 / 123.84
    low, high = wilson(1, 20)
    assert (low, high) == (pytest.approx(0.0089, abs=1e-4), pytest.approx(0.2361, abs=1e-4))
    with pytest.raises(ValueError):
        wilson(0, 0)


def test_reached_counts_the_steps_passed_in_a_row() -> None:
    assert reached([True, True, False, True]) == 2
    assert reached([False] * 7) == 0 and reached([True] * 7) == 7


def test_rule_0_does_not_fire_at_ten_percent(tmp_path: Path) -> None:
    chosen, extra, missing = rollouts_for(tmp_path, {0: 0, 1: 1, 2: 1})
    assert summarize(PLAN, chosen, extra, missing)["rule0"]["fires"] is False


def steps_file(path: Path, pairs: list[tuple[float, float]], episode_id: str = "episode_0") -> Path:
    path.mkdir(parents=True)
    lines = [
        json.dumps(
            {
                "episode_id": episode_id,
                "cmd_lower": [0.0] * 6 + [cmd],
                "meas_lower": [0.0] * 6 + [meas],
            }
        )
        for cmd, meas in pairs
    ]
    (path / "steps.jsonl").write_text("\n".join(lines) + "\n")
    (path / "rollout_result.json").write_text("{}")
    return path / "steps.jsonl"


def test_yaw_error_raw_versus_wrapped(tmp_path: Path) -> None:
    steps = steps_file(tmp_path / "t", [(3.19, -3.13), (0.4, 0.0), (3.0, -0.2), (0.0, 0.0)])
    errors = yaw_errors(steps)
    assert (errors["cycles"], errors["raw_over"], errors["wrapped_over"]) == (4, 2, 1)
    assert errors["max_wrapped"] == pytest.approx(2 * math.pi - 3.2)  # 3.2 rad wraps to -3.08
    assert abs(math.atan2(math.sin(6.32), math.cos(6.32))) < 0.05


def test_the_trace_of_a_rollout_is_found_by_episode(tmp_path: Path) -> None:
    episode(tmp_path, L1, 0, 0, success=False)
    episode(tmp_path, L1, 0, 1, success=False)
    traces = tmp_path / "l1-000/attempt-0/traces"
    steps_file(traces / "job-a", [(0.0, 0.0)], "episode_0")
    second = steps_file(traces / "job-b", [(0.0, 0.0)], "episode_1")
    chosen, _, _ = collect(tmp_path, [L1])
    assert trace_of(tmp_path, chosen[1]) == second
    assert len(STEP_NAMES) == 7


def test_a_smaller_set_reports_its_levels_and_no_rule_0(tmp_path: Path) -> None:
    chunk = Chunk("l1-000", 1, 0, tuple(1000100 + i for i in range(20)))
    for i in range(20):
        episode(tmp_path, chunk, 0, i, success=i < 2)
    chosen, extra, missing = collect(tmp_path, [chunk])
    result = summarize(PLAN, chosen, extra, missing, full=False)
    assert list(result["levels"]) == ["1"] and result["levels"]["1"]["successes"] == 2
    assert result["rule0"] is None and result["full_eval_set"] is False
    assert result["all"]["n"] == 20
    assert "gộp" not in table(result) and "| cả lô | 20 | 2 | 10.0 |" in table(result)


def test_paired_counts_per_condition_and_the_gains(tmp_path: Path) -> None:
    chunk = Chunk("l1-000", 1, 0, tuple(1000100 + i for i in range(4)))
    # baseline: 1 success (episode 0); variant: successes 1 and 2, episode 3 reaches place
    for i, ok in enumerate((True, False, False, False)):
        episode(tmp_path / "base", chunk, 0, i, success=ok, steps=5)
    for i, (ok, steps) in enumerate(((False, 5), (True, 7), (True, 7), (False, 6))):
        episode(tmp_path / "var", chunk, 0, i, success=ok, steps=steps)
    base, _, _ = collect(tmp_path / "base", [chunk])
    var, _, _ = collect(tmp_path / "var", [chunk])
    result = paired(var, base)
    assert result["success"] == {"both": 0, "variant_only": 2, "baseline_only": 1, "neither": 1}
    assert result["success_gain"] == 1
    # place (step 6): variant on episodes 1, 2, 3; baseline on episode 0 (its success)
    assert result["steps"]["place"]["variant_only"] == 3 and result["place_gain"] == 2
    with pytest.raises(ValueError):
        paired(var[:3], base)


def test_mcnemar_exact_two_sided() -> None:
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 0) == mcnemar_exact(0, 5) == pytest.approx(2 / 32)
    assert mcnemar_exact(10, 2) == pytest.approx(2 * (1 + 12 + 66) / 4096)  # 0.0386
    assert mcnemar_exact(3, 3) == 1.0  # capped


def _two_level_runs(
    tmp_path: Path, var_ok: dict[int, list[bool]], base_ok: dict[int, list[bool]]
) -> tuple[Any, Any]:
    chunks = [
        Chunk(f"l{lv}-000", lv, 0, tuple(1000100 + i for i in range(len(var_ok[lv]))))
        for lv in var_ok
    ]
    for name, oks in (("var", var_ok), ("base", base_ok)):
        for chunk in chunks:
            for i, ok in enumerate(oks[chunk.level]):
                episode(tmp_path / name, chunk, 0, i, success=ok, steps=5)
    var, _, _ = collect(tmp_path / "var", chunks)
    base, _, _ = collect(tmp_path / "base", chunks)
    return var, base


def test_paired_diff_resamples_the_differences_within_each_level(tmp_path: Path) -> None:
    # level 1: variant 3/4 vs 0/4; level 2: variant 1/4 vs 1/4 (one swap)
    var, base = _two_level_runs(
        tmp_path,
        {1: [True, True, True, False], 2: [True, False, False, False]},
        {1: [False, False, False, False], 2: [False, True, False, False]},
    )
    result = paired_diff(var, base, [1, 2], PLAN.stats)
    assert (result["n"], result["variant"], result["baseline"]) == (8, 4, 1)
    assert result["diff"] == pytest.approx(3 / 8)
    assert (result["variant_only"], result["baseline_only"]) == (4, 1)
    assert result["mcnemar_exact_p"] == pytest.approx(round(mcnemar_exact(4, 1), 4))
    groups = [[1, 1, 1, 0], [1, -1, 0, 0]]
    expected = bootstrap_ci(groups, PLAN.stats.resamples, PLAN.stats.seed, PLAN.stats.ci)
    assert result["ci"] == pytest.approx(expected, abs=1e-4)
    assert result["ci_vs_0"] == ("above" if expected[0] > 0 else "contains")
    only_2 = paired_diff(var, base, [2], PLAN.stats)
    assert (only_2["n"], only_2["diff"], only_2["ci_vs_0"]) == (4, 0.0, "contains")


def test_paired_diff_reads_below_zero_and_refuses_other_conditions(tmp_path: Path) -> None:
    var, base = _two_level_runs(tmp_path, {1: [False] * 6}, {1: [True] * 6})
    result = paired_diff(var, base, [1], PLAN.stats)
    assert (result["diff"], result["ci"], result["ci_vs_0"]) == (-1.0, (-1.0, -1.0), "below")
    with pytest.raises(ValueError, match="different conditions"):
        paired_diff(var[:5], base, [1], PLAN.stats)
    with pytest.raises(ValueError, match="no condition"):
        paired_diff(var, base, [2], PLAN.stats)


@pytest.mark.parametrize(
    ("b", "c", "ci", "outcome"),
    [
        (11, 0, (0.1, 0.3), "E1"),  # p 0.00098: paired_diff rounds it to 0.001
        (12, 1, (0.1, 0.3), "continue"),  # p 0.0034: not clear yet, B ahead
        (11, 0, (0.0, 0.3), "continue"),  # clear p but the CI touches 0
        (0, 11, (-0.3, -0.1), "E3"),
        (0, 11, (-0.3, 0.0), "F"),
        (3, 3, (-0.1, 0.1), "F"),  # b = c: no gain, stop
        (1, 4, (-0.1, 0.02), "F"),
        (4, 1, (-0.02, 0.1), "continue"),
    ],
)
def test_stage1_stop_rule(b: int, c: int, ci: tuple[float, float], outcome: str) -> None:
    # tray.md 18.2, Hiếu 10/11/2026: E1 / E3 stop on a clear difference, F on no gain
    diff = {"variant_only": b, "baseline_only": c, "ci": ci}
    assert stage1_outcome(diff) == outcome


def _stage1_set(tmp_path: Path) -> list[Chunk]:
    from flywheel_psi0.tray.eval_batch import chunk_plan

    rows = [
        {"level": lv, "seed": 1000100 + i}
        for lv, n in ((0, 30), (1, 120), (2, 120))
        for i in range(n)
    ]
    (tmp_path / "set").mkdir()
    (tmp_path / "set/conditions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return chunk_plan(rows, 10)


def test_stage1_reads_the_first_six_chunks_of_both_sides(tmp_path: Path) -> None:
    from flywheel_psi0.tray import eval_results

    chunks = _stage1_set(tmp_path)
    for chunk in chunks[:6]:
        for i in range(10):
            # B: the first 2 of each chunk (12/60), C: none; C's 7th chunk is not read
            episode(tmp_path / "b", chunk, 0, chunk.start + i, success=i < 2)
            episode(tmp_path / "c", chunk, 0, chunk.start + i, success=False)
    for i in range(10):
        episode(tmp_path / "c", chunks[6], 0, chunks[6].start + i, success=True)
    common = [
        str(ROOT / "configs/runplans/tray/he-tray-b.yaml"), "--set", str(tmp_path / "set"),
        "--out", str(tmp_path / "b"), "--no-yaw",
    ]  # fmt: skip
    out = tmp_path / "b-vs-c.json"
    assert eval_results.main([*common, "--baseline", str(tmp_path / "c"), "--stage1",
                              "--json", str(out)]) == 0  # fmt: skip
    result = json.loads(out.read_text())
    assert result["stage1"]["chunks"] == [c.id for c in chunks[:6]]
    assert result["stage1"]["conditions"] == 60 and result["stage1"]["outcome"] == "E1"
    headline = result["paired"]["headline"]
    assert (headline["n"], headline["variant_only"], headline["baseline_only"]) == (60, 12, 0)
    assert result["rule0"] is None and result["full_eval_set"] is False
    assert list(result["levels"]) == ["1", "2"] and result["rollouts"] == 60
    assert sorted(result["paired"]["by_level"]) == ["1", "2"]
    with pytest.raises(SystemExit):
        eval_results.main([*common, "--stage1"])  # stage 1 pairs with a baseline
    (tmp_path / "b/l2-020/attempt-0/eval/eval_stats.txt").write_text("")
    with pytest.raises(ValueError, match="stage 1 misses"):
        eval_results.main([*common, "--baseline", str(tmp_path / "c"), "--stage1"])

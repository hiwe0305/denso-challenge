"""The eval result of a batch directory: earliest finished rollout, levels, CI, rule 0 (DA-34)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from flywheel_psi0.tray.eval_batch import Chunk, with_repeats
from flywheel_psi0.tray.eval_results import (
    STEP_NAMES,
    Rollout,
    bootstrap_ci,
    clustered_wilson,
    collect,
    mcnemar_exact,
    paired,
    paired_diff,
    paired_diff_repeats,
    reached,
    repeat_0,
    scorer_v1_vs_v2,
    scorer_version,
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
    scorer_version: int | None = None,
) -> None:
    folder = out / chunk.dir_id / f"attempt-{attempt}"
    (folder / "eval").mkdir(parents=True, exist_ok=True)
    row = {
        "seed": chunk.seed_of(i),
        "level": chunk.level,
        "success": success,
        "failure": None if success else failure,
        "scorer_steps": [k < (7 if success else steps) for k in range(7)],
    }
    if scorer_version is not None:
        row["scorer_version"] = scorer_version
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
    assert missing == [(1, 1000101, 0), (1, 1000102, 0)]
    assert missing[0].seed == 1000101 and missing[0].repeat == 0


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


# --- DA-42 3.3: scorer version ------------------------------------------------------


def _scored(out: Path, versions: list[int | None], ok: list[bool] | None = None) -> Any:
    chunk = Chunk("l1-000", 1, 0, tuple(1000100 + i for i in range(len(versions))))
    for i, v in enumerate(versions):
        episode(out, chunk, 0, i, success=bool(ok and ok[i]), scorer_version=v)
    return collect(out, [chunk])


def test_results_name_the_scorer_version(tmp_path: Path) -> None:
    chosen, extra, missing = _scored(tmp_path / "v2", [2, 2, 2])
    result = summarize(PLAN, chosen, extra, missing, full=False)
    assert result["scorer_version"] == 2 and result["scorer_version_note"] is None
    assert table(result).startswith("Bộ chấm khay: phiên bản 2")


def test_rows_without_a_version_are_unrecorded_not_version_1(tmp_path: Path) -> None:
    chosen, extra, missing = _scored(tmp_path / "old", [None, None])
    result = summarize(PLAN, chosen, extra, missing, full=False)
    assert result["scorer_version"] is None
    assert "before DA-42" in result["scorer_version_note"]
    assert table(result).startswith("Bộ chấm khay: không ghi phiên bản")


@pytest.mark.parametrize("versions", [[1, 2], [None, 2], [2, None, 2]])
def test_a_directory_of_two_scorer_versions_is_refused(
    tmp_path: Path, versions: list[int | None]
) -> None:
    chosen, extra, missing = _scored(tmp_path, versions)
    with pytest.raises(ValueError, match="mix scorer versions"):
        scorer_version(chosen)
    with pytest.raises(ValueError, match="mix scorer versions"):
        summarize(PLAN, chosen, extra, missing, full=False)


def test_pairing_two_scorer_versions_needs_cross_scorer(tmp_path: Path) -> None:
    var, _, _ = _scored(tmp_path / "var", [2, 2, 2, 2], [True, True, False, False])
    base, _, _ = _scored(tmp_path / "base", [None] * 4, [True, False, False, False])
    with pytest.raises(ValueError, match="--cross-scorer"):
        paired(var, base)
    with pytest.raises(ValueError, match="--cross-scorer"):
        paired_diff(var, base, [1], PLAN.stats)
    result = paired(var, base, cross_scorer=True)
    assert result["cross_scorer"] is True
    assert result["scorer_versions"] == {"variant": 2, "baseline": None}
    diff = paired_diff(var, base, [1], PLAN.stats, cross_scorer=True)
    assert diff["scorer_versions"] == {"variant": 2, "baseline": None}


def test_same_scorer_pairs_say_so(tmp_path: Path) -> None:
    var, _, _ = _scored(tmp_path / "var", [2, 2], [True, False])
    base, _, _ = _scored(tmp_path / "base", [2, 2], [False, False])
    result = paired(var, base)
    assert result["cross_scorer"] is False and result["scorer_versions"]["baseline"] == 2


# --- DA-42 4.2: repeats per condition -----------------------------------------------


def _repeated(out: Path, wins: list[list[bool]]) -> Any:
    """Level 1 conditions, wins[i][r]: success of repeat r of condition i."""
    base = Chunk("l1-000", 1, 0, tuple(1000100 + i for i in range(len(wins))))
    chunks = with_repeats([base], len(wins[0]))
    for chunk in chunks:
        for i, oks in enumerate(wins):
            episode(out, chunk, 0, i, success=oks[chunk.repeat], scorer_version=2)
    return collect(out, chunks)


def test_one_rollout_per_condition_keeps_the_plain_wilson() -> None:
    result = clustered_wilson([[1], [0], [0], [0], [0]])
    assert result["interval"] == pytest.approx(wilson(1, 5))
    assert clustered_wilson([[0]] * 5)["interval"] == pytest.approx(wilson(0, 5))
    assert result["n_eff"] == 5 and result["design_effect"] == 1
    assert result["method"].startswith("independent")


def test_conditions_that_always_agree_count_once() -> None:
    # 4 conditions x 3 repeats, each condition all-or-nothing: 12 rollouts carry the
    # information of 4 conditions
    result = clustered_wilson([[1, 1, 1], [0, 0, 0], [0, 0, 0], [0, 0, 0]])
    assert result["design_effect"] == pytest.approx(3 * 4 / 3, rel=1e-3)  # 4 / (4-1) * ...
    assert result["n_eff"] == 4 and result["interval"] == pytest.approx(wilson(1, 4))
    plain = wilson(3, 12)
    assert result["interval"][1] - result["interval"][0] > plain[1] - plain[0]


def test_coin_flip_conditions_still_count_per_condition() -> None:
    # every condition 1 of 2: design effect 1, reported; the interval stays per condition
    result = clustered_wilson([[1, 0]] * 10)
    assert result["design_effect"] == 1 and result["n_eff"] == 10
    assert result["interval"] == pytest.approx(wilson(5, 10))


def test_all_failures_count_per_condition_and_leave_the_design_effect_null() -> None:
    result = clustered_wilson([[0, 0, 0]] * 5)
    assert result["n_eff"] == 5 and "n_eff = conditions" in result["method"]
    assert result["interval"] == pytest.approx(wilson(0, 5))
    assert result["design_effect"] is None


def test_the_interval_moves_monotonically_with_the_successes() -> None:
    # 30 conditions x 3 repeats: the bound of 0/90 is not above the bound of 1/90 (review c)
    def bounds(k: int) -> tuple[float, float]:
        groups = [[1, 0, 0] if i < k else [0, 0, 0] for i in range(30)]
        return clustered_wilson(groups)["interval"]

    (l0, h0), (l1, h1), (l2, h2) = bounds(0), bounds(1), bounds(2)
    assert l0 <= l1 <= l2 and h0 < h1 < h2
    assert h0 == pytest.approx(wilson(0, 30)[1]) and h1 == pytest.approx(wilson(1 / 3, 30)[1])


def test_repeats_give_per_condition_counts_and_step_rates(tmp_path: Path) -> None:
    chosen, extra, missing = _repeated(tmp_path, [[True, True], [False, True], [False, False]])
    assert [(r.seed, r.repeat, r.chunk) for r in chosen] == [
        (1000100, 0, "l1-000"), (1000101, 0, "l1-000"), (1000102, 0, "l1-000"),
        (1000100, 1, "l1-000.r1"), (1000101, 1, "l1-000.r1"), (1000102, 1, "l1-000.r1"),
    ]  # fmt: skip
    result = summarize(PLAN, chosen, extra, missing, full=False)
    level = result["levels"]["1"]
    assert (level["n"], level["conditions"], level["successes"]) == (6, 3, 3)
    assert level["p"] == 0.5 and level["wilson_n_eff"] == 3
    assert level["wilson_design_effect"] is not None
    assert level["step_pass"]["approach_a"] == 1.0 and level["step_pass"]["place"] == 0.5
    assert result["repeats"] == 2
    assert result["per_condition"] == {
        "1:1000100": {"successes": 2, "rollouts": 2},
        "1:1000101": {"successes": 1, "rollouts": 2},
        "1:1000102": {"successes": 0, "rollouts": 2},
    }
    # bootstrap over conditions: the CI can only reach the condition means' range
    assert 0.0 <= level["ci"][0] <= 0.5 <= level["ci"][1] <= 1.0


def test_a_missing_repeat_is_listed_per_repeat(tmp_path: Path) -> None:
    base = Chunk("l1-000", 1, 0, (1000100,))
    chunks = with_repeats([base], 2)
    episode(tmp_path, chunks[0], 0, 0, success=True)
    _, _, missing = collect(tmp_path, chunks)
    assert missing == [(1, 1000100, 1)]  # repeat 1 never ran


def test_pairing_reads_repeat_0_only(tmp_path: Path) -> None:
    var, _, _ = _repeated(tmp_path / "var", [[True, False], [False, True]])
    base, _, _ = _repeated(tmp_path / "base", [[False, False], [False, False]])
    with pytest.raises(ValueError, match="repeat 0"):
        paired(var, base)
    result = paired(repeat_0(var), repeat_0(base))
    assert result["conditions"] == 2 and result["success"]["variant_only"] == 1


# --- DA-42 5.2: version 1 beside version 2 ------------------------------------------


def _with_v1(level: int, seed: int, own: tuple[bool, Any], v1: tuple[bool, Any, bool]) -> Rollout:
    ok, failure = own
    v1_ok, v1_failure, hands = v1
    row = {
        "success": ok,
        "failure": failure,
        "scorer_version": 2,
        "scorer_steps": [True] * 7 if ok else [True] * 5 + [False] * 2,
        "scorer_v1": {
            "success": v1_ok,
            "failure": v1_failure,
            "steps": [False] * 7 if v1_failure == "L-PLACE-POSE" else [True] * 5 + [False] * 2,
            "at_failure": None
            if v1_failure is None
            else {"hand_contacts": {"left": hands, "right": hands}},
        },
    }
    return Rollout(level, seed, 0, "l1-000", 0, row)


def test_version_1_beside_version_2_counts_label_changes() -> None:
    rollouts = [
        _with_v1(1, 1, (True, None), (False, "L-TRAY-TILT", False)),  # released, then settled
        _with_v1(1, 2, (False, "L-PLACE-POSE"), (False, "L-TRAY-TILT", False)),
        _with_v1(1, 3, (False, "L-TRAY-TILT"), (False, "L-TRAY-TILT", True)),  # held: both
        _with_v1(1, 4, (False, "L-ONE-HAND"), (False, "L-PLACE-POSE", True)),  # v1 approach_a gap
        _with_v1(1, 5, (True, None), (True, None, False)),
    ]
    result = scorer_v1_vs_v2(rollouts)
    assert result is not None
    assert result["rollouts"] == 5 and result["versions"] == [2]
    assert result["successes"] == {"v1": 1, "own": 2}
    assert result["labels"] == {
        "L-PLACE-POSE -> L-ONE-HAND": 1,
        "L-TRAY-TILT -> L-PLACE-POSE": 1,
        "L-TRAY-TILT -> success": 1,
    }
    assert result["v1_tilt_released"] == 2
    assert result["approach_a"] == {"v1": 4, "own": 5}


def test_rows_without_version_1_have_no_comparison(tmp_path: Path) -> None:
    chosen, extra, missing = _scored(tmp_path, [2, 2])
    assert scorer_v1_vs_v2(chosen) is None
    assert summarize(PLAN, chosen, extra, missing, full=False)["scorer_v1_vs_v2"] is None


def test_more_repeats_on_disk_than_read_are_noted(tmp_path: Path) -> None:
    from flywheel_psi0.tray.eval_results import repeats_found, repeats_note

    base = Chunk("l1-000", 1, 0, (1000100,))
    for chunk in with_repeats([base], 3):
        episode(tmp_path, chunk, 0, 0, success=True)
    (tmp_path / "l2-000.r7").mkdir()  # another chunk's repeat is not counted
    assert repeats_found(tmp_path, [base]) == 3
    assert repeats_note(tmp_path, [base], 3) is None
    note = repeats_note(tmp_path, [base], 1)
    assert note is not None and "3 repeats per condition, 1 read" in note
    assert repeats_found(tmp_path / "none", [base]) == 1


def test_stage1_with_repeats_checks_repeat_0_only(tmp_path: Path, capsys: Any) -> None:
    from flywheel_psi0.tray import eval_results

    chunks = _stage1_set(tmp_path)
    for chunk in chunks[:6]:
        for i in range(10):
            episode(tmp_path / "b", chunk, 0, chunk.start + i, success=i < 2)
            episode(tmp_path / "c", chunk, 0, chunk.start + i, success=False)
    # repeat 1 of the first chunk only: repeats 1 of the other five are missing
    first_r1 = with_repeats(chunks[:1], 2)[1]
    for i in range(10):
        episode(tmp_path / "b", first_r1, 0, first_r1.start + i, success=True)
    common = [
        str(ROOT / "configs/runplans/tray/he-tray-b.yaml"), "--set", str(tmp_path / "set"),
        "--out", str(tmp_path / "b"), "--no-yaw", "--baseline", str(tmp_path / "c"), "--stage1",
    ]  # fmt: skip
    out = tmp_path / "r.json"
    assert eval_results.main([*common, "--repeats", "2", "--json", str(out)]) == 0
    result = json.loads(out.read_text())
    assert result["stage1"]["outcome"] == "E1" and len(result["missing"]) == 50
    assert all(m[2] == 1 for m in result["missing"]) and result["repeats_note"] is None
    capsys.readouterr()
    assert eval_results.main([*common, "--json", str(out)]) == 0  # repeats 1 left unread
    assert "2 repeats per condition, 1 read" in capsys.readouterr().out
    assert "2 repeats per condition" in json.loads(out.read_text())["repeats_note"]


# --- DA-50: paired difference on every repeat (docs/he/tray-jig.md 6) ---------------


def _repeated_levels(out: Path, wins: dict[int, list[list[bool]]], version: int = 2) -> Any:
    """wins[level][i][r]: success of repeat r of condition i of that level."""
    chunks = []
    for level, conds in wins.items():
        base = Chunk(f"l{level}-000", level, 0, tuple(1000100 + i for i in range(len(conds))))
        for chunk in with_repeats([base], len(conds[0])):
            for i, oks in enumerate(conds):
                if chunk.repeat < len(oks):
                    episode(out, chunk, 0, i, success=oks[chunk.repeat], scorer_version=version)
            chunks.append(chunk)
    chosen, _, _ = collect(out, chunks)
    return chosen


T, F = True, False
# level 1 condition means: variant 1, 1/3, 0; baseline 1/3, 1/3, 1/3 -> d 2/3, 0, -1/3
# level 2: variant 2/3, 0; baseline 0, 0 -> d 2/3, 0
VAR = {1: [[T, T, T], [T, F, F], [F, F, F]], 2: [[T, T, F], [F, F, F]]}
BASE = {1: [[T, F, F], [F, T, F], [F, F, T]], 2: [[F, F, F], [F, F, F]]}


def test_paired_diff_repeats_reads_every_repeat_per_condition(tmp_path: Path) -> None:
    var = _repeated_levels(tmp_path / "var", VAR)
    base = _repeated_levels(tmp_path / "base", BASE)
    result = paired_diff_repeats(var, base, [1, 2], 2000, 7, 0.95)
    assert (result["levels"], result["conditions"], result["repeats"]) == ([1, 2], 5, 3)
    assert result["variant_rate"] == 0.4 and result["baseline_rate"] == 0.2
    assert result["diff"] == 0.2
    assert result["conditions_variant_higher"] == 2
    assert result["conditions_baseline_higher"] == 1 and result["conditions_equal"] == 2
    assert (result["resamples"], result["seed"]) == (2000, 7)
    assert result["scorer_versions"] == {"variant": 2, "baseline": 2}
    assert result["cross_scorer"] is False
    only_2 = paired_diff_repeats(var, base, [2], 2000, 7, 0.95)
    assert (only_2["conditions"], only_2["diff"]) == (2, 0.3333)


def test_paired_diff_repeats_resamples_within_each_level(tmp_path: Path) -> None:
    var = _repeated_levels(tmp_path / "var", VAR)
    base = _repeated_levels(tmp_path / "base", BASE)
    result = paired_diff_repeats(var, base, [1, 2], 2000, 7, 0.95)
    stratified = bootstrap_ci([[2 / 3, 0, -1 / 3], [2 / 3, 0]], 2000, 7, 0.95)
    assert result["ci"] == pytest.approx(stratified, abs=1e-4)
    assert result["ci_vs_0"] == ("above" if stratified[0] > 0 else "contains")
    # the same seed gives the same CI; the seed is what the CI is drawn with
    assert paired_diff_repeats(var, base, [1, 2], 2000, 7, 0.95)["ci"] == result["ci"]
    other = paired_diff_repeats(var, base, [1, 2], 2000, 8, 0.95)
    assert other["ci"] == pytest.approx(
        bootstrap_ci([[2 / 3, 0, -1 / 3], [2 / 3, 0]], 2000, 8, 0.95), abs=1e-4
    )


def test_paired_diff_repeats_above_zero_and_identical_sides_contain_zero(
    tmp_path: Path,
) -> None:
    var = _repeated_levels(tmp_path / "var", {1: [[T, T, T]] * 4, 2: [[T, T, F]] * 4})
    base = _repeated_levels(tmp_path / "base", {1: [[F, F, F]] * 4, 2: [[F, F, F]] * 4})
    better = paired_diff_repeats(var, base, [1, 2], 2000, 7, 0.95)
    assert better["ci_vs_0"] == "above" and better["ci"][0] > 0
    # identical sides: every d_i is 0, the CI is (0, 0) and reads "contains", not a difference
    same = paired_diff_repeats(var, var, [1, 2], 2000, 7, 0.95)
    assert (same["diff"], same["ci"], same["ci_vs_0"]) == (0.0, (0.0, 0.0), "contains")
    assert same["conditions_equal"] == 8


def test_paired_diff_repeats_refuses_unpaired_sides(tmp_path: Path) -> None:
    var = _repeated_levels(tmp_path / "var", VAR)
    base = _repeated_levels(tmp_path / "base", BASE)
    with pytest.raises(ValueError, match="different conditions"):
        paired_diff_repeats([r for r in var if r.seed != 1000102], base, [1], 2000, 7, 0.95)
    with pytest.raises(ValueError, match="no condition"):
        paired_diff_repeats(var, base, [0], 2000, 7, 0.95)
    two = _repeated_levels(tmp_path / "two", {1: [[T, F]] * 3, 2: [[F, F]] * 2})
    with pytest.raises(ValueError, match="3 rollouts per condition, baseline 2"):
        paired_diff_repeats(var, two, [1, 2], 2000, 7, 0.95)
    uneven = [r for r in var if not (r.level == 1 and r.seed == 1000100 and r.repeat == 2)]
    with pytest.raises(ValueError, match="variant has uneven rollouts per condition"):
        paired_diff_repeats(uneven, base, [1, 2], 2000, 7, 0.95)
    old = _repeated_levels(tmp_path / "v1", BASE, version=1)
    with pytest.raises(ValueError, match="--cross-scorer"):
        paired_diff_repeats(var, old, [1, 2], 2000, 7, 0.95)
    crossed = paired_diff_repeats(var, old, [1, 2], 2000, 7, 0.95, cross_scorer=True)
    assert crossed["scorer_versions"] == {"variant": 2, "baseline": 1}
    assert crossed["cross_scorer"] is True


def _cli_set(tmp_path: Path, var: dict[int, list[list[bool]]], base: Any) -> list[str]:
    """A level 1 + 2 set with both sides written for every repeat; the common CLI args."""
    from flywheel_psi0.tray.eval_batch import chunk_plan, phases_for

    rows = [{"level": lv, "seed": 1000100 + i} for lv in var for i in range(len(var[lv]))]
    (tmp_path / "set").mkdir()
    (tmp_path / "set/conditions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    chunks = with_repeats(chunk_plan(rows, 10, phases_for(rows)), len(var[1][0]))
    for name, wins in (("var", var), ("base", base)):
        for chunk in chunks:
            for i in range(len(chunk.seeds)):
                ok = wins[chunk.level][i][chunk.repeat]
                episode(tmp_path / name, chunk, 0, chunk.start + i, success=ok, scorer_version=2)
    return [
        str(ROOT / "configs/runplans/tray/he-tray-v2.yaml"), "--set", str(tmp_path / "set"),
        "--out", str(tmp_path / "var"), "--no-yaw", "--baseline", str(tmp_path / "base"),
    ]  # fmt: skip


def test_cli_adds_the_all_repeats_pairing_beside_repeat_0(tmp_path: Path, capsys: Any) -> None:
    from flywheel_psi0.tray import eval_results

    common = _cli_set(tmp_path, VAR, BASE)
    out1, out3 = tmp_path / "r1.json", tmp_path / "r3.json"
    assert eval_results.main([*common, "--json", str(out1)]) == 0
    assert eval_results.main([*common, "--repeats", "3", "--json", str(out3)]) == 0
    r1, r3 = json.loads(out1.read_text()), json.loads(out3.read_text())
    assert "repeats" not in r1["paired"] and "bootstrap_seed" not in r1
    # the repeat-0 block is the same whether or not the later repeats are read
    assert {k: v for k, v in r3["paired"].items() if k != "repeats"} == r1["paired"]
    block = r3["paired"]["repeats"]
    assert block["on"] == "all repeats of each condition"
    head = block["headline"]
    assert (head["levels"], head["conditions"], head["repeats"]) == ([1, 2], 5, 3)
    assert (head["diff"], head["variant_rate"], head["baseline_rate"]) == (0.2, 0.4, 0.2)
    assert head["seed"] == PLAN.stats.seed and head["resamples"] == PLAN.stats.resamples
    stratified = bootstrap_ci(
        [[2 / 3, 0, -1 / 3], [2 / 3, 0]], PLAN.stats.resamples, PLAN.stats.seed, PLAN.stats.ci
    )
    assert head["ci"] == pytest.approx(stratified, abs=1e-4)
    assert sorted(block["by_level"]) == ["1", "2"]
    assert block["by_level"]["2"]["diff"] == 0.3333
    printed = capsys.readouterr().out
    assert "Cặp theo điều kiện, mọi lượt (3 lượt/điều kiện), mức 1+2 gộp: 5 điều kiện" in printed
    assert f"seed {PLAN.stats.seed}" in printed


def test_cli_bootstrap_seed_replaces_the_plans_seed(tmp_path: Path) -> None:
    from flywheel_psi0.tray import eval_results

    common = _cli_set(tmp_path, VAR, BASE)
    out = tmp_path / "r.json"
    args = [*common, "--repeats", "3", "--bootstrap-seed", "20261126", "--json", str(out)]
    assert eval_results.main(args) == 0
    result = json.loads(out.read_text())
    assert result["bootstrap_seed"] == 20261126 and result["stats"]["seed"] == 20261126
    assert result["paired"]["repeats"]["headline"]["seed"] == 20261126
    stats = PLAN.stats.model_copy(update={"seed": 20261126})
    expected = bootstrap_ci([[2 / 3, 0, -1 / 3], [2 / 3, 0]], stats.resamples, stats.seed, stats.ci)
    assert result["paired"]["repeats"]["headline"]["ci"] == pytest.approx(expected, abs=1e-4)
    # the repeat-0 paired CI and the per-level CI are drawn with it too
    var = _repeated_levels(tmp_path / "var2", VAR)
    base = _repeated_levels(tmp_path / "base2", BASE)
    repeat0 = paired_diff(repeat_0(var), repeat_0(base), [1, 2], stats)
    assert result["paired"]["headline"]["ci"] == pytest.approx(repeat0["ci"], abs=1e-4)
    level_1 = bootstrap_ci([[1.0, 1 / 3, 0.0]], stats.resamples, stats.seed, stats.ci)
    assert result["levels"]["1"]["ci"] == pytest.approx(level_1)


def test_cli_skips_the_all_repeats_pairing_when_a_rollout_is_missing(tmp_path: Path) -> None:
    from flywheel_psi0.tray import eval_results

    common = _cli_set(tmp_path, VAR, BASE)
    (tmp_path / "base/l2-000.r2/attempt-0/eval/eval_stats.txt").write_text("")
    out = tmp_path / "r.json"
    assert eval_results.main([*common, "--repeats", "3", "--json", str(out)]) == 0
    block = json.loads(out.read_text())["paired"]["repeats"]
    assert "headline" not in block and block["skipped"] == "missing: variant 0, baseline 2"

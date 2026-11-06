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
    summarize,
    table,
    trace_of,
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

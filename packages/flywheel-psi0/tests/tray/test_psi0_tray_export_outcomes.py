"""A tray eval batch as `RolloutOutcome` records (DA-43 K1)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.outcome import RolloutOutcome
from flywheel_psi0.tray import export_scores
from flywheel_psi0.tray.eval_batch import Chunk
from flywheel_psi0.tray.eval_results import STEP_NAMES, Rollout
from flywheel_psi0.tray.export_outcomes import (
    FINAL_MEASURES,
    default_target_of,
    export,
    final_measures,
    main,
)
from flywheel_psi0.tray.place_error import pose_error, rows_for

L1 = Chunk("l1-000", 1, 0, (1000100, 1000101, 1000102))
PLAN_ID = "rp_test"


def z_quat(yaw: float) -> list[float]:
    """(w, x, y, z) of a turn about z, MuJoCo's xquat order."""
    return [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]


def rollout(out: Path, i: int, success: bool, flags: list[bool], failure: str | None,
            pos: tuple[float, float, float] = (-1.12, 0.01, 0.85), yaw: float = 0.05,
            drop: str | None = None) -> None:
    folder = out / L1.id / "attempt-0"
    (folder / "eval").mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {"seed": L1.seed_of(i), "level": 1, "success": success,
                           "failure": failure, "tray_pos": list(pos), "tray_quat": z_quat(yaw),
                           "steps": 4664, "scorer_steps": flags, "sim_time_s": 93.285}
    if drop is not None:
        del row[drop]
    with (folder / "outcomes.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")
    with (folder / "eval/eval_stats.txt").open("a") as f:
        f.write(f"episode_{i}: {success} \n")
    steps = folder / "traces" / f"t{i}" / "steps.jsonl"
    steps.parent.mkdir(parents=True)
    (steps.parent / "rollout_result.json").write_text("{}")
    steps.write_text(json.dumps({"episode_id": f"episode_{i}", "step": 0}) + "\n")


def eval_set(tmp_path: Path) -> Path:
    folder = tmp_path / "set"
    folder.mkdir(exist_ok=True)
    rows = [{"level": 1, "seed": s,
             "environment_config": {"flywheel": {"seed": s, "run_plan_id": PLAN_ID}}}
            for s in L1.seeds]
    (folder / "conditions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return folder


def successes(out: Path) -> None:
    for i, yaw in enumerate((0.05, 3.0, -0.1)):
        rollout(out, i, True, [True] * 7, None, yaw=yaw)


def test_outcomes_join_their_scores_and_carry_the_verdict(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    successes(out)
    outcomes = export(eval_set(tmp_path), out, "C_70")
    config = tmp_path / "tray.yaml"
    config.write_text("r_reach: 0.10\n")
    scores = export_scores.export(eval_set(tmp_path), out, "C_70", scorer_config=config)
    assert [o.episode_id for o in outcomes] == [s.episode_id for s in scores]
    first = outcomes[0]
    assert (first.run, first.seed, first.level, first.repeat) == ("C_70", 1000100, 1, 0)
    assert (first.run_plan_id, first.task_id) == (PLAN_ID, "tray")
    assert (first.sim_time_s, first.control_steps) == (93.285, 4664)
    assert first.verdict.step_names == list(STEP_NAMES)
    assert first.verdict.step_latched == [True] * 7 and first.verdict.success
    assert first.verdict.scorer_version == export_scores.SCORER_VERSION
    assert first.verdict.failure_t is None and first.verdict.at_failure is None
    assert sorted(first.final) == sorted(FINAL_MEASURES)
    assert first.extrema == {} and first.videos == []


def test_place_measures_are_place_errors(tmp_path: Path) -> None:
    target_of = default_target_of()
    row = {"tray_pos": [-1.08, 0.04, 0.85], "tray_quat": z_quat(2.9)}
    target = target_of(1, 1000101)
    final = final_measures(row, target)
    assert (final["place_distance_m"], final["place_yaw_error_deg"]) == pose_error(
        row["tray_pos"], row["tray_quat"], target)
    r = Rollout(1, 1000101, 1, "l1-000", 0, {**row, "success": False, "failure": "L-PLACE-POSE"})
    side = rows_for([r], target_of, 0.05, 10.0)[0]
    assert round(final["place_distance_m"], 4) == side["distance_m"]
    assert round(final["place_yaw_error_deg"], 2) == side["yaw_error_deg"]
    assert final["target_xy_m"] == [target[0], target[1]] and final["target_yaw_rad"] == target[2]


def test_the_quaternion_stays_scalar_first() -> None:
    """The row's xquat is (w, x, y, z), the contract's `_quat` order: kept as is, and its yaw
    is the turn about z (read as (x, y, z, w) the same numbers would flip the tray)."""
    quat = z_quat(1.2)
    final = final_measures({"tray_pos": [0.0, 0.0, 0.85], "tray_quat": quat}, (0.0, 0.0, 0.0))
    assert final["tray_quat"] == quat and final["tray_quat"][0] == pytest.approx(math.cos(0.6))
    assert final["tray_yaw_rad"] == pytest.approx(1.2)
    assert final["place_yaw_error_deg"] == pytest.approx(math.degrees(1.2))


def test_main_writes_valid_lines_the_same_bytes_twice(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    successes(out)
    files = [tmp_path / "a.jsonl", tmp_path / "b.jsonl"]
    for f in files:
        assert main(["--set", str(eval_set(tmp_path)), "--out", str(out), "--run", "C_70",
                     "--outcomes", str(f)]) == 0
    lines = files[0].read_text().splitlines()
    assert len(lines) == 3 and files[0].read_bytes() == files[1].read_bytes()
    assert all(RolloutOutcome.model_validate_json(line).verdict.success for line in lines)
    assert "failure_t" not in lines[0]  # absent, not null


def test_a_missing_rollout_is_refused(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    for i in range(2):
        rollout(out, i, True, [True] * 7, None)
    target = tmp_path / "outcomes.jsonl"
    assert main(["--set", str(eval_set(tmp_path)), "--out", str(out), "--run", "C_70",
                 "--outcomes", str(target)]) == 1
    assert not target.exists()


def test_a_row_without_sim_time_is_refused(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    successes(out)
    (out / L1.id / "attempt-0" / "outcomes.jsonl").unlink()
    for i in range(3):
        folder = out / L1.id / "attempt-0"
        row = {"seed": L1.seed_of(i), "level": 1, "success": True, "failure": None,
               "tray_pos": [0, 0, 0.85], "tray_quat": [1, 0, 0, 0], "steps": 10,
               "scorer_steps": [True] * 7}
        with (folder / "outcomes.jsonl").open("a") as f:
            f.write(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="sim_time_s"):
        export(eval_set(tmp_path), out, "C_70")


def test_a_labelled_failure_is_refused_while_the_contract_needs_failure_t(
    tmp_path: Path,
) -> None:
    """The batch has no failure time; `ScorerVerdict` sets `failure_t` exactly when a label
    is set. The export refuses rather than invent one. Flip this test when the contract
    lets `failure_t` be absent next to a label."""
    out = tmp_path / "batch"
    rollout(out, 0, False, [True] * 5 + [False] * 2, "L-PLACE-POSE")
    rollout(out, 1, True, [True] * 7, None)
    rollout(out, 2, True, [True] * 7, None)
    with pytest.raises(ValueError, match="failure_t"):
        export(eval_set(tmp_path), out, "C_70")

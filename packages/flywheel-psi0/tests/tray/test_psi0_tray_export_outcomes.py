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


def test_a_labelled_failure_exports_with_its_time_left_absent(tmp_path: Path) -> None:
    """The batch has no failure time. Since #211 `ScorerVerdict` takes a label without
    `failure_t`, so the export writes the label and leaves the time absent, never invents
    one; a reader treats the time as a missing signal."""
    out = tmp_path / "batch"
    rollout(out, 0, False, [True] * 5 + [False] * 2, "L-PLACE-POSE")
    rollout(out, 1, True, [True] * 7, None)
    rollout(out, 2, True, [True] * 7, None)
    outcomes = export(eval_set(tmp_path), out, "C_70")
    failed = outcomes[0].verdict
    assert (failed.success, failed.failure_label) == (False, "L-PLACE-POSE")
    assert failed.failure_t is None and failed.at_failure is None
    assert [o.verdict.success for o in outcomes[1:]] == [True, True]


# --- DA-47: K1 from DA-42 rows, repeats, scene ----------------------------------------

LATCH = [7.645, 8.085, 10.585, 14.865, 23.405, 28.285]
END = 31.724999999997973  # a real sim time: the last latch is exactly the episode's end


def da42_row(i: int, **over: Any) -> dict[str, Any]:
    """A replayed episode's row of DA-42: success under both scorer versions."""
    row: dict[str, Any] = {
        "seed": L1.seed_of(i), "level": 1, "success": True, "failure": None, "steps": 1586,
        "scorer_steps": [True] * 7, "sim_time_s": END, "scorer_version": 2,
        "failure_t": None, "at_failure": None, "step_latch_t": [*LATCH, END],
        "palm_handle_min_m": {"left": 0.069, "right": 0.065, "both": 0.069},
        "palm_handle_bar_min_m": {"left": 0.032, "right": 0.040, "both": 0.040},
        "scorer_v1": {
            "scorer_version": 1, "steps": [True] * 7, "success": True, "failure": None,
            "failure_t": None, "at_failure": None, "step_latch_t": [8.005, *LATCH[1:], END],
        },
        "tray_pos": [-1.1012, 0.0034, 0.7921], "tray_quat": z_quat(0.012),
    }  # fmt: skip
    row.update(over)
    return row


SNAPSHOT = {
    "tray_on_table": "none", "hand_contacts": {"left": True, "right": False},
    "tilt_deg": 31.5, "tray_pos": [0.2, 0.01, 1.02], "tray_quat": [0.96, 0.27, 0.0, 0.0],
}  # fmt: skip
TILT = {
    "success": False, "failure": "L-TRAY-TILT", "scorer_steps": [True] * 3 + [False] * 4,
    "failure_t": 12.5, "at_failure": SNAPSHOT,
    "step_latch_t": [7.6, 8.0, 10.5, None, None, None, None],
}  # fmt: skip


def write_rows(out: Path, rows: list[dict[str, Any]], folder: str = L1.id) -> None:
    attempt = out / folder / "attempt-0"
    (attempt / "eval").mkdir(parents=True, exist_ok=True)
    with (attempt / "outcomes.jsonl").open("a") as f:
        f.writelines(json.dumps(row) + "\n" for row in rows)
    with (attempt / "eval/eval_stats.txt").open("a") as f:
        f.writelines(f"episode_{k}: {row['success']} \n" for k, row in enumerate(rows))


def test_a_real_da42_row_exports_every_signal(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    write_rows(out, [da42_row(i) for i in range(3)])
    outcome = export(eval_set(tmp_path), out, "C_70")[0]
    v = outcome.verdict
    assert v.scorer_version == "simple-tray-predicates@2" and v.success
    assert v.step_latch_t == [*LATCH, END] and outcome.sim_time_s == END
    assert v.failure_t is None and v.at_failure is None and v.failure_label is None
    [v1] = outcome.other_verdicts
    assert v1.scorer_version == "simple-tray-predicates@1" and v1.step_names == v.step_names
    assert v1.step_latch_t is not None and v1.step_latch_t[0] == 8.005
    assert outcome.extrema == {
        "palm_handle_left_min_m": 0.069, "palm_handle_right_min_m": 0.065,
        "palm_handle_both_min_m": 0.069, "palm_bar_left_min_m": 0.032,
        "palm_bar_right_min_m": 0.040, "palm_bar_both_min_m": 0.040,
    }  # fmt: skip
    again = RolloutOutcome.model_validate_json(outcome.model_dump_json(exclude_none=True))
    assert again == outcome  # null latch times survive the dump


def test_a_failure_carries_its_time_and_state(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    v1_tilt = {
        **da42_row(0)["scorer_v1"],
        **{k: TILT[k] for k in ("failure", "failure_t", "at_failure", "step_latch_t")},
        "success": False,
        "steps": TILT["scorer_steps"],
    }
    write_rows(out, [da42_row(0, **TILT, scorer_v1=v1_tilt,
                              palm_handle_min_m={"left": 0.05, "right": None, "both": None}),
                     da42_row(1), da42_row(2)])  # fmt: skip
    outcome = export(eval_set(tmp_path), out, "C_70")[0]
    v = outcome.verdict
    assert (v.failure_label, v.failure_t) == ("L-TRAY-TILT", 12.5)
    assert v.at_failure == {
        "tilt_deg": 31.5, "tray_pos_m": [0.2, 0.01, 1.02], "tray_quat": [0.96, 0.27, 0.0, 0.0],
        "tray_on_table": "none", "hand_contact_left": True, "hand_contact_right": False,
    }  # fmt: skip
    assert outcome.other_verdicts[0].at_failure == v.at_failure
    assert outcome.extrema["palm_handle_left_min_m"] == 0.05
    assert "palm_handle_right_min_m" not in outcome.extrema  # null: left out


def test_a_label_without_a_time_has_no_state(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    timeout = {
        "success": False,
        "failure": "L-TIMEOUT",
        "scorer_steps": [False] * 7,
        "step_latch_t": [None] * 7,
    }
    write_rows(out, [da42_row(0, **timeout), da42_row(1), da42_row(2)])
    v = export(eval_set(tmp_path), out, "C_70")[0].verdict
    assert (v.failure_label, v.failure_t, v.at_failure) == ("L-TIMEOUT", None, None)


@pytest.mark.parametrize(
    ("over", "why"),
    [
        ({"step_latch_t": [*LATCH, None]}, "latch time is set exactly when"),
        ({"step_latch_t": [*LATCH, END + 0.01]}, "latched after the episode ended"),
        ({**TILT, "failure_t": END + 1}, "failure_t is after the episode ended"),
        ({"failure_t": 3.0}, "failure_t needs a failure label"),
        ({**TILT, "failure_t": None}, "at_failure without failure_t"),
        ({**TILT, "at_failure": {"tilt_deg": 3.0}}, "KeyError"),
    ],
)
def test_a_row_the_contract_refuses_names_the_rollout(
    tmp_path: Path, over: dict[str, Any], why: str
) -> None:
    out = tmp_path / "batch"
    write_rows(out, [da42_row(0), da42_row(1, **over), da42_row(2)])
    with pytest.raises(ValueError, match="1 rollouts the contract refuses") as error:
        export(eval_set(tmp_path), out, "C_70")
    assert "C_70/l1-s1000101" in str(error.value) and why in str(error.value)


def test_a_batch_of_two_scorer_versions_is_refused(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    write_rows(out, [da42_row(0), da42_row(1, scorer_version=None), da42_row(2)])
    with pytest.raises(ValueError, match="mix scorer versions"):
        export(eval_set(tmp_path), out, "C_70")


def test_each_repeat_is_one_outcome_with_its_own_id(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    for folder in (L1.id, f"{L1.id}.r1", f"{L1.id}.r2"):
        write_rows(out, [da42_row(i) for i in range(3)], folder)
    conditions = eval_set(tmp_path)
    outcomes = export(conditions, out, "C_70", repeats=3)
    assert len(outcomes) == 9
    assert [(o.episode_id, o.repeat) for o in outcomes[::3]] == [
        ("C_70/l1-s1000100", 0), ("C_70/l1-s1000100-r1", 1), ("C_70/l1-s1000100-r2", 2),
    ]  # fmt: skip
    assert len({o.episode_id for o in outcomes}) == 9
    with pytest.raises(ValueError, match=r"rollouts missing: .*repeat=3"):
        export(conditions, out, "C_70", repeats=4)


def test_a_jig_rollout_is_placed_against_the_jig_target(tmp_path: Path) -> None:
    from flywheel_psi0.tray.place_error import JIG_TASK_UID, target_for

    out = tmp_path / "batch"
    jig = target_for(JIG_TASK_UID)
    rows = []
    for i in range(3):
        x, y, yaw = jig(1, L1.seed_of(i))
        rows.append(da42_row(i, task_uid=JIG_TASK_UID, tray_pos=[x, y, 0.85],
                             tray_quat=z_quat(yaw)))  # fmt: skip
    write_rows(out, rows)
    outcomes = export(eval_set(tmp_path), out, "C_70")
    assert all(o.final["place_distance_m"] == pytest.approx(0.0, abs=1e-9) for o in outcomes)
    assert outcomes[0].task_id == "tray"
    zone1 = default_target_of()(1, L1.seed_of(0))
    assert outcomes[0].final["target_xy_m"] != [zone1[0], zone1[1]]


def test_a_batch_of_two_scenes_is_refused(tmp_path: Path) -> None:
    from flywheel_psi0.tray.place_error import JIG_TASK_UID

    out = tmp_path / "batch"
    write_rows(out, [da42_row(0, task_uid=JIG_TASK_UID), da42_row(1), da42_row(2)])
    with pytest.raises(ValueError, match="mix scenes"):
        export(eval_set(tmp_path), out, "C_70")

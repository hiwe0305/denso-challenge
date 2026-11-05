"""The tray task scored through `configs/eval/scorer/tray.yaml` (DA-36 task 9.2, AC 8).

One case per tray code, each checked for the shared class spec v10.6 section
5.2 gives it (PO decision 5/11/2026 on #59, option a), and the three codes that
take the class of the failed step checked at steps of different classes. The
task is `tray_fake.TrayTask`; nothing in the scorer knows it is a tray.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel.eval.api import SCORER_CONFIG_DIR, score_trace
from flywheel.eval.cli import app
from flywheel.eval.scorer.artifact import build_record
from flywheel.eval.scorer.score import EpisodeScore
from tray_fake import ROWS, TrayTask, from_row, tray_rows
from typer.testing import CliRunner

CONFIG = SCORER_CONFIG_DIR / "tray.yaml"


def score(tmp_path: Path, rows: list[dict[str, object]]) -> EpisodeScore:
    path = tmp_path / "ep.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return score_trace(path, TrayTask(), CONFIG)


def test_a_clean_tray_episode_passes_all_seven_steps(tmp_path: Path) -> None:
    scored = score(tmp_path, tray_rows())

    assert [step.status for step in scored.steps] == ["pass"] * 7
    assert scored.success is True
    # Both halves of the control: nothing failed and nothing was unknown.
    assert scored.unknown_steps == ()
    assert scored.balance.unknown is False


# (case, overrides, failed step k, kind, shared class)
CASES: list[tuple[str, dict[str, list[float | None]], int, str, str]] = [
    ("part-drop", {"parts_in_tray": from_row(12, 1.0, 0.0)}, 4, "L-PART-DROP", "carry"),
    (
        "one-hand",
        {"right_handle_contact": [1.0 if 3 <= i < 11 else 0.0 for i in range(ROWS)]},
        4,
        "L-ONE-HAND",
        "carry",
    ),
    ("place-pose", {"tray_target_pos_error": from_row(18, 0.01, 0.2)}, 5, "L-PLACE-POSE", "place"),
    ("walk", {"torso_in_zone_b": [0.0] * ROWS}, 4, "L-WALK", "carry"),
    # L-TRAY-TILT takes the class of step k: tipped while lifting, while
    # carrying, and while lowering onto table B.
    ("tilt-lift", {"tray_tilt_deg": from_row(4, 2.0, 30.0)}, 2, "L-TRAY-TILT", "grasp"),
    ("tilt-carry", {"tray_tilt_deg": from_row(7, 2.0, 30.0)}, 3, "L-TRAY-TILT", "carry"),
    ("tilt-place", {"tray_tilt_deg": from_row(16, 2.0, 30.0)}, 5, "L-TRAY-TILT", "place"),
    ("collide-approach", {"collision": from_row(1, 0.0, 1.0)}, 0, "L-COLLIDE", "approach"),
    ("collide-carry", {"collision": from_row(8, 0.0, 1.0)}, 3, "L-COLLIDE", "carry"),
    ("collide-place", {"collision": from_row(16, 0.0, 1.0)}, 5, "L-COLLIDE", "place"),
    (
        "timeout-approach",
        {
            "left_palm_handle_distance": [0.3] * ROWS,
            "t": [3.0 * i for i in range(ROWS)],
        },
        0,
        "L-TIMEOUT",
        "approach",
    ),
    (
        "timeout-reach-b",
        {"torso_in_zone_b": [0.0] * ROWS, "t": [3.0 * i for i in range(ROWS)]},
        4,
        "L-TIMEOUT",
        "carry",
    ),
]


@pytest.mark.parametrize(
    ("overrides", "failed", "kind", "klass"),
    [case[1:] for case in CASES],
    ids=[case[0] for case in CASES],
)
def test_each_tray_code_carries_its_shared_class(
    tmp_path: Path, overrides: dict[str, list[float | None]], failed: int, kind: str, klass: str
) -> None:
    scored = score(tmp_path, tray_rows(**overrides))

    assert scored.unknown_steps == ()
    assert scored.failure.first_failed_step == failed
    assert scored.failure.failure_kind == kind
    assert scored.failure.failure_class == klass
    assert scored.steps[failed].status == "fail"
    assert all(step.status == "not_attempted" for step in scored.steps[failed + 1 :])


def test_every_tray_code_the_task_declares_has_a_case() -> None:
    declared = {spec.kind for spec in TrayTask().failure_kinds()}
    covered = {case[3] for case in CASES} | {"L-BALANCE"}

    assert declared == covered


def test_a_fall_after_seven_clean_steps_is_l_balance(tmp_path: Path) -> None:
    scored = score(tmp_path, tray_rows(pelvis_height=from_row(33, 0.75, 0.3)))

    assert [step.status for step in scored.steps] == ["pass"] * 7
    assert scored.failure.failure_kind == "L-BALANCE"
    assert scored.failure.failure_class == "balance"
    assert scored.balance.row == 33


def test_a_missing_tray_signal_is_unknown_not_a_failure(tmp_path: Path) -> None:
    rows = [{k: v for k, v in row.items() if k != "tray_tilt_deg"} for row in tray_rows()]

    record = build_record(score(tmp_path, rows))

    assert record.step_status[3] == "unknown"
    assert record.unknown_reason is not None
    assert record.unknown_reason[3] == "missing_signal"
    assert record.failure_kind == "L-UNKNOWN"
    assert record.failure_class is None
    assert record.success is None


def test_the_tray_record_is_a_seven_step_score(tmp_path: Path) -> None:
    record = build_record(score(tmp_path, tray_rows(collision=from_row(8, 0.0, 1.0))))

    assert record.task_id == "tray"
    assert record.scorer_version == "0.2.0"
    assert record.meta["step_names"] == [stage.name for stage in TrayTask().stages()]
    assert record.step_status == ["pass"] * 3 + ["fail"] + ["not_attempted"] * 3
    assert (record.failure_kind, record.failure_class) == ("L-COLLIDE", "carry")


def test_fw_eval_score_scores_a_tray_trace(tmp_path: Path) -> None:
    trace = tmp_path / "ep.jsonl"
    rows = tray_rows(tray_tilt_deg=from_row(7, 2.0, 30.0))
    trace.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["score", "--trace", str(trace), "--task", "tray_fake:TrayTask", "--config", str(CONFIG)],
    )

    assert result.exit_code == 0, result.output
    assert "task: tray 0.2.0" in result.output
    assert "kiểu lỗi: L-TRAY-TILT (carry); hỏng trước ở: bước 3" in result.output

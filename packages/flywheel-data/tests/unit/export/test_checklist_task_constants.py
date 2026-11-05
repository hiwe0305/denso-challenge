"""Point 6 with action dims declared constant per task (DA-02, PO decision 5/11/2026).

Planner-made tray data holds thumb_0 and the waist at exactly 0 (D-12, D-13), while
psi-data moves them; configs/data/export_checklist.yaml declares them for the tray task
only, so g1.yaml keeps them free for every other G1 dataset.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from checklist_data import REPO, edit_jsonl, frames_of, g1_layout, make_tray_dataset
from flywheel.data.config import ConfigError
from flywheel.data.export.checklist import (
    TASK_CONSTANTS_YAML,
    ChecklistFinding,
    TaskConstants,
    load_task_constants,
    run_checklist,
)
from flywheel.data.ingest.lerobot import write_episode
from flywheel.data.inject.stats import write_stats

TRAY_UID = "g1_wholebody_tray_transfer_teleop"
TWO_TABLE_UID = "g1_wholebody_locomotion_pick_between_tables_teleop"
TRAY_ZEROS = [0, 7, 28, 29, 30]
LENGTHS = (6, 9, 4)


def make_dataset(root: Path, uids: list[str | None], zeros: list[int]) -> Path:
    """The tray test dataset with action `zeros` at 0 in every frame and one task UID
    per episode in meta/episodes.jsonl (None: no environment_config)."""
    make_tray_dataset(root, LENGTHS)
    for index, length in enumerate(LENGTHS):
        frames = frames_of(index, length)
        frames.action[:, zeros] = 0.0
        write_episode(root, frames)
    write_stats(root)
    rows = iter(uids)

    def set_uid(row: dict[str, object]) -> None:
        uid = next(rows)
        if uid is not None:
            row["environment_config"] = json.dumps({"uid": uid, "label": "test"})

    edit_jsonl(root / "meta" / "episodes.jsonl", set_uid)
    return root


def constant_finding(root: Path, constants: TaskConstants | None) -> ChecklistFinding:
    findings = {f.check.name: f for f in run_checklist(root, g1_layout(), constants)}
    return findings["v21.6.stats.constant"]


@pytest.fixture
def constants() -> TaskConstants:
    return load_task_constants(REPO / TASK_CONSTANTS_YAML, g1_layout())


def test_the_config_declares_the_tray_zeros_for_the_tray_task_only(
    constants: TaskConstants,
) -> None:
    assert dict(constants.dims) == {TRAY_UID: tuple(TRAY_ZEROS)}
    assert constants.version.startswith("checklist-1@")
    assert len(constants.version.split("@")[1]) == 12
    # g1.yaml keeps them free: psi-data moves these joints.
    assert not any(g1_layout().dimensions[i].constant for i in TRAY_ZEROS)


def test_undeclared_constant_dims_fail(tmp_path: Path) -> None:
    root = make_dataset(tmp_path / "tray", [TRAY_UID] * 3, TRAY_ZEROS)
    finding = constant_finding(root, None)
    assert not finding.check.passed
    assert finding.check.value == 5
    assert finding.detail == (
        "constant action dims [0, 7, 28, 29, 30, 31]; masked or declared [31]; "
        "errors [0, 7, 28, 29, 30]"
    )


def test_dims_declared_for_the_task_pass(tmp_path: Path, constants: TaskConstants) -> None:
    root = make_dataset(tmp_path / "tray", [TRAY_UID] * 3, TRAY_ZEROS)
    finding = constant_finding(root, constants)
    assert finding.check.passed
    assert finding.detail == (
        "constant action dims [0, 7, 28, 29, 30, 31]; masked or declared "
        f"[0, 7, 28, 29, 30, 31]; errors []; {constants.version} declares "
        f"[0, 7, 28, 29, 30] for tasks ['{TRAY_UID}']"
    )
    failed = [f.check.name for f in run_checklist(root, g1_layout(), constants)
              if not f.check.passed]
    assert failed == []


def test_a_task_without_a_declaration_still_fails_on_those_dims(
    tmp_path: Path, constants: TaskConstants
) -> None:
    root = make_dataset(tmp_path / "other", [TWO_TABLE_UID] * 3, TRAY_ZEROS)
    finding = constant_finding(root, constants)
    assert finding.check.value == 5
    assert "errors [0, 7, 28, 29, 30]" in finding.detail
    assert f"declares [] for tasks ['{TWO_TABLE_UID}']" in finding.detail


def test_a_declaration_must_hold_for_every_task_of_the_dataset(
    tmp_path: Path, constants: TaskConstants
) -> None:
    # The stats cover every episode, so one undeclared task leaves the dims undeclared.
    mixed = make_dataset(tmp_path / "mixed", [TRAY_UID, TWO_TABLE_UID, TRAY_UID], TRAY_ZEROS)
    assert constant_finding(mixed, constants).check.value == 5
    # An episode without a task UID is not the tray task either.
    unknown = make_dataset(tmp_path / "unknown", [TRAY_UID, None, TRAY_UID], TRAY_ZEROS)
    finding = constant_finding(unknown, constants)
    assert finding.check.value == 5
    assert f"tasks ['<no uid>', '{TRAY_UID}']" in finding.detail


def test_psi_data_like_dims_that_vary_are_unaffected(
    tmp_path: Path, constants: TaskConstants
) -> None:
    root = make_dataset(tmp_path / "psi", [TWO_TABLE_UID] * 3, [])
    with_config = constant_finding(root, constants)
    without = constant_finding(root, None)
    assert with_config.check.passed and without.check.passed
    assert without.detail == "constant action dims [31]; masked or declared [31]; errors []"
    assert with_config.detail.startswith(without.detail)


def test_a_declared_dim_that_varies_is_stale_and_fails(
    tmp_path: Path, constants: TaskConstants
) -> None:
    # Tray data whose waist moves again: the declaration no longer matches the data.
    root = make_dataset(tmp_path / "moving", [TRAY_UID] * 3, [0, 7])
    finding = constant_finding(root, constants)
    assert not finding.check.passed
    assert finding.check.value == 3
    assert "errors []" in finding.detail
    assert finding.detail.endswith(
        "; stale [28, 29, 30] (declared for the task, not constant in the data)"
    )


def write_config(path: Path, body: str) -> Path:
    path.write_text(body)
    return path


def test_the_loader_refuses_a_name_other_than_the_layout(tmp_path: Path) -> None:
    path = write_config(tmp_path / "c.yaml", (
        "version: t\nconstant_action_dims:\n  tray:\n    28: waist_yaw_joint\n"
    ))
    with pytest.raises(ConfigError, match="'waist_yaw_joint', the layout has 'waist_roll_joint'"):
        load_task_constants(path, g1_layout())
    path = write_config(tmp_path / "w.yaml", (
        "version: t\nconstant_action_dims:\n  tray:\n    36: base_height_command\n"
    ))
    with pytest.raises(ConfigError, match="the layout has None"):
        load_task_constants(path, g1_layout())


def test_the_loader_refuses_missing_and_unknown_keys(tmp_path: Path) -> None:
    path = write_config(tmp_path / "c.yaml", "constant_action_dims: {}\n")
    with pytest.raises(ConfigError, match=r"missing \['version'\]"):
        load_task_constants(path, g1_layout())
    path = write_config(tmp_path / "d.yaml", "version: t\nconstant_action_dims: {}\nextra: 1\n")
    with pytest.raises(ConfigError, match=r"unknown \['extra'\]"):
        load_task_constants(path, g1_layout())
    path = write_config(tmp_path / "e.yaml", (
        "version: t\nconstant_action_dims:\n  tray:\n    left: left_hand_thumb_0_joint\n"
    ))
    with pytest.raises(ConfigError, match="not an action dim index"):
        load_task_constants(path, g1_layout())

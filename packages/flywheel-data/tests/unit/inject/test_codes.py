"""Defect codes follow design 27/10/2026 sections 9.2 and 10 (fixed 3/11/2026, issue #34)."""

from flywheel.data.inject.applied import CHECKS
from flywheel.data.inject.codes import DATA_DEFECT_CODES


def test_data_codes_follow_design_table() -> None:
    assert DATA_DEFECT_CODES == {
        "nan_values": "D1",
        "timestamp_sync_offset": "D2",
        "drop_frames": "D2",
        "joint_jump": "D3",
        "joint_limit_exceeded": "D3",
        "unit_deg_rad": "D3",
        "holdout_seed_leak": "D5",
        "duplicate_episode": "D5",
        "corrupted_success_label": "D6",
        "wrong_task_instruction": "D6",
        "action_sign_flip": "D7",
    }


def test_every_data_kind_has_an_applied_check() -> None:
    assert set(CHECKS) | {"duplicate_episode"} == set(DATA_DEFECT_CODES)

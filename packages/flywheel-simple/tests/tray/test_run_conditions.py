"""The runner's condition reader takes tray LeRobot conditions without `dr_state_dict`."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import numpy as np

TRAY_CONDITION = {"uid": "g1_wholebody_tray_transfer_teleop", "tray": {"sample": {"seed": 7}}}


class FakeDataset:
    """Two episodes of 3 and 2 frames; frame i is {"index": i}."""

    def __init__(self, conditions: list[dict[str, Any]]) -> None:
        self.episode_data_index = {"from": np.array([0, 3]), "to": np.array([3, 5])}
        self.meta = SimpleNamespace(
            episodes=[{"environment_config": json.dumps(c)} for c in conditions]
        )

    def __getitem__(self, i: int) -> dict[str, int]:
        return {"index": i}


def test_tray_condition_without_dr_state_dict_is_read_as_recorded() -> None:
    from flywheel_simple.tray.run import get_episode_lerobot

    env_conf, frames = get_episode_lerobot(FakeDataset([{}, TRAY_CONDITION]), 1)
    assert env_conf == TRAY_CONDITION
    assert frames == [{"index": 3}, {"index": 4}]


def test_condition_with_dr_state_dict_gets_simples_scene_uid_rewrite() -> None:
    from flywheel_simple.tray.run import get_episode_lerobot

    hssd = {"uid": "two_table", "dr_state_dict": {"scene": {"uid": "hssd:102344280"}}}
    env_conf, frames = get_episode_lerobot(FakeDataset([hssd, {}]), 0)
    assert env_conf["dr_state_dict"]["scene"]["uid"] == "hssd:scene3"
    assert frames == [{"index": 0}, {"index": 1}, {"index": 2}]


def test_plain_int_index_is_accepted() -> None:
    from flywheel_simple.tray.run import get_episode_lerobot

    dataset = FakeDataset([TRAY_CONDITION, {}])
    dataset.episode_data_index = {"from": [0, 3], "to": [3, 5]}  # type: ignore[dict-item]
    assert len(get_episode_lerobot(dataset, 0)[1]) == 3

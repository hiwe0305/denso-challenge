"""Tray fields, outcome, flywheel meta and attempt log of a PICO session (DA-35 AC 1, 2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel_simple.tray.pico.conditions import Condition
from flywheel_simple.tray.pico.recording import (
    TRAY_FEATURES,
    AttemptLog,
    episode_outcome,
    flywheel_block,
    tray_frame,
)
from flywheel_simple.tray.predicates import STEP_NAMES, StepReport


def privileged() -> dict[str, np.ndarray]:
    return {
        "tray_pos": np.array([0.9, 0.1, 0.85]),
        "tray_quat": np.array([1.0, 0.0, 0.0, 0.0]),
        "part_pos": np.arange(18, dtype=float).reshape(6, 3),
        "target_pose": np.array([-0.9, 0.0, 0.0]),
    }


def report(steps: int = 0, success: bool = False, failure: str | None = None) -> StepReport:
    flags = tuple(i < steps for i in range(len(STEP_NAMES)))
    return StepReport(steps=flags, success=success, failure=failure)  # type: ignore[arg-type]


def test_frame_matches_the_declared_features() -> None:
    frame = tray_frame(privileged(), report(steps=3))
    assert set(frame) == set(TRAY_FEATURES)
    for key, feature in TRAY_FEATURES.items():
        assert frame[key].shape == feature["shape"]
        assert frame[key].dtype == np.dtype(feature["dtype"])
        assert len(feature["names"]) == feature["shape"][0]


def test_frame_values() -> None:
    frame = tray_frame(privileged(), report(steps=3))
    np.testing.assert_allclose(frame["observation.tray_pose"], [0.9, 0.1, 0.85, 1, 0, 0, 0])
    np.testing.assert_allclose(frame["observation.part_pos"], np.arange(18))
    np.testing.assert_allclose(frame["observation.tray_steps"], [1, 1, 1, 0, 0, 0, 0])


def test_frame_before_the_first_report_has_no_steps() -> None:
    frame = tray_frame(privileged(), None)
    assert not frame["observation.tray_steps"].any()


@pytest.mark.parametrize(
    ("terminated", "truncated", "rep", "reset", "expected"),
    [
        (False, False, report(steps=2), False, None),
        (True, False, report(steps=7, success=True), False, "success"),
        (False, True, report(steps=4), False, "timeout"),
        (False, False, report(steps=4, failure="L-TRAY-TILT"), False, "failure"),
        (False, True, report(steps=4, failure="L-PART-DROP"), False, "failure"),
        (True, False, report(steps=7, success=True), True, "operator_reset"),
        (False, False, None, False, None),
        (False, True, None, False, "timeout"),
    ],
)
def test_episode_outcome(
    terminated: bool,
    truncated: bool,
    rep: StepReport | None,
    reset: bool,
    expected: str | None,
) -> None:
    assert episode_outcome(terminated, truncated, rep, reset) == expected


def test_flywheel_block() -> None:
    block = flywheel_block(
        condition=Condition(1, 7),
        operator="op-02",
        session="s-20261103-a",
        source_detail="teleop_pico",
        outcome="success",
        simple_commit="6d10628",
    )
    assert block["story"] == "DA-35"
    assert block["source_kind"] == "teleop"
    assert (block["level"], block["seed"]) == (1, 7)
    assert block["operator"] == "op-02"
    json.dumps(block)  # goes into environment_config as JSON


def test_flywheel_block_of_a_virtual_teleop_episode() -> None:
    block = flywheel_block(
        condition=Condition(0, 12),
        operator="op-virtual",
        session="s",
        source_detail="virtual_teleop",
        outcome="success",
        simple_commit="6d10628",
        source_kind="synthetic",
        extra={"synthetic_tier": "S1", "action_quality": "planned", "style_seed": 5},
    )
    assert (block["source_kind"], block["synthetic_tier"]) == ("synthetic", "S1")
    assert (block["split"], block["data_class"], block["style_seed"]) == ("train", "public", 5)
    json.dumps(block)


def test_flywheel_block_refuses_unknown_kinds_and_overwrites() -> None:
    kw: dict[str, Any] = dict(
        condition=Condition(0, 0),
        operator="op-virtual",
        session="s",
        source_detail="virtual_teleop",
        outcome="success",
        simple_commit="x",
    )
    with pytest.raises(ValueError, match="source_kind"):
        flywheel_block(**kw, source_kind="human")
    with pytest.raises(ValueError, match="overwrite"):
        flywheel_block(**kw, source_kind="synthetic", extra={"seed": 3})


@pytest.mark.parametrize("operator", ["Hieu", "op-", "op-Hung", "op 01", ""])
def test_operator_must_be_a_pseudonym(operator: str) -> None:
    with pytest.raises(ValueError, match="pseudonym"):
        flywheel_block(
            condition=Condition(0, 0),
            operator=operator,
            session="s",
            source_detail="teleop_pico",
            outcome="success",
            simple_commit="x",
        )


def test_attempt_log_appends(tmp_path: Path) -> None:
    path = tmp_path / "attempts.jsonl"
    log = AttemptLog(path)
    log.append({"attempt": 1, "outcome": "timeout"})
    AttemptLog(path).append({"attempt": 2, "outcome": "success"})
    assert [r["attempt"] for r in AttemptLog(path).read()] == [1, 2]


def test_attempt_log_refuses_non_json_values(tmp_path: Path) -> None:
    log = AttemptLog(tmp_path / "attempts.jsonl")
    with pytest.raises(TypeError):
        log.append({"bad": object()})
    assert log.read() == []

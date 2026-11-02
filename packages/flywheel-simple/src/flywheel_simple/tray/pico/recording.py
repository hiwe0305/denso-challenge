"""What a PICO session adds to SIMPLE's teleop recording of the tray task.

SIMPLE's recorder logs object poses from `mj_objects`, which is empty for the
tray scene (one articulated MJCF), so the tray, its parts and the seven scorer
steps would be missing. S2 needs them per frame to cut demos into steps and to
transform the hands relative to the tray (DA-35 AC 3, 4). Each saved episode
also gets a `flywheel` block in its environment_config, and every attempt, kept
or not, gets one line in an append-only log for the cost ledger.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.pico.conditions import Condition
from flywheel_simple.tray.predicates import STEP_NAMES, StepReport

WRAPPER_VERSION = "da35-pico-1"
STORY = "DA-35"
OPERATOR = re.compile(r"^op-[0-9a-z]+$")  # pseudonym only, never a name

Outcome = Literal["success", "failure", "timeout", "operator_reset", "interrupted"]

_POSE_NAMES = ["pos_x", "pos_y", "pos_z", "quat_w", "quat_x", "quat_y", "quat_z"]
TRAY_FEATURES: dict[str, dict[str, Any]] = {
    "observation.tray_pose": {
        "dtype": "float64",
        "shape": (7,),
        "names": [f"tray.{n}" for n in _POSE_NAMES],
    },
    "observation.part_pos": {
        "dtype": "float64",
        "shape": (18,),
        "names": [f"part_{i}.{axis}" for i in range(6) for axis in "xyz"],
    },
    "observation.tray_steps": {
        "dtype": "float64",
        "shape": (len(STEP_NAMES),),
        "names": list(STEP_NAMES),
    },
}


def tray_frame(
    privileged: Mapping[str, NDArray[np.float64]], report: StepReport | None
) -> dict[str, NDArray[np.float64]]:
    """Tray pose, part positions and reached steps for one frame, as TRAY_FEATURES declares."""
    steps = report.steps if report is not None else (False,) * len(STEP_NAMES)
    return {
        "observation.tray_pose": np.concatenate(
            [privileged["tray_pos"], privileged["tray_quat"]]
        ).astype(np.float64),
        "observation.part_pos": np.asarray(privileged["part_pos"], np.float64).reshape(-1),
        "observation.tray_steps": np.asarray(steps, np.float64),
    }


def episode_outcome(
    terminated: bool, truncated: bool, report: StepReport | None, reset_requested: bool
) -> Outcome | None:
    """How the attempt ends this step, or None if it goes on.

    The operator's reset wins; then success (`terminated` is check_success); then a
    StepTracker failure label, which is final (no success after it); then time out.
    """
    if reset_requested:
        return "operator_reset"
    if terminated:
        return "success"
    if report is not None and report.failure is not None:
        return "failure"
    if truncated:
        return "timeout"
    return None


def flywheel_block(
    *,
    condition: Condition,
    operator: str,
    session: str,
    source_detail: str,
    outcome: Outcome,
    simple_commit: str,
) -> dict[str, Any]:
    """Meta stored as `environment_config["flywheel"]` of a saved episode."""
    if not OPERATOR.match(operator):
        raise ValueError(f"operator {operator!r} must be a pseudonym like op-01")
    return {
        "story": STORY,
        "source_kind": "teleop",
        "source_detail": source_detail,
        "operator": operator,
        "session": session,
        "level": condition.level,
        "seed": condition.seed,
        "outcome": outcome,
        "simple_commit": simple_commit,
        "wrapper_version": WRAPPER_VERSION,
    }


class AttemptLog:
    """Append-only JSON-lines log of every attempt of a session, saved or discarded."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: Mapping[str, Any]) -> None:
        line = json.dumps(dict(record))  # serialise first: a bad record writes nothing
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(line + "\n")

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line]

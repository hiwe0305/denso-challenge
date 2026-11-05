"""A parent demo of S2 as arrays: what the generator reads from a recorded episode (DA-35 AC 4, 5).

Parents are episodes recorded through SIMPLE's PICO pipeline: the virtual
operator's now, a person's at the headset later. Per frame S2 needs

| Field | LeRobot feature | Meaning |
|---|---|---|
| `eef` | `action.eef` | the wrist targets WristsPreProcessor made that step, robot model frame |
| `navigate` | `teleop.navigate_command` | the sticks: vx, vy, vyaw, PICO's integrated target yaw |
| `base_pose` | `observation.base_pose` | pelvis position and quaternion (wxyz), world |
| `tray_pose` | `observation.tray_pose` | tray position and quaternion, world |
| `steps` | `observation.tray_steps` | the seven StepTracker flags |
| `hands_closed` | Dex3 joints of `action` | whether PICO's grasp closed each hand |

A frame holds the state before its step, so the last frame of a successful
episode can miss the seventh flag. Pure numpy apart from `load_parent`, which
reads parquet with pandas (SIMPLE venv).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.predicates import STEP_NAMES

Array = NDArray[np.float64]

# Frames between the operator sending a signal and the recording showing it (measured by
# replaying parents-1103b shard-00 episode 0, DA-35 task 9): a frame shows the wrist targets
# sent that step, the hands and vyaw sent one step and vx, vy and the target yaw sent two
# steps before.
HAND_LEAD = 1
NAV_LEAD = (2, 2, 1, 2)
# PICO closes a Dex3 hand into a fixed grasp, so its joint targets are either all zero
# (open) or a set of large angles (1-1.5 rad on the closing fingers).
HAND_CLOSED_RAD = 0.3
DATASET_ID = "G1WholebodyTrayTransferTeleop-v0"
PALMS_FILE = "s2_palms.npz"  # the parents' palm points by FK (scripts/g0/tray/s2/parent_palms.py)


@dataclass(frozen=True)
class ParentDemo:
    parent_id: str  # "<batch>/<shard>/<episode_index>"
    level: int
    seed: int
    eef: Array  # (T, 14): left pos, quat wxyz, right pos, quat wxyz
    navigate: Array  # (T, 4)
    base_pose: Array  # (T, 7)
    tray_pose: Array  # (T, 7)
    steps: NDArray[np.bool_]  # (T, 7)
    hands_closed: NDArray[np.bool_]  # (T, 2): left, right
    meta: Mapping[str, Any] = field(default_factory=dict)  # the episode's flywheel block
    palms: Array | None = None  # (T, 2, 3): where the palms were (left, right; world)

    def __post_init__(self) -> None:
        n = len(self.eef)
        shapes = {
            "eef": (self.eef, 14),
            "navigate": (self.navigate, 4),
            "base_pose": (self.base_pose, 7),
            "tray_pose": (self.tray_pose, 7),
            "steps": (self.steps, len(STEP_NAMES)),
            "hands_closed": (self.hands_closed, 2),
        }
        for name, (value, width) in shapes.items():
            if value.shape != (n, width):
                raise ValueError(f"{name} has shape {value.shape}, expected ({n}, {width})")
        if self.palms is not None and self.palms.shape != (n, 2, 3):
            raise ValueError(f"palms has shape {self.palms.shape}, expected ({n}, 2, 3)")

    @property
    def frames(self) -> int:
        return len(self.eef)


def hands_closed_from_action(action: Array, names: Sequence[str]) -> NDArray[np.bool_]:
    """(T, 2) closed flags from the Dex3 joint targets in `action` (columns named `names`)."""
    out = []
    for side in ("left", "right"):
        cols = [i for i, n in enumerate(names) if n.startswith(f"{side}_hand_")]
        if not cols:
            raise ValueError(f"action has no {side}_hand_* joints")
        out.append(np.abs(action[:, cols]).max(axis=1) > HAND_CLOSED_RAD)
    return np.stack(out, axis=1)


def episode_flywheel(dataset_root: Path, episode_index: int) -> dict[str, Any]:
    """The flywheel block a session stored in the episode's environment_config."""
    lines = (dataset_root / "meta" / "episodes.jsonl").read_text().splitlines()
    for line in lines:
        entry = json.loads(line)
        if entry["episode_index"] == episode_index:
            block: dict[str, Any] = json.loads(entry["environment_config"])["flywheel"]
            return block
    raise KeyError(f"episode {episode_index} is not in {dataset_root}")


def load_parent(dataset_root: Path, episode_index: int, parent_id: str) -> ParentDemo:
    """One recorded episode of a LeRobot v2.1 dataset written by the PICO session."""
    import pandas  # type: ignore[import-untyped]  # SIMPLE venv only

    info = json.loads((dataset_root / "meta" / "info.json").read_text())
    chunk = episode_index // int(info["chunks_size"])
    path = dataset_root / info["data_path"].format(episode_chunk=chunk, episode_index=episode_index)
    df = pandas.read_parquet(path)

    def column(name: str) -> Array:
        return np.stack(df[name].to_numpy()).astype(np.float64)

    block = episode_flywheel(dataset_root, episode_index)
    return ParentDemo(
        parent_id=parent_id,
        level=int(block["level"]),
        seed=int(block["seed"]),
        eef=column("action.eef"),
        navigate=column("teleop.navigate_command"),
        base_pose=column("observation.base_pose"),
        tray_pose=column("observation.tray_pose"),
        steps=column("observation.tray_steps") > 0.5,
        hands_closed=hands_closed_from_action(
            column("action"), info["features"]["action"]["names"]
        ),
        meta=block,
    )


def palms_key(parent_id: str) -> str:
    return parent_id.replace("/", "__")


def load_palms(batch: Path) -> dict[str, Array]:
    """The palm arrays of a batch by parent id; empty when parent_palms.py has not run."""
    path = batch / PALMS_FILE
    if not path.exists():
        return {}
    with np.load(path) as archive:
        return {key.replace("__", "/"): archive[key] for key in archive.files}


def parent_dataset(batch: Path, shard: str) -> Path:
    """Where generate_parents.py put a shard's LeRobot dataset."""
    return batch / shard / "simple" / DATASET_ID

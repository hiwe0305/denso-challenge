"""Small EgoDex-like episodes written in the test, with a known grasp and release.

The camera sits at the world origin looking down +z (EgoDex's camera frame is
OpenCV-like). The right wrist starts still, reaches for 30 frames, dwells at GRASP
while thumb and index close from 8 to 3 cm, carries for 40 frames, dwells at RELEASE
while they open again, then goes back and rests. The left hand does not move.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from flywheel.data.ingest.egocentric.egodex import FINGERS, tip_joint, wrist_joint
from flywheel.data.ingest.egocentric.pose import EgoPose
from numpy.typing import NDArray

FRAMES = 150
GRASP = (40, 50)  # dwell, half-open
RELEASE = (90, 100)
K = np.array([[736.6339, 0, 960.0], [0, 736.6339, 540.0], [0, 0, 1]], dtype=np.float32)
REPO = Path(__file__).resolve().parents[5]
CONFIG = REPO / "configs" / "data" / "egocentric.yaml"


def right_wrist_track(frames: int = FRAMES) -> NDArray[np.float64]:
    """x of the right wrist per frame: rest, reach, dwell, carry, dwell, back, rest."""
    x = np.zeros(frames)
    keys = [(0, 0.0), (10, 0.0), (GRASP[0], -0.15), (GRASP[1], -0.15), (RELEASE[0], 0.15),
            (RELEASE[1], 0.15), (130, 0.0), (frames - 1, 0.0)]
    for (f0, x0), (f1, x1) in zip(keys, keys[1:]):
        x[f0:f1 + 1] = np.linspace(x0, x1, f1 - f0 + 1)
    return x


def aperture_track(frames: int = FRAMES) -> NDArray[np.float64]:
    a = np.full(frames, 0.08)
    a[GRASP[0]:GRASP[1]] = np.linspace(0.08, 0.03, GRASP[1] - GRASP[0])
    a[GRASP[1]:RELEASE[0]] = 0.03
    a[RELEASE[0]:RELEASE[1]] = np.linspace(0.03, 0.08, RELEASE[1] - RELEASE[0])
    return a


def transforms(frames: int = FRAMES) -> dict[str, NDArray[np.float32]]:
    """World poses of the camera, both wrists and all tips."""
    out: dict[str, NDArray[np.float32]] = {}
    eye = np.tile(np.eye(4), (frames, 1, 1))
    out["camera"] = eye.astype(np.float32)
    x = right_wrist_track(frames)
    a = aperture_track(frames)
    for side, base in (("right", x), ("left", np.full(frames, -0.25))):
        wrist = eye.copy()
        wrist[:, 0, 3], wrist[:, 1, 3], wrist[:, 2, 3] = base, 0.1, 0.4
        out[wrist_joint(side)] = wrist.astype(np.float32)
        for i, finger in enumerate(FINGERS):
            tip = wrist.copy()
            tip[:, 1, 3] = 0.05
            tip[:, 0, 3] = base + (a / 2 if i == 0 else -a / 2 if i == 1 else 0.01 * i)
            out[tip_joint(side, finger)] = tip.astype(np.float32)
    return out


def write_hdf5(path: Path, *, frames: int = FRAMES, confidences: bool = True,
               attrs: dict[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as f:
        for name, value in transforms(frames).items():
            f[f"transforms/{name}"] = value
            if confidences and name != "camera":
                f[f"confidences/{name}"] = np.full(frames, 0.9, dtype=np.float32)
        f["camera/intrinsic"] = K
        f.attrs.update(attrs or {"llm_description": "Pick up the cup and place it on the plate.",
                                 "llm_objects": ["cup"], "task": path.parent.name,
                                 "llm_type": "reset"})


def write_mp4(path: Path, frames: int = FRAMES, size: tuple[int, int] = (64, 36),
              fps: float = 30.0) -> None:
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    rng = np.random.default_rng(0)
    for i in range(frames):
        image = rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)
        image[:, : i % size[0]] = 40
        writer.write(image)
    writer.release()


def make_egodex(store: Path, tasks: Sequence[str] = ("basic_pick_place", "stack_cups"),
                per_task: int = 3, frames: int = FRAMES) -> Path:
    """An EgoDex-like sample under `store/egodex/part1/<task>/<i>.{hdf5,mp4}`."""
    root = store / "egodex" / "part1"
    for task in tasks:
        for i in range(per_task):
            write_hdf5(root / task / f"{i}.hdf5", frames=frames)
            write_mp4(root / task / f"{i}.mp4", frames)
    return store / "egodex"


def config_for(tmp: Path, tasks: Sequence[str] = ("basic_pick_place", "stack_cups"),
               per_task: int = 2, edit: dict[str, Any] | None = None) -> Path:
    """The repo's egocentric.yaml with the EgoDex subset pointed at the test store."""
    import yaml

    data = yaml.safe_load(CONFIG.read_text())
    egodex = data["sources"]["egodex"]
    egodex.update({"root": "egodex", "tasks": list(tasks), "episodes_per_task": per_task})
    for key, value in (edit or {}).items():
        section, name = key.split(".", 1)
        data[section][name] = value
    path = tmp / "egocentric.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def make_videos(root: Path, frames: int = 60) -> Path:
    """A recording root as the team would hand it over: device.json and one mp4."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "device.json").write_text(json.dumps({
        "device": "test-phone", "fps": 30, "width": 64, "height": 36,
        "intrinsic": [[50.0, 0, 32.0], [0, 50.0, 18.0], [0, 0, 1]],
        "tasks": {"two_table": "pick the cup and place it on the other table"},
        "objects": ["cup"],
    }))
    write_mp4(root / "two_table" / "0.mp4", frames)
    return root


def synthetic_pose(frames: int = FRAMES) -> EgoPose:
    t = transforms(frames)
    values: dict[str, NDArray[np.float32]] = {"camera": t["camera"]}
    for side in ("left", "right"):
        values[f"{side}_wrist"] = t[wrist_joint(side)]
        values[f"{side}_tips"] = np.stack(
            [t[tip_joint(side, f)][:, :3, 3] for f in FINGERS], axis=1)
        values[f"confidence_{side}"] = np.full(frames, 0.9, dtype=np.float32)
    return EgoPose(**values)

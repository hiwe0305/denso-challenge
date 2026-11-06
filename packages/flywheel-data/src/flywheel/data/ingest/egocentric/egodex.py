"""Read one EgoDex episode: Apple Vision Pro tracking in HDF5 next to its mp4.

An EgoDex HDF5 holds, at 30 Hz, `transforms/<joint>` (T, 4, 4) poses in ARKit's world
frame (y up, metres), `confidences/<joint>` (T,) in [0, 1], `transforms/camera` and
`camera/intrinsic` (3, 3) of the 1920x1080 video. In the camera's own frame, which
`inv(camera) @ p` gives, x points right, y down and z forward, as in OpenCV: a point
projects to `K @ p / z` (checked by drawing tracked wrists on frames, 6/11/2026).

Attributes describe the episode: `llm_description` and, when `which_llm_description`
is 2, `llm_description2` is the one to use; `description` is the annotator's own
sentence; `llm_objects` names the objects. Only these are read here; `actions_48d`,
which DA-30's H-RDT step adds, is ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

FPS = 30.0
IMAGE_SIZE = (1920, 1080)  # width, height of the EgoDex video
FINGERS = ("Thumb", "IndexFinger", "MiddleFinger", "RingFinger", "LittleFinger")
NO_TEXT = ("", "None", "none")


@dataclass(frozen=True)
class EgoDexMeta:
    frames: int
    instruction: str
    objects: tuple[str, ...]
    task: str
    llm_type: str
    intrinsic: NDArray[np.float32]  # (3, 3)


def tip_joint(side: str, finger: str) -> str:
    return f"{side}{finger}Tip"


def wrist_joint(side: str) -> str:
    return f"{side}Hand"


def read_meta(path: Path) -> EgoDexMeta:
    h5py = _h5py()
    with h5py.File(path, "r") as f:
        attrs = dict(f.attrs)
        return EgoDexMeta(
            frames=int(f["transforms/camera"].shape[0]),
            instruction=instruction_of(attrs),
            objects=tuple(str(o) for o in attrs.get("llm_objects", ())),
            task=_text(attrs.get("task")) or path.parent.name,
            llm_type=_text(attrs.get("llm_type")),
            intrinsic=np.asarray(f["camera/intrinsic"][()], dtype=np.float32),
        )


def instruction_of(attrs: dict[str, Any]) -> str:
    """The episode's sentence: the LLM one EgoDex says to use, else the annotator's."""
    first = _text(attrs.get("llm_description"))
    second = _text(attrs.get("llm_description2"))
    if _text(attrs.get("which_llm_description")) == "2" and second not in NO_TEXT:
        return second
    if first not in NO_TEXT:
        return first
    return _text(attrs.get("description"))


def read_transforms(path: Path, joints: list[str]) -> dict[str, NDArray[np.float32]]:
    h5py = _h5py()
    with h5py.File(path, "r") as f:
        return {j: np.asarray(f[f"transforms/{j}"][()], dtype=np.float32) for j in joints}


def read_confidences(path: Path, joints: list[str]) -> dict[str, NDArray[np.float32]]:
    """Confidence per joint; a joint without one is left out. The camera never has one,
    and 11 of the 218 files of DA-30's sample have no `confidences` group at all."""
    h5py = _h5py()
    with h5py.File(path, "r") as f:
        if "confidences" not in f:
            return {}
        return {j: np.asarray(f[f"confidences/{j}"][()], dtype=np.float32)
                for j in joints if j in f["confidences"]}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode()
    return str(value).strip()


def _h5py() -> Any:
    import h5py  # egocentric extra; loaded only by the readers that need it

    return h5py

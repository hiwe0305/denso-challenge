"""Helpers of the Human-1M view tests: a fake encoder and the EgoDex joints the small
sample of ego_data lacks (DA-04, 11/11/2026)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from flywheel.data.export.human1m.layout import arkit_joints
from flywheel.data.export.human1m.video import Encoded, VideoSettings


def _frames(path: Path, limit: int | None = None) -> list[np.ndarray]:  # type: ignore[type-arg]
    capture = _cv2().VideoCapture(str(path))
    out = []
    while limit is None or len(out) < limit:
        ok, image = capture.read()
        if not ok:
            break
        out.append(image)
    return out


def _write(path: Path, images: Sequence[np.ndarray]) -> None:  # type: ignore[type-arg]
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w = images[0].shape[:2]
    writer = _cv2().VideoWriter(str(path), _cv2().VideoWriter_fourcc(*"mp4v"), 30.0, (w, h))
    for image in images:
        writer.write(image)
    writer.release()


class FakeEncoder:
    """The Encoder protocol with OpenCV's mp4v: same frames, no scaling."""

    def encode(self, src: Path, dst: Path, frames: int, settings: VideoSettings) -> Encoded:
        images = _frames(src, frames)
        _write(dst, images)
        h, w = images[0].shape[:2]
        return Encoded(dst, len(images), w, h, codec="mpeg4")

    def concat(self, parts: Sequence[Path], dst: Path) -> None:
        _write(dst, [image for p in parts for image in _frames(p)])

    def poster(self, src: Path, dst: Path, frame: int, fps: float) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        _cv2().imwrite(str(dst), _frames(src, frame + 1)[-1])


def add_hand_joints(sample: Path) -> None:
    """The test sample has wrists and tips only; add the other EgoDex joints."""
    for path in sorted(sample.rglob("*.hdf5")):
        with h5py.File(path, "a") as f:
            for side in ("left", "right"):
                wrist = f[f"transforms/{side}Hand"][()]
                for j, name in enumerate(arkit_joints(side)):
                    if f"transforms/{name}" not in f:
                        pose = wrist.copy()
                        pose[:, 0, 3] += 0.004 * j
                        pose[:, 1, 3] -= 0.002 * j
                        f[f"transforms/{name}"] = pose
                        f[f"confidences/{name}"] = np.full(len(pose), 0.9, np.float32)




def _cv2() -> Any:
    import cv2  # egocentric extra

    return cv2

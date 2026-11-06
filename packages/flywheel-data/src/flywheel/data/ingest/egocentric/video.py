"""Frames of an egocentric mp4, through OpenCV (egocentric extra, loaded only here)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray


def frame_count(mp4: Path) -> int:
    """Frames the mp4 header declares; 0 when it cannot be opened."""
    cv2 = _cv2()
    capture = cv2.VideoCapture(str(mp4))
    try:
        return int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) if capture.isOpened() else 0
    finally:
        capture.release()


def read_frames(
    mp4: Path, indices: Sequence[int], max_side: int | None = None
) -> list[NDArray[np.uint8]]:
    """The frames at `indices` (BGR), downscaled so the longer side is at most `max_side`."""
    cv2 = _cv2()
    capture = cv2.VideoCapture(str(mp4))
    if not capture.isOpened():
        raise ValueError(f"{mp4}: cannot open")
    frames = []
    try:
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok, image = capture.read()
            if not ok:
                raise ValueError(f"{mp4}: no frame {index}")
            frames.append(_fit(image, max_side))
    finally:
        capture.release()
    return frames


def jpeg(image: NDArray[np.uint8], quality: int = 85) -> bytes:
    cv2 = _cv2()
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("JPEG encoding failed")
    return bytes(data.tobytes())


def _fit(image: NDArray[np.uint8], max_side: int | None) -> NDArray[np.uint8]:
    if max_side is None or max(image.shape[:2]) <= max_side:
        return image
    cv2 = _cv2()
    scale = max_side / max(image.shape[:2])
    size = (round(image.shape[1] * scale), round(image.shape[0] * scale))
    return np.asarray(cv2.resize(image, size, interpolation=cv2.INTER_AREA), dtype=np.uint8)


def _cv2() -> Any:
    import cv2  # egocentric extra

    return cv2

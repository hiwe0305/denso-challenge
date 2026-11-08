"""Blur the faces of an egocentric video on this machine (DA-04 subtask 8; AC 2, NFR13).

The team's recordings are `internal`: no frame goes to a hosted API. The face detector
is YuNet from the OpenCV Zoo (MIT licence, 230 KB ONNX), run by OpenCV's
`FaceDetectorYN` on the CPU; OpenCV is already the egocentric extra, so nothing joins
`uv.lock` (as MediaPipe stays out of it, D5). The model file lives under the store, out
of git, and is refused unless its sha256 is the one in `configs/data/egocentric.yaml`.

A video goes through two passes:

1. decode every frame and detect faces on a copy scaled to `detect_side_px`; each box
   is grown by `pad` of its size on every side;
2. decode again and cover, in each frame, every box detected within `hold_frames`
   frames before or after it (a detector misses a face for a frame or two when it
   turns or blurs with motion), with a mosaic of `mosaic_cells` cells across the box's
   longer side, smoothed. The mosaic drops the detail a sharpening filter would need.

The copy is written as mp4v at the source's fps and size, whole or not at all (a
temporary file swapped in at the end). OpenCV writes no audio track, so voices are
gone too. The frame count is checked against the first pass.

Not covered yet: name badges, screens and documents (AC 2 names them); see
docs/g0/egocentric.md section 3.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

Box = tuple[int, int, int, int]  # x, y, w, h in pixels of the full frame
Frame = NDArray[np.uint8]
FOURCC = "mp4v"
CHUNK = 1 << 20


@dataclass(frozen=True)
class BlurParams:
    """`deid` of configs/data/egocentric.yaml, without the model's identity."""

    score_threshold: float
    nms_threshold: float
    detect_side_px: int
    pad: float
    hold_frames: int
    mosaic_cells: int


class FaceDetector(Protocol):
    """Faces of one BGR frame, as boxes in that frame's pixels."""

    def detect(self, frame: Frame) -> list[Box]: ...


@dataclass(frozen=True)
class DeidVideo:
    """What blurring one video did; `source.json` keeps it per video."""

    frames: int
    fps: float
    width: int
    height: int
    frames_with_faces: int  # frames where the detector found at least one face
    frames_blurred: int  # frames with at least one box covered, holds included
    detections: int
    seconds: float


class YuNet:
    """OpenCV's FaceDetectorYN with the pinned YuNet ONNX file."""

    def __init__(self, model: Path, sha256: str, params: BlurParams) -> None:
        if not model.is_file():
            raise FileNotFoundError(f"{model}: the YuNet face model is not there")
        digest = file_sha256(model)
        if digest != sha256:
            raise ValueError(f"{model}: sha256 {digest} is not the pinned {sha256}")
        self.cv2 = _cv2()
        self.params = params
        self.size = (0, 0)
        self.model = self.cv2.FaceDetectorYN.create(
            str(model), "", (320, 320), params.score_threshold, params.nms_threshold, 5000)

    def detect(self, frame: Frame) -> list[Box]:
        height, width = frame.shape[:2]
        scale = min(1.0, self.params.detect_side_px / max(width, height))
        image = frame if scale == 1.0 else self.cv2.resize(
            frame, (round(width * scale), round(height * scale)),
            interpolation=self.cv2.INTER_AREA)
        size = (image.shape[1], image.shape[0])
        if size != self.size:
            self.model.setInputSize(size)
            self.size = size
        _, faces = self.model.detect(image)
        if faces is None:
            return []
        boxes: list[Box] = []
        for face in faces:
            x, y, w, h = (round(float(v) / scale) for v in face[:4])
            boxes.append((x, y, w, h))
        return boxes


def pad_box(box: Box, pad: float, width: int, height: int) -> Box | None:
    """`box` grown by `pad` of its size on each side, clipped to the frame; None if empty."""
    x, y, w, h = box
    x0, y0 = max(0, round(x - pad * w)), max(0, round(y - pad * h))
    x1, y1 = min(width, round(x + w + pad * w)), min(height, round(y + h + pad * h))
    return (x0, y0, x1 - x0, y1 - y0) if x1 > x0 and y1 > y0 else None


def held_boxes(detections: Sequence[Sequence[Box]], hold: int) -> list[list[Box]]:
    """The boxes to cover in each frame: those detected within `hold` frames of it."""
    frames = len(detections)
    held: list[list[Box]] = [[] for _ in range(frames)]
    for index, boxes in enumerate(detections):
        for target in range(max(0, index - hold), min(frames, index + hold + 1)):
            held[target].extend(boxes)
    return held


def mosaic(frame: Frame, boxes: Sequence[Box], cells: int) -> Frame:
    """A copy of `frame` with each box replaced by a smoothed mosaic of `cells` cells
    across its longer side."""
    cv2 = _cv2()
    out = frame.copy()
    for x, y, w, h in boxes:
        roi = out[y:y + h, x:x + w]
        if roi.size == 0:
            continue
        step = max(w, h) / cells
        small = cv2.resize(roi, (max(1, round(w / step)), max(1, round(h / step))),
                           interpolation=cv2.INTER_AREA)
        out[y:y + h, x:x + w] = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    return np.asarray(out, dtype=np.uint8)


def deid_video(raw: Path, out: Path, detector: FaceDetector, params: BlurParams) -> DeidVideo:
    """Write `out`, `raw` with its faces covered; the two passes are in the module doc."""
    cv2 = _cv2()
    start = time.monotonic()
    detections: list[list[Box]] = []
    capture = _open(raw)
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS)) or 30.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            height, width = frame.shape[:2]  # after OpenCV applied the rotation tag
            padded = (pad_box(b, params.pad, width, height) for b in detector.detect(frame))
            detections.append([b for b in padded if b is not None])
    finally:
        capture.release()
    if not detections:
        raise ValueError(f"{raw}: no frame could be decoded")
    held = held_boxes(detections, params.hold_frames)
    temporary = out.with_name(f".{out.stem}.{os.getpid()}.tmp{out.suffix}")
    written = 0
    try:
        writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*FOURCC), fps,
                                 (width, height))
        if not writer.isOpened():
            raise OSError(f"{temporary}: OpenCV cannot write {FOURCC}")
        capture = _open(raw)
        try:
            for boxes in held:
                ok, frame = capture.read()
                if not ok:
                    break
                writer.write(mosaic(frame, boxes, params.mosaic_cells) if boxes else frame)
                written += 1
        finally:
            capture.release()
            writer.release()
        if written != len(held):
            raise ValueError(f"{raw}: {len(held)} frames on the first pass, {written} on the"
                             " second")
        os.replace(temporary, out)
    finally:
        temporary.unlink(missing_ok=True)
    return DeidVideo(
        frames=written, fps=fps, width=width, height=height,
        frames_with_faces=sum(bool(d) for d in detections),
        frames_blurred=sum(bool(h) for h in held),
        detections=sum(len(d) for d in detections),
        seconds=round(time.monotonic() - start, 2),
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _open(path: Path) -> Any:
    capture = _cv2().VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"{path}: OpenCV cannot open it")
    return capture


def _cv2() -> Any:
    import cv2  # egocentric extra

    return cv2

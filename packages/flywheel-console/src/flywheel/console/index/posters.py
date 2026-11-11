"""Poster and filmstrip JPEGs cut from episode videos (cv2 only, no network)."""

from __future__ import annotations

from multiprocessing import Pool
from pathlib import Path

import cv2

POOL_MIN = 50
POOL_SIZE = 6


def _read_frame(cap: cv2.VideoCapture, pos: int) -> cv2.typing.MatLike | None:
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, pos))
    ok, frame = cap.read()
    return frame if ok else None


def _open(video: Path) -> tuple[cv2.VideoCapture, int]:
    if not video.is_file():
        raise FileNotFoundError(video)
    cap = cv2.VideoCapture(str(video))
    return cap, int(cap.get(cv2.CAP_PROP_FRAME_COUNT))


def _encode(img: cv2.typing.MatLike) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if not ok:
        raise ValueError("jpeg encode failed")
    return bytes(buf.tobytes())


def poster_jpeg(video: Path, width: int = 320) -> bytes:
    """JPEG (q70) of the middle frame, scaled to ``width``."""
    cap, n = _open(video)
    try:
        frame = _read_frame(cap, n // 2)
    finally:
        cap.release()
    if frame is None:
        raise ValueError(f"unreadable video: {video}")
    h, w = frame.shape[:2]
    return _encode(cv2.resize(frame, (width, max(1, int(width * h / w)))))


def strip_jpeg(video: Path, n: int = 8, height: int = 72) -> bytes:
    """Horizontal strip of ``n`` evenly spaced frames, each ``height`` px tall."""
    cap, total = _open(video)
    tiles = []
    try:
        for k in range(n):
            frame = _read_frame(cap, int((k + 0.5) * total / n))
            if frame is None:
                continue
            h, w = frame.shape[:2]
            tiles.append(cv2.resize(frame, (max(1, int(height * w / h)), height)))
    finally:
        cap.release()
    if not tiles:
        raise ValueError(f"unreadable video: {video}")
    return _encode(cv2.hconcat(tiles))


def _job(job: tuple[Path, Path, int]) -> int:
    video, dst, width = job
    if dst.exists():
        return 0
    try:
        data = poster_jpeg(video, width)
    except (FileNotFoundError, ValueError):
        return -1
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    return 1


def write_posters(jobs: list[tuple[Path, Path]], width: int = 320) -> dict[str, int]:
    """Write ``(video, dst)`` posters; existing files are kept. Pool(6) above 50 jobs."""
    args = [(v, d, width) for v, d in jobs]
    if len(args) > POOL_MIN:
        with Pool(POOL_SIZE) as pool:
            res = pool.map(_job, args, chunksize=8)
    else:
        res = [_job(a) for a in args]
    return {"made": res.count(1), "kept": res.count(0), "failed": res.count(-1)}

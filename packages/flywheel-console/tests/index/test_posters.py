from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from conftest import FRAMES, H, W, write_mp4
from flywheel.console.index.posters import poster_jpeg, strip_jpeg, write_posters


def _decode(b: bytes) -> tuple[int, int]:
    img = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
    assert img is not None
    return img.shape[1], img.shape[0]


def test_poster_jpeg_width(tmp_path: Path) -> None:
    v = write_mp4(tmp_path / "v.mp4")
    data = poster_jpeg(v, 32)
    assert data[:2] == b"\xff\xd8"
    assert _decode(data) == (32, 24)
    assert _decode(poster_jpeg(v))[0] == 320


def test_strip_jpeg_frame_count(tmp_path: Path) -> None:
    v = write_mp4(tmp_path / "v.mp4")
    w, h = _decode(strip_jpeg(v, n=5, height=24))
    assert h == 24
    assert w == 5 * int(24 * W / H)
    assert FRAMES >= 5


def test_missing_video_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        poster_jpeg(tmp_path / "nope.mp4")
    with pytest.raises(FileNotFoundError):
        strip_jpeg(tmp_path / "nope.mp4")


def test_write_posters_keeps_existing_and_counts_failures(tmp_path: Path) -> None:
    v = write_mp4(tmp_path / "v.mp4")
    r = write_posters(
        [(v, tmp_path / "o" / "1.jpg"), (tmp_path / "x.mp4", tmp_path / "o" / "2.jpg")]
    )
    assert r == {"made": 1, "kept": 0, "failed": 1}
    assert write_posters([(v, tmp_path / "o" / "1.jpg")])["kept"] == 1

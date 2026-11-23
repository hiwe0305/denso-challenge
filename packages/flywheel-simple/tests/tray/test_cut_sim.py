"""trim_video on a real mp4 through PyAV (DA-46 task 3); needs `av`, no simulator.

    PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python -m pytest \
        packages/flywheel-simple/tests/tray/test_cut_sim.py -m sim
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from flywheel_simple.tray.cut import trim_video
from flywheel_simple.tray.recorder import JoinedVideoWriter

pytestmark = pytest.mark.sim

W, H, FRAMES = 64, 48, 60


def _grey(k: int) -> int:
    return 20 + 3 * k  # 20 .. 197, a distinct level per frame


def _source(path: Path) -> Path:
    writer = JoinedVideoWriter(path, W, H, 50)
    for k in range(FRAMES):
        writer.add_frame(np.full((H, W, 3), _grey(k), dtype=np.uint8))
    writer.stop()
    return path


def _decode(path: Path) -> tuple[list[float], int, str, int, int]:
    av = pytest.importorskip("av")
    with av.open(str(path)) as c:
        s = c.streams.video[0]
        means = [float(f.to_ndarray(format="rgb24").mean()) for f in c.decode(s)]
        return means, int(s.average_rate), s.codec_context.pix_fmt, s.width, s.height


def test_trim_keeps_the_frames_from_start(tmp_path: Path) -> None:
    pytest.importorskip("av")
    src = _source(tmp_path / "src.mp4")
    dst = tmp_path / "out" / "dst.mp4"
    trim_video(src, dst, 20, FRAMES - 20, 50)
    means, fps, pix_fmt, w, h = _decode(dst)
    src_means, _, src_pix_fmt, _, _ = _decode(src)
    assert len(means) == FRAMES - 20
    assert (fps, pix_fmt, w, h) == (50, src_pix_fmt, W, H)
    assert abs(means[0] - src_means[20]) < 2.0
    assert abs(means[0] - _grey(20)) < 3.0
    assert abs(means[-1] - _grey(FRAMES - 1)) < 3.0


def test_trim_with_a_wrong_count_fails_and_leaves_nothing(tmp_path: Path) -> None:
    pytest.importorskip("av")
    src = _source(tmp_path / "src.mp4")
    dst = tmp_path / "dst.mp4"
    with pytest.raises(ValueError, match="expected 41"):
        trim_video(src, dst, 20, 41, 50)
    assert not dst.exists()

"""JoinedVideoWriter: the recorder's video writer never flushes during an encode (DA-33).

decoupled_wbc's VideoWriter flushed and closed the encoder while its worker could
still be encoding (3/3 SIGSEGV in scripts/g0/tray/video_writer_race.py). Needs PyAV,
which is in the SIMPLE venv:

    PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m pytest packages/flywheel-simple/tests/tray/test_video_writer.py -m sim -v
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytestmark = pytest.mark.sim
av = pytest.importorskip("av")

WIDTH, HEIGHT, FPS = 160, 120, 50


class CountingStream:
    """PyAV stream proxy counting `encode` calls that overlap another one."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._lock = threading.Lock()
        self._in_flight = 0
        self.overlaps = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    def encode(self, frame: Any = None) -> Any:
        with self._lock:
            self.overlaps += self._in_flight > 0
            self._in_flight += 1
        try:
            return self._stream.encode(frame)
        finally:
            with self._lock:
                self._in_flight -= 1


def frames(n: int) -> list[np.ndarray]:
    rng = np.random.default_rng(0)
    return [rng.integers(0, 255, (HEIGHT, WIDTH, 3), dtype=np.uint8) for _ in range(n)]


def decoded_frames(path: str) -> int:
    with av.open(path) as container:
        return sum(1 for _ in container.decode(video=0))


def test_stop_encodes_every_frame_and_never_overlaps_an_encode(tmp_path: Path) -> None:
    from flywheel_simple.tray.recorder import JoinedVideoWriter

    video = frames(30)
    for i in range(20):
        writer = JoinedVideoWriter(tmp_path / f"v{i}.mp4", WIDTH, HEIGHT, FPS)
        writer.stream = CountingStream(writer.stream)
        for frame in video:
            writer.add_frame(frame)
        path = writer.stop()
        assert writer.stream.overlaps == 0
        assert not writer._thread.is_alive()
        assert decoded_frames(path) == len(video)


def test_cancel_deletes_the_video(tmp_path: Path) -> None:
    from flywheel_simple.tray.recorder import JoinedVideoWriter

    writer = JoinedVideoWriter(tmp_path / "v.mp4", WIDTH, HEIGHT, FPS)
    for frame in frames(5):
        writer.add_frame(frame)
    writer.cancel()
    assert not (tmp_path / "v.mp4").exists()
    assert not writer._thread.is_alive()


def test_an_encoding_error_is_raised_by_stop_without_blocking_add_frame(tmp_path: Path) -> None:
    from flywheel_simple.tray.recorder import JoinedVideoWriter

    class Failing:
        def __init__(self, stream: Any) -> None:
            self._stream = stream

        def __getattr__(self, name: str) -> Any:
            return getattr(self._stream, name)

        def encode(self, frame: Any = None) -> Any:
            raise OSError("x264 failed")

    writer = JoinedVideoWriter(tmp_path / "v.mp4", WIDTH, HEIGHT, FPS, buffer_size=4)
    writer.stream = Failing(writer.stream)
    for frame in frames(20):  # more than the queue holds: the worker keeps draining
        writer.add_frame(frame)
    with pytest.raises(RuntimeError, match="encoding") as error:
        writer.stop()
    assert isinstance(error.value.__cause__, OSError)


def test_add_frame_rejects_a_frame_of_the_wrong_size(tmp_path: Path) -> None:
    from flywheel_simple.tray.recorder import JoinedVideoWriter

    writer = JoinedVideoWriter(tmp_path / "v.mp4", WIDTH, HEIGHT, FPS)
    with pytest.raises(ValueError, match="frame"):
        writer.add_frame(np.zeros((HEIGHT + 2, WIDTH, 3), np.uint8))
    writer.cancel()

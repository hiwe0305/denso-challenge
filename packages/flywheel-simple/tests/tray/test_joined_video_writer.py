"""JoinedVideoWriter joins its worker before the flush, on CPU with a fake PyAV (DA-33).

decoupled_wbc's VideoWriter waited only for `queue.empty()` and then flushed from
the caller's thread while its worker could still be inside `encode` of the same
libx264 context (scripts/g0/tray/video_writer_race.py: 3/3 SIGSEGV, one 14 h hang).
A fake `av` whose `encode` is slow makes that window wide; the encoder records
every overlapping call and whether the worker was still alive at the flush.
test_video_writer.py runs the same writer on real PyAV in the SIMPLE venv.
"""

from __future__ import annotations

import sys
import threading
import time
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

WIDTH, HEIGHT, FPS = 8, 6, 50
ENCODE_S = 0.005


class FakeStream:
    def __init__(self) -> None:
        self.width = 0
        self.height = 0
        self.lock = threading.Lock()
        self.in_flight = 0
        self.overlaps = 0
        self.frames = 0
        self.flushes = 0
        self.worker_alive_at_flush: bool | None = None
        self.writer: Any = None

    def encode(self, frame: Any = None) -> list[str]:
        with self.lock:
            self.overlaps += self.in_flight > 0
            self.in_flight += 1
        try:
            if frame is None:
                self.flushes += 1
                self.worker_alive_at_flush = self.writer._thread.is_alive()
                return ["flush"]
            time.sleep(ENCODE_S)
            self.frames += 1
            return ["packet"]
        finally:
            with self.lock:
                self.in_flight -= 1


class FakeContainer:
    def __init__(self, path: str) -> None:
        self.path = path
        self.stream = FakeStream()
        self.packets = 0
        self.closed = False
        Path(path).write_bytes(b"")

    def add_stream(self, codec: str, rate: float) -> FakeStream:
        return self.stream

    def mux(self, packet: str) -> None:
        assert not self.closed, "mux after close"
        self.packets += 1

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_av(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.ModuleType]:
    av = types.ModuleType("av")
    av.open = lambda path, mode: FakeContainer(path)  # type: ignore[attr-defined]
    av.VideoFrame = types.SimpleNamespace(  # type: ignore[attr-defined]
        from_ndarray=lambda frame, format: frame
    )
    monkeypatch.setitem(sys.modules, "av", av)
    yield av


def writer(path: Path, **kwargs: Any) -> Any:
    from flywheel_simple.tray.recorder import JoinedVideoWriter

    w = JoinedVideoWriter(path, WIDTH, HEIGHT, FPS, **kwargs)
    w.stream.writer = w
    return w


FRAME = np.zeros((HEIGHT, WIDTH, 3), np.uint8)


def test_stop_joins_the_worker_before_the_flush(fake_av: Any, tmp_path: Path) -> None:
    for i in range(20):
        w = writer(tmp_path / f"v{i}.mp4")
        for _ in range(10):
            w.add_frame(FRAME)
        assert w.stop() == str(tmp_path / f"v{i}.mp4")
        stream = w.stream
        assert stream.overlaps == 0
        assert stream.worker_alive_at_flush is False
        assert (stream.frames, stream.flushes) == (10, 1)
        assert w.container.closed and w.container.packets == 11
        assert not w._thread.is_alive()


def test_the_old_queue_empty_stop_overlaps_the_last_encode(fake_av: Any, tmp_path: Path) -> None:
    # VideoWriter.stop of decoupled_wbc: poll queue.empty(), then flush. The fake must
    # catch it, or the test above would pass for the wrong reason.
    def queue_empty_stop(w: Any) -> None:
        while not w.queue.empty():
            time.sleep(0.001)
        w._encode(None)

    caught = 0
    for i in range(5):
        w = writer(tmp_path / f"v{i}.mp4")
        for _ in range(10):
            w.add_frame(FRAME)
        queue_empty_stop(w)
        caught += w.stream.worker_alive_at_flush and w.stream.overlaps > 0
        w._join()
    assert caught >= 1


def test_cancel_joins_and_deletes_the_video(fake_av: Any, tmp_path: Path) -> None:
    w = writer(tmp_path / "v.mp4")
    for _ in range(5):
        w.add_frame(FRAME)
    w.cancel()
    assert not (tmp_path / "v.mp4").exists()
    assert not w._thread.is_alive() and w.container.closed
    assert w.stream.flushes == 0


def test_an_encoding_error_is_raised_by_stop(fake_av: Any, tmp_path: Path) -> None:
    w = writer(tmp_path / "v.mp4", buffer_size=2)

    def fail(frame: Any = None) -> list[str]:
        raise OSError("x264 failed")

    w.stream.encode = fail
    for _ in range(10):  # more than the queue holds: the worker keeps draining it
        w.add_frame(FRAME)
    with pytest.raises(RuntimeError, match="encoding") as error:
        w.stop()
    assert isinstance(error.value.__cause__, OSError)
    assert w.container.closed


def test_add_frame_rejects_a_frame_of_the_wrong_size(fake_av: Any, tmp_path: Path) -> None:
    w = writer(tmp_path / "v.mp4")
    with pytest.raises(ValueError, match="frame"):
        w.add_frame(np.zeros((HEIGHT + 1, WIDTH, 3), np.uint8))
    w.cancel()


def test_the_recorder_opens_an_exporter_that_writes_through_joined_writers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The fix lives in EpisodeRecorder._open: a plain Gr00tDataExporter would bring
    # back decoupled_wbc's VideoWriter and its flush race.
    from flywheel_simple.tray import recorder

    class FakeExporter:
        kwargs: dict[str, Any]

        @classmethod
        def create(cls, **kwargs: Any) -> Any:
            made = cls.__new__(cls)
            made.kwargs = kwargs
            return made

    fakes = {
        "decoupled_wbc.data.exporter": types.SimpleNamespace(Gr00tDataExporter=FakeExporter),
        "decoupled_wbc.data.utils": types.SimpleNamespace(
            get_dataset_features=lambda model: {"observation.state": {}},
            get_modality_config=lambda model: {},
        ),
        "simple.cli._decoupled_wbc_recording": types.SimpleNamespace(
            set_ego_view_feature_shape=lambda features, shape: None,
            validate_existing_ego_view_feature_shape=lambda root, shape: None,
        ),
    }
    monkeypatch.setattr(recorder, "_mod", fakes.__getitem__)
    recorder._exporter_class.cache_clear()
    try:
        rec = recorder.EpisodeRecorder(tmp_path, None, ["j"], "t")
        exporter = rec._open((HEIGHT, WIDTH, 3))
    finally:
        recorder._exporter_class.cache_clear()
    assert isinstance(exporter, FakeExporter)
    assert vars(type(exporter))["create_video_writer"] is recorder._create_video_writer
    assert exporter.kwargs["save_root"] == tmp_path

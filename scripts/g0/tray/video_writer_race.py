"""Does decoupled_wbc's VideoWriter flush while its worker thread still encodes? (DA-33)

The tray recorder writes ego-view video through `decoupled_wbc.data.video_writer
.VideoWriter`: `add_frame` queues frames, a daemon thread encodes them, and `stop()`
waits for `queue.empty()` before it flushes the encoder and closes the file from the
caller's thread. An empty queue only means the worker has taken the last frame, not
that it has encoded it. This script wraps the stream so every `encode` call is
counted, writes short videos the way the recorder does (frames, then `stop()` at once),
and reports how often the flush began while the worker was still inside `encode` of
the same libx264 context. No sim; frames are noise of the recorder's size.

`--writer sync` and `--writer joined` run the two proposed fixes instead: SyncVideoWriter
(same interface, encodes in the caller's thread) and JoinedVideoWriter (one worker
thread, joined before the flush). All report the process's RSS growth: the original
worker thread never exits, so each writer keeps its encoder alive.

    fwdata/simple/.venv/bin/python -X faulthandler scripts/g0/tray/video_writer_race.py \
        --videos 200 --writer threaded
"""

from __future__ import annotations

import argparse
import importlib
import json
import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np


class CountingStream:
    """Proxy of a PyAV stream that records overlapping `encode` calls."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._lock = threading.Lock()
        self.in_flight = 0
        self.overlaps = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_") or name in ("in_flight", "overlaps"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._stream, name, value)

    def encode(self, frame: Any = None) -> Any:
        with self._lock:
            if self.in_flight:
                self.overlaps += 1
            self.in_flight += 1
        try:
            return self._stream.encode(frame)
        finally:
            with self._lock:
                self.in_flight -= 1


def _rss_mb() -> float:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    return float("nan")


class SyncVideoWriter:
    """Proposed recorder writer: VideoWriter's interface, encoding in the caller's thread.

    No worker thread, so `stop()` flushes only after the last frame and nothing keeps
    the encoder alive once the exporter drops the writer.
    """

    def __init__(self, output_path: str, width: int, height: int, fps: float,
                 codec: str = "h264") -> None:
        av = importlib.import_module("av")
        self._av = av
        self.output_path = output_path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self.container = av.open(output_path, mode="w")
        self.stream = self.container.add_stream(codec, rate=fps)
        self.stream.width, self.stream.height = width, height

    def add_frame(self, frame: np.ndarray) -> None:
        assert frame.shape[1] == self.stream.width and frame.shape[0] == self.stream.height
        for packet in self.stream.encode(self._av.VideoFrame.from_ndarray(frame, "rgb24")):
            self.container.mux(packet)

    def stop(self) -> str:
        for packet in self.stream.encode():
            self.container.mux(packet)
        self.container.close()
        return self.output_path

    def cancel(self) -> None:
        self.container.close()
        Path(self.output_path).unlink(missing_ok=True)


class JoinedVideoWriter(SyncVideoWriter):
    """Proposed recorder writer that keeps encoding off the sim thread.

    Frames go through a queue to one worker thread as in VideoWriter; `stop()` sends a
    sentinel and joins the worker before it flushes, so the encoder is only ever used
    by one thread at a time, and the finished worker no longer holds the writer.
    """

    def __init__(self, output_path: str, width: int, height: int, fps: float,
                 codec: str = "h264") -> None:
        super().__init__(output_path, width, height, fps, codec)
        self.queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=50)
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _worker(self) -> None:
        while (frame := self.queue.get()) is not None:
            SyncVideoWriter.add_frame(self, frame)

    def add_frame(self, frame: np.ndarray) -> None:
        assert frame.shape[1] == self.stream.width and frame.shape[0] == self.stream.height
        self.queue.put(frame)

    def stop(self) -> str:
        self.queue.put(None)
        self.thread.join()
        return super().stop()

    def cancel(self) -> None:
        self.queue.put(None)
        self.thread.join()
        super().cancel()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--videos", type=int, default=200)
    parser.add_argument("--frames", type=int, default=50)
    parser.add_argument("--writer", choices=("threaded", "sync", "joined"), default="threaded")
    args = parser.parse_args()
    VideoWriter = importlib.import_module("decoupled_wbc.data.video_writer").VideoWriter
    if args.writer == "sync":
        VideoWriter = SyncVideoWriter
    if args.writer == "joined":
        VideoWriter = JoinedVideoWriter
    rng = np.random.default_rng(0)
    frames = [rng.integers(0, 255, (360, 640, 3), dtype=np.uint8) for _ in range(8)]
    overlaps = 0
    rss0 = _rss_mb()
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.perf_counter()
        for i in range(args.videos):
            writer = VideoWriter(str(Path(tmp) / f"v{i}.mp4"), 640, 360, 50)
            writer.stream = CountingStream(writer.stream)
            for k in range(args.frames):
                writer.add_frame(frames[k % len(frames)])
            writer.stop()
            overlaps += writer.stream.overlaps > 0
            del writer
        wall = time.perf_counter() - t0
    print(json.dumps({"writer": args.writer, "videos": args.videos, "frames": args.frames,
                      "flush_overlapped_encode": overlaps, "wall_s": round(wall, 1),
                      "rss_growth_mb": round(_rss_mb() - rss0, 1)}))


if __name__ == "__main__":
    main()

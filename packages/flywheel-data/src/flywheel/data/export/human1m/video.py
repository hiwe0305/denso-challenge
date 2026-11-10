"""Video for the shards and the explorer: H.264 mp4 that every browser plays.

The OpenCV wheels in the workspace write MPEG-4 Part 2, which browsers do not play,
and their VP9 runs at about 7 frames per second; so an ffmpeg binary with libx264 is
used, found as `$FW_FFMPEG` or `ffmpeg` on the PATH. Without one, the commands stop
and say how to get one (`uvx --from imageio-ffmpeg`), nothing is added to the
workspace. Each episode is encoded once, starting on a key frame; a shard's file is
the episodes joined without re-encoding, so an episode starts at the sum of the frames
before it over the fps.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

FFMPEG_HINT = ("no ffmpeg with libx264: set FW_FFMPEG, e.g. FW_FFMPEG=$(uvx --from"
               " imageio-ffmpeg python -c 'import imageio_ffmpeg as f;"
               " print(f.get_ffmpeg_exe())')")


@dataclass(frozen=True)
class VideoSettings:
    height: int = 480
    crf: int = 23
    preset: str = "veryfast"
    gop: int = 15  # key frame every half second: seeking in the explorer lands near


@dataclass(frozen=True)
class Encoded:
    path: Path
    frames: int
    width: int
    height: int
    codec: str = "h264"
    pix_fmt: str = "yuv420p"


class Encoder(Protocol):
    def encode(self, src: Path, dst: Path, frames: int, settings: VideoSettings) -> Encoded: ...

    def concat(self, parts: Sequence[Path], dst: Path) -> None: ...

    def poster(self, src: Path, dst: Path, frame: int, fps: float) -> None: ...


def count_frames(path: Path) -> tuple[int, int, int]:
    """(frames, width, height) by decoding every frame."""
    import cv2  # egocentric extra

    capture = cv2.VideoCapture(str(path))
    frames = 0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    while capture.grab():
        frames += 1
    capture.release()
    return frames, width, height


def find_ffmpeg() -> str:
    found = os.environ.get("FW_FFMPEG") or shutil.which("ffmpeg")
    if not found:
        raise FileNotFoundError(FFMPEG_HINT)
    return found


@dataclass(frozen=True)
class Ffmpeg:
    binary: str

    def _run(self, *args: str) -> None:
        done = subprocess.run([self.binary, "-hide_banner", "-loglevel", "error", "-y", *args],
                              capture_output=True, text=True, check=False)
        if done.returncode:
            raise RuntimeError(f"ffmpeg {' '.join(args)}: {done.stderr.strip()}")

    def encode(self, src: Path, dst: Path, frames: int, settings: VideoSettings) -> Encoded:
        dst.parent.mkdir(parents=True, exist_ok=True)
        self._run("-i", str(src), "-frames:v", str(frames), "-vf", f"scale=-2:{settings.height}",
                  "-c:v", "libx264", "-preset", settings.preset, "-crf", str(settings.crf),
                  "-pix_fmt", "yuv420p", "-g", str(settings.gop), "-an",
                  "-movflags", "+faststart", str(dst))
        counted, width, height = count_frames(dst)
        return Encoded(dst, counted, width, height)

    def concat(self, parts: Sequence[Path], dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        listing = dst.with_suffix(".txt")
        listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
        try:
            self._run("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy",
                      "-movflags", "+faststart", str(dst))
        finally:
            listing.unlink()

    def poster(self, src: Path, dst: Path, frame: int, fps: float) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        self._run("-ss", f"{frame / fps:.3f}", "-i", str(src), "-frames:v", "1",
                  "-q:v", "4", str(dst))

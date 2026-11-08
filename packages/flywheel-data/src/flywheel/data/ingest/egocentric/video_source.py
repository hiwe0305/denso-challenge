"""EgoVideoSource: the team's own egocentric recordings through the same pipeline (AC 6).

A recording root holds `device.json` and `<task>/<i>.mp4`:

    {"device": "iphone-15-wide", "fps": 30, "width": 1920, "height": 1080,
     "intrinsic": [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],
     "tasks": {"two_table": "pick the cup from the left table, place it on the right"},
     "objects": ["cup"]}

`tasks` and `objects` are optional. There is no tracking: pose comes from the E-A job
(`estimate_job.py`), `action_quality` is `pseudo`, and the video is `internal` with
no waiver, so the de-identification gate stops it at Annotate until `fw egocentric
deid` has written a blurred copy of every video (subtask 8). Everything after that is
the EgoDex pipeline unchanged, reading the copies.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.source import (
    DEVICE_FILE,
    EgoEpisodeFile,
    EgoSourceRecord,
    make_record,
)

DEVICE_KEYS = ("device", "fps", "width", "height", "intrinsic")
_INDEX = re.compile(r"^\d+$")


def select_videos(root: Path) -> list[EgoEpisodeFile]:
    """Every `<task>/<i>.mp4` under a recording root, in name order."""
    chosen = [
        EgoEpisodeFile(p.parent.name, int(p.stem), p.relative_to(root).as_posix(), None)
        for p in root.glob("*/*.mp4") if _INDEX.match(p.stem)
    ]
    if not chosen:
        raise ValueError(f"{root}: no <task>/<i>.mp4 recording")
    return sorted(chosen, key=lambda e: (e.task, e.index))


def register_videos(root: Path, cfg: EgoConfig) -> EgoSourceRecord:
    """EgoVideoSource: every recording under `root`, described by its device.json."""
    root = root.resolve()
    device = read_device(root)
    chosen = select_videos(root)
    return make_record("ego_video", cfg.sources["ego_video"], root, chosen, cfg, device)


def read_device(root: Path) -> dict[str, Any]:
    """device.json: device name, fps, width, height, intrinsic (3x3); `tasks` and
    `objects` optional."""
    path = root / DEVICE_FILE
    if not path.is_file():
        raise ValueError(f"{root}: no {DEVICE_FILE} (device, fps, width, height, intrinsic)")
    device = json.loads(path.read_text())
    missing = [k for k in DEVICE_KEYS if k not in device]
    if missing:
        raise ValueError(f"{path}: missing {', '.join(missing)}")
    intrinsic = device["intrinsic"]
    if len(intrinsic) != 3 or any(len(row) != 3 for row in intrinsic):
        raise ValueError(f"{path}: intrinsic must be 3x3")
    return cast(dict[str, Any], device)

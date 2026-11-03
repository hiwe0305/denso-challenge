"""The public surface of the data lane for the teleop and synthetic pipeline (DA-03).

Other stories call these names and do not import the modules behind them: DA-27
reads a dataset and writes injected copies with `iter_episodes` and
`write_episode`, DA-17 and DA-02 read `EpisodeFrames`. Only DA-03 edits this
file (plan 3/11/2026 section 4).

Everything here is CPU-only and reads or writes files; nothing imports
`lerobot`, a simulator or a model (03 section 7.3).
"""

from __future__ import annotations

from flywheel.data.ingest.lerobot import (
    EpisodeFrames,
    LeRobotFormatError,
    iter_episodes,
    read_info,
    write_episode,
)
from flywheel.data.ingest.sources import SourceRecord, register_source, to_episode

__all__ = [
    "EpisodeFrames",
    "LeRobotFormatError",
    "SourceRecord",
    "iter_episodes",
    "read_info",
    "register_source",
    "to_episode",
    "write_episode",
]

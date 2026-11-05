"""Public interface of the defect injector for the other data stories (plan 3/11, session 2).

DA-03 `release` calls `has_injected_defect` to keep benchmark copies out of the release
train (plan Q5); each side has its own test.
"""

import json
from pathlib import Path

from flywheel.contracts.artifacts import Episode
from flywheel.data.inject.lerobot_copy import COPY_MARKER


def has_injected_defect(episode: Episode) -> bool:
    """True when the episode belongs to a benchmark copy, defective or clean.

    Every episode of a copy carries `benchmark_copy_id` (design 6.1, 9.2; issue #62), so
    clean episodes of a copy stay out of the release train too.
    """
    return episode.meta.benchmark_copy_id is not None


def copy_marker(root: Path) -> str | None:
    """The `benchmark_copy_id` of the LeRobot dataset at root, or None if it is no copy."""
    path = root / "meta" / COPY_MARKER
    if not path.is_file():
        return None
    return str(json.loads(path.read_text(encoding="utf-8"))["benchmark_copy_id"])


def mark_copy_episode(episode: Episode, root: Path) -> Episode:
    """The Episode of a dataset at root, stamped with its copy marker if root is a copy.

    Ingest of a benchmark copy calls this on every Episode it builds, so the release
    gate sees the marker on defective and clean episodes alike.
    """
    copy_id = copy_marker(root)
    if copy_id is None:
        return episode
    meta = episode.meta.model_copy(update={"benchmark_copy_id": copy_id})
    return episode.model_copy(update={"meta": meta})

"""Console index: catalog, robot and egocentric datasets, and the story file."""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Callable
from pathlib import Path

from flywheel.console import paths as _paths
from flywheel.console.index import catalog, egocentric, robot, story
from flywheel.console.paths import ConsolePaths

PARTS = ("catalog", "robot", "ego", "story")


def build_all(
    paths: ConsolePaths | None = None, only: set[str] | list[str] | None = None
) -> dict[str, dict[str, int]]:
    """Build the selected parts into a temp dir and swap it in for ``paths.index``.

    On a partial run the parts not selected are carried over from the previous index.
    Any exception leaves the previous index untouched.
    """
    paths = paths or _paths.active()
    chosen = set(only) if only else set(PARTS)
    unknown = chosen - set(PARTS)
    if unknown:
        raise ValueError(f"unknown index part: {sorted(unknown)}")
    final = paths.index
    final.parent.mkdir(parents=True, exist_ok=True)
    tag = uuid.uuid4().hex[:8]
    tmp, old = final.with_name(f".index.tmp-{tag}"), final.with_name(f".index.old-{tag}")
    if final.is_dir() and chosen != set(PARTS):
        shutil.copytree(final, tmp, symlinks=True)
    else:
        tmp.mkdir()
    runners: dict[str, Callable[[ConsolePaths, Path], dict[str, int]]] = {
        "catalog": catalog.build,
        "robot": robot.build,
        "ego": egocentric.build,
        "story": story.build,
    }
    counts: dict[str, dict[str, int]] = {}
    try:
        for name in PARTS:  # story reads catalog.json, so keep this order
            if name in chosen:
                counts[name] = runners[name](paths, tmp)
        if final.is_dir():
            final.rename(old)
        try:
            tmp.rename(final)
        except OSError:
            if old.is_dir():
                old.rename(final)
            raise
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    shutil.rmtree(old, ignore_errors=True)
    return counts

"""The de-identification gate of tier 3 (Annotate) for egocentric episodes (DA-04 AC 2).

CLAUDE.md: egocentric video is de-identified before any other step, and the catalog
stops a `raw` episode from leaving Annotate (NFR13). `deid_blocks_annotate` of the
data lane's API says which episodes the gate stops: egocentric and `raw` (Q4, PO
3/11/2026).

D2 (Hiếu, 6/11/2026): no blurring is implemented before the demo. Apple's published
EgoDex sample, `egodex` with `data_class` `public`, is waived: it keeps
`deid_status = raw`, passes the gate, and its `source.json` records why. This
extends DA-30's "Waive for EgoDex" of 4/11/2026, which `flywheel_psi0.stage1.
egodex_sample.MASKING_WAIVED` holds for the stage 1 runs; the set is mirrored here,
not imported (the lane does not import adapters). Every other source, the team's own
recordings first, stays blocked until a blurring step sets `blurred` or `verified`.

The waiver is a PO decision, so it lives in code and not in a config a run could
widen. The labels alone prove nothing: they come from the `ingest egodex` command and
a root in the config, and a root pointed at the team's recordings would carry them
too (review of PR 152, 7/11/2026). So a waiver is honoured only when the source
record names it, the pair is in `WAIVED`, *and* every video of the source has its
name and sha256 in `egodex_pin.json`, the videos of DA-30's sample checked against
Apple's zip (`pin.py`). The record names the pin it was checked against
(`deid_waiver_manifest` in `source.json`); the gate checks the digests again.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path

from flywheel.contracts.artifacts import Episode
from flywheel.data.annotate.deid.pin import pin_key
from flywheel.data.api import deid_blocks_annotate

WAIVED = frozenset({("egodex", "public")})
PIN = Path(__file__).with_name("egodex_pin.json")
VIDEO = ".mp4"
WAIVER_REASON = (
    "D2, Hiếu 6/11/2026: extends DA-30's 'Waive for EgoDex' (4/11/2026) to the DA-04"
    " pipeline. Apple's published EgoDex sample (Vision Pro view down at a table) keeps"
    " deid_status raw; no blurring is implemented. Every other source stays blocked."
)


class DeidBlocked(ValueError):
    """An egocentric episode is raw and its source is not waived."""


@cache
def egodex_pin() -> tuple[str, Mapping[str, str]]:
    """`(pin id, {<task>/<i>.mp4: sha256})`; the id is the name and the file's sha256."""
    data = PIN.read_bytes()
    pin = json.loads(data)
    return f"{pin['name']}@{hashlib.sha256(data).hexdigest()[:12]}", pin["files"]


def unpinned_videos(files: Mapping[str, str]) -> list[str]:
    """Videos of a source (relative path -> sha256) whose name and sha256 are not pinned;
    every file when the source has no video at all."""
    _, pinned = egodex_pin()
    videos = {name: digest for name, digest in files.items() if name.endswith(VIDEO)}
    if not videos:
        return sorted(files) or ["<no files>"]
    return sorted(n for n, d in videos.items() if pinned.get(pin_key(n)) != d)


def deid_waiver(
    source_detail: str, data_class: str, files: Mapping[str, str]
) -> tuple[str | None, str | None]:
    """`(reason, pin id)` a source records in its `source.json`, or `(None, None)`."""
    if (source_detail, data_class) not in WAIVED or unpinned_videos(files):
        return None, None
    return WAIVER_REASON, egodex_pin()[0]


def annotate_allowed(
    episode: Episode, source_detail: str, data_class: str, waiver: str | None,
    files: Mapping[str, str],
) -> bool:
    """Whether this episode may leave Annotate.

    `source_detail`, `data_class`, `waiver` and `files` (relative path -> sha256, as
    checked against the disk at ingest and before each step) come from the episode's
    source record; the record must be the episode's own (same data_class).
    """
    if not deid_blocks_annotate(episode):
        return True
    if episode.data_class != data_class:
        return False
    return (waiver is not None and (source_detail, data_class) in WAIVED
            and not unpinned_videos(files))


def require_annotate(
    episode: Episode, source_detail: str, data_class: str, waiver: str | None,
    files: Mapping[str, str],
) -> None:
    """Raise `DeidBlocked` when the gate stops the episode."""
    if not annotate_allowed(episode, source_detail, data_class, waiver, files):
        unpinned = unpinned_videos(files)
        why = (f"{len(unpinned)} of the source's videos are not in the pinned EgoDex sample"
               f" ({egodex_pin()[0]}), e.g. {unpinned[0]}"
               if (source_detail, data_class) in WAIVED and unpinned else "it is not waived")
        raise DeidBlocked(
            f"{episode.episode_id} is egocentric with deid_status {episode.deid_status!r}"
            f" and source {source_detail!r}/{data_class!r}: {why}. It cannot leave"
            " Annotate until it is blurred (NFR13; D2 waives only Apple's pinned"
            " egodex/public videos)"
        )

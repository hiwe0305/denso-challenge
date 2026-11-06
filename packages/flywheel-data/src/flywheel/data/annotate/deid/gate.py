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
widen. A waiver is honoured only when the source record names it *and* the pair is
in `WAIVED`.
"""

from __future__ import annotations

from flywheel.contracts.artifacts import Episode
from flywheel.data.api import deid_blocks_annotate

WAIVED = frozenset({("egodex", "public")})
WAIVER_REASON = (
    "D2, Hiếu 6/11/2026: extends DA-30's 'Waive for EgoDex' (4/11/2026) to the DA-04"
    " pipeline. Apple's published EgoDex sample (Vision Pro view down at a table) keeps"
    " deid_status raw; no blurring is implemented. Every other source stays blocked."
)


class DeidBlocked(ValueError):
    """An egocentric episode is raw and its source is not waived."""


def deid_waiver(source_detail: str, data_class: str) -> str | None:
    """The waiver reason a source records in its `source.json`, or None."""
    return WAIVER_REASON if (source_detail, data_class) in WAIVED else None


def annotate_allowed(
    episode: Episode, source_detail: str, data_class: str, waiver: str | None
) -> bool:
    """Whether this episode may leave Annotate.

    `source_detail`, `data_class` and `waiver` come from the episode's source record;
    the record must be the episode's own (same data_class).
    """
    if not deid_blocks_annotate(episode):
        return True
    if episode.data_class != data_class:
        return False
    return waiver is not None and (source_detail, data_class) in WAIVED


def require_annotate(
    episode: Episode, source_detail: str, data_class: str, waiver: str | None
) -> None:
    """Raise `DeidBlocked` when the gate stops the episode."""
    if not annotate_allowed(episode, source_detail, data_class, waiver):
        raise DeidBlocked(
            f"{episode.episode_id} is egocentric with deid_status {episode.deid_status!r}"
            f" and source {source_detail!r}/{data_class!r} is not waived: it cannot leave"
            " Annotate until it is blurred (NFR13; D2 waives only egodex/public)"
        )

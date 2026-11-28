"""How live a Colab session record is when the index is built.

A batch record (``colab/batch-*/<session>.json``) keeps the last ``state`` its watcher wrote, so a
watcher that died leaves ``running`` behind for good (``batch-20261111-103700`` still said
``running`` 17 days later). The index therefore keeps a passing state (``starting``,
``running``, ``stopping``) only with a fresh heartbeat: ``beat`` at most ``STALE_AFTER_S``
seconds before the build. A passing state with an older or missing beat becomes ``stale``; the
pages and the chat never show a stale session as running. 600 s is the default of
``cu_watch guard --stale``, the same rule the guard uses to count a watcher as alive.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

STALE_AFTER_S = 600.0
LIVE_STATES = ("starting", "running")  # as in scripts/colab/cu_watch.py
# states a watcher passes through: true only while it still beats
PASSING_STATES = (*LIVE_STATES, "stopping")


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def live_state(state: Any, beat: Any, now: float) -> Any:
    """``state`` as written, except a passing state whose ``beat`` is missing or older than
    ``STALE_AFTER_S`` at ``now`` (both Unix seconds): then ``"stale"``."""
    if state not in PASSING_STATES:
        return state
    b = _num(beat)
    return state if b is not None and now - b <= STALE_AFTER_S else "stale"


def beat_iso(beat: Any) -> str | None:
    """The heartbeat as UTC ``YYYY-MM-DDTHH:MM:SSZ``, or None."""
    b = _num(beat)
    if b is None:
        return None
    return _dt.datetime.fromtimestamp(b, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch(iso: Any) -> float | None:
    if not isinstance(iso, str):
        return None
    try:
        t = _dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
        return t.replace(tzinfo=_dt.timezone.utc).timestamp()
    except ValueError:
        return None


def aged(rows: Any, now: float) -> Any:
    """Session rows of an index as of ``now``: a passing ``state`` whose ``beat`` (UTC string) is
    older than ``STALE_AFTER_S`` becomes ``stale``. Rows without a ``beat`` field (an index built
    before 28/11/2026) are left as they are."""
    if not isinstance(rows, list):
        return rows
    out: list[Any] = []
    for r in rows:
        if isinstance(r, dict) and "beat" in r and r.get("state") in PASSING_STATES:
            r = {**r, "state": live_state(r["state"], _epoch(r["beat"]), now)}
        out.append(r)
    return out


def fresh(rows: Any, now: float) -> Any:
    """``aged`` rows without the stale ones: the lists the pages show as live."""
    if not isinstance(rows, list):
        return rows
    return [r for r in aged(rows, now) if not (isinstance(r, dict) and r.get("state") == "stale")]

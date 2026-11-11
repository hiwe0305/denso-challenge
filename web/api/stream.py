"""`GET /notifications/stream`: server-sent `fw_changed` events (DESIGN.md §3.1, §6.4).

With Postgres the source is `NOTIFY fw_changed`, sent by `fw_sync` after each
import. In sink mode there is no database to listen to, so the stream watches
the files that change instead: the JSONL sink `fwsync import` writes and the
API's own state (`human_actions.jsonl`, drafts, sync runs). A change refreshes
the read model's cache and sends one event; the FE then re-reads, so an
import run outside the API shows up without a reload. Nothing else is sent:
the event says "something changed", never what, so no row can leak through it
to a role that may not read it (BR-10).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterable
from pathlib import Path

from web.fwsync import actions as log

Signature = tuple[tuple[str, int, int], ...]


def signature(directories: Iterable[Path]) -> Signature:
    """Name, mtime and size of every JSON or JSONL file directly under the directories."""
    out = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json*")):
            stat = path.stat()
            out.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(out)


async def change_events(
    current: Callable[[], Signature],
    on_change: Callable[[], None],
    *,
    interval: float = 2.0,
    keepalive: float = 15.0,
    limit: int | None = None,
) -> AsyncIterator[str]:
    """SSE frames: a retry hint, then `fw_changed` on each change, a comment as keep-alive.

    `limit` stops after that many events, for tests; the route streams forever.
    """
    last = current()
    sent = 0
    quiet = 0.0
    yield "retry: 5000\n\n"
    while limit is None or sent < limit:
        await asyncio.sleep(interval)
        now = current()
        if now != last:
            last = now
            on_change()
            sent += 1
            quiet = 0.0
            yield f"event: fw_changed\ndata: {json.dumps({'at': log.now_iso()})}\n\n"
        else:
            quiet += interval
            if quiet >= keepalive:
                quiet = 0.0
                yield ": ping\n\n"

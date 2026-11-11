"""`GET /notifications/stream` in sink mode (DESIGN.md §6.4): one `fw_changed` per change."""

from __future__ import annotations

import asyncio
from pathlib import Path

from web.api.stream import change_events, signature


def test_a_change_to_a_watched_file_sends_one_event_and_refreshes(tmp_path: Path) -> None:
    (tmp_path / "decisions.jsonl").write_text("{}\n", encoding="utf-8")
    refreshed: list[int] = []

    async def run() -> list[str]:
        frames = change_events(lambda: signature([tmp_path]), lambda: refreshed.append(1),
                               interval=0.01, limit=1)
        out = [await anext(frames)]
        (tmp_path / "decisions.jsonl").write_text("{}\n{}\n", encoding="utf-8")
        out += [frame async for frame in frames]
        return out

    frames = asyncio.run(run())
    assert frames[0].startswith("retry:")
    assert frames[-1].startswith("event: fw_changed\ndata: ")
    assert refreshed == [1]


def test_a_quiet_stream_sends_keep_alive_comments_only(tmp_path: Path) -> None:
    async def run() -> list[str]:
        frames = change_events(lambda: signature([tmp_path]), lambda: None,
                               interval=0.01, keepalive=0.02, limit=1)
        out = []
        async for frame in frames:
            out.append(frame)
            if len(out) == 3:
                break
        return out

    frames = asyncio.run(run())
    assert frames[1:] == [": ping\n\n", ": ping\n\n"]


def test_the_signature_ignores_files_that_are_not_artifacts(tmp_path: Path) -> None:
    before = signature([tmp_path, tmp_path / "missing"])
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    assert signature([tmp_path]) == before
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    assert signature([tmp_path]) != before

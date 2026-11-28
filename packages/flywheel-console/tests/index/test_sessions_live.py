"""Colab sessions are live only with a fresh heartbeat, and no presented list names a serve or
eval session of a held run (review of PR #266, 28/11/2026: the Home card said "da34-b-all (A100)
đang chạy" from a batch record 17 days old)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from flywheel.console.index import colab, hidden, jig, story, tasks
from flywheel.console.paths import ConsolePaths

REPO = Path(__file__).resolve().parents[4]
NOW = 1_795_000_000.0  # a fixed build time


def _write(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), encoding="utf-8")


def _real_hidden() -> hidden.Hidden:
    return hidden.from_manifest(tasks.load(ConsolePaths(repo=REPO, fw_root=REPO / "fwdata")))


def test_live_state_needs_a_heartbeat_younger_than_the_guard_limit() -> None:
    assert colab.STALE_AFTER_S == 600.0
    assert colab.live_state("running", NOW - 599, NOW) == "running"
    assert colab.live_state("starting", NOW - 10, NOW) == "starting"
    assert colab.live_state("running", NOW - 601, NOW) == "stale"
    assert colab.live_state("running", NOW - 17 * 86400, NOW) == "stale"
    assert colab.live_state("running", None, NOW) == "stale"
    assert colab.live_state("stopping", NOW - 16 * 86400, NOW) == "stale"
    assert colab.live_state("stopping", NOW - 5, NOW) == "stopping"
    assert colab.live_state("stopped", NOW - 17 * 86400, NOW) == "stopped"  # final state
    assert colab.beat_iso(0) == "1970-01-01T00:00:00Z" and colab.beat_iso(None) is None


def test_colab_rows_of_a_dead_watcher_are_stale(fw: ConsolePaths) -> None:
    b = fw.fw_root / "colab" / "batch-20261111-103700"
    _write(b / "da34-b-all.json", {"name": "da34-b-all", "state": "running", "gpu": "A100",
                                   "beat": NOW - 17 * 86400})  # fmt: skip
    _write(b / "da48-m.json", {"name": "da48-m", "state": "running", "gpu": "L4", "beat": NOW - 60})
    _write(b / "da34-c-70.json", {"name": "da34-c-70", "state": "stopped", "beat": NOW - 86400})
    _bal, rows = story._colab(fw.fw_root, NOW)
    by = {r["session"]: r for r in rows}
    assert by["da34-b-all"]["state"] == "stale" and by["da48-m"]["state"] == "running"
    assert by["da34-c-70"]["state"] == "stopped"
    assert by["da48-m"]["beat"] == colab.beat_iso(NOW - 60)


def test_eval_watcher_without_a_fresh_beat_is_stale(fw: ConsolePaths) -> None:
    d = fw.fw_root / "colab" / "da47-eval-m-20261126-124730"
    d.mkdir(parents=True)
    (d / "watch.log").write_text("lanes=3 complete=3 rows=180\n", encoding="utf-8")
    _write(d / "da48-serve-m-1.json", {"name": "da48-serve-m-1", "state": "running",
                                       "beat": NOW - 2 * 86400})  # fmt: skip
    assert jig.live_eval_watchers(fw.fw_root, NOW)[0]["state"] == "stale"
    _write(d / "da48-serve-m-1.json", {"name": "da48-serve-m-1", "state": "running"})
    w = jig.live_eval_watchers(fw.fw_root, (d / "watch.log").stat().st_mtime + 30)[0]
    assert w["state"] == "running"  # no beat in the record: the watch.log mtime is the beat


def test_serve_and_eval_sessions_of_a_held_run_are_hidden() -> None:
    h = _real_hidden()
    assert "*serve*c70r1*" in h.held_sessions and "*eval*c70r1*" in h.held_sessions
    for name in ("da34-serve-c70r1-1", "da34-serve-c70r1-4", "da34-eval-c70r1-x",
                 "da50-n", "da50-serve-n-1"):  # fmt: skip
        assert h.session(name), name
    for name in ("da34-c70r1", "da34-b-all", "da48-m", "da48-serve-m-1"):
        assert not h.session(name), name  # C70_R1's training session is not a result
    rows = [{"session": "da34-serve-c70r1-1"}, {"session": "da48-m"},
            {"session": "x", "folder": "tray/jig-n/eval"}]  # fmt: skip
    assert hidden.off_sessions(rows, h, "session", "folder") == [{"session": "da48-m"}]


def test_serving_a_stale_index_ages_the_sessions_and_drops_held_ones() -> None:
    h = _real_hidden()
    old, new = colab.beat_iso(time.time() - 86400), colab.beat_iso(time.time() - 30)
    doc = {
        "colab_sessions": [
            {"session": "da34-b-all", "state": "running", "beat": old},
            {"session": "da48-m", "state": "running", "beat": new},
            {"session": "da34-serve-c70r1-1", "state": "running", "beat": new},
            {"session": "da34-c-70", "state": "running"},  # pre-28/11 index: no beat field
        ],
        "jig": {
            "runs": [], "evals": [],
            "active_sessions": [{"session": "da34-b-all", "state": "running", "beat": old},
                                {"session": "da34-serve-c70r1-2", "state": "running", "beat": new},
                                {"session": "da48-m", "state": "running", "beat": new}],
            "live_evals": [{"folder": "da47-eval-m", "session": "s", "state": "running",
                            "beat": old}],
        },
    }  # fmt: skip
    out = hidden.story(doc, h)
    states = {r["session"]: r["state"] for r in out["colab_sessions"]}
    assert states == {"da34-b-all": "stale", "da48-m": "running", "da34-c-70": "running"}
    assert [s["session"] for s in out["jig"]["active_sessions"]] == ["da48-m"]
    assert out["jig"]["live_evals"] == []


def test_built_index_shows_no_stale_or_held_session_as_running(fw: ConsolePaths) -> None:
    b = fw.fw_root / "colab" / "batch-20261111-103700"
    for name, gpu in (("da34-b-all", "A100"), ("da34-serve-c70r1-1", "L4")):
        _write(b / f"{name}.json", {"name": name, "state": "running", "gpu": gpu,
                                    "beat": time.time() - 17 * 86400})  # fmt: skip
    out = fw.fw_root / "index"
    story.build(fw, out)
    d = json.loads((out / "story.json").read_text(encoding="utf-8"))
    assert [r["session"] for r in d["colab_sessions"]] == ["da34-b-all"]
    assert d["colab_sessions"][0]["state"] == "stale"
    assert "serve-c70r1" not in json.dumps(d)
    assert d["jig"]["active_sessions"] == []

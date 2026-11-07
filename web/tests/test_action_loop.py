"""Milestone M4 acceptance in sink mode (DESIGN.md §9.2):

    click approve → artifact in the outbox → fake core applies → re-import sees APPLIED

Covers the action log (append-only, status only moves forward), the CLI path
(`fwsync export`, `fwsync fake-core`, `fwsync import --actions`) and the
one-call cycle the API runs for `POST /sync/run`.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from web.fwsync import actions as log
from web.fwsync.cli import app
from web.fwsync.runner import run_cycle
from web.fwsync.sink import JsonlSink

ACTION = {
    "id": "act_0001",
    "action_kind": "RECOMMENDATION_DECISION",
    "target_kind": "flywheel_recommendations",
    "target_id": "rec_round1",
    "payload": {"items": [{"intervention_id": "iv_1", "decision": "APPROVE"}]},
    "reason": None,
    "sync_status": "PENDING",
}


def write_log(path: Path, *rows: dict[str, object]) -> Path:
    log.append(path, rows)
    return path


def test_status_only_moves_forward(tmp_path: Path) -> None:
    path = write_log(tmp_path / "human_actions.jsonl", ACTION)
    assert log.mark(path, ["act_0001"], "APPLIED") == ["act_0001"]
    # EXPORTED after APPLIED would move it backwards; ignored, nothing appended.
    lines_before = len(log.read_lines(path))
    assert log.mark(path, ["act_0001"], "EXPORTED") == []
    assert len(log.read_lines(path)) == lines_before
    state = log.fold(log.read_lines(path))["act_0001"]
    assert state["sync_status"] == "APPLIED" and state["applied_at"]


def test_the_log_is_append_only(tmp_path: Path) -> None:
    path = write_log(tmp_path / "human_actions.jsonl", ACTION)
    first = path.read_text(encoding="utf-8")
    log.mark(path, ["act_0001"], "EXPORTED")
    assert path.read_text(encoding="utf-8").startswith(first)


def test_unknown_ids_are_not_marked(tmp_path: Path) -> None:
    path = write_log(tmp_path / "human_actions.jsonl", ACTION)
    assert log.mark(path, ["act_9999"], "APPLIED") == []


def test_the_loop_closes_through_the_cli(tmp_path: Path) -> None:
    actions = write_log(tmp_path / "human_actions.jsonl", ACTION)
    outbox, inbox, sink = tmp_path / "outbox", tmp_path / "inbox", tmp_path / "sink"
    runner = CliRunner()

    exported = runner.invoke(app, ["export", "--actions", str(actions), "--to", str(outbox)])
    assert exported.exit_code == 0, exported.output
    assert log.fold(log.read_lines(actions))["act_0001"]["sync_status"] == "EXPORTED"
    # A second export finds nothing PENDING and writes nothing new.
    again = runner.invoke(app, ["export", "--actions", str(actions), "--to", str(outbox)])
    assert "EXPORTED: 0" in again.output

    core = runner.invoke(app, ["fake-core", "--outbox", str(outbox), "--to", str(inbox)])
    assert core.exit_code == 0, core.output

    imported = runner.invoke(app, [
        "import", "--from", str(inbox), "--out", str(sink), "--origin", "mock",
        "--actions", str(actions),
    ])
    assert imported.exit_code == 0, imported.output
    assert log.fold(log.read_lines(actions))["act_0001"]["sync_status"] == "APPLIED"
    decisions = [
        json.loads(line)
        for line in (sink / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert decisions[0]["source_action_id"] == "act_0001"


def test_one_cycle_does_the_whole_loop(tmp_path: Path) -> None:
    actions = write_log(tmp_path / "human_actions.jsonl", ACTION)
    sink = JsonlSink(directory=tmp_path / "sink")

    result = run_cycle(actions, tmp_path / "outbox", tmp_path / "inbox", sink,
                       fake_core=True, origin="mock")

    assert result.status == "ok"
    assert result.exported == ["act_0001"] and result.applied == ["act_0001"]
    # Running it again is harmless: nothing pending, nothing newly applied.
    again = run_cycle(actions, tmp_path / "outbox", tmp_path / "inbox", sink,
                      fake_core=True, origin="mock")
    assert again.exported == [] and again.applied == []


def test_without_the_fake_core_an_action_waits_in_exported(tmp_path: Path) -> None:
    actions = write_log(tmp_path / "human_actions.jsonl", ACTION)
    result = run_cycle(actions, tmp_path / "outbox", tmp_path / "inbox",
                       JsonlSink(directory=tmp_path / "sink"), fake_core=False)
    assert result.exported == ["act_0001"] and result.applied == []
    assert log.fold(log.read_lines(actions))["act_0001"]["sync_status"] == "EXPORTED"

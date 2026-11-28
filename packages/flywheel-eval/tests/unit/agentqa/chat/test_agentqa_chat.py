"""`fw agentqa chat` and `chat.turn` (DA-54 task 2.3, AC 5) with a fake harness.

The fake is a Python script written into tmp_path. The child environment is an allowlist,
so the fake takes its script from `$DSH_HOME/script.json` and records each start (argv,
environment, working directory, stdin) in `$DSH_HOME/starts.jsonl`. It may append an
answer line to `$AGENTQA_RECORD/answers.jsonl`, as the MCP server's `answer_submit` does.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "round"))
sys.path.insert(0, str(_HERE.parent / "mcp"))
from flywheel.eval.agentqa.chat import harness as chat_harness  # noqa: E402
from flywheel.eval.agentqa.cli import app  # noqa: E402
from flywheel.eval.agentqa.mcp.records import (  # noqa: E402
    ANSWERS_FILE,
    QUESTIONS_FILE,
    RECORD_FILE,
    VERDICTS_LIVE_FILE,
    latest_question,
)
from flywheel.eval.agentqa.round.pipeline import run_round  # noqa: E402
from helpers_mcp import REPO, internal, repacked  # noqa: E402
from helpers_round import NOW, isolated_store, pack_maker  # noqa: E402, F401

KEY = "sk-test-NOT-A-REAL-KEY-7f3a9c"
OTHER = "other-secret-value-5521"
SESSION = "sess-0001"
RECORDS = ("rec", "rec2")  # the record directories the tests use
FAKE = r'''
import json, os, subprocess, sys, time
home = os.environ["DSH_HOME"]
script = json.load(open(os.path.join(home, "script.json")))
task = sys.stdin.read()
with open(os.path.join(home, "starts.jsonl"), "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "env": dict(os.environ), "cwd": os.getcwd(),
                        "task": task}) + "\n")
record = os.environ.get("AGENTQA_RECORD", "")
for name, rows in script.get("append", {}).items():
    os.makedirs(record, exist_ok=True)
    with open(os.path.join(record, name), "a") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
if script.get("grandchild"):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    open(os.path.join(home, "grandchild.pid"), "w").write(str(child.pid))
for line in script.get("stdout", []):
    if isinstance(line, dict) and "__sleep" in line:  # a pause between two events
        time.sleep(line["__sleep"])
        continue
    if isinstance(line, dict) and "__append" in line:  # what the MCP server writes mid-turn
        for name, rows in line["__append"].items():
            with open(os.path.join(record, name), "a") as f:
                for row in rows:
                    f.write(json.dumps(row) + "\n")
        continue
    print(line if isinstance(line, str) else json.dumps(line), flush=True)
sys.stderr.write(script.get("stderr", ""))
time.sleep(script.get("sleep", 0))
sys.exit(script.get("exit", 0))
'''

ANSWER = {"answer_id": "A1", "text": "See {F1}.", "cites": ["F1"],
          "rendered": "See 11 rollouts.\n\nCited facts:\n- F1 members: 11 rollouts",
          "facts": [], "ts": "2026-11-27T00:00:00+00:00"}
VERDICT = {"item_id": "H1", "role": "investigate", "unit": "H1", "verdict": "accepted",
           "failed_rules": [], "call_ids": [], "accepted_call_id": "", "reason": ""}


def _events(session: str = SESSION, text: str = "I think it is the grip.",
            reason: str = "completed") -> list[Any]:
    return [
        {"type": "session", "sessionId": session, "cwd": "/x"},
        {"type": "status", "phase": "turn_start", "turn": 1},
        {"type": "status", "phase": "step_start", "turn": 1, "step": 1},
        {"type": "thinking", "text": "hmm"},
        {"type": "tool_call", "callId": "c1", "tool": "mcp__agentqa__measure_compare",
         "input": {}},
        {"type": "tool_result", "callId": "c1", "status": "completed", "result": {}},
        {"type": "status", "phase": "step_end", "turn": 1, "step": 1,
         "usage": {"inputTokens": 100, "outputTokens": 20}},
        {"type": "status", "phase": "step_start", "turn": 1, "step": 2},
        {"type": "tool_call", "callId": "c2", "tool": "mcp__agentqa__answer_submit",
         "input": {}},
        {"type": "tool_result", "callId": "c2", "status": "error", "result": None,
         "error": "rejected"},
        {"type": "brand_new_event", "whatever": 1},
        {"type": "status", "phase": "step_end", "turn": 1, "step": 2,
         "usage": {"inputTokens": 150, "outputTokens": 30}, "extra": True},
        {"type": "text", "text": text},
        {"type": "status", "phase": "turn_end", "turn": 1, "reason": reason},
        {"type": "final", "sessionId": session, "reason": reason, "text": text},
    ]


@pytest.fixture(autouse=True)
def drop_workdirs(tmp_path: Path) -> Iterator[None]:
    """The working directories are kept by design; the tests' own ones are removed."""
    yield
    for name in RECORDS:
        path = chat_harness.workdir_for(tmp_path / name)
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        elif path.is_file():
            path.unlink()


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    made: Path = pack_maker(tmp_path)()
    return made


@pytest.fixture
def home(tmp_path: Path) -> Path:
    path = tmp_path / "dsh-home"
    path.mkdir()
    return path


@pytest.fixture
def dsh(tmp_path: Path) -> Path:
    path = tmp_path / "bin" / "dsh"
    path.parent.mkdir()
    path.write_text(f"#!{sys.executable}\n{FAKE}")
    path.chmod(0o755)
    return path


@pytest.fixture(autouse=True)
def parent_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CKEY_API_KEY", KEY)
    monkeypatch.setenv("OTHER_API_KEY", OTHER)
    monkeypatch.delenv("AGENTQA_DSH_BIN", raising=False)
    monkeypatch.delenv("AGENTQA_DSH_HOME", raising=False)


def _script(home: Path, **script: Any) -> None:
    (home / "script.json").write_text(json.dumps(script))


def _starts(home: Path) -> list[dict[str, Any]]:
    path = home / "starts.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


def _chat(pack: Path, record: Path, dsh: Path, home: Path, *args: str,
          stdin: str | None = None) -> Any:
    return CliRunner().invoke(app, ["chat", "--pack", str(pack), "--record", str(record),
                                    "--dsh", str(dsh), "--harness-home", str(home), *args],
                              input=stdin)


def _turn(pack: Path, record: Path, dsh: Path, home: Path, **kw: Any) -> chat_harness.ChatTurn:
    return chat_harness.turn(kw.pop("task", "why do the place failures fail?"), pack=pack,
                          record=record, dsh=dsh, harness_home=home,
                          patch=REPO / chat_harness.DEFAULT_PATCH, repo=REPO, **kw)


# -- the command line and the environment ------------------------------------------------------


def test_first_turn_learns_the_session_and_the_second_passes_it(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    record = tmp_path / "rec"
    _script(home, stdout=_events())
    first = _turn(pack, record, dsh, home)
    assert first.session_id == SESSION and first.completed
    second = _turn(pack, record, dsh, home, session=first.session_id)
    assert second.session_id == SESSION
    one, two = (s["argv"] for s in _starts(home))
    patch = str((REPO / chat_harness.DEFAULT_PATCH).resolve())
    fixed = ["--profile", "headless", "--patch", patch, "--json", "--approval-policy",
             "never", "--permission-mode", "read-only"]
    assert one == [*fixed, "-"]
    assert two == [*fixed, "--session-id", SESSION, "-"]
    assert _starts(home)[0]["task"] == "why do the place failures fail?"


def test_the_child_gets_the_allowlist_and_the_harness_variables_only(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    record = tmp_path / "rec"
    _script(home, stdout=_events())
    _turn(pack, record, dsh, home)
    env = _starts(home)[0]["env"]
    assert env["CKEY_API_KEY"] == KEY
    assert "OTHER_API_KEY" not in env
    assert env["DSH_HOME"] == str(home.resolve()) and env["DSH_TELEMETRY_DISABLED"] == "1"
    assert env["AGENTQA_REPO"] == str(REPO.resolve())
    assert env["AGENTQA_PACK"] == str(pack.resolve())
    assert env["AGENTQA_RECORD"] == str(record.resolve())
    allowed = {"PATH", "HOME", "LANG", "CKEY_API_KEY", "DSH_HOME", "DSH_TELEMETRY_DISABLED",
               "AGENTQA_REPO", "AGENTQA_PACK", "AGENTQA_RECORD"}
    # the interpreter may add a few of its own (e.g. LC_CTYPE); nothing else of ours
    extra = {k for k in env if k not in allowed and not k.startswith("LC_")}
    assert extra <= {"PWD", "SHLVL", "_"}, extra


def test_the_child_runs_in_a_neutral_directory_bound_to_the_record_and_kept(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    _script(home, stdout=_events())
    _turn(pack, tmp_path / "rec", dsh, home)
    _turn(pack, tmp_path / "rec", dsh, home, session=SESSION)
    _turn(pack, tmp_path / "rec2", dsh, home)
    first, again, other = (s["cwd"] for s in _starts(home))
    assert first == again != other
    for cwd in (first, other):
        assert Path(cwd).name.startswith("agentqa-chat-") and len(Path(cwd).name) == 25
        assert Path(cwd).parent.resolve() == Path(tempfile.gettempdir()).resolve()
        assert str(REPO) not in cwd and str(Path.home()) not in cwd
        assert Path(cwd).is_dir() and not any(Path(cwd).iterdir())
        assert Path(cwd).stat().st_mode & 0o777 == 0o700


def test_a_working_directory_path_that_is_not_a_directory_is_refused(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    record = tmp_path / "rec"
    blocker = chat_harness.workdir_for(record)
    blocker.write_text("not a directory")
    _script(home, stdout=_events())
    with pytest.raises(chat_harness.ChatRefused, match="not a directory of the current user"):
        _turn(pack, record, dsh, home)
    result = _chat(pack, record, dsh, home, "why?")
    assert result.exit_code == 2 and len(result.stderr.strip().splitlines()) == 1
    assert _starts(home) == []


def test_a_session_of_another_directory_gets_the_binding_note(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    message = (f"session {SESSION} was recorded in /tmp/agentqa-chat-aaaaaaaaaaaa, "
               "not /tmp/agentqa-chat-bbbbbbbbbbbb")
    _script(home, exit=1, stdout=[{"type": "error", "message": message}])
    turn = _turn(pack, tmp_path / "rec", dsh, home, session=SESSION)
    assert turn.errors == (message,)
    assert chat_harness.SESSION_BOUND_NOTE in turn.diagnostics


def test_a_custom_key_variable_is_passed(
        pack: Path, tmp_path: Path, dsh: Path, home: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_KEY", "local-key-value-1234")
    _script(home, stdout=_events())
    _turn(pack, tmp_path / "rec", dsh, home, key_env=["LOCAL_KEY"])
    env = _starts(home)[0]["env"]
    assert env["LOCAL_KEY"] == "local-key-value-1234" and "CKEY_API_KEY" not in env


# -- what the command prints and its exit code ------------------------------------------------


def test_a_checked_answer_is_shown_and_exits_0(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    record = tmp_path / "rec"
    record.mkdir()
    old = {**ANSWER, "answer_id": "A0", "rendered": "an answer of an earlier turn"}
    (record / ANSWERS_FILE).write_text(json.dumps(old) + "\n")
    _script(home, stdout=_events(), append={ANSWERS_FILE: [ANSWER],
                                            VERDICTS_LIVE_FILE: [VERDICT]})
    result = _chat(pack, record, dsh, home, "why?")
    assert result.exit_code == 0, result.output
    out = result.stdout
    lines = out.splitlines()
    assert lines[:2] == ["measure_compare: completed", "answer_submit: error"]
    checked = out.index("CHECKED ANSWER (numbers filled in by code)")
    unchecked = out.index("UNCHECKED (the model's own words, not verified)")
    assert checked < out.index("See 11 rollouts.") < unchecked
    assert "an answer of an earlier turn" not in out
    assert "H1: kept" in out
    assert out.index("I think it is the grip.") > unchecked
    assert lines[-1].startswith(f"session {SESSION}: completed, 2 model calls")
    assert "inputTokens 250 outputTokens 50" in lines[-1]
    assert f"--session {SESSION}" in lines[-1]


def test_a_completed_turn_without_an_answer_exits_1_and_says_so(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    _script(home, stdout=_events())
    result = _chat(pack, tmp_path / "rec", dsh, home, "why?")
    assert result.exit_code == 1
    assert "No checked answer" in result.stdout
    assert "CHECKED ANSWER" not in result.stdout
    assert "UNCHECKED (the model's own words, not verified)" in result.stdout


def test_an_error_event_exits_1(pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    _script(home, exit=1, stdout=[{"type": "session", "sessionId": SESSION, "cwd": "/x"},
                                  {"type": "error", "message": "provider unreachable"}])
    result = _chat(pack, tmp_path / "rec", dsh, home, "--json", "why?")
    assert result.exit_code == 1
    turn = json.loads(result.stdout)
    assert turn["finish_reason"] == "error" and turn["completed"] is False
    assert turn["errors"] == ["provider unreachable"]
    assert turn["session_id"] == SESSION


def test_a_line_that_is_not_json_is_kept_as_a_diagnostic(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    events = _events()
    _script(home, stdout=[events[0], "warning: something odd", "[1, 2]", *events[1:]],
            stderr="entry foo not found\n")
    turn = _turn(pack, tmp_path / "rec", dsh, home)
    assert turn.completed and turn.finish_reason == "completed"
    assert "stdout: warning: something odd" in turn.diagnostics
    assert "stdout: [1, 2]" in turn.diagnostics
    assert [c.tool for c in turn.tool_calls] == ["measure_compare", "answer_submit"]
    assert turn.usage == {"inputTokens": 250, "outputTokens": 50} and turn.steps == 2


def test_the_task_can_come_from_stdin(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    _script(home, stdout=_events())
    _chat(pack, tmp_path / "rec", dsh, home, "-", stdin="a task from stdin\n")
    assert _starts(home)[0]["task"] == "a task from stdin\n"


def test_a_timeout_kills_the_process_group_and_reports(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    _script(home, stdout=[_events()[0]], sleep=60, grandchild=True)
    started = time.monotonic()
    turn = _turn(pack, tmp_path / "rec", dsh, home, timeout=2)
    assert time.monotonic() - started < 30
    assert turn.finish_reason == "timeout" and not turn.completed
    assert turn.session_id == SESSION
    assert any("timed out" in d for d in turn.diagnostics)
    pid = int((home / "grandchild.pid").read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail("the harness's child survived the timeout")


# -- refused before anything starts -------------------------------------------------------------


def test_a_missing_executable_exits_2_with_one_line(
        pack: Path, tmp_path: Path, home: Path) -> None:
    result = _chat(pack, tmp_path / "rec", tmp_path / "nope", home, "why?")
    assert result.exit_code == 2
    assert len(result.stderr.strip().splitlines()) == 1
    assert "AGENTQA_DSH_BIN" in result.stderr


def test_no_executable_given_exits_2_naming_the_variable(
        pack: Path, tmp_path: Path, home: Path) -> None:
    result = CliRunner().invoke(app, ["chat", "--pack", str(pack), "--record",
                                      str(tmp_path / "rec"), "--harness-home", str(home), "x"])
    assert result.exit_code == 2
    assert result.stderr.strip() == "error: no harness executable: set --dsh or " \
        "AGENTQA_DSH_BIN"


def test_a_missing_home_exits_2_with_one_line(
        pack: Path, tmp_path: Path, dsh: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = CliRunner().invoke(app, ["chat", "--pack", str(pack), "--record",
                                      str(tmp_path / "rec"), "--dsh", str(dsh), "x"])
    assert result.exit_code == 2 and "AGENTQA_DSH_HOME" in result.stderr
    monkeypatch.setenv("AGENTQA_DSH_HOME", str(tmp_path / "absent"))
    result = CliRunner().invoke(app, ["chat", "--pack", str(pack), "--record",
                                      str(tmp_path / "rec"), "--dsh", str(dsh), "x"])
    assert result.exit_code == 2
    assert len(result.stderr.strip().splitlines()) == 1
    assert "AGENTQA_DSH_HOME" in result.stderr


def test_the_environment_variables_are_the_defaults(
        pack: Path, tmp_path: Path, dsh: Path, home: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTQA_DSH_BIN", str(dsh))
    monkeypatch.setenv("AGENTQA_DSH_HOME", str(home))
    _script(home, stdout=_events())
    result = CliRunner().invoke(app, ["chat", "--pack", str(pack), "--record",
                                      str(tmp_path / "rec"), "why?"])
    assert result.exit_code == 1 and len(_starts(home)) == 1


def test_a_pack_not_confirmed_public_exits_2_and_starts_nothing(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    closed = repacked(pack, "closed", internal)
    _script(home, stdout=_events())
    result = _chat(closed, tmp_path / "rec", dsh, home, "why?")
    assert result.exit_code == 2
    assert result.stderr.startswith("error: ") and len(result.stderr.strip().splitlines()) == 1
    assert _starts(home) == []
    assert not (tmp_path / "rec").exists()


# -- no key value anywhere -------------------------------------------------------------------


def test_no_key_value_appears_in_any_output(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    leaky = _events(text=f"the key is {KEY}")
    _script(home, exit=1, stdout=[*leaky[:-1], f"raw {KEY}",
                                  {"type": "error", "message": f"401 for key {KEY}"}],
            stderr=f"auth failed: {KEY}\n")
    for extra in ([], ["--json"]):
        result = _chat(pack, tmp_path / "rec", dsh, home, *extra, "why?")
        assert result.exit_code == 1
        assert KEY not in result.stdout and KEY not in result.stderr
        assert OTHER not in result.stdout and OTHER not in result.stderr
        assert "[redacted]" in result.stdout


# -- a record bound to a run (DA-54 task 3.1) --------------------------------------------------


def _floor(pack: Path, out: Path) -> Path:
    run_round(pack, out, now=NOW, store=out.parent / "store", no_model=True)
    return out


def test_run_binds_the_record_before_the_harness_starts(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    run = _floor(pack, tmp_path / "run")
    record = tmp_path / "rec"
    _script(home, stdout=_events())
    result = _chat(pack, record, dsh, home, "--run", str(run), "why?")
    assert result.exit_code == 1, result.output  # the fake submitted no answer
    head = json.loads((record / RECORD_FILE).read_text())
    assert head["run_id"] == json.loads((run / "run.json").read_text())["run_id"]
    assert head["run_dir"] == str(run.resolve())
    assert len(_starts(home)) == 1
    _turn(pack, record, dsh, home)  # later turns need no --run: the head holds it
    assert json.loads((record / RECORD_FILE).read_text()) == head


def test_a_run_that_cannot_bind_starts_nothing(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    other = _floor(pack_maker(tmp_path)("other"), tmp_path / "other-run")
    _script(home, stdout=_events())
    with pytest.raises(chat_harness.ChatRefused, match="another pack"):
        _turn(pack, tmp_path / "rec", dsh, home, run=other)
    assert _starts(home) == [] and not (tmp_path / "rec").exists()
    result = _chat(pack, tmp_path / "rec", dsh, home, "--run", str(tmp_path / "nope"), "why?")
    assert result.exit_code == 2 and "not a run directory" in result.stderr
    assert _starts(home) == [] and not (tmp_path / "rec").exists()


def test_a_pack_not_public_is_refused_before_any_binding(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    run = _floor(pack, tmp_path / "run")
    refused = repacked(pack, "internal", internal)
    with pytest.raises(chat_harness.ChatRefused, match="internal"):
        _turn(refused, tmp_path / "rec", dsh, home, run=run)
    assert not (tmp_path / "rec").exists()


# -- the events of --events (DA-55 task 2.1) ----------------------------------------------------

REJECTED = {**VERDICT, "item_id": "H2", "unit": "H2", "verdict": "rejected",
            "failed_rules": ["statement_cites"], "reason": "rejected: cites no fact"}
QUESTIONED = {**ANSWER, "question": "why?"}


def _live(session: str = SESSION) -> list[Any]:
    """A turn whose record lines appear while it runs, as the MCP server writes them."""
    return [
        {"type": "session", "sessionId": session, "cwd": "/x"},
        {"__sleep": 1.5},
        {"type": "status", "phase": "step_start", "turn": 1, "step": 1},
        {"type": "tool_call", "callId": "c1", "tool": "mcp__agentqa__measure_compare",
         "input": {"cluster": "R/place", "measure": "final.offset_m"}},
        {"type": "tool_result", "callId": "c1", "status": "completed", "result": {}},
        {"type": "tool_call", "callId": "c2", "tool": "mcp__agentqa__hypothesis_propose",
         "input": {}},
        {"__sleep": 0.5},  # the fake does not wait for our read of the result before
        {"__append": {VERDICTS_LIVE_FILE: [VERDICT, REJECTED]}},
        {"type": "tool_result", "callId": "c2", "status": "completed", "result": {}},
        {"type": "tool_call", "callId": "c3", "tool": "mcp__agentqa__answer_submit",
         "input": {}},
        {"__sleep": 0.5},
        {"__append": {ANSWERS_FILE: [QUESTIONED]}},
        {"type": "tool_result", "callId": "c3", "status": "completed", "result": {}},
        {"type": "status", "phase": "step_end", "turn": 1, "step": 1,
         "usage": {"inputTokens": 100, "outputTokens": 20}},
        {"type": "text", "text": "I think it is the grip."},
        {"type": "final", "sessionId": session, "reason": "completed",
         "text": "I think it is the grip."},
    ]


def _lines(result: Any) -> list[dict[str, Any]]:
    return [json.loads(x) for x in result.stdout.splitlines()]


def test_each_event_is_out_as_soon_as_the_harness_emits_it(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    _script(home, stdout=_live())
    seen: list[tuple[float, dict[str, Any]]] = []
    started = time.monotonic()
    result = _turn(pack, tmp_path / "rec", dsh, home,
                   on_event=lambda e: seen.append((time.monotonic() - started, e)))
    assert result.completed and len(result.answers) == 1
    (first_at, first), (done_at, done) = seen[0], seen[-1]
    assert first == {"event": "session", "session_id": SESSION}
    assert first_at < 1.4 < done_at  # the session line did not wait for the turn's end
    assert done["event"] == "done" and done["checked"] is True


def test_the_events_command_prints_one_object_per_line_and_done_last(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    _script(home, stdout=_live())
    result = _chat(pack, tmp_path / "rec", dsh, home, "--events", "why?")
    assert result.exit_code == 0, result.output
    lines = _lines(result)
    assert [x["event"] for x in lines] == [
        "session", "tool_start", "tool_result", "tool_start", "tool_result", "hypothesis",
        "hypothesis", "tool_start", "tool_result", "checked_answer", "text", "done"]
    assert lines[1] == {"event": "tool_start", "call_id": "c1", "name": "measure_compare",
                        "args": {"cluster": "R/place", "measure": "final.offset_m"}}
    assert lines[2] == {"event": "tool_result", "call_id": "c1", "name": "measure_compare",
                        "ok": True}
    assert lines[5] == {"event": "hypothesis", "hypothesis": "H1", "verdict": "kept",
                        "failed_rules": []}
    assert lines[6] == {"event": "hypothesis", "hypothesis": "H2",
                        "verdict": "rejected: cites no fact",
                        "failed_rules": ["statement_cites"]}
    assert lines[9] == {"event": "checked_answer", "answer_id": "A1",
                        "rendered": ANSWER["rendered"], "cites": ["F1"], "question": "why?"}
    assert lines[10] == {"event": "text", "text": "I think it is the grip.", "checked": False}
    done = lines[-1]
    assert done["completed"] is True and done["checked"] is True
    assert done["session_id"] == SESSION and done["finish_reason"] == "completed"
    assert done["usage"] == {"inputTokens": 100, "outputTokens": 20} and done["steps"] == 1
    assert isinstance(done["seconds"], float) and done["errors"] == []


def test_the_events_of_a_turn_without_a_checked_answer_say_so_and_exit_1(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    _script(home, stdout=_events())
    result = _chat(pack, tmp_path / "rec", dsh, home, "--events", "why?")
    assert result.exit_code == 1
    lines = _lines(result)
    assert "checked_answer" not in [x["event"] for x in lines]
    assert [x for x in lines if x["event"] == "tool_result"] == [
        {"event": "tool_result", "call_id": "c1", "name": "measure_compare", "ok": True},
        {"event": "tool_result", "call_id": "c2", "name": "answer_submit", "ok": False}]
    assert [x for x in lines if x["event"] == "text"] == [
        {"event": "text", "text": "I think it is the grip.", "checked": False}]
    assert lines[-1]["event"] == "done"
    assert lines[-1]["completed"] is True and lines[-1]["checked"] is False


def test_the_final_text_is_an_unchecked_text_when_no_text_event_came(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    events = [e for e in _events() if e.get("type") != "text"]
    _script(home, stdout=events)
    lines = _lines(_chat(pack, tmp_path / "rec", dsh, home, "--events", "why?"))
    assert [x for x in lines if x["event"] == "text"] == [
        {"event": "text", "text": "I think it is the grip.", "checked": False}]


def test_an_error_event_and_a_bad_exit_end_with_error_then_done(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    _script(home, exit=1, stdout=[{"type": "session", "sessionId": SESSION, "cwd": "/x"},
                                  {"type": "error", "message": "provider unreachable"}])
    lines = _lines(_chat(pack, tmp_path / "rec", dsh, home, "--events", "why?"))
    assert lines[-2] == {"event": "error", "message": "provider unreachable"}
    assert lines[-1]["event"] == "done" and lines[-1]["completed"] is False
    assert lines[-1]["errors"] == ["provider unreachable"]
    _script(home, exit=3, stdout=[])
    lines = _lines(_chat(pack, tmp_path / "rec2", dsh, home, "--events", "why?"))
    assert [x["event"] for x in lines] == ["error", "done"]
    assert lines[0]["message"] == "the harness exited with code 3 without a final event"


def test_a_timeout_in_event_mode_ends_with_error_then_done(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    _script(home, stdout=[_events()[0]], sleep=60, grandchild=True)
    started = time.monotonic()
    result = _chat(pack, tmp_path / "rec", dsh, home, "--events", "--timeout", "2", "why?")
    assert time.monotonic() - started < 30
    assert result.exit_code == 1
    lines = _lines(result)
    assert [x["event"] for x in lines] == ["session", "error", "done"]
    assert lines[1]["message"].startswith("timed out after 2 s")
    assert lines[2]["finish_reason"] == "timeout" and lines[2]["completed"] is False
    pid = int((home / "grandchild.pid").read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail("the harness's child survived the timeout")


def test_a_harness_that_cannot_start_ends_with_error_then_done(
        pack: Path, tmp_path: Path, home: Path) -> None:
    broken = tmp_path / "bin" / "dsh"
    broken.parent.mkdir()
    broken.write_text("#!/nonexistent/interpreter\n")
    broken.chmod(0o755)
    result = _chat(pack, tmp_path / "rec", broken, home, "--events", "why?")
    assert result.exit_code == 2 and len(result.stderr.strip().splitlines()) == 1
    lines = _lines(result)
    assert [x["event"] for x in lines] == ["error", "done"]
    assert lines[0]["message"].startswith("cannot start the harness")
    assert lines[1]["checked"] is False and lines[1]["completed"] is False


def test_a_refusal_in_event_mode_ends_with_error_then_done_without_the_home_path(
        pack: Path, tmp_path: Path, dsh: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    absent = tmp_path / "absent-harness-home"
    monkeypatch.setenv("AGENTQA_DSH_HOME", str(absent))
    result = CliRunner().invoke(app, ["chat", "--pack", str(pack), "--record",
                                      str(tmp_path / "rec"), "--dsh", str(dsh), "--events",
                                      "why?"])
    assert result.exit_code == 2 and str(absent) in result.stderr
    lines = _lines(result)
    assert [x["event"] for x in lines] == ["error", "done"]
    assert str(absent) not in result.stdout and "[redacted]" in lines[0]["message"]
    closed = repacked(pack, "closed", internal)
    home = tmp_path / "dsh-home"
    home.mkdir()
    result = _chat(closed, tmp_path / "rec", dsh, home, "--events", "why?")
    assert result.exit_code == 2 and [x["event"] for x in _lines(result)] == ["error", "done"]
    assert not (tmp_path / "rec").exists() and _starts(home) == []


def test_json_and_events_together_are_refused(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    result = _chat(pack, tmp_path / "rec", dsh, home, "--events", "--json", "why?")
    assert result.exit_code == 2 and "cannot be used together" in result.stderr
    assert _starts(home) == []


def test_no_key_value_or_home_path_reaches_an_event_line(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    where = str(home.resolve())
    leaky = [
        {"type": "session", "sessionId": SESSION, "cwd": "/x"},
        {"type": "tool_call", "callId": "c1", "tool": "mcp__agentqa__measure_compare",
         "input": {"note": f"use {KEY}", KEY: "as a key"}},
        {"type": "tool_result", "callId": "c1", "status": "completed",
         "result": {"leak": KEY, "home": where}},
        {"type": "text", "text": f"the key is {KEY}, kept in {where}"},
        f"raw {KEY} {where}",
        {"type": "error", "message": f"401 for key {KEY} from {where}/config"},
    ]
    _script(home, exit=1, stdout=leaky, stderr=f"auth failed: {KEY} in {where}\n",
            append={ANSWERS_FILE: [{**ANSWER, "rendered": f"See {KEY}."}]})
    result = _chat(pack, tmp_path / "rec", dsh, home, "--events", "why?")
    assert result.exit_code == 1
    for hidden in (KEY, OTHER, where, str(home)):
        assert hidden not in result.stdout, hidden
    lines = _lines(result)
    assert lines[1]["args"] == {"note": "use [redacted]", "[redacted]": "as a key"}
    assert any("auth failed: [redacted]" in n for n in lines[-1]["notes"])
    assert "[redacted]" in lines[-1]["errors"][0]
    assert next(x for x in lines if x["event"] == "checked_answer")["rendered"] == \
        "See [redacted]."


def test_a_closed_reader_stops_the_harness(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    _script(home, stdout=[*_events()[:1], {"__sleep": 60}], grandchild=True)

    def closed(event: dict[str, Any]) -> None:
        raise BrokenPipeError("reader gone")

    started = time.monotonic()
    with pytest.raises(chat_harness.EventSinkClosed):
        _turn(pack, tmp_path / "rec", dsh, home, on_event=closed)
    assert time.monotonic() - started < 30
    pid = int((home / "grandchild.pid").read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail("the harness's child survived a closed reader")


# -- the question and the working directory (DA-55 task 2.2) -----------------------------------


def test_each_turn_appends_its_question_after_the_head(
        pack: Path, tmp_path: Path, dsh: Path, home: Path) -> None:
    record = tmp_path / "rec"
    _script(home, stdout=_events())
    _chat(pack, record, dsh, home, "why do the place failures fail?")
    _chat(pack, record, dsh, home, "-", stdin="and the grip?\n")
    rows = [json.loads(x) for x in (record / QUESTIONS_FILE).read_text().splitlines()]
    assert [(r["turn"], r["question"]) for r in rows] == [
        (1, "why do the place failures fail?"), (2, "and the grip?")]
    assert all(isinstance(r["ts"], str) for r in rows)
    head = json.loads((record / RECORD_FILE).read_text())  # a new directory gets its head
    assert head["pack_id"] and "run_id" not in head
    assert latest_question(record) == "and the grip?"


def test_the_working_directory_can_live_under_a_durable_root(
        pack: Path, tmp_path: Path, dsh: Path, home: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "durable" / "chat"
    _script(home, stdout=_events())
    _turn(pack, tmp_path / "rec", dsh, home, workdir_root=root)
    monkeypatch.setenv("AGENTQA_CHAT_WORKDIR_ROOT", str(root))
    _chat(pack, tmp_path / "rec", dsh, home, "why?")
    first, again = (Path(s["cwd"]) for s in _starts(home))
    assert first == again == chat_harness.workdir_for(tmp_path / "rec", root)
    assert first.parent == root.resolve() and first.name.startswith("agentqa-chat-")
    assert len(first.name) == 25 and first.stat().st_mode & 0o777 == 0o700
    assert first.name == chat_harness.workdir_for(tmp_path / "rec").name  # same neutral name

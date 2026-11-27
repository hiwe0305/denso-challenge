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
from flywheel.eval.agentqa.mcp.records import ANSWERS_FILE, VERDICTS_LIVE_FILE  # noqa: E402
from helpers_mcp import REPO, internal, repacked  # noqa: E402
from helpers_round import isolated_store, pack_maker  # noqa: E402, F401

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

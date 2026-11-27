"""One chat turn through the outside agent harness `dsh` (DA-54 task 2.3).

The harness is a native executable installed outside this repo; nothing here imports it.
`turn` spawns it once, headless, for one task:

    dsh --profile headless --patch <patch.yml> --json --approval-policy never
        --permission-mode read-only [--session-id <id>] -

with the task on stdin, and reads its NDJSON events from stdout. The first turn of a
session runs without `--session-id` (an unknown id is an error) and learns the id from
the `session` event; later turns pass it.

The harness is the chat shell only. The gate is the MCP server of `fw agentqa mcp
--record <dir>`, which the patch starts: a checked answer is a line its `answer_submit`
appended to `<record>/answers.jsonl` during this turn, never the model's free text.

What the child gets, and nothing more:

- environment: PATH, HOME, LANG, LC_* and the key variables named by `key_env` from the
  parent, then DSH_HOME, DSH_TELEMETRY_DISABLED=1 and AGENTQA_REPO / AGENTQA_PACK /
  AGENTQA_RECORD (absolute paths). A key value is never printed: every string kept in
  the turn record has the key values replaced by `[redacted]`.
- working directory: `<system temp dir>/agentqa-chat-<12 hex of sha256 of the record
  path>` (the harness shows this path to the model, so it names neither machine nor
  project). The harness binds a session to its working directory, so the same record
  directory gives the same path on every turn and the directory is kept (it stays empty).

A pack that admit does not confirm public is refused before anything is spawned, with
the check `fw agentqa mcp` applies; the MCP server checks again at its own start.

With `run` (DA-54 task 3.1) the record directory is bound to that run before spawning
(`bind_record` writes the binding into `record.json`), so the server the patch starts
finds it there; the patch needs no new flag.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from flywheel.eval.agentqa.mcp.records import (
    ANSWERS_FILE,
    VERDICTS_LIVE_FILE,
    RecordRefused,
    bind_record,
    live_verdict,
)
from flywheel.eval.agentqa.mcp.server import PackNotPublic, open_public_session
from flywheel.eval.agentqa.round.measure import PlanRefused
from flywheel.eval.agentqa.round.pack import PackRefused
from flywheel.eval.agentqa.round.records import Admission, VerdictRecord

PROFILE = "headless"
FIXED_FLAGS = ("--json", "--approval-policy", "never", "--permission-mode", "read-only")
TOOL_PREFIX = "mcp__agentqa__"
DEFAULT_KEY_ENV = ("CKEY_API_KEY",)
DEFAULT_TIMEOUT = 900.0
DEFAULT_PATCH = Path("configs") / "eval" / "agentqa" / "harness" / "agentqa.patch.yml"
PASSED_ENV = ("PATH", "HOME", "LANG")
PASSED_PREFIX = "LC_"
WORKDIR_PREFIX = "agentqa-chat-"
_OTHER_DIRECTORY = "was recorded in"  # the harness's error for a session of another cwd
SESSION_BOUND_NOTE = ("a session is bound to the record directory it was started with: "
                      "continue it with the same --record")
REDACTED = "[redacted]"
_KEEP_CHARS = 500
_KEEP_LINES = 40
_HARMLESS_STDERR = ("not found",)  # the patch's rows the headless profile lacks


class ChatRefused(ValueError):
    """The turn cannot start (configuration or data class); nothing was spawned."""


@dataclass(frozen=True)
class ToolCall:
    tool: str  # without the `mcp__agentqa__` prefix
    status: str  # `completed`, `error`, or `no result` when the turn ended first


@dataclass(frozen=True)
class ChatTurn:
    session_id: str | None
    finish_reason: str  # the `final` event's reason, or `error` / `timeout`
    exit_code: int | None
    tool_calls: tuple[ToolCall, ...]
    text: str  # the model's free final text: not checked
    usage: dict[str, int] | None
    steps: int  # model calls (`step_start` events)
    seconds: float
    answers: tuple[dict[str, Any], ...]  # lines appended to answers.jsonl in this turn
    verdicts: tuple[dict[str, str], ...]  # hypotheses given a verdict in this turn
    errors: tuple[str, ...] = ()  # the harness's `error` events
    diagnostics: tuple[str, ...] = field(default=())  # non-JSON lines, stderr, exit notes

    @property
    def completed(self) -> bool:
        """The harness finished the turn: exit 0, a `final` event, no error."""
        return (self.exit_code == 0 and not self.errors
                and self.finish_reason not in ("error", "timeout"))

    def to_json(self) -> dict[str, Any]:
        out = asdict(self)
        out["completed"] = self.completed
        return out


# --- before spawning ------------------------------------------------------------------------


def _first_line(error: BaseException) -> str:
    text = str(error).strip()
    return text.splitlines()[0] if text else type(error).__name__


def refuse_non_public(pack: Path) -> Admission:
    """`ChatRefused` unless admit confirms `pack` public (the check of `fw agentqa mcp`);
    the admission when it does."""
    try:
        return open_public_session(pack).admission
    except (PackRefused, PackNotPublic, PlanRefused, OSError) as error:
        raise ChatRefused(_first_line(error)) from error


def child_env(parent: Mapping[str, str], key_env: Sequence[str], *, harness_home: Path,
              repo: Path, pack: Path, record: Path) -> dict[str, str]:
    """The child's environment: the allowlist of `parent`, then the harness's variables."""
    env = {k: v for k, v in parent.items()
           if k in PASSED_ENV or k.startswith(PASSED_PREFIX) or k in key_env}
    env.update({"DSH_HOME": str(harness_home), "DSH_TELEMETRY_DISABLED": "1",
                "AGENTQA_REPO": str(repo), "AGENTQA_PACK": str(pack),
                "AGENTQA_RECORD": str(record)})
    return env


def workdir_for(record: Path) -> Path:
    """The child's working directory for `record`: the same path for the same record."""
    digest = hashlib.sha256(str(record.resolve()).encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"{WORKDIR_PREFIX}{digest}"


def ensure_workdir(record: Path) -> Path:
    """`workdir_for(record)`, created (0700) when absent; `ChatRefused` when it is not a
    directory of the current user."""
    path = workdir_for(record)
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        pass
    except OSError as error:
        raise ChatRefused(f"cannot create the working directory {path}: "
                          f"{_first_line(error)}") from error
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid():
        raise ChatRefused(f"{path} exists and is not a directory of the current user; "
                          "remove it or use another record directory")
    return path


def command(dsh: Path, patch: Path, session: str | None) -> list[str]:
    """Launcher flags first, then the app flags, then `-` (the task on stdin)."""
    argv = [str(dsh), "--profile", PROFILE, "--patch", str(patch), *FIXED_FLAGS]
    if session:
        argv += ["--session-id", session]
    return [*argv, "-"]


# --- the record directory -------------------------------------------------------------------


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _answer_ids(record: Path) -> set[str]:
    return {str(a.get("answer_id")) for a in _jsonl(record / ANSWERS_FILE)}


def _verdict_units(record: Path) -> set[str]:
    return {str(v.get("unit")) for v in _jsonl(record / VERDICTS_LIVE_FILE)}


def _new_verdicts(record: Path, before: set[str]) -> list[dict[str, str]]:
    out = []
    for row in _jsonl(record / VERDICTS_LIVE_FILE):
        unit = str(row.get("unit"))
        if unit in before:
            continue
        try:
            shown = live_verdict(VerdictRecord.model_validate(row))
        except ValueError:
            shown = str(row.get("verdict", "?"))
        out.append({"hypothesis": unit, "verdict": shown})
    return out


# --- the events -----------------------------------------------------------------------------


class _Redactor:
    def __init__(self, secrets: Sequence[str]) -> None:
        self._secrets = sorted({s for s in secrets if len(s) >= 4}, key=len, reverse=True)

    def __call__(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, REDACTED)
        return text


def _add_usage(total: dict[str, int], usage: object) -> None:
    if not isinstance(usage, dict):
        return
    for key, value in usage.items():
        if isinstance(value, int) and not isinstance(value, bool):
            total[str(key)] = total.get(str(key), 0) + value


@dataclass
class _Events:
    session_id: str | None = None
    final: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    calls: list[tuple[str, str]] = field(default_factory=list)  # (call id, tool)
    results: dict[str, str] = field(default_factory=dict)
    texts: list[str] = field(default_factory=list)
    steps: int = 0
    step_usage: dict[str, int] = field(default_factory=dict)
    turn_usage: dict[str, int] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)


def parse_events(stdout: str, redact: _Redactor) -> _Events:
    """The NDJSON of one turn; a line that is not a JSON object is kept as a diagnostic."""
    ev = _Events()
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            event = None
        if not isinstance(event, dict):
            ev.diagnostics.append("stdout: " + redact(line)[:_KEEP_CHARS])
            continue
        kind = event.get("type")
        if kind == "session" and isinstance(event.get("sessionId"), str):
            ev.session_id = event["sessionId"]
        elif kind == "status":
            phase = event.get("phase")
            if phase == "step_start":
                ev.steps += 1
            elif phase == "step_end":
                _add_usage(ev.step_usage, event.get("usage"))
            elif phase == "turn_end":
                _add_usage(ev.turn_usage, event.get("usage"))
        elif kind == "text" and isinstance(event.get("text"), str):
            ev.texts.append(event["text"])
        elif kind == "tool_call":
            ev.calls.append((str(event.get("callId", "")), str(event.get("tool", "?"))))
        elif kind == "tool_result":
            ev.results[str(event.get("callId", ""))] = str(event.get("status", "?"))
        elif kind == "final":
            ev.final = event
            if isinstance(event.get("sessionId"), str):
                ev.session_id = event["sessionId"]
        elif kind == "error":
            ev.errors.append(redact(str(event.get("message", "error")))[:_KEEP_CHARS])
        # `thinking` and unknown types: tolerated, not kept
    return ev


def _stderr_lines(stderr: str, redact: _Redactor) -> list[str]:
    kept = [redact(x.strip())[:_KEEP_CHARS] for x in stderr.splitlines()
            if x.strip() and not any(h in x for h in _HARMLESS_STDERR)]
    return ["stderr: " + x for x in kept[-_KEEP_LINES:]]


# --- the process ----------------------------------------------------------------------------


def _kill_group(proc: subprocess.Popen[str]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _run(argv: list[str], task: str, env: dict[str, str], cwd: Path,
         timeout: float) -> tuple[str, str, int | None, bool]:
    """(stdout, stderr, exit code, timed out); the process group is killed on timeout."""
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=cwd, env=env, text=True,
                            encoding="utf-8", errors="replace", start_new_session=True)
    try:
        out, err = proc.communicate(task, timeout=timeout)
        return out, err, proc.returncode, False
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:  # a pipe still held open: give up on the rest
            proc.kill()
            out, err = "", ""
        return out or "", err or "", proc.returncode, True
    finally:
        if proc.poll() is None:
            _kill_group(proc)
            proc.wait()


def turn(task: str, *, pack: Path, record: Path, dsh: Path, harness_home: Path,
         patch: Path, repo: Path, session: str | None = None,
         key_env: Sequence[str] = DEFAULT_KEY_ENV, timeout: float = DEFAULT_TIMEOUT,
         environ: Mapping[str, str] | None = None, run: Path | None = None) -> ChatTurn:
    """Run one task through the harness; `ChatRefused` before spawning when it cannot run.

    `run`: bind `record` to this run directory first (a bound record keeps its binding).
    """
    parent = os.environ if environ is None else environ
    if not dsh.is_file() or not os.access(dsh, os.X_OK):
        raise ChatRefused(f"harness executable not found or not executable: {dsh} "
                          "(set --dsh or AGENTQA_DSH_BIN)")
    if not harness_home.is_dir():
        raise ChatRefused(f"harness home is not a directory: {harness_home} "
                          "(set --harness-home or AGENTQA_DSH_HOME)")
    if not patch.is_file():
        raise ChatRefused(f"harness patch not found: {patch} (set --patch)")
    if not task.strip():
        raise ChatRefused("the task is empty")
    admission = refuse_non_public(pack)
    if run is not None:
        try:
            bind_record(record, admission.pack_id, admission.pack_sha256, run)
        except (RecordRefused, OSError) as error:
            raise ChatRefused(_first_line(error)) from error
    paths = {name: p.resolve() for name, p in (("dsh", dsh), ("home", harness_home),
                                               ("patch", patch), ("repo", repo),
                                               ("pack", pack), ("record", record))}
    env = child_env(parent, key_env, harness_home=paths["home"], repo=paths["repo"],
                    pack=paths["pack"], record=paths["record"])
    redact = _Redactor([parent[k] for k in key_env if parent.get(k)])
    answers_before = _answer_ids(paths["record"])
    verdicts_before = _verdict_units(paths["record"])
    workdir = ensure_workdir(paths["record"])
    started = time.monotonic()
    try:
        out, err, code, timed_out = _run(command(paths["dsh"], paths["patch"], session),
                                         task, env, workdir, timeout)
    except OSError as error:
        raise ChatRefused(f"cannot start the harness: {redact(_first_line(error))}") from error
    seconds = round(time.monotonic() - started, 3)
    ev = parse_events(out, redact)
    diagnostics = list(ev.diagnostics)
    if timed_out:
        reason = "timeout"
        diagnostics.append(f"timed out after {timeout:g} s; the process group was killed")
    elif ev.errors:
        reason = "error"
    elif ev.final is not None and code == 0:
        reason = str(ev.final.get("reason") or "completed")
    else:
        reason = "error"
        diagnostics.append(f"the harness exited with code {code}"
                           + ("" if ev.final is not None else " without a final event"))
    if code != 0 or timed_out:
        diagnostics += _stderr_lines(err, redact)
    if session and any(_OTHER_DIRECTORY in x for x in [*ev.errors, *diagnostics]):
        diagnostics.append(SESSION_BOUND_NOTE)
    final_text = ev.final.get("text") if ev.final is not None else None
    text = final_text if isinstance(final_text, str) else "".join(ev.texts)
    usage = ev.turn_usage or ev.step_usage or None
    answers = tuple(a for a in _jsonl(paths["record"] / ANSWERS_FILE)
                    if str(a.get("answer_id")) not in answers_before)
    return ChatTurn(
        session_id=ev.session_id or session, finish_reason=reason, exit_code=code,
        tool_calls=tuple(ToolCall(tool.removeprefix(TOOL_PREFIX),
                                  ev.results.get(call_id, "no result"))
                         for call_id, tool in ev.calls),
        text=redact(text.strip()), usage=usage, steps=ev.steps, seconds=seconds,
        answers=answers, verdicts=tuple(_new_verdicts(paths["record"], verdicts_before)),
        errors=tuple(ev.errors), diagnostics=tuple(diagnostics))


__all__ = ["DEFAULT_KEY_ENV", "DEFAULT_PATCH", "DEFAULT_TIMEOUT", "ChatRefused", "ChatTurn",
           "ToolCall", "child_env", "command", "ensure_workdir", "parse_events",
           "refuse_non_public", "turn", "workdir_for"]

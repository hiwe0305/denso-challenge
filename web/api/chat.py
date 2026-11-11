"""The chat pane, read-only minimum (DESIGN.md §5.4, §6.2 "Ngăn chat", §7.2).

The pane knows the screen that is open and the record selected on it. A turn
loads that record through the `ReadModel` the way the role `agent_ro` would
see it, builds one prompt, asks a model, and keeps both messages.

What makes it the read-only minimum, and what keeps it inside the rules:

* **No actions.** The model is told it cannot act, and every assistant message
  is stored with ``proposed_action = None``; ``POST /chat/actions/{id}/confirm``
  does not exist yet (§6.2: chat is the first cut, its minimum is read-only).
* **R8 and BR-10, as `agent_ro`.** The loaders never call the group-S methods
  (`defect_scoreboard`, `defect_scores`), and they read evaluations under
  ``AGENT_ROLE``, which is not ADMIN, so a sealed evaluation is invisible to the
  agent whoever is asking. M3 is not loaded at all.
* **R6.** Every record whose ``data_class`` is not ``public`` is dropped from
  the context before the prompt is built, and its id is listed as withheld.
* **R6, the model.** The endpoint must be a machine of ours (loopback, a private
  address, or a host passed in ``local_hosts``), the request ignores proxy
  variables and refuses redirects. Same rule and same mechanism as Agent QA/QC
  (``flywheel/eval/agentqa/endpoint.py``), copied because the web is not a lane
  and may not import one.
* **§5.4 point 3.** A message keeps the ids it loaded and the sha256 of the
  prompt, never the prompt itself.

Sink mode stores sessions and messages as append-only JSONL in the API's
state directory (tables ``agent_chat_sessions`` and ``agent_chat_messages``).
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from email.message import Message as Headers
from pathlib import Path
from typing import IO, Any, NoReturn, Protocol
from urllib.parse import urlparse

from web.api.readmodel import ReadModel
from web.fwsync import actions as log

Row = dict[str, Any]
Message = dict[str, str]

#: The role the agent reads as. Not ADMIN, so sealed evaluations stay hidden (BR-10).
AGENT_ROLE = "agent_ro"
#: The prompt's context block is cut at this many characters of JSON.
CONTEXT_CHARS = 24_000
#: Earlier turns of the session sent with each new question.
HISTORY_TURNS = 6
#: Longest question accepted.
MAX_QUESTION_CHARS = 4_000

CONTEXT_KEYS = ("dataset_id", "experiment_id", "evaluation_id", "recommendation_id",
                "cluster_id")
SCREENS = ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10")

SYSTEM_PROMPT = (
    "Bạn là trợ lý chỉ đọc của web Humanoid Data Flywheel. Chỉ trả lời dựa trên khối "
    "NGỮ CẢNH bên dưới; điều gì không có trong đó thì nói rõ là không có, đừng đoán. "
    "Số liệu nào trong ngữ cảnh có origin = mock là số bịa của bộ demo, phải nói vậy khi "
    "dùng nó. Bạn không làm được hành động nào: không duyệt, không nộp, không chạy job, "
    "không đề xuất bấm nút; nếu người hỏi muốn làm, chỉ cho họ màn hình có nút đó. "
    "Bạn không đọc được bản sao có lỗi cấy và đáp án của nó, lượt eval đang niêm phong, "
    "và dữ liệu không phải public; có bản ghi bị giữ lại thì danh sách WITHHELD nói. "
    "Trả lời tiếng Việt, ngắn, có mã bản ghi khi nhắc tới nó."
)


class ChatError(Exception):
    """A request the chat refuses, with the status and code the API returns."""

    def __init__(self, status: int, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.hint = status, code, message, hint


# ---------------------------------------------------------------- the model


class ChatModel(Protocol):
    @property
    def name(self) -> str: ...

    def complete(self, messages: Sequence[Message]) -> str: ...


def is_local(host: str, local_hosts: Sequence[str] = ()) -> bool:
    """Loopback, a private-network address, `localhost`, or a host named in `local_hosts`."""
    if host == "localhost" or host in local_hosts:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect could carry the prompt to a host nobody checked."""

    def redirect_request(self, req: urllib.request.Request, fp: IO[bytes], code: int,
                         msg: str, headers: Headers, newurl: str) -> NoReturn:
        raise urllib.error.HTTPError(req.full_url, code, f"redirect to {newurl} refused",
                                     headers, fp)


@dataclass(frozen=True)
class LocalEndpoint:
    """A model behind ``<base_url>/chat/completions`` on a machine of ours (Ollama, vLLM)."""

    base_url: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout_s: float = 120.0
    local_hosts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError(f"chat endpoint {self.base_url!r} is not an http(s) URL with a host")
        if not is_local(parsed.hostname, self.local_hosts):
            raise ValueError(
                f"chat endpoint host {parsed.hostname!r} is not a machine of ours (R6); "
                "pass it in --chat-local-host only if it is served inside our network")

    @property
    def name(self) -> str:
        return self.model

    def complete(self, messages: Sequence[Message]) -> str:
        body = {"model": self.model, "messages": list(messages),
                "temperature": self.temperature, "max_tokens": self.max_tokens}
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        try:
            with opener.open(request, timeout=self.timeout_s) as response:
                reply = json.loads(response.read().decode("utf-8"))
            content = reply["choices"][0]["message"]["content"]
        except (urllib.error.URLError, OSError, json.JSONDecodeError,
                KeyError, IndexError, TypeError) as exc:
            raise ChatError(502, "CHAT_MODEL_FAILED", f"model {self.model} không trả lời: {exc}",
                            "kiểm tra máy chạy model rồi hỏi lại") from exc
        if not isinstance(content, str) or not content.strip():
            raise ChatError(502, "CHAT_MODEL_FAILED", f"model {self.model} trả lời rỗng")
        return content.strip()


# ---------------------------------------------------------------- context


@dataclass
class Context:
    """What one turn loaded: the records, their ids, and what was held back."""

    records: dict[str, Any] = field(default_factory=dict)
    loaded: list[Row] = field(default_factory=list)
    withheld: list[Row] = field(default_factory=list)
    missing: list[Row] = field(default_factory=list)
    truncated: bool = False

    def add(self, kind: str, ref: str | None, value: Any) -> None:
        if value is None:
            self.missing.append({"kind": kind, "id": ref})
            return
        kept = _public_only(value, self.withheld)
        if kept is None:
            return
        self.records[kind if ref is None else f"{kind}:{ref}"] = kept
        self.loaded.append({"kind": kind, "id": ref})

    def snapshot(self) -> Row:
        return {"loaded": self.loaded, "withheld": self.withheld, "missing": self.missing,
                "truncated": self.truncated}


def _record_id(value: Row) -> str | None:
    for key in ("id", "dataset_id", "episode_id", "experiment_id", "evaluation_id"):
        if isinstance(value.get(key), str):
            return str(value[key])
    return None


def _public_only(value: Any, withheld: list[Row]) -> Any:
    """`value` without any record whose `data_class` is not public (R6); None if it is one."""
    if isinstance(value, dict):
        data_class = value.get("data_class")
        if data_class is not None and data_class != "public":
            withheld.append({"id": _record_id(value), "data_class": data_class})
            return None
        return {k: kept for k, v in value.items()
                if (kept := _public_only(v, withheld)) is not None or v is None}
    if isinstance(value, list):
        return [kept for v in value if (kept := _public_only(v, withheld)) is not None]
    return value


def _sample(rows: list[Row] | None, n: int = 20) -> list[Row] | None:
    return None if rows is None else rows[:n]


def _screen_loaders(model: ReadModel) -> dict[str, Callable[[Context], None]]:
    """What each screen contributes when no record is selected. M3 adds nothing (R8)."""

    def m1(c: Context) -> None:
        c.add("recommendations", None, model.recommendations())
        c.add("evaluations", None, model.evaluations(AGENT_ROLE))
        c.add("datasets", None, model.datasets())

    return {
        "M1": m1,
        "M2": lambda c: c.add("datasets", None, model.datasets()),
        "M3": lambda c: None,
        "M4": lambda c: c.add("releases", None, model.releases()),
        "M5": lambda c: c.add("experiments", None, model.experiments()),
        "M6": lambda c: c.add("evaluations", None, model.evaluations(AGENT_ROLE)),
        "M7": lambda c: c.add("recommendations", None, model.recommendations()),
        "M8": lambda c: c.add("cost_by_branch", None, model.cost_by_branch()),
        "M9": lambda c: c.add("he_curve", None, model.he_curve(AGENT_ROLE)),
        "M10": lambda c: c.add("decisions", None, model.decisions()[:30]),
    }


def build_context(model: ReadModel, screen: str, focus: Row) -> Context:
    """The records of `screen` and of the selected record, as `agent_ro` would read them."""
    c = Context()
    if screen != "M3":  # group S and the scoreboard derived from it are not the agent's (R8)
        if ref := focus.get("dataset_id"):
            c.add("dataset", ref, model.dataset(ref))
            c.add("dataset_report", ref, model.report(ref))
            c.add("dataset_stages", ref, model.stages(ref))
            c.add("dataset_episodes", ref, _sample(model.episodes(ref)))
        if ref := focus.get("experiment_id"):
            c.add("experiment", ref,
                  next((x for x in model.experiments() if x["experiment_id"] == ref), None))
            c.add("train_diagnoses", ref, model.diagnoses(ref))
            c.add("probes", ref, model.probes(ref))
            c.add("checkpoints", ref, model.checkpoints(ref))
        if ref := focus.get("evaluation_id"):
            c.add("evaluation", ref, model.evaluation(ref, AGENT_ROLE))
            c.add("funnel", ref, model.funnel(ref, AGENT_ROLE))
            c.add("failures", ref, model.failures(ref, AGENT_ROLE))
            c.add("system_checks", ref, _sample(model.system_checks(ref, AGENT_ROLE)))
        if ref := focus.get("recommendation_id"):
            c.add("recommendation", ref, model.recommendation(ref))
            c.add("algo_steps", ref, model.steps(ref))
            c.add("clusters", ref, model.clusters(ref))
            c.add("repair_tickets", ref, model.repair_tickets(ref))
        if ref := focus.get("cluster_id"):
            c.add("cluster_card", ref, model.card(ref))
    if not c.loaded and not c.missing:
        _screen_loaders(model)[screen](c)
    return c


def build_prompt(context: Context, screen: str, history: list[Row],
                 question: str) -> list[Message]:
    block = json.dumps(context.records, ensure_ascii=False, sort_keys=True, default=str)
    if len(block) > CONTEXT_CHARS:
        block = block[:CONTEXT_CHARS] + " …(cắt)"
        context.truncated = True
    head = (f"MÀN HÌNH: {screen}\n"
            f"WITHHELD: {json.dumps(context.withheld, ensure_ascii=False)}\n"
            f"KHÔNG THẤY: {json.dumps(context.missing, ensure_ascii=False)}\n"
            f"NGỮ CẢNH:\n{block}")
    messages: list[Message] = [{"role": "system", "content": SYSTEM_PROMPT},
                               {"role": "system", "content": head}]
    for turn in history[-2 * HISTORY_TURNS:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": question})
    return messages


def prompt_sha256(messages: Sequence[Message]) -> str:
    canonical = json.dumps(list(messages), ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- store


def _check_context(body: Row) -> tuple[str, Row]:
    screen = body.get("screen")
    if screen not in SCREENS:
        raise ChatError(422, "BAD_SCREEN", f"screen {screen!r} không có; chỉ {list(SCREENS)}")
    focus = body.get("focus") or {}
    if not isinstance(focus, dict):
        raise ChatError(422, "BAD_FOCUS", "focus phải là đối tượng")
    unknown = sorted(set(focus) - set(CONTEXT_KEYS))
    if unknown:
        raise ChatError(422, "BAD_FOCUS", f"focus không nhận {unknown}; chỉ {list(CONTEXT_KEYS)}")
    if not all(v is None or isinstance(v, str) for v in focus.values()):
        raise ChatError(422, "BAD_FOCUS", "mỗi giá trị focus là chuỗi hoặc null")
    return str(screen), {k: v for k, v in focus.items() if v}


@dataclass
class ChatStore:
    directory: Path
    model: ReadModel
    chat_model: ChatModel | None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def sessions_path(self) -> Path:
        return self.directory / "agent_chat_sessions.jsonl"

    @property
    def messages_path(self) -> Path:
        return self.directory / "agent_chat_messages.jsonl"

    def _session(self, session_id: str) -> Row | None:
        return next((s for s in log.read_lines(self.sessions_path) if s["id"] == session_id),
                    None)

    def _messages(self, session_id: str) -> list[Row]:
        return [m for m in log.read_lines(self.messages_path) if m["session_id"] == session_id]

    def create_session(self, body: Row, user_role: str) -> Row:
        screen, focus = _check_context(body)
        title = str(body.get("title") or "").strip()[:255] or None
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            count = len(log.read_lines(self.sessions_path))
            row: Row = {
                "id": f"chs_{count + 1:04d}", "user_role": user_role, "title": title,
                "screen": screen,
                **{f"context_{k}": focus.get(k) for k in CONTEXT_KEYS},
                "created_at": log.now_iso(), "closed_at": None,
            }
            log.append(self.sessions_path, [row])
        return {**row, "messages": []}

    def session(self, session_id: str) -> Row | None:
        row = self._session(session_id)
        return None if row is None else {**row, "messages": self._messages(session_id)}

    def ask(self, session_id: str, body: Row) -> Row:
        session = self._session(session_id)
        if session is None:
            raise ChatError(404, "NOT_FOUND", "phiên chat không tồn tại")
        question = str(body.get("content") or "").strip()
        if not question:
            raise ChatError(422, "EMPTY_MESSAGE", "câu hỏi rỗng")
        if len(question) > MAX_QUESTION_CHARS:
            raise ChatError(422, "MESSAGE_TOO_LONG", f"câu hỏi dài quá {MAX_QUESTION_CHARS} ký tự")
        if self.chat_model is None:
            raise ChatError(503, "CHAT_MODEL_UNAVAILABLE", "API chạy không kèm model chat",
                            "khởi động lại API với --chat-url của máy chạy model (Ollama, vLLM)")
        focus = {k: session[f"context_{k}"] for k in CONTEXT_KEYS if session.get(f"context_{k}")}
        context = build_context(self.model, session["screen"], focus)
        prompt = build_prompt(context, session["screen"], self._messages(session_id), question)
        digest = prompt_sha256(prompt)
        answer = self.chat_model.complete(prompt)  # outside the lock: it may take a minute
        snapshot = {**context.snapshot(), "screen": session["screen"]}
        with self._lock:
            count = len(log.read_lines(self.messages_path))
            now = log.now_iso()
            base: Row = {"session_id": session_id, "attachments": [], "proposed_action": None,
                    "confirmed_action_id": None, "created_at": now}
            user: Row = {**base, "id": count + 1, "role": "user", "content": question,
                    "context_snapshot": {}, "prompt_sha256": None, "model": None}
            assistant: Row = {**base, "id": count + 2, "role": "assistant", "content": answer,
                         "context_snapshot": snapshot, "prompt_sha256": digest,
                         "model": self.chat_model.name}
            log.append(self.messages_path, [user, assistant])
        return {"user": user, "assistant": assistant}

# ruff: noqa: E501, UP031  (ported prompt, guard-regex and tool-schema strings stay on one line)
"""Chat backend: Nemotron over the loopback ssh tunnel by default, tools in ``registry``.

``events(body)`` yields ``(event, data)`` pairs; ``stream(body)`` yields them as SSE bytes for
the HTTP server. Guardrails live in code: per-turn caps, no tool that can train or write,
GPU-busy fallback, and a request filter for the actions the console never performs. The model
may be another server (``providers``); when it is hosted, the turn runs with ``common.HOSTED``
set before anything is built, so the tools see public rows only, the local-only tools are not
offered, and earlier answers stay out of the history sent. Traces go to
``<fw_root>/console/chat/<date>.jsonl``.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Collection, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from flywheel.console.paths import active
from flywheel.console.server import runner

from . import providers, registry, tools_round
from .common import HOSTED, UNREADABLE, ManifestUnreadable, fail, hidden_runs, withheld_runs
from .numbers import numbers_in, unsupported_numbers
from .tools_ops import all_jobs

ENDPOINT = "http://127.0.0.1:11435"
LOOPBACK_PORT = 11435
MODEL = runner.AGENT_MODEL
NUM_CTX = 16384
KEEP_ALIVE = "30m"
MAX_ROUNDS = 3
NUM_PREDICT = 640
TURN_CAP_S = 45.0  # 20 s until 16/11/2026: an analysis answer (three parts) needs more than a lookup
DEEP_ROUNDS = 5
DEEP_PREDICT = 2000  # about 400 words in five parts; 1,280 until 28/11/2026
DEEP_CAP_S = 85.0  # a model on this machine or the tunnel
DEEP_CAP_HOSTED_S = 150.0  # a hosted model: Opus 5.5 needed 96 s for one deep turn (audit 28/11/2026)
# A generation must START before the turn cap; once started it may stream until the cap plus
# this grace, so an answer already on screen is not cut into an error (Website, 28/11/2026: a
# two-round answer of a hosted model finished just past 45 s)
STREAM_GRACE_S = 60.0
HTTP_TIMEOUT_S = 30.0
TUNNEL_WAIT_S = 8.0
MAX_CALLS_PER_ROUND = 3

SYSTEM = (
    "You are the analysis assistant of the Flywheel Console, a robot-learning data flywheel dashboard. "
    "For any question about datasets, episodes, QA, runs, eval, rounds, loop, jobs, findings or cost, call a tool first and never answer from memory. "
    "Pass IDs exactly as the user wrote them. Do not explain before calling a tool, and never write your plan or the name of a tool in the answer. "
    "For a lookup question (how many, which, list, show) about one dataset, run or job, answer in the user's language in at most 60 words, plain text, no tables. "
    "For a question about the results of a round, whether a mark is met, where the robot fails, the cost of the round, why, or what to do next, call round_report; "
    "for failure groups and system checks call round_diagnosis; for the confidence intervals of the paired comparisons call pair_comparisons; for egocentric or human-video clips as a whole call ego_summary. "
    "Their result is already written in the user's language: open with its DIRECT ANSWER sentence, reuse its sentences word for word instead of rewording figures, and follow its HOW TO ANSWER line. Keep it short, about 150 to 200 words, plain text; do not count words.  Never copy the upper-case headings of the tool result. "
    "Name the round once at the start and the run next to each number; every number then belongs to that round unless you name another. Never give a number of one round for another round. "
    "Compare with a control only when the tool says the conditions are the same; otherwise put the numbers side by side and say why they cannot be compared. "
    "Say which interval is the bootstrap CI the rules read and which is descriptive only. Keep measured and estimated cost apart. Say what has not been checked. "
    "For a result that is not presented, write only the sentence the tool gives; never confirm or deny a figure the user offers for it. "
    "Cite only numbers that appear in the tool results. End an answer about a round with one short line naming the source the tool result gives (Nguồn: … / Source: …). "
    "Never claim to change a QA status, start a job, train a model or read holdout data. "
    "If the question is not about this console's data, say so in one short sentence and call no tool."
)

DEEP = (
    " Mode: DEEP ANALYSIS. round_report for the selected round is already read. Call round_diagnosis or pair_comparisons only when they add to the answer. "
    "Then write about 400 words in the user's language, in five parts with short bold headings: {parts}. "
    "Numbers: the direct answer and the readings against the rules. Controls: what each number is compared with and whether the conditions are the same. "
    "Limits: seeds, simulation, what has not been checked. Next steps: the options of the tool result, as proposals. Sources: the documents the tool results name. "
    "Cite only verified tool numbers."
)
DEEP_PARTS = {"Vietnamese": "Số liệu / Đối chứng / Giới hạn / Việc nên làm / Nguồn",
              "English": "Numbers / Controls / Limits / Next steps / Sources"}  # fmt: skip

FORCE_ANSWER = (
    "Stop looking things up. Write the answer now in {lang}, plain text, briefly, "
    "using only the tool results above. If they do not answer the question, say what is missing."
)

VI = re.compile(
    r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]|"
    r"\b(tap|cua|bao nhieu|cho toi|hien|loi|chay|xem|nao|khong|sao|the nao|nhung|duoc)\b",
    re.I,
)

# Requests the console never performs. Matched in code before any model call.
GUARDS = [
    ("training", re.compile(r"\b(start|launch|kick ?off|begin|run|bắt đầu|chạy|khởi động)\s+(a\s+|the\s+|new\s+)?(train(ing)?|fine-?tun\w*|huấn luyện)\b|"
                            r"\b(re-?train|fine-?tune|train|huấn luyện)\s+(c\+|c-?plus|c_?(70|all)|b_?70|b|c|the model|model|policy|it|now|lại|ngay|đi)\b", re.I),
     "Training is not available from the console: it starts only from a RunPlan that Hiếu launches.",
     "Chat không khởi động train được: train chỉ chạy từ RunPlan do Hiếu khởi động."),
    ("holdout", re.compile(r"\b(read|show|open|print|dump|list|load|give me|access|fetch|export|đọc|xem|mở|in ra|liệt kê|lấy|truy cập|tải|xuất)\b.{0,40}\b(vault|hold-?out)\b|"
                           r"\b(vault|hold-?out)\b.{0,30}\b(rows?|samples?|files?|episodes?|contents?|mẫu|tập|file|nội dung)\b.{0,20}\b(show|list|print|read|xem|liệt kê|đọc|in ra)\b", re.I),
     "Holdout and vault data are not readable here: only the gate module reads them (fw holdout run).",
     "Không đọc được holdout hay vault: chỉ module gate đọc (fw holdout run)."),
    ("shell", re.compile(r"\brm\s+-|\bsudo\b|\bchmod\b|\bmkfs\b|\bdd\s+if=|\bkill\s+-9|(run|execute|exec|chạy|thực thi)\s+(a\s+|this\s+)?(shell|bash|command|lệnh|script)\b|\|\s*(ba)?sh\b", re.I),
     "No shell access: the console only runs its allowlisted fw jobs, and only after a human confirms.",
     "Không có quyền shell: console chỉ chạy các job fw trong allowlist, sau khi người xác nhận."),
    ("hosted_api", re.compile(r"(send|forward|paste|ask|share|upload|gửi|chuyển|hỏi|dán).{0,40}\b(gpt\S*|openai|chatgpt|gemini|claude|anthropic|hosted|external api|cloud api|api ngoài)\b", re.I),
     "Data never leaves the machine: the chat model runs on a machine of the team.",
     "Dữ liệu không rời máy: model chat chạy trên máy của đội."),
    ("qa_status", re.compile(r"\b(mark|set|change|flip|override|force|đánh dấu|chuyển|sửa|đổi)\b.{0,40}\b(as\s+)?(pass|flag|reject)\b|\bqa status\b.{0,20}\b(to|thành)\b", re.I),
     "QA status comes only from the rule layer; chat cannot change it. Overrides go through agentqa.review with a reason.",
     "Trạng thái QA chỉ do tầng luật quyết định; chat không đổi được. Muốn ghi đè phải qua agentqa.review kèm lý do."),
    ("upload", re.compile(r"\b(upload|push|publish|share|post|đăng|tải lên|đưa lên)\b.{0,60}\b(hugging ?face|\bhf\b|google drive|drive|s3|github|public|online|external|bên ngoài|công khai)\b", re.I),
     "Raw team video is internal data and is never uploaded outside; only de-identified public releases leave the machine.",
     "Video thô của đội là dữ liệu nội bộ, không được tải ra ngoài; chỉ bản phát hành đã che danh tính mới rời máy."),
]  # fmt: skip


# A question that weighs an action ("should we retrain?", "có nên huấn luyện lại không?") is an
# analysis question, not a request: only a request to act trips the training guard (A5)
ADVISORY = re.compile(r"\b(có nên|nên|liệu|có cần|vì sao|tại sao|khi nào|bao giờ|có đáng|should|would it|is it worth|worth it|do we need|why|when|whether)\b", re.I)


def guard_check(question: str, prov: providers.Provider | None = None) -> tuple[str | None, str | None]:
    """The guard a question trips and its refusal, worded for the model that answers ``prov``."""
    for name, rx, en, vi in GUARDS:
        if name == "training" and ADVISORY.search(question):
            continue
        if rx.search(question):
            if name == "hosted_api" and prov is not None and prov.hosted:
                en = (f"The console sends no data to an outside service on request. The model answering now ({prov.name}) "
                      "is hosted, so the tools hand it public rows only.")
                vi = (f"Console không gửi dữ liệu ra dịch vụ ngoài theo yêu cầu. Model đang trả lời ({prov.name}) "
                      "là model hosted nên các tool chỉ đưa cho nó dữ liệu public.")  # fmt: skip
            return name, (vi if VI.search(question) else en)
    return None, None


def endpoint_ok(url: str | None = None) -> bool:
    """True only for plain http to 127.0.0.1 on the tunnel port."""
    u = urllib.parse.urlparse(url or ENDPOINT)
    return u.scheme == "http" and u.hostname == "127.0.0.1" and u.port == LOOPBACK_PORT


def provider() -> providers.Provider:
    """The model that answers: Nemotron over the tunnel, or the server ``FW_CHAT_BASE_URL`` names."""
    return providers.active(ENDPOINT, MODEL)


def needs_tunnel(p: providers.Provider) -> bool:
    return p.loopback and p.port == LOOPBACK_PORT


def lang_of(q: str) -> str:
    return "Vietnamese" if VI.search(q) else "English"


# ------------------------------------------------------------------ number grounding
def ground(answer: str, evidence_texts: list[str]) -> list[dict[str, Any]]:
    """[{text, grounded}] for every numeral of the answer, matched against the turn's evidence."""
    ev = [t for t in evidence_texts if t]
    return [
        {"text": tok, "grounded": not unsupported_numbers(tok, ev)} for tok in numbers_in(answer)
    ]


# ------------------------------------------------------------------ model status
def _get(path: str, timeout: float = 2.5) -> Any:
    with runner.LOOPBACK.open(ENDPOINT + path, timeout=timeout) as r:
        return json.load(r)


def gpu_busy() -> str | None:
    """Job id of a running or queued ego.annotate (RoboBrain holds the GPU), else None."""
    for j in all_jobs():
        if j.get("state") in ("running", "queued") and (
            j.get("kind") == "ego.annotate"
            or (j.get("kind") == "ego.pipeline" and (j.get("params") or {}).get("annotate"))
        ):
            return str(j["id"])
    return None


def nemotron_status() -> str:
    p = provider()
    if p.kind in ("openai", "anthropic") and not needs_tunnel(p):
        return "down" if providers.problem(p) else "warm"  # nothing to load: ready when configured
    if runner.TUNNEL.tags() is None:
        return "down"
    if gpu_busy():
        return "busy"
    try:
        loaded = [m.get("name") for m in _get("/api/ps").get("models", [])]
    except Exception:
        return "cold"
    return "warm" if MODEL in loaded else "cold"


def prewarm() -> dict[str, Any]:
    p = provider()
    if p.kind in ("openai", "anthropic") and not needs_tunnel(p):
        why = providers.problem(p)
        return {"ok": not why, "nemotron": nemotron_status(), "error": why, "ms": 0}
    if runner.TUNNEL.tags() is None and not runner.TUNNEL.ensure(10):
        return {"ok": False, "nemotron": "down", "error": "tunnel down"}
    busy = gpu_busy()
    if busy:
        return {"ok": False, "nemotron": "busy", "error": f"GPU busy: {busy} annotate"}
    t0 = time.time()
    body = json.dumps({"model": MODEL, "prompt": "", "keep_alive": KEEP_ALIVE, "stream": False,
                       "options": {"num_ctx": NUM_CTX}}).encode()  # fmt: skip
    req = urllib.request.Request(
        ENDPOINT + "/api/generate", body, {"Content-Type": "application/json"}
    )
    try:
        runner.LOOPBACK.open(req, timeout=90).read()
    except Exception as e:
        return {"ok": False, "nemotron": nemotron_status(), "error": str(e)}
    return {"ok": True, "nemotron": nemotron_status(), "ms": int((time.time() - t0) * 1000)}


# ------------------------------------------------------------------ traces
def _trace_files() -> list[Path]:
    d = active().chat
    return sorted(d.glob("2*.jsonl"), reverse=True) if d.is_dir() else []


def save_trace(tr: dict[str, Any]) -> None:
    d = active().chat
    d.mkdir(parents=True, exist_ok=True)
    with open(d / (datetime.now().strftime("%Y-%m-%d") + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(tr, ensure_ascii=False) + "\n")


def _plain(ln: str) -> str:
    """A stored trace line as JSON text without \\u escapes ("run nào" must not read as "run n")."""
    try:
        return json.dumps(json.loads(ln), ensure_ascii=False)
    except ValueError:
        return ln


def list_traces(limit: int = 20, hide: Collection[str] = ()) -> list[dict[str, Any]]:
    """The newest turns; a turn that names a run in ``hide`` (held results) is left out, and so
    is a turn naming a run in ``withhold_runs`` (``hidden.Hidden.mentions``). No turn is listed
    while the seed cannot say which runs those are."""
    try:
        gone = hidden_runs()
    except ManifestUnreadable:
        return []
    out: list[dict[str, Any]] = []
    for f in _trace_files():
        for ln in reversed(f.read_text(encoding="utf-8").splitlines()):
            if any(h in ln for h in hide) or gone.mentions(_plain(ln)):
                continue
            try:
                t = json.loads(ln)
            except ValueError:
                continue
            out.append({
                "turn_id": t["turn_id"], "conversation_id": t.get("conversation_id"), "ts": t.get("ts"),
                "question": t.get("question"),
                "tools": [n["name"] for n in t.get("nodes", []) if n.get("type") == "tool"],
                "ms_total": t.get("ms_total"), "tokens_in": t.get("tokens_in"),
                "tokens_out": t.get("tokens_out"), "error": t.get("error"), "guard": t.get("guard"),
                "round": t.get("round"), "cost": t.get("cost"),
            })  # fmt: skip
            if len(out) >= limit:
                return out
    return out


def latest_bench() -> dict[str, Any] | None:
    """Newest ``bench-*.json`` as {time, n, tool_acc, arg_acc, guardrail, grounded_rate, ...}."""
    d = active().chat
    fs = sorted(d.glob("bench-*.json")) if d.is_dir() else []

    def ratio(p: list[int]) -> float | None:
        return round(p[0] / p[1], 4) if p[1] else None

    for f in reversed(fs):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))["summary"]
            if not s.get("n") or s["latency_p50_s"] == 0:
                continue  # a run that never reached the model
            return {
                "time": s["time"], "n": s["n"], "tool_acc": ratio(s["tool_accuracy"]),
                "arg_acc": ratio(s["arg_accuracy"]),
                "guardrail": {"pass": s["guardrail_pass"][0], "n": s["guardrail_pass"][1]},
                "grounded_rate": ratio(s["grounded_numbers"]),
                "p50_ms": int(s["latency_p50_s"] * 1000), "p95_ms": int(s["latency_p95_s"] * 1000),
                "by_group": {g: {"ok": v[0], "n": v[1]} for g, v in s["by_group"].items()},
                "file": f.name,
            }  # fmt: skip
        except (OSError, ValueError, KeyError, IndexError):
            continue
    return None


def get_trace(turn_id: str, hide: Collection[str] = ()) -> dict[str, Any] | None:
    try:
        gone = hidden_runs()  # a hidden run's id ("N") cannot be tested as a substring
    except ManifestUnreadable:
        return None
    for f in _trace_files():
        for ln in f.read_text(encoding="utf-8").splitlines():
            if turn_id in ln and not any(h in ln for h in hide) and not gone.mentions(_plain(ln)):
                try:
                    t = json.loads(ln)
                except ValueError:
                    continue
                if t.get("turn_id") == turn_id:
                    return t  # type: ignore[no-any-return]
    return None


# ------------------------------------------------------------------ the turn
def build_messages(
    body: dict[str, Any], context: dict[str, Any]
) -> tuple[list[dict[str, Any]], str]:
    hist = [
        m
        for m in body.get("messages", [])
        if m.get("role") in ("user", "assistant") and str(m.get("content") or "").strip()
    ]
    q = hist[-1]["content"] if hist and hist[-1]["role"] == "user" else ""
    d = registry.context_defaults(context)
    d.pop("question", None)
    ctxline = "Current page: %s." % (context.get("route") or "home")
    if d:
        ctxline += (
            " Defaults for words like 'this/here/tập này/run này/vòng này': "
            + ", ".join("{}={}".format(*kv) for kv in d.items())
            + "."
        )
    try:  # the round the user looks at, so every number is tied to it (A14)
        rline = tools_round.round_context(context.get("task"), context.get("round"), q)
    except Exception:
        rline = ""
    if rline:
        ctxline += " " + rline
    mode = str(body.get("mode") or "ask").strip().lower()
    sys_prompt = SYSTEM
    if mode == "investigate":
        sys_prompt += DEEP.format(parts=DEEP_PARTS[lang_of(str(q))])
    elif mode == "operate":
        sys_prompt += (
            " Mode: OPERATE. Help the user inspect jobs, pipelines, and prepare allowlisted workflow "
            "actions or navigation links while strictly respecting all safety guardrails."
        )
    msgs: list[dict[str, Any]] = [{"role": "system", "content": sys_prompt + " " + ctxline}]
    prev = hist[:-1]
    users = [i for i, m in enumerate(prev) if m["role"] == "user"]
    keep_from = users[-4] if len(users) >= 4 else 0
    for i, m in enumerate(prev):
        if m["role"] == "assistant" and (i < keep_from or HOSTED.get()):
            # older answers reduced to the question; a hosted model gets no earlier answer at
            # all, since a local model may have written it from rows that are not public
            continue
        msgs.append({"role": m["role"], "content": str(m["content"])[:600]})
    msgs.append({"role": "user", "content": str(q)[:1500]})
    return msgs, str(q)


def _chunks(resp: Any, deadline: float) -> Iterator[dict[str, Any]]:
    """Yield parsed ndjson objects of an Ollama stream; stop at the deadline.

    The turn cap is checked between reads, so a read that blocks is bounded by the socket
    timeout of the request (``HTTP_TIMEOUT_S``), not by the deadline itself.
    """
    buf = b""
    while True:
        if time.time() > deadline:
            raise TimeoutError("turn cap reached")
        b = resp.read1(4096) if hasattr(resp, "read1") else resp.read(1)
        if not b:
            break
        buf += b
        while b"\n" in buf:
            ln, buf = buf.split(b"\n", 1)
            if ln.strip():
                yield json.loads(ln)


# a call in text form: the model's special-token markup, or a bare ``name{...}`` at the very start
# (seen 16/11/2026: ``round_report{task:<|"|>tray<|"|>}`` without the opening token)
_MARK = re.compile(r"<\||<tool_call|^\s*(?:call:)?[a-z_]{3,}\{")


def _maybe_call_start(raw: str) -> bool:
    """True while the text so far could still grow into a bare ``name{`` call: do not show it yet."""
    head = raw.strip().removeprefix("call:")
    return bool(head) and head.replace("_", "").isalpha() and any(n.startswith(head) for n in registry.TOOLS)

_CALL = re.compile(r"call:(\w+)\{(.*?)\}\s*(?:<tool_call\|>|$)", re.S)
_ARG = re.compile(r'(\w+)\s*:\s*(?:<\|"\|>(.*?)<\|"\|>|"([^"]*)"|([^,}]*))', re.S)


def parse_markup_calls(text: str) -> list[dict[str, Any]]:
    """Text form ``<|tool_call>call:NAME{k:<|"|>v<|"|>,n:3}<tool_call|>`` -> [{name, arguments}]."""
    calls: list[dict[str, Any]] = []
    for m in _CALL.finditer(text):
        args: dict[str, Any] = {}
        for a in _ARG.finditer(m.group(2)):
            v: Any = (
                a.group(2)
                if a.group(2) is not None
                else a.group(3)
                if a.group(3) is not None
                else (a.group(4) or "").strip()
            )
            if a.group(2) is None and a.group(3) is None:
                try:
                    v = int(v)
                except ValueError:
                    try:
                        v = float(v)
                    except ValueError:
                        v = {"true": True, "false": False}.get(str(v).lower(), v)
            args[a.group(1)] = v
        calls.append({"name": m.group(1), "arguments": args})
    return calls


def generate(
    messages: list[dict[str, Any]],
    tool_schemas: list[dict[str, Any]] | None,
    deadline: float,
    max_tokens: int = NUM_PREDICT,
) -> Iterator[tuple[str, Any]]:
    """One streamed /api/chat call. Yields ("tok"|"think", text) live, then ("end", (content, calls, tin, tout))."""
    p = provider()
    if p.kind in ("openai", "anthropic"):
        yield from providers.generate(p, messages, tool_schemas, deadline, max_tokens)
        return
    if not endpoint_ok():
        raise RuntimeError("model endpoint must be the loopback tunnel")
    remaining = deadline - time.time()
    if remaining <= 0.5:
        raise TimeoutError("turn cap reached")
    payload: dict[str, Any] = {
        "model": MODEL, "messages": messages, "stream": True, "think": False,
        "keep_alive": KEEP_ALIVE, "options": {"temperature": 0, "num_ctx": NUM_CTX, "num_predict": NUM_PREDICT},
    }  # fmt: skip
    if tool_schemas:
        payload["tools"] = tool_schemas
    req = urllib.request.Request(
        ENDPOINT + "/api/chat", json.dumps(payload).encode(), {"Content-Type": "application/json"}
    )
    raw, sent, tin, tout = "", 0, 0, 0
    calls: list[dict[str, Any]] = []
    with runner.LOOPBACK.open(req, timeout=min(remaining, HTTP_TIMEOUT_S)) as resp:
        for ch in _chunks(resp, deadline):
            m = ch.get("message") or {}
            if m.get("content"):
                raw += m["content"]
                mk = _MARK.search(raw)
                if mk:
                    safe = mk.start()
                else:  # hold back a tail that could still grow into a special token
                    lt = raw.rfind("<")
                    safe = lt if lt >= max(sent, len(raw) - 12) else len(raw)
                if safe > sent and not _maybe_call_start(raw):
                    yield "tok", raw[sent:safe]
                    sent = safe
            for tc in m.get("tool_calls") or []:
                calls.append(tc.get("function") or {})
            if ch.get("done"):
                tin, tout = ch.get("prompt_eval_count", 0), ch.get("eval_count", 0)
    mk = _MARK.search(raw)
    if mk:
        tail = raw[mk.start() :]
        if not tail.startswith("<"):  # the bare form: give it the prefix the parser reads
            tail = "call:" + tail.strip().removeprefix("call:")
        calls += [c for c in parse_markup_calls(tail) if c["name"] in registry.TOOLS or tail.startswith("<")]
        content = raw[: mk.start()]
    else:
        content = raw
        if len(raw) > sent:
            yield "tok", raw[sent:]
    yield "end", (content, calls, tin, tout)


def events(body: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    # the provider decides HOSTED before anything is built: the history, the tools offered and
    # every tool result of the turn depend on it; it is reset when the turn ends
    prov = provider()
    tok = HOSTED.set(prov.hosted)
    try:
        yield from _turn(body, prov)
    finally:
        try:
            HOSTED.reset(tok)
        except ValueError:
            pass  # closed from another context, which never saw the value set


# an answer that is the model's own plan instead of an answer (seen 28/11/2026, Fable 5:
# "... This is a 'why' type question — call round_report.")
_INTERNAL = re.compile(
    r"\b(round_report|round_diagnosis|pair_comparisons|ego_summary|run_list|eval_summary|loop_proposals|ledger_query)\b|"
    r"^\s*(the question|the user|user) (is|asks|wants|:)|\bthis is an? ['\"]?\w+['\"]?[ -]type question\b|"
    r"\b(i'?ll|i will|let me|need to|should|so) (call|check the tool|look up)\b",
    re.I,
)


def looks_internal(text: str) -> bool:
    """True for a reply that reads as the model's reasoning about tools, not an answer."""
    return bool(text.strip()) and bool(_INTERNAL.search(text))


def _turn(body: dict[str, Any], prov: providers.Provider) -> Iterator[tuple[str, dict[str, Any]]]:
    t0 = time.time()
    context = dict(body.get("context") or {})
    conv = body.get("conversation_id") or f"c-{os.urandom(4).hex()}"
    turn = "t-{}-{}".format(datetime.now().strftime("%Y%m%d-%H%M%S"), os.urandom(2).hex())
    msgs, question = build_messages(body, context)
    # which runs are held or hidden comes from the seed; unknown means no figures and no tool
    try:
        hidden_runs()
        withheld_runs()
        seed_ok = True
    except ManifestUnreadable:
        seed_ok = False
    # the round of the turn: one the question names, else the one chosen in the top bar; every
    # tool reads it and every number of the answer is checked against it (A2, A4)
    try:
        turn_round = tools_round.round_named(question, context.get("round")) or ""
    except Exception:
        turn_round = str(context.get("round") or "")
    if turn_round:
        context["round"] = turn_round
    mode = str(body.get("mode") or "ask").strip().lower()
    deep = mode == "investigate"
    names = registry.offered_names(context.get("route"), question) if seed_ok else []
    forced_all = registry.forced_tools(question) if seed_ok else []
    forced = forced_all[0] if forced_all else None
    if deep and seed_ok:
        # deep analysis always starts from the round's facts; the model may then look further,
        # but opens no page (A4, A14)
        extra = [n for n in names if n not in registry.ANALYSIS_TOOLS and n != "open_page"]
        names = [n for n in registry.ANALYSIS_TOOLS if registry.usable(n)] + extra
        names = names[: registry.MAX_OFFERED]
        prefetch = list(dict.fromkeys(["round_report", *forced_all]))
    else:
        prefetch = list(forced_all)
        names = [n for n in forced_all if n not in names] + names
    answer_only = bool(forced) and not deep  # the code makes the lookup; the model only writes
    tr: dict[str, Any] = {
        "turn_id": turn, "conversation_id": conv, "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": prov.model, "provider": prov.name, "hosted": prov.hosted, "question": question,
        "context": context, "round": turn_round or None, "mode": mode, "tools_offered": names,
        "tools_forced": list(prefetch), "nodes": [],
        "answer": "", "tokens_in": 0, "tokens_out": 0,
    }  # fmt: skip
    yield (
        "trace_start",
        {"conversation_id": conv, "turn_id": turn, "model": prov.model, "tools_offered": names,
         "tools_forced": list(prefetch), "round": turn_round or None},
    )

    def finish(event: str, data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        tr["ms_total"] = int((time.time() - t0) * 1000)
        try:
            save_trace(tr)
        except OSError:
            pass
        return event, data

    def refuse(code: str, message: str) -> tuple[str, dict[str, Any]]:
        tr["error"] = message
        return finish("error", {"code": code, "message": message + " Slash commands still work.", "fallback": "slash"})

    # 1. code-level guardrails (no model involved)
    why, refusal = guard_check(question, prov)
    if why:
        tr["guard"] = why
        tr["answer"] = refusal
        yield "token", {"text": refusal}
        yield finish("done", {"turn_id": turn, "ms_total": int((time.time() - t0) * 1000), "tokens_in": 0, "tokens_out": 0,
                              "numbers": [], "unverified": [], "guard": why, "round": turn_round or None})  # fmt: skip
        return
    # 1b. the seed cannot say which runs are held or hidden: a fixed answer, no model, no tool
    if not seed_ok:
        msg = UNREADABLE[0 if lang_of(question) == "Vietnamese" else 1]
        tr["guard"] = "manifest"
        tr["error"] = "seed/tasks.yaml unreadable"
        tr["answer"] = msg
        yield "token", {"text": msg}
        yield finish("done", {"turn_id": turn, "ms_total": int((time.time() - t0) * 1000), "tokens_in": 0, "tokens_out": 0,
                              "numbers": [], "unverified": [], "guard": "manifest", "round": turn_round or None})  # fmt: skip
        return
    # 1c. a run or story that is not presented (run N, DA-50): a scoped, true sentence that neither
    # confirms nor denies it; no model, no tool (same rule as W5)
    if tools_round.asks_hidden(question):
        msg = tools_round.NOT_PRESENTED[0 if lang_of(question) == "Vietnamese" else 1]
        tr["guard"] = "hidden"
        tr["answer"] = msg
        yield "token", {"text": msg}
        yield finish("done", {"turn_id": turn, "ms_total": int((time.time() - t0) * 1000), "tokens_in": 0, "tokens_out": 0,
                              "numbers": [], "unverified": [], "guard": "hidden", "round": turn_round or None})  # fmt: skip
        return
    # 2. GPU busy / tunnel down -> slash fallback (only when the model sits behind the tunnel)
    why_not = providers.problem(prov)
    if why_not:
        yield refuse("config", why_not)
        return
    busy = gpu_busy() if needs_tunnel(prov) else None
    if busy:
        tr["error"] = "gpu busy"
        yield finish("error", {"code": "busy", "message": f"GPU busy: {busy} annotate. Slash commands only.", "fallback": "slash"})
        return
    if needs_tunnel(prov) and runner.TUNNEL.tags() is None and not runner.TUNNEL.ensure(TUNNEL_WAIT_S):
        tr["error"] = "tunnel down"
        yield finish("error", {"code": "tunnel", "message": "Model tunnel to rtx3060 is down. Slash commands still work.", "fallback": "slash"})
        return
    max_rounds = DEEP_ROUNDS if deep else MAX_ROUNDS
    max_predict = DEEP_PREDICT if deep else NUM_PREDICT
    turn_cap = (DEEP_CAP_HOSTED_S if prov.hosted else DEEP_CAP_S) if deep else TURN_CAP_S
    keep_md = mode in ("investigate", "operate")
    deadline = t0 + turn_cap
    # evidence the numbers are checked against: the question, the page context, and the tool
    # results of the turn's round; a result tagged with another round counts apart (A2)
    evidence = [question] + ["{} {}".format(*kv) for kv in registry.context_defaults(context).items()]
    other_round: list[str] = []
    answer_parts: list[str] = []
    live: list[str] = []  # text streamed by the generation in progress (kept if the cap cuts it)
    nodes: list[dict[str, Any]] = tr["nodes"]
    lang = lang_of(question)
    tool_rounds = 0
    retried = False
    pending_calls: list[dict[str, Any]] = [{"name": n, "arguments": {}} for n in prefetch]
    tool_ctx = {**context, "lang": "vi" if lang == "Vietnamese" else "en", "question": question, "deep": mode == "investigate"}

    def _call_gen(m_list: list[dict[str, Any]], sch: list[dict[str, Any]] | None) -> Iterator[tuple[str, Any]]:
        if time.time() > deadline:
            raise TimeoutError("turn cap reached")  # no new generation starts after the cap
        stream_until = deadline + STREAM_GRACE_S  # one that started in time is not cut at the cap
        if max_predict == NUM_PREDICT:
            return generate(m_list, sch, stream_until)
        try:
            return generate(m_list, sch, stream_until, max_predict)
        except TypeError:  # test doubles with 3-arg signature (msgs, schemas, deadline)
            return generate(m_list, sch, stream_until)

    def _gen(m_list: list[dict[str, Any]], sch: list[dict[str, Any]] | None, md: bool) -> Iterator[tuple[str, dict[str, Any]]]:
        """Stream one generation; leaves (content, calls, tin, tout) in ``out``."""
        live.clear()
        for kind, val in _call_gen(m_list, sch):
            if kind == "think":
                yield "thinking", {"text": val}
            elif kind == "tok":
                t = val if md else val.replace("**", "")
                live.append(t)
                yield "token", {"text": t}
            elif kind == "cost":
                tr["cost"] = round(float(tr.get("cost") or 0) + float(val or 0), 6)
            elif kind == "end":
                out[:] = list(val)
        live.clear()

    out: list[Any] = ["", [], 0, 0]
    try:
        for rnd in range(max_rounds + 1):
            offered = registry.schemas(context.get("route"), names) if rnd < max_rounds and not answer_only else None
            g0 = time.time()
            content, tin, tout = "", 0, 0
            tcalls: list[dict[str, Any]] = []
            by_code = bool(pending_calls)
            if pending_calls:
                tcalls, pending_calls = pending_calls, []
            else:
                out[:] = ["", [], 0, 0]
                yield from _gen(msgs, offered, keep_md)
                content, tcalls, tin, tout = out
                if not keep_md:
                    content = content.replace("**", "")
                if offered is None:
                    tcalls = []  # no tool is offered now: a call written as text is not run
                if not tcalls and looks_internal(content) and not retried:
                    # the model wrote its plan instead of an answer: drop it and try once more,
                    # with the lookup made by the code (A9)
                    retried = True
                    yield "retract", {"reason": "internal"}
                    nodes.append({"type": "generation", "round": rnd, "ms": int((time.time() - g0) * 1000), "tokens_in": tin,
                                  "tokens_out": tout, "content": content[:500], "tool_calls": [], "dropped": "internal"})  # fmt: skip
                    tr["tokens_in"] += tin
                    tr["tokens_out"] += tout
                    if tool_rounds:
                        msgs.append({"role": "user", "content": FORCE_ANSWER.format(lang=lang)})
                    else:
                        named = next((n for n in registry.ANALYSIS_TOOLS if n in content and registry.usable(n)), None)
                        pending_calls = [{"name": named or forced or "round_report", "arguments": {}}]
                        prefetch.append(pending_calls[0]["name"])  # made by the code: allowed on any page
                    answer_only = True
                    continue
            nodes.append(
                {
                    "type": "generation", "round": rnd, "ms": int((time.time() - g0) * 1000), "tokens_in": tin,
                    "tokens_out": tout, "content": content[:500], "tool_calls": tcalls, **({"by_code": True} if by_code else {}),
                }
            )  # fmt: skip
            tr["tokens_in"] += tin
            tr["tokens_out"] += tout
            if not tcalls or rnd == max_rounds:
                # the last round offers no tools: calls parsed from text markup are ignored too
                if content.strip():
                    answer_parts.append(content)
                break
            # a round that asks for tools: run them; any preamble text is dropped
            tool_rounds += 1
            used = tcalls[:MAX_CALLS_PER_ROUND]
            msgs.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": c.get("name"), "arguments": c.get("arguments") or {}}}
                        for c in used
                    ],
                }
            )
            seen: set[tuple[str, str]] = set()
            fixed = ""
            for i, c in enumerate(used):
                name, args = c.get("name") or "", c.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                key = (name, json.dumps(args, sort_keys=True))
                cid = "call_%d_%d" % (rnd, i)
                yield "tool_start", {"call_id": cid, "name": name, "args": args}
                k0 = time.time()
                if name not in names and name not in prefetch:
                    res = fail(f"Tool '{name}' is not offered on this page.")
                elif key in seen:
                    res = fail("Duplicate call ignored.")
                else:
                    res = registry.call(name, args, tool_ctx)
                seen.add(key)
                ms = int((time.time() - k0) * 1000)
                res_round = res.get("round")
                if res_round and turn_round and res_round != turn_round:
                    other_round.append(res["model"])
                else:
                    evidence.append(res["model"])
                nodes.append(
                    {
                        "type": "tool", "call_id": cid, "name": name, "args": args, "ms": ms, "ok": res["ok"],
                        "model_text": res["model"], "ui": res["ui"], "navigate": res.get("navigate"),
                        **({"round": res_round} if res_round else {}), **({"by_code": True} if by_code else {}),
                    }
                )  # fmt: skip
                ev: dict[str, Any] = {"call_id": cid, "name": name, "ms": ms, "ok": res["ok"], "ui": res["ui"], "model_chars": len(res["model"])}
                if res_round:
                    ev["round"] = res_round
                if res.get("navigate"):
                    ev["navigate"] = res["navigate"]
                yield "tool_result", ev
                msgs.append({"role": "tool", "tool_name": name, "content": res["model"]})
                if res.get("answer"):
                    fixed = str(res["answer"])  # the tool's own answer, shown as it stands
            if fixed:
                answer_parts.append(fixed)
                yield "token", {"text": fixed}
                break
            msgs[-1]["content"] += (
                f"\n[Answer the user now in {lang}, briefly. Use only numbers shown above. "
                "Name the round once and the run next to each number. Do not call more tools unless a different lookup is clearly needed.]"
            )
        if not answer_parts and tool_rounds:
            # the model spent every round on lookups, or asked for one more on the round that
            # offers none: ask once more, as the user, for the answer from what it already has
            msgs.append({"role": "user", "content": FORCE_ANSWER.format(lang=lang)})
            g0 = time.time()
            out[:] = ["", [], 0, 0]
            yield from _gen(msgs, None, keep_md)
            content, tcalls, tin, tout = out
            nodes.append({"type": "generation", "round": max_rounds + 1, "ms": int((time.time() - g0) * 1000), "tokens_in": tin,
                          "tokens_out": tout, "content": content[:500], "tool_calls": tcalls, "forced": True})  # fmt: skip
            tr["tokens_in"] += tin
            tr["tokens_out"] += tout
            if content.strip() and not looks_internal(content):
                answer_parts.append(content)
    except TimeoutError:
        # the cap cut the turn: say so, keep what was written, and record it as an error (A6)
        partial = ("".join(answer_parts) + "".join(live)).strip()
        tr["error"] = "timeout"
        tr["answer"] = partial
        yield finish("error", {"code": "timeout", "message": f"The turn cap of {int(turn_cap)} s was reached.", "partial": partial,
                               "round": turn_round or None, "fallback": None})  # fmt: skip
        return
    except Exception as e:
        tr["error"] = f"model: {e}"
        yield finish("error", {"code": "model", "message": f"Model call failed: {e}. Slash commands still work.", "fallback": "slash"})
        return
    answer = "".join(answer_parts).strip()
    tr["answer"] = answer
    numbers = ground(answer, evidence)
    unverified = [n["text"] for n in numbers if not n["grounded"]]
    if not tool_rounds and numbers:
        unverified = [n["text"] for n in numbers if n["text"] not in question]
    # a number found only in a result of another round: not checked against this round
    elsewhere = [n["text"] for n in ground(answer, other_round) if n["grounded"]] if other_round else []
    mismatch = [t for t in unverified if t in elsewhere]
    tr["numbers"] = numbers
    tr["unverified"] = unverified
    if mismatch:
        tr["round_mismatch"] = mismatch
    if not answer:
        tr["error"] = "empty answer"
    yield finish("done", {"turn_id": turn, "ms_total": int((time.time() - t0) * 1000), "tokens_in": tr["tokens_in"], "tokens_out": tr["tokens_out"],
                          "numbers": numbers, "unverified": unverified, "round": turn_round or None, "round_mismatch": mismatch,
                          "no_narration": (not answer) or None})  # fmt: skip


def sse(event: str, data: dict[str, Any]) -> bytes:
    return (f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n").encode()


def stream(body: dict[str, Any]) -> Iterator[bytes]:
    """SSE bytes of a turn, for ``POST /api/chat``."""
    for ev, data in events(body):
        yield sse(ev, data)

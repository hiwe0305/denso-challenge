# ruff: noqa: E501, UP031
"""Chat backend: Nemotron over the loopback ssh tunnel, tools in ``registry``.

``events(body)`` yields ``(event, data)`` pairs; ``stream(body)`` yields them as SSE bytes for
the HTTP server. Guardrails live in code: loopback endpoint only, per-turn caps, no tool that
can train or write, GPU-busy fallback, and a request filter for the actions the console never
performs. Traces go to ``<fw_root>/console/chat/<date>.jsonl``.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from flywheel.console.paths import active
from flywheel.console.server import runner

from . import registry
from .common import fail
from .numbers import numbers_in, unsupported_numbers
from .tools_ops import all_jobs

ENDPOINT = "http://127.0.0.1:11435"
LOOPBACK_PORT = 11435
MODEL = runner.AGENT_MODEL
NUM_CTX = 16384
KEEP_ALIVE = "30m"
MAX_ROUNDS = 3
TURN_CAP_S = 20.0
HTTP_TIMEOUT_S = 20.0
TUNNEL_WAIT_S = 8.0
MAX_CALLS_PER_ROUND = 3

SYSTEM = (
    "You are the assistant of the Flywheel Console, a robot-learning data flywheel dashboard. "
    "For any question about datasets, episodes, QA, runs, eval, loop, jobs, findings or cost, call a tool first and never answer from memory. "
    "Pass IDs exactly as the user wrote them. Do not explain before calling a tool. "
    "After the tool results, answer in the user's language in at most 60 words, plain text, no tables. "
    "Cite only numbers that appear in the tool results. Never give generic advice. "
    "Never claim to change a QA status, start a job, train a model or read holdout data. "
    "If the question is not about this console's data, say so in one short sentence and call no tool."
)

VI = re.compile(
    r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]|"
    r"\b(tap|cua|bao nhieu|cho toi|hien|loi|chay|xem|nao|khong|sao|the nao|nhung|duoc)\b",
    re.I,
)

# Requests the console never performs. Matched in code before any model call.
GUARDS = [
    ("training", re.compile(r"\b(start|launch|kick ?off|begin|bắt đầu|chạy|khởi động)\s+(a\s+|the\s+|new\s+)?(train(ing)?|fine-?tun\w*|huấn luyện)\b|"
                            r"\b(re-?train|fine-?tune|train|huấn luyện)\s+(c\+|c-?plus|c_?(70|all)|b_?70|b|c|the model|model|policy|it|now|lại|ngay|đi)\b", re.I),
     "Training is not available from the console: it starts only from a RunPlan that Hiếu launches.",
     "Chat không khởi động train được: train chỉ chạy từ RunPlan do Hiếu khởi động."),
    ("holdout", re.compile(r"\b(vault|hold-?out)\b", re.I),
     "Holdout and vault data are not readable here: only the gate module reads them (fw holdout run).",
     "Không đọc được holdout hay vault: chỉ module gate đọc (fw holdout run)."),
    ("shell", re.compile(r"\brm\s+-|\bsudo\b|\bchmod\b|\bmkfs\b|\bdd\s+if=|\bkill\s+-9|(run|execute|exec|chạy|thực thi)\s+(a\s+|this\s+)?(shell|bash|command|lệnh|script)\b|\|\s*(ba)?sh\b", re.I),
     "No shell access: the console only runs its allowlisted fw jobs, and only after a human confirms.",
     "Không có quyền shell: console chỉ chạy các job fw trong allowlist, sau khi người xác nhận."),
    ("hosted_api", re.compile(r"(send|forward|paste|ask|share|upload|gửi|chuyển|hỏi|dán).{0,40}\b(gpt\S*|openai|chatgpt|gemini|claude|anthropic|hosted|external api|cloud api|api ngoài)\b", re.I),
     "Data never leaves the machine: the only model is the local Nemotron over the loopback tunnel.",
     "Dữ liệu không rời máy: chỉ dùng Nemotron cục bộ qua tunnel loopback."),
    ("qa_status", re.compile(r"\b(mark|set|change|flip|override|force|đánh dấu|chuyển|sửa|đổi)\b.{0,40}\b(as\s+)?(pass|flag|reject)\b|\bqa status\b.{0,20}\b(to|thành)\b", re.I),
     "QA status comes only from the rule layer; chat cannot change it. Overrides go through agentqa.review with a reason.",
     "Trạng thái QA chỉ do tầng luật quyết định; chat không đổi được. Muốn ghi đè phải qua agentqa.review kèm lý do."),
    ("upload", re.compile(r"\b(upload|push|publish|share|post|đăng|tải lên|đưa lên)\b.{0,60}\b(hugging ?face|\bhf\b|google drive|drive|s3|github|public|online|external|bên ngoài|công khai)\b", re.I),
     "Raw team video is internal data and is never uploaded outside; only de-identified public releases leave the machine.",
     "Video thô của đội là dữ liệu nội bộ, không được tải ra ngoài; chỉ bản phát hành đã che danh tính mới rời máy."),
]  # fmt: skip


def guard_check(question: str) -> tuple[str | None, str | None]:
    for name, rx, en, vi in GUARDS:
        if rx.search(question):
            return name, (vi if VI.search(question) else en)
    return None, None


def endpoint_ok(url: str | None = None) -> bool:
    """True only for plain http to 127.0.0.1 on the tunnel port."""
    u = urllib.parse.urlparse(url or ENDPOINT)
    return u.scheme == "http" and u.hostname == "127.0.0.1" and u.port == LOOPBACK_PORT


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
    with urllib.request.urlopen(ENDPOINT + path, timeout=timeout) as r:
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
        urllib.request.urlopen(req, timeout=90).read()
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


def list_traces(limit: int = 20) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in _trace_files():
        for ln in reversed(f.read_text(encoding="utf-8").splitlines()):
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


def get_trace(turn_id: str) -> dict[str, Any] | None:
    for f in _trace_files():
        for ln in f.read_text(encoding="utf-8").splitlines():
            if turn_id in ln:
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
    d = registry.context_defaults(context)
    ctxline = "Current page: %s." % (context.get("route") or "home")
    if d:
        ctxline += (
            " Defaults for words like 'this/here/tập này/run này': "
            + ", ".join("{}={}".format(*kv) for kv in d.items())
            + "."
        )
    msgs: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM + " " + ctxline}]
    hist = [
        m
        for m in body.get("messages", [])
        if m.get("role") in ("user", "assistant") and str(m.get("content") or "").strip()
    ]
    q = hist[-1]["content"] if hist and hist[-1]["role"] == "user" else ""
    prev = hist[:-1]
    users = [i for i, m in enumerate(prev) if m["role"] == "user"]
    keep_from = users[-4] if len(users) >= 4 else 0
    for i, m in enumerate(prev):
        if i < keep_from and m["role"] == "assistant":
            continue  # older answers reduced to the question
        msgs.append({"role": m["role"], "content": str(m["content"])[:600]})
    msgs.append({"role": "user", "content": str(q)[:1500]})
    return msgs, str(q)


def _chunks(resp: Any, deadline: float) -> Iterator[dict[str, Any]]:
    """Yield parsed ndjson objects of an Ollama stream; stop at the deadline."""
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


_MARK = re.compile(r"<\||<tool_call")
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
    messages: list[dict[str, Any]], tool_schemas: list[dict[str, Any]] | None, deadline: float
) -> Iterator[tuple[str, Any]]:
    """One streamed /api/chat call. Yields ("tok", text) live, then ("end", (content, calls, tin, tout))."""
    if not endpoint_ok():
        raise RuntimeError("model endpoint must be the loopback tunnel")
    remaining = deadline - time.time()
    if remaining <= 0.5:
        raise TimeoutError("turn cap reached")
    payload: dict[str, Any] = {
        "model": MODEL, "messages": messages, "stream": True, "think": False,
        "keep_alive": KEEP_ALIVE, "options": {"temperature": 0, "num_ctx": NUM_CTX, "num_predict": 320},
    }  # fmt: skip
    if tool_schemas:
        payload["tools"] = tool_schemas
    req = urllib.request.Request(
        ENDPOINT + "/api/chat", json.dumps(payload).encode(), {"Content-Type": "application/json"}
    )
    raw, sent, tin, tout = "", 0, 0, 0
    calls: list[dict[str, Any]] = []
    with urllib.request.urlopen(req, timeout=min(remaining, HTTP_TIMEOUT_S)) as resp:
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
                if safe > sent:
                    yield "tok", raw[sent:safe]
                    sent = safe
            for tc in m.get("tool_calls") or []:
                calls.append(tc.get("function") or {})
            if ch.get("done"):
                tin, tout = ch.get("prompt_eval_count", 0), ch.get("eval_count", 0)
    mk = _MARK.search(raw)
    if mk:
        calls += parse_markup_calls(raw[mk.start() :])
        content = raw[: mk.start()]
    else:
        content = raw
        if len(raw) > sent:
            yield "tok", raw[sent:]
    yield "end", (content, calls, tin, tout)


def events(body: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    t0 = time.time()
    context = body.get("context") or {}
    conv = body.get("conversation_id") or f"c-{os.urandom(4).hex()}"
    turn = "t-{}-{}".format(datetime.now().strftime("%Y%m%d-%H%M%S"), os.urandom(2).hex())
    msgs, question = build_messages(body, context)
    names = registry.offered_names(context.get("route"), question)
    tr: dict[str, Any] = {
        "turn_id": turn, "conversation_id": conv, "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": MODEL, "question": question, "context": context, "tools_offered": names, "nodes": [],
        "answer": "", "tokens_in": 0, "tokens_out": 0,
    }  # fmt: skip
    yield (
        "trace_start",
        {"conversation_id": conv, "turn_id": turn, "model": MODEL, "tools_offered": names},
    )

    def finish(event: str, data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        tr["ms_total"] = int((time.time() - t0) * 1000)
        try:
            save_trace(tr)
        except OSError:
            pass
        return event, data

    # 1. code-level guardrails (no model involved)
    why, refusal = guard_check(question)
    if why:
        tr["guard"] = why
        tr["answer"] = refusal
        yield "token", {"text": refusal}
        yield finish(
            "done",
            {
                "turn_id": turn,
                "ms_total": int((time.time() - t0) * 1000),
                "tokens_in": 0,
                "tokens_out": 0,
                "numbers": [],
                "unverified": [],
                "guard": why,
            },
        )
        return
    # 2. GPU busy / tunnel down -> slash fallback
    busy = gpu_busy()
    if busy:
        tr["error"] = "gpu busy"
        yield finish(
            "error",
            {"message": f"GPU busy: {busy} annotate. Slash commands only.", "fallback": "slash"},
        )
        return
    if runner.TUNNEL.tags() is None and not runner.TUNNEL.ensure(TUNNEL_WAIT_S):
        tr["error"] = "tunnel down"
        yield finish(
            "error",
            {
                "message": "Model tunnel to rtx3060 is down. Slash commands still work.",
                "fallback": "slash",
            },
        )
        return
    deadline = t0 + TURN_CAP_S
    evidence = [question] + [
        "{} {}".format(*kv) for kv in registry.context_defaults(context).items()
    ]
    answer_parts: list[str] = []
    nodes: list[dict[str, Any]] = tr["nodes"]
    lang = lang_of(question)
    tool_rounds = 0
    try:
        final_needed = True
        for rnd in range(MAX_ROUNDS + 1):
            offered = registry.schemas(context.get("route"), names) if rnd < MAX_ROUNDS else None
            g0 = time.time()
            content, tcalls, tin, tout = "", [], 0, 0
            for kind, val in generate(msgs, offered, deadline):
                if kind == "tok":
                    yield "token", {"text": val}
                else:
                    content, tcalls, tin, tout = val
            nodes.append(
                {
                    "type": "generation",
                    "round": rnd,
                    "ms": int((time.time() - g0) * 1000),
                    "tokens_in": tin,
                    "tokens_out": tout,
                    "content": content[:500],
                    "tool_calls": tcalls,
                }
            )
            tr["tokens_in"] += tin
            tr["tokens_out"] += tout
            if not tcalls:
                if content.strip():
                    answer_parts.append(content)
                final_needed = False
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
                if name not in names:
                    res = fail(f"Tool '{name}' is not offered on this page.")
                elif key in seen:
                    res = fail("Duplicate call ignored.")
                else:
                    res = registry.call(name, args, context)
                seen.add(key)
                ms = int((time.time() - k0) * 1000)
                evidence.append(res["model"])
                nodes.append(
                    {
                        "type": "tool",
                        "call_id": cid,
                        "name": name,
                        "args": args,
                        "ms": ms,
                        "ok": res["ok"],
                        "model_text": res["model"],
                        "ui": res["ui"],
                        "navigate": res.get("navigate"),
                    }
                )
                ev: dict[str, Any] = {
                    "call_id": cid,
                    "name": name,
                    "ms": ms,
                    "ok": res["ok"],
                    "ui": res["ui"],
                    "model_chars": len(res["model"]),
                }
                if res.get("navigate"):
                    ev["navigate"] = res["navigate"]
                yield "tool_result", ev
                msgs.append({"role": "tool", "tool_name": name, "content": res["model"]})
            msgs[-1]["content"] += (
                f"\n[Answer the user now in {lang}, at most 60 words. Use only numbers shown above. Do not call more tools unless a different lookup is clearly needed.]"
            )
        if final_needed or (not answer_parts and tool_rounds):
            # the tool-round budget ended with tool output and no prose: narrate without tools
            g0 = time.time()
            content, tin, tout = "", 0, 0
            for kind, val in generate(msgs, None, deadline):
                if kind == "tok":
                    yield "token", {"text": val}
                else:
                    content, _c, tin, tout = val
            nodes.append(
                {
                    "type": "generation",
                    "round": "final",
                    "ms": int((time.time() - g0) * 1000),
                    "tokens_in": tin,
                    "tokens_out": tout,
                    "content": content[:500],
                }
            )
            tr["tokens_in"] += tin
            tr["tokens_out"] += tout
            answer_parts.append(content)
    except TimeoutError:
        tr["error"] = "timeout"
        yield "token", {"text": ""}
    except Exception as e:
        tr["error"] = f"model: {e}"
        yield finish(
            "error",
            {
                "message": f"Model call failed: {e}. Slash commands still work.",
                "fallback": "slash",
            },
        )
        return
    answer = "".join(answer_parts).strip()
    tr["answer"] = answer
    numbers = ground(answer, evidence)
    unverified = [n["text"] for n in numbers if not n["grounded"]]
    if not tool_rounds and numbers:
        unverified = [n["text"] for n in numbers if n["text"] not in question]
    tr["numbers"] = numbers
    tr["unverified"] = unverified
    yield finish("done", {"turn_id": turn, "ms_total": int((time.time() - t0) * 1000), "tokens_in": tr["tokens_in"], "tokens_out": tr["tokens_out"], "numbers": numbers, "unverified": unverified, "no_narration": (not answer) or None})  # fmt: skip


def sse(event: str, data: dict[str, Any]) -> bytes:
    return (f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n").encode()


def stream(body: dict[str, Any]) -> Iterator[bytes]:
    """SSE bytes of a turn, for ``POST /api/chat``."""
    for ev, data in events(body):
        yield sse(ev, data)

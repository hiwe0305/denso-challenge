"""Which model answers the chat, and how it is reached.

Default: Nemotron in the Ollama of rtx3060, over the loopback ssh tunnel, with Ollama's own
``/api/chat`` (``llm.generate``). Setting ``FW_CHAT_BASE_URL`` switches to any server that
speaks the OpenAI chat-completions protocol, called through the ``openai`` client library:
OpenRouter, OpenCode Zen, a NIM, or the same Ollama at ``/v1``.

    FW_CHAT_BASE_URL   e.g. https://openrouter.ai/api/v1  or  http://127.0.0.1:11435/v1
    FW_CHAT_MODEL      the model id the server knows
    FW_CHAT_API_KEY    the key, read from the environment only; never written to a file or a log
    FW_CHAT_NAME       label shown in the chat header (default: the host name)
    FW_CHAT_REASONING  off (default) | low | medium | high | default. OpenRouter only: models that
                       think before answering spend the whole reply budget on it (seen 16/11/2026:
                       600 of 600 tokens, empty answer); the chat phrases facts a tool computed,
                       so thinking is switched off unless asked for

A server that is not on this machine is *hosted*. Data rule (design 27/10 section 8.4,
CLAUDE.md): rows that are not ``data_class: public`` never leave for a hosted service, so while
a hosted provider answers, the chat tools do not see those rows (``common.HOSTED``).
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


@dataclass(frozen=True)
class Provider:
    name: str
    kind: str  # "ollama" (native /api/chat) or "openai" (chat completions, openai library)
    base_url: str
    model: str
    hosted: bool
    port: int | None = None

    @property
    def key(self) -> str:
        return os.environ.get("FW_CHAT_API_KEY", "")


def active(default_url: str, default_model: str) -> Provider:
    base = os.environ.get("FW_CHAT_BASE_URL", "").strip()
    if not base:
        return Provider("nemotron", "ollama", default_url, default_model, False,
                        urllib.parse.urlparse(default_url).port)  # fmt: skip
    u = urllib.parse.urlparse(base)
    hosted = (u.hostname or "") not in LOCAL_HOSTS
    name = os.environ.get("FW_CHAT_NAME", "").strip() or (u.hostname or "model")
    return Provider(name, "openai", base.rstrip("/"), os.environ.get("FW_CHAT_MODEL", "").strip(),
                    hosted, u.port)  # fmt: skip


def problem(p: Provider) -> str | None:
    """Why this provider cannot be called, in one sentence; None when it can."""
    if p.kind != "openai":
        return None
    if not p.model:
        return "FW_CHAT_MODEL is not set."
    if p.hosted and not p.base_url.startswith("https://"):
        return "A hosted chat endpoint must use https."
    if p.hosted and not p.key:
        return "FW_CHAT_API_KEY is not set for the hosted chat model."
    return None


def reasoning_body(p: Provider) -> dict[str, Any] | None:
    """OpenRouter's ``reasoning`` field for this turn; None for other servers or ``default``."""
    if "openrouter.ai" not in p.base_url:
        return None
    mode = os.environ.get("FW_CHAT_REASONING", "off").strip().lower() or "off"
    if mode == "default":
        return None
    if mode in ("low", "medium", "high"):
        return {"reasoning": {"effort": mode}}
    return {"reasoning": {"enabled": False}}


def to_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The turn's messages (Ollama shape) as chat-completions messages.

    Ours: an assistant message lists ``tool_calls: [{function: {name, arguments: dict}}]`` and
    each result follows as ``{role: tool, tool_name, content}``. The protocol wants an id on
    every call, arguments as a JSON string, and the result tied to the call by that id.
    """
    out: list[dict[str, Any]] = []
    pending: list[str] = []
    n = 0
    for m in messages:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            calls = []
            for c in m["tool_calls"]:
                f = c.get("function") or {}
                cid = f"call_{n}"
                n += 1
                pending.append(cid)
                args = f.get("arguments")
                text = args if isinstance(args, str) else json.dumps(args or {}, ensure_ascii=False)
                fn = {"name": f.get("name"), "arguments": text}
                calls.append({"id": cid, "type": "function", "function": fn})
            head = {"role": "assistant", "content": m.get("content") or None}
            out.append({**head, "tool_calls": calls})
        elif role == "tool":
            cid = pending.pop(0) if pending else f"call_{n}"
            body = str(m.get("content") or "")
            out.append({"role": "tool", "tool_call_id": cid, "content": body})
        else:
            out.append({"role": role, "content": str(m.get("content") or "")})
    return out


def generate(
    p: Provider, messages: list[dict[str, Any]], tool_schemas: list[dict[str, Any]] | None,
    deadline: float, max_tokens: int,
) -> Iterator[tuple[str, Any]]:  # fmt: skip
    """One streamed chat-completions call. Same contract as ``llm.generate``:
    yields ("tok", text) live, then ("end", (content, calls, tokens_in, tokens_out))."""
    from openai import OpenAI  # imported here: the default (Ollama) path does not need the library

    why = problem(p)
    if why:
        raise RuntimeError(why)
    remaining = deadline - time.time()
    if remaining <= 0.5:
        raise TimeoutError("turn cap reached")
    client = OpenAI(base_url=p.base_url, api_key=p.key or "local", timeout=remaining, max_retries=0)
    kw: dict[str, Any] = {"model": p.model, "messages": to_openai(messages), "stream": True,
                          "temperature": 0, "max_tokens": max_tokens,
                          "stream_options": {"include_usage": True}}  # fmt: skip
    if tool_schemas:
        kw["tools"] = tool_schemas
    extra = reasoning_body(p)
    if extra:
        kw["extra_body"] = extra
    content, tin, tout = "", 0, 0
    parts: dict[int, dict[str, str]] = {}  # tool calls arrive in pieces, keyed by their index
    with client.chat.completions.create(**kw) as stream:
        for ch in stream:
            if time.time() > deadline:
                raise TimeoutError("turn cap reached")
            if getattr(ch, "usage", None):
                tin, tout = ch.usage.prompt_tokens or 0, ch.usage.completion_tokens or 0
            if not ch.choices:
                continue
            d = ch.choices[0].delta
            if d.content:
                content += d.content
                yield "tok", d.content
            for tc in d.tool_calls or []:
                slot = parts.setdefault(tc.index, {"name": "", "arguments": ""})
                if tc.function and tc.function.name:
                    slot["name"] += tc.function.name
                if tc.function and tc.function.arguments:
                    slot["arguments"] += tc.function.arguments
    calls = []
    for i in sorted(parts):
        try:
            args = json.loads(parts[i]["arguments"] or "{}")
        except ValueError:
            args = {}
        ok = args if isinstance(args, dict) else {}
        calls.append({"name": parts[i]["name"], "arguments": ok})
    yield "end", (content, calls, tin, tout)

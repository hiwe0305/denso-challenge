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

    FW_CHAT_SELF_HOSTED  1 declares that the server runs on a machine of the team (a NIM, an
                       Ollama on another port); without it the server counts as hosted

Data rule (design 27/10 section 8.4, CLAUDE.md): rows that are not ``data_class: public`` never
leave for a hosted service, so while a hosted provider answers, the chat tools do not see those
rows (``common.HOSTED``) and the tools that cannot filter them are not offered. The test fails
closed: a server counts as self-hosted only when it is the console's own tunnel to rtx3060 (the
default endpoint's loopback port) or ``FW_CHAT_SELF_HOSTED=1`` says so. A loopback address alone
proves nothing, since any port on this machine can forward to a hosted service. An Ollama model
whose tag ends in ``cloud`` runs on ollama.com and is hosted whatever the address.
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
    loopback: bool = False  # the address is this machine (a tunnel or a local server)

    @property
    def key(self) -> str:
        return os.environ.get("FW_CHAT_API_KEY", "")


def cloud_model(model: str) -> bool:
    """True for an Ollama model whose tag ends in ``cloud`` (``gpt-oss:120b-cloud``): Ollama
    forwards it to ollama.com, so it is hosted even behind a loopback address."""
    return ":" in model and model.rsplit(":", 1)[1].lower().endswith("cloud")


def active(default_url: str, default_model: str) -> Provider:
    tunnel = urllib.parse.urlparse(default_url)
    base = os.environ.get("FW_CHAT_BASE_URL", "").strip()
    if not base:
        on_loopback = (tunnel.hostname or "") in LOCAL_HOSTS
        hosted = cloud_model(default_model)
        return Provider(
            "nemotron", "ollama", default_url, default_model, hosted, tunnel.port, on_loopback
        )
    u = urllib.parse.urlparse(base)
    model = os.environ.get("FW_CHAT_MODEL", "").strip()
    loopback = (u.hostname or "") in LOCAL_HOSTS
    own_tunnel = loopback and u.port is not None and u.port == tunnel.port
    declared = os.environ.get("FW_CHAT_SELF_HOSTED", "").strip() == "1"
    hosted = not (own_tunnel or declared) or cloud_model(model)
    name = os.environ.get("FW_CHAT_NAME", "").strip() or (u.hostname or "model")
    return Provider(name, "openai", base.rstrip("/"), model, hosted, u.port, loopback)


def problem(p: Provider) -> str | None:
    """Why this provider cannot be called, in one sentence; None when it can.

    https and a key are asked of a remote hosted server only: a loopback address that counts as
    hosted (an undeclared tunnel, a cloud model in a local Ollama) is called as it is, and the
    data rule still applies through ``hosted``."""
    if p.kind != "openai":
        return None
    if not p.model:
        return "FW_CHAT_MODEL is not set."
    remote = p.hosted and not p.loopback
    if remote and not p.base_url.startswith("https://"):
        return (
            "A hosted chat endpoint must use https"
            " (set FW_CHAT_SELF_HOSTED=1 if the server runs on a machine of the team)."
        )
    if remote and not p.key:
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

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
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from flywheel.console.paths import active as active_paths

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")

PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "openai": {
        "label": "OpenAI API",
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1",
        "models": ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "o4-mini"],
        "env_key": "OPENAI_API_KEY",
    },
    "deepseek": {
        "label": "DeepSeek API",
        "kind": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "env_key": "DEEPSEEK_API_KEY",
    },
    "anthropic": {
        "label": "Anthropic Claude API",
        "kind": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-20250514",
        "models": [
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-latest",
            "claude-3-5-haiku-latest",
        ],
        "env_key": "ANTHROPIC_API_KEY",
    },
    "gemini": {
        "label": "Google Gemini API",
        "kind": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.5-flash",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
        "env_key": "GEMINI_API_KEY",
    },
    "openrouter": {
        "label": "OpenRouter API",
        "kind": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-sonnet-4",
        "models": [
            "anthropic/claude-sonnet-4",
            "deepseek/deepseek-r1",
            "openai/gpt-4.1",
            "google/gemini-2.5-pro",
        ],
        "env_key": "OPENROUTER_API_KEY",
    },
    "custom": {
        "label": "Custom OpenAI-Compatible / Harness",
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1-mini",
        "models": [],
        "env_key": "FW_CHAT_API_KEY",
    },
}

# Runtime override set via POST /api/chat/config. API key stays in RAM only (never written to disk).
_RUNTIME_CFG: dict[str, Any] = {}
_RUNTIME_API_KEY: str = ""


def _config_file_path() -> Any:
    try:
        return active_paths().console_dir / "config" / "chat_provider.json"
    except Exception:
        return None


def _load_persisted_cfg() -> dict[str, Any]:
    fp = _config_file_path()
    if fp is None or not fp.is_file():
        return {}
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def reset_runtime_config() -> None:
    """Clear in-memory runtime overrides (used by tests)."""
    global _RUNTIME_API_KEY
    _RUNTIME_CFG.clear()
    _RUNTIME_API_KEY = ""


def set_runtime_config(body: dict[str, Any], persist: bool = True) -> dict[str, Any]:
    """Update runtime API provider configuration; API key is kept strictly in memory."""
    global _RUNTIME_API_KEY
    preset = str(body.get("preset") or "custom").strip().lower()
    spec = PROVIDER_PRESETS.get(preset, PROVIDER_PRESETS["custom"])
    base_url = str(body.get("base_url") or spec["base_url"]).strip().rstrip("/")
    model = str(body.get("model") or spec["default_model"]).strip()
    kind = str(body.get("kind") or spec["kind"]).strip().lower()
    if "api.anthropic.com" in base_url and "/openai" not in base_url:
        kind = "anthropic"
    elif kind not in ("openai", "anthropic"):
        kind = "openai"
    name = str(body.get("name") or spec["label"]).strip()
    reasoning = str(body.get("reasoning") or "off").strip().lower()
    # a request body never declares a server self-hosted: only the operator can, through
    # FW_CHAT_SELF_HOSTED; otherwise a POST could open restricted data to a hosted API

    if "api_key" in body:
        raw_key = str(body.get("api_key") or "").strip()
        if raw_key:
            _RUNTIME_API_KEY = raw_key
        elif body.get("clear_key"):
            _RUNTIME_API_KEY = ""

    clean_cfg = {
        "preset": preset if preset in PROVIDER_PRESETS else "custom",
        "kind": kind,
        "base_url": base_url,
        "model": model,
        "name": name,
        "reasoning": reasoning,
    }
    _RUNTIME_CFG.clear()
    _RUNTIME_CFG.update(clean_cfg)

    if persist:
        fp = _config_file_path()
        if fp is not None:
            try:
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(json.dumps(clean_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass
    return get_runtime_config()


def _resolve_api_key(preset: str = "", base_url: str = "") -> tuple[str, str]:
    """Return (api_key, source_label) without ever exposing the key to callers."""
    if _RUNTIME_API_KEY:
        return _RUNTIME_API_KEY, "session"
    env_main = os.environ.get("FW_CHAT_API_KEY", "").strip()
    if env_main:
        return env_main, "FW_CHAT_API_KEY"
    if preset in PROVIDER_PRESETS:
        ek = PROVIDER_PRESETS[preset]["env_key"]
        val = os.environ.get(ek, "").strip()
        if val:
            return val, ek
    host = (urllib.parse.urlparse(base_url).hostname or "").lower()
    host_env_map = [
        ("openai.com", "OPENAI_API_KEY"),
        ("deepseek.com", "DEEPSEEK_API_KEY"),
        ("anthropic.com", "ANTHROPIC_API_KEY"),
        ("googleapis.com", "GEMINI_API_KEY"),
        ("openrouter.ai", "OPENROUTER_API_KEY"),
    ]
    for needle, ek in host_env_map:
        if needle in host:
            val = os.environ.get(ek, "").strip()
            if val:
                return val, ek
    return "", "none"


def get_runtime_config(
    default_url: str = "http://127.0.0.1:11435", default_model: str = "nemo"
) -> dict[str, Any]:
    """Safe public representation of current chat provider config (never includes raw API key)."""
    p = active(default_url, default_model)
    cfg = _RUNTIME_CFG or _load_persisted_cfg()
    preset = str(cfg.get("preset") or "").strip()
    if not preset:
        for pk, pv in PROVIDER_PRESETS.items():
            if pk != "custom" and pv["base_url"] in p.base_url:
                preset = pk
                break
        else:
            preset = "openai" if p.kind == "ollama" else "custom"
    _, key_source = _resolve_api_key(preset, p.base_url)
    why = problem(p)
    return {
        "preset": preset,
        "provider": p.name,
        "kind": p.kind,
        "base_url": p.base_url if p.kind != "ollama" else PROVIDER_PRESETS["openai"]["base_url"],
        "active_kind": p.kind,
        "model": p.model if p.kind != "ollama" else PROVIDER_PRESETS["openai"]["default_model"],
        "active_model": p.model,
        "hosted": p.hosted,
        "reasoning": str(cfg.get("reasoning") or os.environ.get("FW_CHAT_REASONING", "off")),
        "self_hosted": os.environ.get("FW_CHAT_SELF_HOSTED", "").strip() == "1",
        "has_key": bool(p.key),
        "key_source": key_source,
        "ready": p.kind != "ollama" and why is None,
        "problem": why if p.kind != "ollama" else "API provider not configured yet.",
        "presets": PROVIDER_PRESETS,
    }


@dataclass(frozen=True)
class Provider:
    name: str
    kind: str  # "ollama", "openai" (OpenAI-compatible), or "anthropic" (Messages API)
    base_url: str
    model: str
    hosted: bool
    port: int | None = None
    loopback: bool = False  # the address is this machine (a tunnel or a local server)
    preset: str = ""
    reasoning: str = ""

    @property
    def key(self) -> str:
        k, _ = _resolve_api_key(self.preset, self.base_url)
        return k


def cloud_model(model: str) -> bool:
    """True for an Ollama model whose tag ends in ``cloud`` (``gpt-oss:120b-cloud``): Ollama
    forwards it to ollama.com, so it is hosted even behind a loopback address."""
    return ":" in model and model.rsplit(":", 1)[1].lower().endswith("cloud")


def active(default_url: str, default_model: str) -> Provider:
    tunnel = urllib.parse.urlparse(default_url)
    base = os.environ.get("FW_CHAT_BASE_URL", "").strip()
    cfg = {} if base else (_RUNTIME_CFG or _load_persisted_cfg())
    if not base and cfg.get("base_url"):
        base = str(cfg["base_url"]).strip()
        u = urllib.parse.urlparse(base)
        model = str(cfg.get("model") or "").strip()
        kind = str(cfg.get("kind") or "openai").strip().lower()
        if "api.anthropic.com" in base and "/openai" not in base:
            kind = "anthropic"
        loopback = (u.hostname or "") in LOCAL_HOSTS
        own_tunnel = loopback and u.port is not None and u.port == tunnel.port
        declared = os.environ.get("FW_CHAT_SELF_HOSTED", "").strip() == "1"
        hosted = not (own_tunnel or declared) or cloud_model(model)
        name = str(cfg.get("name") or u.hostname or "api").strip()
        return Provider(
            name,
            kind,
            base.rstrip("/"),
            model,
            hosted,
            u.port,
            loopback,
            preset=str(cfg.get("preset") or ""),
            reasoning=str(cfg.get("reasoning") or ""),
        )
    if not base:
        on_loopback = (tunnel.hostname or "") in LOCAL_HOSTS
        hosted = cloud_model(default_model)
        return Provider(
            "nemotron", "ollama", default_url, default_model, hosted, tunnel.port, on_loopback
        )
    u = urllib.parse.urlparse(base)
    model = os.environ.get("FW_CHAT_MODEL", "").strip()
    kind = os.environ.get("FW_CHAT_KIND", "").strip().lower() or "openai"
    if "api.anthropic.com" in base and "/openai" not in base:
        kind = "anthropic"
    loopback = (u.hostname or "") in LOCAL_HOSTS
    own_tunnel = loopback and u.port is not None and u.port == tunnel.port
    declared = os.environ.get("FW_CHAT_SELF_HOSTED", "").strip() == "1"
    hosted = not (own_tunnel or declared) or cloud_model(model)
    name = os.environ.get("FW_CHAT_NAME", "").strip() or (u.hostname or "model")
    return Provider(name, kind, base.rstrip("/"), model, hosted, u.port, loopback)


def problem(p: Provider) -> str | None:
    """Why this provider cannot be called, in one sentence; None when it can.

    https and a key are asked of a remote hosted server only: a loopback address that counts as
    hosted (an undeclared tunnel, a cloud model in a local Ollama) is called as it is, and the
    data rule still applies through ``hosted``."""
    if p.kind not in ("openai", "anthropic"):
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
    raw = p.reasoning or os.environ.get("FW_CHAT_REASONING", "off")
    mode = raw.strip().lower() or "off"
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


def to_anthropic(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Convert internal message list into Anthropic Messages API (system_str, messages_list)."""
    sys_parts: list[str] = []
    out: list[dict[str, Any]] = []
    pending_ids: list[str] = []
    n = 0
    for m in messages:
        role = m.get("role")
        if role == "system":
            if m.get("content"):
                sys_parts.append(str(m["content"]))
        elif role == "assistant" and m.get("tool_calls"):
            blocks: list[dict[str, Any]] = []
            if m.get("content"):
                blocks.append({"type": "text", "text": str(m["content"])})
            for c in m["tool_calls"]:
                f = c.get("function") or {}
                cid = f"toolu_{n}"
                n += 1
                pending_ids.append(cid)
                args = f.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                blocks.append({
                    "type": "tool_use",
                    "id": cid,
                    "name": f.get("name") or "",
                    "input": args if isinstance(args, dict) else {},
                })
            out.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            cid = pending_ids.pop(0) if pending_ids else f"toolu_{n}"
            tr_block = {
                "type": "tool_result",
                "tool_use_id": cid,
                "content": str(m.get("content") or ""),
            }
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(tr_block)
            else:
                out.append({"role": "user", "content": [tr_block]})
        elif role in ("user", "assistant"):
            out.append({"role": role, "content": str(m.get("content") or "")})
    return "\n\n".join(sys_parts), out


def _generate_anthropic(
    p: Provider,
    messages: list[dict[str, Any]],
    tool_schemas: list[dict[str, Any]] | None,
    deadline: float,
    max_tokens: int,
) -> Iterator[tuple[str, Any]]:
    why = problem(p)
    if why:
        raise RuntimeError(why)
    remaining = deadline - time.time()
    if remaining <= 0.5:
        raise TimeoutError("turn cap reached")
    sys_text, anth_msgs = to_anthropic(messages)
    payload: dict[str, Any] = {
        "model": p.model,
        "max_tokens": max_tokens,
        "messages": anth_msgs,
        "stream": True,
    }
    if sys_text:
        payload["system"] = sys_text
    if tool_schemas:
        payload["tools"] = [
            {
                "name": s["function"]["name"],
                "description": s["function"].get("description", ""),
                "input_schema": s["function"].get(
                    "parameters", {"type": "object", "properties": {}}
                ),
            }
            for s in tool_schemas
            if "function" in s
        ]
    url = p.base_url.rstrip("/")
    if not url.endswith("/messages"):
        url += "/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": p.key,
        "anthropic-version": "2023-06-01",
    }
    req = urllib.request.Request(url, json.dumps(payload).encode("utf-8"), headers)
    content, tin, tout = "", 0, 0
    tool_blocks: dict[int, dict[str, str]] = {}
    try:
        resp_ctx = urllib.request.urlopen(req, timeout=min(remaining, 45.0))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:240]
        raise RuntimeError(f"Anthropic HTTP {e.code}: {detail}") from e

    with resp_ctx as resp:
        buf = b""
        while True:
            if time.time() > deadline:
                raise TimeoutError("turn cap reached")
            chunk = resp.read1(4096) if hasattr(resp, "read1") else resp.read(256)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                raw_ln, buf = buf.split(b"\n", 1)
                ln = raw_ln.decode("utf-8", errors="replace").strip()
                if not ln.startswith("data:"):
                    continue
                data_str = ln[5:].strip()
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    ev = json.loads(data_str)
                except ValueError:
                    continue
                etype = ev.get("type")
                if etype == "message_start":
                    u = (ev.get("message") or {}).get("usage") or {}
                    tin += int(u.get("input_tokens") or 0)
                elif etype == "message_delta":
                    u = ev.get("usage") or {}
                    tout += int(u.get("output_tokens") or 0)
                elif etype == "content_block_start":
                    cb = ev.get("content_block") or {}
                    if cb.get("type") == "tool_use":
                        tool_blocks[int(ev.get("index", 0))] = {
                            "name": str(cb.get("name") or ""),
                            "arguments": "",
                        }
                elif etype == "content_block_delta":
                    idx = int(ev.get("index", 0))
                    delta = ev.get("delta") or {}
                    dtype = delta.get("type")
                    if dtype == "text_delta" and delta.get("text"):
                        content += delta["text"]
                        yield "tok", delta["text"]
                    elif dtype == "thinking_delta" and delta.get("thinking"):
                        yield "think", delta["thinking"]
                    elif dtype == "input_json_delta" and idx in tool_blocks:
                        tool_blocks[idx]["arguments"] += str(delta.get("partial_json") or "")

    calls = []
    for idx in sorted(tool_blocks):
        raw_args = tool_blocks[idx]["arguments"] or "{}"
        try:
            parsed = json.loads(raw_args)
        except ValueError:
            parsed = {}
        calls.append({
            "name": tool_blocks[idx]["name"],
            "arguments": parsed if isinstance(parsed, dict) else {},
        })
    yield "end", (content, calls, tin, tout)


def generate(
    p: Provider, messages: list[dict[str, Any]], tool_schemas: list[dict[str, Any]] | None,
    deadline: float, max_tokens: int,
) -> Iterator[tuple[str, Any]]:  # fmt: skip
    """One streamed chat-completions call. Same contract as ``llm.generate``:
    yields ("tok"|"think", text) live, then ("end", (content, calls, tokens_in, tokens_out))."""
    if p.kind == "anthropic":
        yield from _generate_anthropic(p, messages, tool_schemas, deadline, max_tokens)
        return

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
            rc = getattr(d, "reasoning_content", None) or getattr(d, "reasoning", None)
            if isinstance(rc, str) and rc:
                yield "think", rc
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

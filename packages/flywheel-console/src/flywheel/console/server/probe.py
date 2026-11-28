"""Does the chat model answer? One tiny real request, made by the server (audit 28/11/2026).

``llm.prewarm`` and ``providers.problem`` only read the configuration of a hosted server, so a
dead address or an unknown model id still read as ready. The probe asks the model to answer the
word "ping" and sends no project data. An error text never carries the key, the address or the
body the server sent.
"""

from __future__ import annotations

import http.client
import json
import math
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from flywheel.console.server import runner

TIMEOUT_S = 10.0
TTL_OK_S = 300.0  # how long a model that answered is believed without asking again
TTL_FAIL_S = 15.0
MAX_MODELS = 200
_NOT_CHAT = re.compile(
    r"embed|rerank|moderation|image|imagen|banana|flux|dall-?e|sora|veo|video|audio|speech|tts|"
    r"whisper|transcri|realtime",
    re.I,
)

_lock = threading.Lock()
# (address, model, key hash) -> (valid until, why the model cannot answer or None)
_seen: dict[tuple[str, str, int], tuple[float, str | None]] = {}


def _key(p: Any) -> tuple[str, str, int]:
    return (p.base_url, p.model, hash(getattr(p, "key", "")))


def _remember(p: Any, why: str | None) -> str | None:
    _seen[_key(p)] = (time.monotonic() + (TTL_FAIL_S if why else TTL_OK_S), why)
    return why


def _recall(p: Any) -> tuple[bool, str | None]:
    hit = _seen.get(_key(p))
    if hit is None or hit[0] < time.monotonic():
        return False, None
    return True, hit[1]


def _open(p: Any, req: urllib.request.Request) -> Any:
    if p.loopback:  # loopback calls must never go through http_proxy
        return runner.LOOPBACK.open(req, timeout=TIMEOUT_S)
    return urllib.request.urlopen(req, timeout=TIMEOUT_S)


def _headers(p: Any) -> dict[str, str]:
    head = {"Content-Type": "application/json", "User-Agent": "curl/8.0"}
    if p.kind == "anthropic":
        head |= {"x-api-key": p.key, "anthropic-version": "2023-06-01"}
    elif p.key:
        head["Authorization"] = f"Bearer {p.key}"
    return head


def _first_event(resp: Any) -> Any:
    """The first JSON object of a streamed reply (or the whole reply of a server that did not
    stream); None for an empty one."""
    for raw in resp:
        line = raw.decode("utf-8", "replace").strip()
        if line.startswith("data:"):
            return json.loads(line[5:])
        if line.startswith("{"):
            return json.loads(line + resp.read().decode("utf-8", "replace"))
    return None


def _ask(p: Any) -> str | None:
    """One short streamed completion, shaped like the chat's own call."""
    url = p.base_url.rstrip("/")
    path = "/messages" if p.kind == "anthropic" else "/chat/completions"
    if not url.endswith(path):
        url += path
    body = {"model": p.model, "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 16, "stream": True}  # fmt: skip
    try:
        req = urllib.request.Request(url, json.dumps(body).encode(), _headers(p))
        with _open(p, req) as resp:
            event = _first_event(resp)
    except urllib.error.HTTPError as e:
        return f"model server answered HTTP {e.code}"
    except (OSError, ValueError, http.client.HTTPException) as e:
        return f"model server did not answer ({type(e).__name__})"
    if event is None:
        return "model server sent an empty reply"
    if isinstance(event, dict) and (event.get("error") or event.get("type") == "error"):
        return "model server answered with an error"
    return None


def check(llm: Any, providers: Any, p: Any, fresh: bool = False) -> str | None:
    """Why ``p`` cannot answer now, or None when it can.

    The Ollama of rtx3060 is ready when the tunnel answers and lists the model (loading it is
    ``prewarm``); any other server is asked, and its answer is remembered for a while."""
    if p.kind == "ollama":
        tags = runner.TUNNEL.tags()
        if tags is None:
            return "tunnel down"
        if p.model not in tags:
            return "model is not on the tunnel server"
        return _recall(p)[1]  # why the last prewarm could not load it
    why = providers.problem(p)
    if why:
        return str(why)
    if llm.needs_tunnel(p) and runner.TUNNEL.tags() is None:
        return "tunnel down"
    with _lock:  # one question at a time, however many pages ask
        known, why = _recall(p)
        if known and not fresh:
            return why
        return _remember(p, _ask(p))


def prewarm(llm: Any, providers: Any) -> dict[str, Any]:
    """``llm.prewarm`` followed by a real question; "ok" only when the model answered."""
    res: dict[str, Any] = llm.prewarm()
    if not hasattr(llm, "provider"):
        return res
    p = llm.provider()
    if p.kind == "ollama":  # llm.prewarm runs the model itself
        if res.get("ok"):
            _seen.pop(_key(p), None)
        elif res.get("nemotron") != "busy" and runner.TUNNEL.tags() is not None:
            # listed but not loading: not ready until a prewarm succeeds
            _seen[_key(p)] = (math.inf, str(res.get("error") or "model not ready"))
        return res
    if not res.get("ok"):
        return res
    why = check(llm, providers, p, fresh=True)
    return res | {"ok": False, "nemotron": "down", "error": why} if why else res


def model_ids(p: Any, query: str = "") -> list[str]:
    """Chat models the server lists, those of the active model's namespace first."""
    req = urllib.request.Request(p.base_url.rstrip("/") + "/models", headers=_headers(p))
    with _open(p, req) as resp:
        data = json.load(resp).get("data") or []
    ids = [str(x["id"]) for x in data if isinstance(x, dict) and x.get("id")]
    ids = [i for i in ids if not _NOT_CHAT.search(i) and query.lower() in i.lower()]
    space = p.model.split("/")[0] + "/" if "/" in p.model else ""
    if space:
        ids.sort(key=lambda i: not i.startswith(space))  # stable: server order within a group
    return ids[:MAX_MODELS]

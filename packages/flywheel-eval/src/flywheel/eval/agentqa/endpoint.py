"""The model behind Agent QA/QC, reached through a local OpenAI-style endpoint (DA-20 AC 1).

Nemotron 3.5 Bolt E4B runs on the team's RTX 3060 under Ollama (or vLLM), which
both speak `/v1/chat/completions`. Nothing here imports a model runtime: the
endpoint is plain HTTP through `urllib`, so the lane stays CPU-only and dev and CI
pass any object with the same `complete` method (the testkit's `FakeLLM` behind
`ScriptedModel` in the tests).

Which model, which revision and which temperature live in
`configs/eval/agentqa/agent.yaml`; the report records all three with the hash of
the prompt (`AgentModel`), so two reports can only be compared when they name the
same four values.

The endpoint must be a machine of ours: loopback, a private-network address, or a
host the config lists in `local_hosts`. The request ignores the proxy variables and
refuses a redirect, so data marked `restricted` or `internal` cannot reach a hosted
API through a typo in a URL, an environment variable or a server that forwards
(CLAUDE.md, architecture invariants). The host check and the proxy-free opener
follow Hưng's `settings._is_local` and `ChatEndpointClient` (commit cbdfc295).
"""

from __future__ import annotations

import ipaddress
import json
import os
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from email.message import Message as Headers
from pathlib import Path
from typing import IO, Any, NoReturn, Protocol
from urllib.parse import urlparse

import yaml

DEFAULT_AGENT_CONFIG = Path("configs") / "eval" / "agentqa" / "agent.yaml"

# One chat message as the OpenAI API spells it. `content` is a string, or for the
# vision endpoint a list of parts ({"type": "text"} and {"type": "image_url"}).
Message = dict[str, Any]


class EndpointError(RuntimeError):
    """The endpoint could not be reached or answered with something that is not a reply."""


def is_local(host: str, local_hosts: Sequence[str] = ()) -> bool:
    """Loopback, a private-network address, `localhost`, or a host named in `local_hosts`."""
    if host == "localhost" or host in local_hosts:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private


def check_local_url(url: str, local_hosts: Sequence[str] = ()) -> None:
    """Refuse a URL that is not http(s) to a machine of ours."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"endpoint {url!r} is not an http(s) URL with a host")
    if not is_local(parsed.hostname, local_hosts):
        raise ValueError(
            f"endpoint host {parsed.hostname!r} is not a machine of ours; add it to "
            "local_hosts in the config only if it is served inside our network"
        )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect could carry the request, and its key, to a host nobody checked."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Headers,
        newurl: str,
    ) -> NoReturn:
        raise urllib.error.HTTPError(req.full_url, code, f"redirect to {newurl} refused",
                                     headers, fp)


class ChatModel(Protocol):
    """What the agent needs of a model: a name to record and one chat turn."""

    @property
    def name(self) -> str: ...

    @property
    def revision(self) -> str: ...

    @property
    def temperature(self) -> float: ...

    def complete(self, messages: Sequence[Message]) -> str: ...


@dataclass(frozen=True)
class OpenAIEndpoint:
    """A model served behind `<base_url>/chat/completions` (Ollama, vLLM, llama.cpp).

    `json_mode` asks the server for a JSON object; Ollama and vLLM both honour
    `response_format`. The key, if the server wants one, comes from the variable
    named by `api_key_env`, never from a config file.
    """

    base_url: str
    model: str
    revision: str
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout_s: float = 300.0
    json_mode: bool = True
    api_key_env: str | None = None
    local_hosts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        check_local_url(self.base_url, self.local_hosts)

    @property
    def name(self) -> str:
        return self.model

    def complete(self, messages: Sequence[Message]) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(self.api_key_env) if self.api_key_env else None
        if key:
            headers["Authorization"] = f"Bearer {key}"
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        try:
            with opener.open(request, timeout=self.timeout_s) as response:
                reply = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise EndpointError(f"{self.base_url}: {exc}") from exc
        try:
            content = reply["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise EndpointError(f"{self.base_url}: no message in reply {str(reply)[:200]}") from exc
        if not isinstance(content, str):
            raise EndpointError(f"{self.base_url}: message content is not text")
        return content


def load_endpoint(role: str = "agent", config: Path = DEFAULT_AGENT_CONFIG) -> OpenAIEndpoint:
    """The endpoint of `role` ("agent" for Nemotron, "vision" for Qwen3.5-4B) in the config.

    `FW_AGENTQA_<ROLE>_URL` overrides the URL, so a run through an SSH tunnel to
    the 3060 needs no config edit; the override passes the same host check.
    """
    raw = yaml.safe_load(config.read_text(encoding="utf-8"))
    models = raw.get("models") if isinstance(raw, dict) else None
    entry = models.get(role) if isinstance(models, dict) else None
    if not isinstance(entry, dict):
        raise ValueError(f"{config}: no models.{role}")
    url = os.environ.get(f"FW_AGENTQA_{role.upper()}_URL") or entry["base_url"]
    hosts = raw.get("local_hosts") or []
    if not isinstance(hosts, list) or not all(isinstance(h, str) and h for h in hosts):
        raise ValueError(f"{config}: local_hosts must be a list of host names")
    return OpenAIEndpoint(
        base_url=str(url),
        model=str(entry["model"]),
        revision=str(entry["revision"]),
        temperature=float(entry.get("temperature", 0.0)),
        max_tokens=int(entry.get("max_tokens", 4096)),
        timeout_s=float(entry.get("timeout_s", 300.0)),
        json_mode=bool(entry.get("json_mode", True)),
        api_key_env=entry.get("api_key_env"),
        local_hosts=tuple(hosts),
    )


@dataclass
class RecordingModel:
    """A live model whose every reply is appended to a JSONL file, so a run can be replayed."""

    inner: ChatModel
    path: Path

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def revision(self) -> str:
        return self.inner.revision

    @property
    def temperature(self) -> float:
        return self.inner.temperature

    def complete(self, messages: Sequence[Message]) -> str:
        reply = self.inner.complete(messages)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"model": self.name, "reply": reply}, ensure_ascii=False) + "\n")
        return reply


@dataclass
class ReplayModel:
    """Replies recorded by `RecordingModel`, given back in order (demo, CI, re-render)."""

    name: str
    revision: str
    replies: list[str]
    temperature: float = 0.0

    @classmethod
    def from_file(cls, path: Path, revision: str = "replay") -> ReplayModel:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        name = str(rows[0]["model"]) if rows else "replay"
        return cls(name=name, revision=revision, replies=[str(r["reply"]) for r in rows])

    def complete(self, messages: Sequence[Message]) -> str:
        if not self.replies:
            raise EndpointError("replay: no recorded reply left")
        return self.replies.pop(0)

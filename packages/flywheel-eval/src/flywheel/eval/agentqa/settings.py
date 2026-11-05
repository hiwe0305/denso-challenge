"""Endpoint and prompt settings of the Agent QA/QC, read from `configs/eval/agentqa/`.

Same two rules as `flywheel.eval.config`, kept in this package so the agent does not
depend on the thresholds module of another owner. No value has a default in code: a
key missing from the file raises, so a run can never quietly use a number nobody wrote
down. And every run carries the sha256 of the bytes it parsed (`Endpoint.config_sha256`,
`Prompt.sha256`), which is what lets a report be reproduced, or told apart from one made
under another prompt (design 27/10/2026 section 9.1: "đổi prompt là phiên bản mới").

One more rule is about where the data goes. The endpoint must be a machine of ours:
a loopback or private-network address, or a host the file lists in `local_hosts`.
Anything else is refused when the file is read, so data of class `restricted` or
`internal` cannot reach a hosted API by a typo in a URL (CLAUDE.md, architecture
invariants).
"""

from __future__ import annotations

import hashlib
import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

DEFAULT_ENDPOINT_CONFIG = Path("configs") / "eval" / "agentqa" / "endpoint.yaml"
DEFAULT_PROMPT_DIR = Path("configs") / "eval" / "agentqa" / "prompts"

_KEYS = (
    "base_url",
    "local_hosts",
    "model",
    "revision",
    "temperature",
    "max_tokens",
    "timeout_s",
    "max_turns",
    "max_prompt_chars",
)


class SettingsError(ValueError):
    """A settings or prompt file the agent must not run on."""


@dataclass(frozen=True)
class Endpoint:
    """Where the local model is served and how a run talks to it."""

    base_url: str
    model: str
    revision: str
    temperature: float
    max_tokens: int
    timeout_s: float
    max_turns: int
    max_prompt_chars: int
    config_sha256: str


@dataclass(frozen=True)
class Prompt:
    """A prompt file and the hash of its bytes."""

    name: str
    text: str
    sha256: str


def _text(raw: Mapping[str, Any], key: str) -> str:
    value = raw[key]
    if not isinstance(value, str) or not value.strip():
        raise SettingsError(f"{key} must be a non-empty string")
    return value


def _number(raw: Mapping[str, Any], key: str, *, integer: bool = False) -> float:
    value = raw[key]
    kinds = (int,) if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, kinds):
        raise SettingsError(f"{key} must be {'an integer' if integer else 'a number'}")
    return float(value)


def _is_local(host: str, local_hosts: tuple[str, ...]) -> bool:
    if host == "localhost" or host in local_hosts:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private


def endpoint_from_mapping(raw: Mapping[str, Any], config_sha256: str) -> Endpoint:
    """Validate a parsed endpoint file; knows nothing about the file format."""
    missing = [key for key in _KEYS if key not in raw]
    if missing:
        raise SettingsError(f"missing key(s): {', '.join(missing)}")
    unknown = sorted(set(raw) - set(_KEYS))
    if unknown:
        raise SettingsError(f"unknown key(s): {', '.join(unknown)}")

    hosts = raw["local_hosts"]
    if not isinstance(hosts, list) or not all(isinstance(h, str) and h for h in hosts):
        raise SettingsError("local_hosts must be a list of host names")
    base_url = _text(raw, "base_url").rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise SettingsError(f"base_url {base_url!r} is not an http(s) URL with a host")
    if not _is_local(parsed.hostname, tuple(hosts)):
        raise SettingsError(
            f"base_url host {parsed.hostname!r} is not a machine of ours; "
            "add it to local_hosts only if it is served inside our network"
        )

    temperature = _number(raw, "temperature")
    timeout_s = _number(raw, "timeout_s")
    max_tokens = int(_number(raw, "max_tokens", integer=True))
    max_turns = int(_number(raw, "max_turns", integer=True))
    max_prompt_chars = int(_number(raw, "max_prompt_chars", integer=True))
    if temperature < 0:
        raise SettingsError("temperature must not be negative")
    if timeout_s <= 0:
        raise SettingsError("timeout_s must be positive")
    if min(max_tokens, max_turns, max_prompt_chars) < 1:
        raise SettingsError("max_tokens, max_turns and max_prompt_chars must be at least 1")
    return Endpoint(
        base_url=base_url,
        model=_text(raw, "model"),
        revision=_text(raw, "revision"),
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_s=timeout_s,
        max_turns=max_turns,
        max_prompt_chars=max_prompt_chars,
        config_sha256=config_sha256,
    )


def load_endpoint(path: Path = DEFAULT_ENDPOINT_CONFIG) -> Endpoint:
    """Read the endpoint file, hashing the same bytes it parses."""
    data = path.read_bytes()
    try:
        raw = yaml.safe_load(data)
    except yaml.YAMLError as exc:
        raise SettingsError(f"{path}: not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise SettingsError(f"{path}: expected a mapping at the top level")
    return endpoint_from_mapping(raw, hashlib.sha256(data).hexdigest())


def load_prompt(path: Path) -> Prompt:
    """Read a prompt file; the hash is of its bytes, so any edit is a new prompt."""
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SettingsError(f"{path}: prompt is not UTF-8") from exc
    if not text.strip():
        raise SettingsError(f"{path}: prompt is empty")
    return Prompt(name=path.stem, text=text, sha256=hashlib.sha256(data).hexdigest())

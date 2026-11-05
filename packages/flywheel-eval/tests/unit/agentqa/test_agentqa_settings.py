"""DA-20 task 1: the endpoint file and the prompt files the agent runs on (AC 1)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.eval.agentqa.settings import (
    SettingsError,
    endpoint_from_mapping,
    load_endpoint,
    load_prompt,
)

REPO = Path(__file__).resolve().parents[5]
ENDPOINT = REPO / "configs" / "eval" / "agentqa" / "endpoint.yaml"
PROMPT = REPO / "configs" / "eval" / "agentqa" / "prompts" / "tool_protocol.md"


def _raw() -> dict[str, Any]:
    loaded = yaml.safe_load(ENDPOINT.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_the_committed_endpoint_file_loads_and_is_hashed() -> None:
    endpoint = load_endpoint(ENDPOINT)
    assert endpoint.model == "nemotron-3.5-bolt-e4b"
    assert endpoint.temperature == 0.0
    assert endpoint.config_sha256 == hashlib.sha256(ENDPOINT.read_bytes()).hexdigest()


def test_a_missing_key_is_an_error_not_a_default() -> None:
    raw = _raw()
    del raw["timeout_s"]
    with pytest.raises(SettingsError, match="timeout_s"):
        endpoint_from_mapping(raw, "0" * 64)


def test_an_unknown_key_is_an_error() -> None:
    with pytest.raises(SettingsError, match="tempreture"):
        endpoint_from_mapping({**_raw(), "tempreture": 0.2}, "0" * 64)


@pytest.mark.parametrize(
    "url",
    [
        "https://integrate.api.nvidia.com/v1",
        "https://build.nvidia.com/v1",
        "http://8.8.8.8:8000/v1",
        "http://llm.example.com/v1",
    ],
)
def test_a_hosted_endpoint_is_refused(url: str) -> None:
    with pytest.raises(SettingsError, match="not a machine of ours"):
        endpoint_from_mapping({**_raw(), "base_url": url}, "0" * 64)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/v1",
        "http://localhost:8000/v1/",
        "http://192.168.1.20:8000/v1",
        "http://10.0.0.5:8000/v1",
    ],
)
def test_a_machine_of_ours_is_accepted(url: str) -> None:
    endpoint = endpoint_from_mapping({**_raw(), "base_url": url}, "0" * 64)
    assert not endpoint.base_url.endswith("/")


def test_a_host_name_needs_to_be_listed() -> None:
    raw = {**_raw(), "base_url": "http://rtx3060:8000/v1"}
    with pytest.raises(SettingsError):
        endpoint_from_mapping(raw, "0" * 64)
    assert endpoint_from_mapping({**raw, "local_hosts": ["rtx3060"]}, "0" * 64).base_url


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("temperature", -0.1),
        ("timeout_s", 0),
        ("max_turns", 0),
        ("max_tokens", True),
        ("max_prompt_chars", 1.5),
        ("model", "  "),
    ],
)
def test_bad_values_are_refused(key: str, value: object) -> None:
    with pytest.raises(SettingsError):
        endpoint_from_mapping({**_raw(), key: value}, "0" * 64)


def test_a_prompt_is_hashed_by_its_bytes(tmp_path: Path) -> None:
    prompt = load_prompt(PROMPT)
    assert prompt.name == "tool_protocol"
    assert prompt.sha256 == hashlib.sha256(PROMPT.read_bytes()).hexdigest()
    edited = tmp_path / "tool_protocol.md"
    edited.write_text(prompt.text + "\nOne more rule.\n", encoding="utf-8")
    assert load_prompt(edited).sha256 != prompt.sha256


def test_an_empty_prompt_is_refused(tmp_path: Path) -> None:
    empty = tmp_path / "empty.md"
    empty.write_text("  \n", encoding="utf-8")
    with pytest.raises(SettingsError):
        load_prompt(empty)

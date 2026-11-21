"""Config of the model gateway: profiles, routes, the hosted block (DA-43 task 5.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.eval.agentqa.round.gateway_config import (
    CONFIG_ROOT,
    GatewayRefused,
    load_gateway_config,
)

LOCAL = {"provider": "local_openai", "hosted": False, "endpoint": "agent",
         "max_tokens": 100, "timeout_s": 10}
HOSTED = {"provider": "anthropic", "hosted": True, "model": "claude-haiku-5-5",
          "api_key_env": "ANTHROPIC_API_KEY", "max_tokens": 100, "timeout_s": 10}


def _all(profile: str) -> dict[str, str]:
    return {"public": profile, "internal": profile, "restricted": profile}


def routing(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "profiles": {"local": dict(LOCAL)},
        "routes": {r: _all("local") for r in ("adjudicate", "rank", "look")},
        "budget": {"max_calls": 5, "max_input_tokens": 1000, "max_usd": 0,
                   "chars_per_token": 2.5},
        "retry": {"retries": 2, "base_delay_s": 1.0},
    }
    base.update(over)
    return base


def write(tmp_path: Path, routing_doc: dict[str, Any],
          hosted_doc: dict[str, Any] | None = None) -> Path:
    (tmp_path / "routing.yaml").write_text(yaml.safe_dump(routing_doc))
    if hosted_doc is not None:
        (tmp_path / "hosted.yaml").write_text(yaml.safe_dump(hosted_doc))
    return tmp_path


def test_shipped_config_is_local_only_with_hosted_off() -> None:
    config = load_gateway_config(CONFIG_ROOT)
    assert config.hosted_enabled is False
    for table in config.routes.values():
        assert all(not config.profiles[name].hosted for name in table.values())
    assert config.retry.retries <= 2


def test_no_hosted_file_means_hosted_off(tmp_path: Path) -> None:
    config = load_gateway_config(write(tmp_path, routing()))
    assert config.hosted_enabled is False and set(config.profiles) == {"local"}


@pytest.mark.parametrize(("doc", "hosted", "needle"), [
    (routing(extra=1), None, "extra"),
    (routing(retry={"retries": 3, "base_delay_s": 1}), None, "retries"),
    (routing(routes={"adjudicate": _all("local"), "rank": _all("local")}), None,
     "routes.look.public is missing"),
    (routing(routes={**routing()["routes"], "rank": _all("nope")}), None, "no profile"),
    (routing(profiles={"local": dict(LOCAL), "h": dict(HOSTED)}), None, "belong in hosted"),
    (routing(), {"enabled": True, "profiles": {"l2": dict(LOCAL)}}, "belongs in routing"),
    (routing(), {"enabled": True, "profiles": {"local": dict(HOSTED)}}, "declared twice"),
    (routing(), {"enabled": True, "profiles": {"h": {**HOSTED, "api_key_env": "sk-abc123"}}},
     "api_key_env"),
    (routing(), {"enabled": True, "profiles": {"h": {**HOSTED, "hosted": False}}}, "hosted"),
    (routing(profiles={"local": {**LOCAL, "model": "x"}}), None, "only an endpoint"),
    (routing(profiles={"local": {**LOCAL, "usd_per_mtok_in": 1}}), None, "costs nothing"),
])
def test_bad_configs_are_refused(tmp_path: Path, doc: dict[str, Any],
                                 hosted: dict[str, Any] | None, needle: str) -> None:
    with pytest.raises(GatewayRefused, match=needle):
        load_gateway_config(write(tmp_path, doc, hosted))


@pytest.mark.parametrize("data_class", ["internal", "restricted"])
def test_a_non_public_class_never_routes_to_hosted(tmp_path: Path, data_class: str) -> None:
    routes = {**routing()["routes"], "rank": {**_all("local"), data_class: "h"}}
    with pytest.raises(GatewayRefused, match=f"routes.rank.{data_class}: h is hosted"):
        load_gateway_config(write(tmp_path, routing(routes=routes),
                                  {"enabled": True, "profiles": {"h": dict(HOSTED)}}))


def test_public_may_route_to_hosted(tmp_path: Path) -> None:
    routes = {**routing()["routes"], "rank": {**_all("local"), "public": "h"}}
    config = load_gateway_config(write(tmp_path, routing(routes=routes),
                                       {"enabled": False, "profiles": {"h": dict(HOSTED)}}))
    assert config.profiles["h"].hosted and not config.hosted_enabled

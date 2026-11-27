"""Configuration of the model gateway (architecture 20/11 sections 8 and 26; DA-43 task 5.1).

    configs/eval/agentqa/routing.yaml   local profiles, role x data class -> profile,
                                        budget per run, retries
    configs/eval/agentqa/hosted.yaml    the separate `hosted` block: off by default,
                                        hosted profiles and the names of their key variables

`investigate` (DA-52) is an optional role: a `routing.yaml` without its route still loads,
and the investigate step refuses with a one-line error.

A local profile names an endpoint of `agent.yaml` (`models.<endpoint>`), so the local
model, its revision and its URL keep one source, and `check_local_url` still guards it.
A hosted profile can only be declared in `hosted.yaml`; a profile in the wrong file, a
route of an `internal` or `restricted` class to a hosted profile, or a hole in the
routing table refuses the config. This is a first guard only: the gateway checks the
pack's class again on every call, whatever the config says.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from flywheel.eval.agentqa.round.records import DataClass
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

CONFIG_ROOT = Path("configs") / "eval" / "agentqa"  # from the repo root
ROUTING_FILE = "routing.yaml"
HOSTED_FILE = "hosted.yaml"

Role = Literal["adjudicate", "rank", "look", "investigate"]
ROLES: tuple[Role, ...] = ("adjudicate", "rank", "look")  # every route cell is required
# Roles a routing.yaml may leave out (DA-52): a config written before the role still loads,
# and the role's step refuses when it runs. A role that is present needs every cell.
OPTIONAL_ROLES: tuple[Role, ...] = ("investigate",)
CLASSES: tuple[DataClass, ...] = ("public", "internal", "restricted")
ProviderKind = Literal["local_openai", "openai_compatible", "anthropic"]
HOSTED_KINDS: frozenset[str] = frozenset({"openai_compatible", "anthropic"})
ENV_NAME = r"^[A-Z_][A-Z0-9_]*$"  # a variable name, so a pasted key does not validate


class GatewayRefused(ValueError):
    """The gateway will not call: bad config, unknown class, or a hosted model not allowed.

    Raised before any provider is built or any connection is opened. The pipeline turns
    it into a broken run and a non-zero exit, like the other refusals of the round.
    """


class _Config(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Profile(_Config):
    """One model the gateway may call, and its limits."""

    provider: ProviderKind
    hosted: bool
    endpoint: str | None = Field(
        default=None, description="Local only: the models.<endpoint> entry of agent.yaml.")
    model: str | None = Field(default=None, description="Hosted only: the provider's model id.")
    base_url: str | None = Field(default=None, description="Hosted only, when the kind needs one.")
    api_key_env: str | None = Field(
        default=None, pattern=ENV_NAME,
        description="Hosted only: the NAME of the variable that holds the key, never the key.")
    max_tokens: int = Field(ge=1, description="Reply cap per call; a request asking more is cut.")
    thinking: bool = Field(default=False, description="Hosted `anthropic` only: adaptive thinking.")
    timeout_s: float = Field(gt=0, le=600)
    usd_per_mtok_in: float = Field(default=0.0, ge=0)
    usd_per_mtok_out: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def _kind_matches(self) -> Profile:
        if self.hosted != (self.provider in HOSTED_KINDS):
            raise ValueError(f"provider {self.provider} has hosted={self.provider in HOSTED_KINDS}")
        if self.hosted:
            if not self.model or not self.api_key_env or self.endpoint:
                raise ValueError("a hosted profile names model and api_key_env, no endpoint")
            if self.provider == "openai_compatible" and not self.base_url:
                raise ValueError("an openai_compatible profile needs a base_url")
            if self.thinking and self.provider != "anthropic":
                raise ValueError("thinking is for the anthropic provider only")
        else:
            if not self.endpoint or self.model or self.base_url or self.api_key_env:
                raise ValueError("a local profile names only an endpoint of agent.yaml; its "
                                 "model, URL and key variable live there")
            if self.thinking:
                raise ValueError("thinking is for the anthropic provider only")
            if self.usd_per_mtok_in or self.usd_per_mtok_out:
                raise ValueError("a local profile costs nothing per token")
        return self


class Budget(_Config):
    """Caps of one run, over every provider call (retries included)."""

    max_calls: int = Field(ge=0)
    max_input_tokens: int = Field(ge=0)
    max_usd: float = Field(ge=0)
    chars_per_token: float = Field(gt=0, description="Estimates a prompt's tokens before sending.")


class Retry(_Config):
    retries: int = Field(ge=0, le=2, description="More tries after a network or overload error.")
    base_delay_s: float = Field(ge=0, description="Wait before retry k is base * 2**(k-1).")


class RoutingFile(_Config):
    profiles: dict[str, Profile]
    routes: dict[Role, dict[DataClass, str]]
    budget: Budget
    retry: Retry


class HostedFile(_Config):
    enabled: bool = False
    profiles: dict[str, Profile] = Field(default_factory=dict)


class GatewayConfig(_Config):
    """Both files, checked together."""

    profiles: dict[str, Profile]
    routes: dict[Role, dict[DataClass, str]]
    budget: Budget
    retry: Retry
    hosted_enabled: bool = False

    @model_validator(mode="after")
    def _routes_complete_and_safe(self) -> GatewayConfig:
        for role in (*ROLES, *(r for r in OPTIONAL_ROLES if r in self.routes)):
            table = self.routes.get(role, {})
            for data_class in CLASSES:
                name = table.get(data_class)
                if name is None:
                    raise ValueError(f"routes.{role}.{data_class} is missing")
                if name not in self.profiles:
                    raise ValueError(f"routes.{role}.{data_class}: no profile {name!r}")
                if data_class != "public" and self.profiles[name].hosted:
                    raise ValueError(f"routes.{role}.{data_class}: {name} is hosted; only "
                                     "public packs may reach a hosted model")
        return self


def _read(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise GatewayRefused(f"{path}: {str(error).splitlines()[0][:200]}") from error


def _first_error(path: Path, error: ValidationError) -> GatewayRefused:
    first = error.errors()[0]
    where = ".".join(str(p) for p in first["loc"])
    return GatewayRefused(f"{path}: {where}: {first['msg']}")


def load_gateway_config(root: Path = CONFIG_ROOT) -> GatewayConfig:
    """Read and check `routing.yaml` and `hosted.yaml` under `root`.

    No `hosted.yaml` means the hosted block is off and declares no profile.
    """
    routing_path, hosted_path = root / ROUTING_FILE, root / HOSTED_FILE
    try:
        routing = RoutingFile.model_validate(_read(routing_path))
    except ValidationError as error:
        raise _first_error(routing_path, error) from error
    try:
        hosted = (HostedFile.model_validate(_read(hosted_path)) if hosted_path.is_file()
                  else HostedFile())
    except ValidationError as error:
        raise _first_error(hosted_path, error) from error
    for name, profile in routing.profiles.items():
        if profile.hosted:
            raise GatewayRefused(f"{routing_path}: profile {name} is hosted; hosted profiles "
                                 f"belong in {HOSTED_FILE}")
    for name, profile in hosted.profiles.items():
        if not profile.hosted:
            raise GatewayRefused(f"{hosted_path}: profile {name} is local; it belongs in "
                                 f"{ROUTING_FILE}")
    both = set(routing.profiles) & set(hosted.profiles)
    if both:
        raise GatewayRefused(f"profiles declared twice: {', '.join(sorted(both))}")
    try:
        return GatewayConfig(
            profiles={**routing.profiles, **hosted.profiles}, routes=routing.routes,
            budget=routing.budget, retry=routing.retry, hosted_enabled=hosted.enabled)
    except ValidationError as error:
        raise _first_error(routing_path, error) from error

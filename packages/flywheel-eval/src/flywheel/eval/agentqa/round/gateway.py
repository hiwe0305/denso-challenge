"""The model gateway: the one place of the round pipeline that calls a model (DA-43 task 5.1).

    gateway = Gateway(run_dir, load_gateway_config())
    reply = gateway.call("rank", ModelRequest(unit=..., system=..., user=..., max_tokens=...))

Architecture 20/11 section 8. In order, for every call:

1. The data class comes from the run's `admission.json` (step B1), never from the
   caller. The route `role x class` names a profile. A hosted profile is refused unless
   the hosted block is on and the admission shows a confirmed `public` pack. This check
   is written again here, apart from B1's, so one config or B1 error cannot leak data.
   Every route of the pack's class is checked when the gateway is built, so a refused
   run stops before its first call; `call` checks again. Refusal raises `GatewayRefused`.
2. A request whose sha256 is already answered in `model_calls.jsonl` is given back
   from the file, with no provider call and no line added.
3. The run's budget (calls, input tokens, dollars) is checked before every provider
   call. Once a cap is hit the gateway stops calling and answers `budget_exhausted`:
   the caller falls back to the code floor and the run is `degraded`.
4. A retryable provider error is tried again at most `retry.retries` (<= 2) times,
   waiting base, 2 x base; `sleep` is injectable. A call that still fails answers
   `failed`, never raises.
5. One line per request goes to `model_calls.jsonl`, the only file holding durations.
   Values of the key variables are scrubbed from the reply and the error before writing.

Calls are sequential (one local GPU); hosted concurrency comes with task 5.4.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from flywheel.eval.agentqa.endpoint import load_endpoint
from flywheel.eval.agentqa.round.admit import ADMISSION_FILE
from flywheel.eval.agentqa.round.gateway_config import (
    ROLES,
    GatewayConfig,
    GatewayRefused,
    Profile,
)
from flywheel.eval.agentqa.round.providers import ChatModel, ProviderError, ProviderReply
from flywheel.eval.agentqa.round.providers.local import LocalEndpointModel
from flywheel.eval.agentqa.round.records import (
    Admission,
    CallStatus,
    ModelCallRecord,
    ModelRequest,
)
from flywheel.eval.agentqa.round.version import AGENT_CONFIG
from pydantic import ValidationError

MODEL_CALLS_FILE = "model_calls.jsonl"
REPLAYABLE: frozenset[str] = frozenset({"ok", "cut"})  # a failure is tried again on a rerun
ProviderFactory = Callable[[str, Profile], ChatModel]


def build_provider(name: str, profile: Profile, agent_config: Path = AGENT_CONFIG) -> ChatModel:
    """The provider of `profile`. Only the gateway calls this, after the class check.

    The one seam: hosted kinds (`openai_compatible`, `anthropic`) are built here from
    `round/providers/`, and nowhere else. A missing key variable or SDK is a refusal.
    """
    if profile.provider == "local_openai" and not profile.hosted:
        assert profile.endpoint is not None  # the profile validator requires it
        try:
            return LocalEndpointModel(load_endpoint(profile.endpoint, agent_config))
        except (ValueError, KeyError, OSError) as error:
            raise GatewayRefused(f"profile {name}: {error}") from error
    assert profile.model is not None and profile.api_key_env is not None  # validator
    try:
        if profile.provider == "anthropic":
            from flywheel.eval.agentqa.round.providers.anthropic import AnthropicModel
            return AnthropicModel(profile.model, profile.api_key_env,
                                  base_url=profile.base_url, thinking=profile.thinking)
        assert profile.base_url is not None  # validator
        from flywheel.eval.agentqa.round.providers.openai_hosted import OpenAICompatibleModel
        return OpenAICompatibleModel(profile.model, profile.api_key_env, profile.base_url)
    except GatewayRefused as error:
        raise GatewayRefused(f"profile {name}: {error}") from error


def hosted_refusal(admission: Admission, hosted_enabled: bool) -> str | None:
    """Why a hosted model may not see this pack, or None when it may.

    Deliberately not B1's code: it reads B1's record and asks every condition again.
    """
    if not hosted_enabled:
        return "the hosted block is off (hosted.yaml enabled: false)"
    if admission.data_class != "public":
        return f"the pack is {admission.data_class}; only public packs reach a hosted model"
    if admission.unconfirmed:
        return ("the class of " + ", ".join(admission.unconfirmed) + " is unknown: no source "
                "record vouches for it")
    if not admission.data_class_basis:
        return "no source record in the pack says public"
    if not admission.hosted_allowed:
        return "the admission does not allow a hosted model"
    return None


def _read_admission(run_dir: Path) -> Admission:
    path = run_dir / ADMISSION_FILE
    try:
        return Admission.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise GatewayRefused(f"{path}: the pack's class is unknown "
                             f"({str(error).strip().splitlines()[0][:200]})") from error


def _sha(payload: object) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GatewayReply:
    """What a role gets back. Only `ok` carries a whole reply; `cut` carries a cut one."""

    status: CallStatus
    call_id: str
    text: str = ""
    replayed: bool = False
    error: str = ""


@dataclass
class Usage:
    """Provider calls of the run directory (replays cost nothing), for run.json and the ledger.

    Rebuilt from `model_calls.jsonl` when a gateway is built, so the caps of the budget
    hold across commands on one run directory, not per command.
    """

    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    usd: float = 0.0
    replayed: int = 0
    exhausted: str = ""  # the cap that stopped the gateway, once one did
    hosts: set[str] = field(default_factory=set)


class Gateway:
    """See the module docstring. One gateway per command; usage and caps are the run directory's."""

    def __init__(self, run_dir: Path, config: GatewayConfig, *,
                 factory: ProviderFactory | None = None,
                 agent_config: Path = AGENT_CONFIG,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._dir = run_dir
        self._config = config
        self._factory = factory or (lambda n, p: build_provider(n, p, agent_config))
        self._sleep, self._clock = sleep, clock
        self._admission = _read_admission(run_dir)
        self._providers: dict[str, ChatModel] = {}
        self.usage = Usage()
        for role in ROLES:  # a refused run stops before its first call
            self._route(role)
        self._lines = 0
        self._answered: dict[str, ModelCallRecord] = {}
        path = run_dir / MODEL_CALLS_FILE
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                record = ModelCallRecord.model_validate_json(line)
                self._lines += 1
                self._recount(record)
                if record.status in REPLAYABLE:
                    self._answered[record.request_sha256] = record

    def _recount(self, record: ModelCallRecord) -> None:
        """Add a recorded line to the usage: the caps are those of the run directory."""
        used = self.usage
        used.calls += record.tries
        used.tokens_in += record.tokens_in
        used.tokens_out += record.tokens_out
        used.usd += record.usd
        if record.tries:
            used.hosts.add(record.host)

    @property
    def data_class(self) -> str:
        return self._admission.data_class

    def _route(self, role: str) -> tuple[str, Profile]:
        if role not in ROLES:
            raise GatewayRefused(f"unknown role {role!r} (roles: {', '.join(ROLES)})")
        data_class = self._admission.data_class
        name = self._config.routes.get(role, {}).get(data_class)
        profile = self._config.profiles.get(name) if name else None
        if name is None or profile is None:
            raise GatewayRefused(f"no profile for {role} on a {data_class} pack")
        if profile.hosted:
            reason = hosted_refusal(self._admission, self._config.hosted_enabled)
            if reason is not None:
                raise GatewayRefused(f"{role} routes to hosted profile {name}: {reason}")
        return name, profile

    def _provider(self, name: str, profile: Profile) -> ChatModel:
        if name not in self._providers:
            self._providers[name] = self._factory(name, profile)
        return self._providers[name]

    def _scrub(self, text: str, provider: ChatModel) -> str:
        names = {provider.key_env, *(p.api_key_env for p in self._config.profiles.values())}
        for env in names:
            value = os.environ.get(env) if env else None
            if value:
                text = text.replace(value, "[key]")
        return text

    def _over_budget(self, profile: Profile, est_in: int, max_tokens: int) -> str:
        budget, used = self._config.budget, self.usage
        est_usd = (est_in * profile.usd_per_mtok_in + max_tokens * profile.usd_per_mtok_out) / 1e6
        if used.calls + 1 > budget.max_calls:
            return f"max_calls {budget.max_calls}"
        if used.tokens_in + est_in > budget.max_input_tokens:
            return f"max_input_tokens {budget.max_input_tokens}"
        if used.usd + est_usd > budget.max_usd:
            return f"max_usd {budget.max_usd:g}"
        return ""

    def call(self, role: str, request: ModelRequest) -> GatewayReply:
        """Answer `request` for `role`; raises only `GatewayRefused`."""
        name, profile = self._route(role)
        provider = self._provider(name, profile)
        max_tokens = min(request.max_tokens, profile.max_tokens)
        prompt = {"system": request.system, "user": request.user}
        request_sha = _sha({**prompt, "role": role, "unit": request.unit,
                            "attempt": request.attempt, "reply_schema": request.reply_schema,
                            "max_tokens": max_tokens, "profile": name,
                            "model": provider.model, "revision": provider.revision})
        known = self._answered.get(request_sha)
        if known is not None:
            self.usage.replayed += 1
            return GatewayReply(status=known.status, call_id=known.call_id, text=known.reply,
                                replayed=True)

        est_in = math.ceil((len(request.system) + len(request.user))
                           / self._config.budget.chars_per_token)
        began = self._clock()
        reply: ProviderReply | None = None
        status: CallStatus = "failed"
        error, tries = "", 0
        for retry in range(self._config.retry.retries + 1):
            cap = self.usage.exhausted or self._over_budget(profile, est_in, max_tokens)
            if cap:
                self.usage.exhausted, status, error = cap, "budget_exhausted", f"budget: {cap}"
                break
            if retry:
                self._sleep(self._config.retry.base_delay_s * 2 ** (retry - 1))
            tries += 1
            self.usage.calls += 1
            try:
                reply = provider.chat(request.system, request.user,
                                      reply_schema=request.reply_schema,
                                      max_tokens=max_tokens, timeout_s=profile.timeout_s)
            except ProviderError as failure:
                error = str(failure)
                if not failure.retryable:
                    break
                continue
            status = "cut" if reply.cut else "ok"
            error = ""
            break

        tokens_in = reply.tokens_in if reply and reply.tokens_in is not None else None
        tokens_out = reply.tokens_out if reply and reply.tokens_out is not None else None
        if reply is not None:
            self.usage.tokens_in += tokens_in if tokens_in is not None else est_in
            self.usage.tokens_out += tokens_out or 0
        t_in = tokens_in if tokens_in is not None else (est_in if reply else 0)
        t_out = tokens_out or 0
        usd = (t_in * profile.usd_per_mtok_in + t_out * profile.usd_per_mtok_out) / 1e6
        self.usage.usd += usd
        if tries:
            self.usage.hosts.add(provider.host)
        record = ModelCallRecord(
            call_id=f"M{self._lines + 1}", role=role, unit=request.unit,
            attempt=request.attempt, request_sha256=request_sha, prompt_sha256=_sha(prompt),
            data_class=self._admission.data_class, profile=name, provider=profile.provider,
            hosted=profile.hosted, model=provider.model, revision=provider.revision,
            host=provider.host, tokens_in=t_in, tokens_out=t_out,
            tokens_estimated=reply is not None and tokens_in is None, usd=usd,
            seconds=max(self._clock() - began, 0.0), tries=tries, status=status,
            reply=self._scrub(reply.text, provider) if reply else "",
            error=self._scrub(error, provider))
        self._append(record)
        return GatewayReply(status=status, call_id=record.call_id, text=record.reply,
                            error=record.error)

    def _append(self, record: ModelCallRecord) -> None:
        with (self._dir / MODEL_CALLS_FILE).open("a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")
        self._lines += 1
        if record.status in REPLAYABLE:
            self._answered[record.request_sha256] = record


__all__ = ["MODEL_CALLS_FILE", "Gateway", "GatewayRefused", "GatewayReply", "Usage",
           "build_provider", "hosted_refusal"]

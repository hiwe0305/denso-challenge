"""Role adjudicate: version 3's review of each source, through the gateway (DA-43 tasks 5.2, 5.3).

The round directory also gets the per-source `AgentReport`s `fw agentqa run` writes,
so the seeded-fault bench (DA-31) scores the round path as it scored version 3:

    reports.jsonl     every AgentReport, one per line, as `run.py` writes it
    dropped.jsonl     code candidates the model dropped, additions code refused
    estimates.jsonl   the estimates of the reports (append-only rows)
    figures/*.svg     the figures the reports name

Nothing is written for a pack with no source version 3 analyses. Which pack kinds are
sources, and of which subject (`run.subjects` builds them, in its order):

    metrics          one `train` subject per entry; the entries of kind action_layout,
                     probe_p3, probe_p4, probe_p4_parent of the same job (`subject.job`,
                     else the entry's directory) are put beside it under the file names
                     DA-08 reads, and only those: no file the pack did not admit is read
    rtc_log          one `inference` subject per entry
    qa_reports, dataset_report, episodes, replay_reports   one `dataset` subject
    probe_p1, probe_p3   one `stage1` or `stage3` subject each

`scores` and `clusters` (version 3's `eval` subject) are left out: the round's own steps
B2-B5 judge them. The rank role does not read these reports yet (a later task).

The analysis, the prompt, the reply rules and the assembly are `agent.review_subject`'s,
unchanged. Only the model differs: `GatewayChatModel` sends each turn through
`Gateway.call("adjudicate", ...)`, so the data-class barrier, the budget and the
record/replay of `model_calls.jsonl` hold. With no gateway (`--no-model`) the
`CodeFloorModel` answers: it keeps every candidate a lane detector raised, drops every
hint and cites the candidate's first fact, so the reports hold what code found.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath

from flywheel.contracts.agentqa import AgentReport
from flywheel.eval.agentqa.agent import AgentConfig, load_agent_config, review_subject
from flywheel.eval.agentqa.analyze import OfflineThresholds
from flywheel.eval.agentqa.endpoint import EndpointError, Message, ReplyCut
from flywheel.eval.agentqa.estimates import record_estimates
from flywheel.eval.agentqa.facts import DroppedCandidate
from flywheel.eval.agentqa.inputs import InputSet, Loaded
from flywheel.eval.agentqa.round.admit import Admitted
from flywheel.eval.agentqa.round.gateway import Gateway
from flywheel.eval.agentqa.round.pack import PackRefused, sha256_of
from flywheel.eval.agentqa.round.records import ModelRequest, Pack, PackEntry
from flywheel.eval.agentqa.round.version import AGENT_CONFIG
from flywheel.eval.agentqa.run import (
    draw_figures,
    subjects,
    write_dropped,
    write_reports,
)
from flywheel.eval.api import DEFAULT_SYSTEM_CONFIG, DEFAULT_TRAIN_CONFIG
from flywheel.eval.diagnosis.train.artifact import (
    LAYOUT_NAME,
    METRICS_NAME,
    PROBE_P3_NAME,
    PROBE_P4_NAME,
    PROBE_P4_PARENT_NAME,
)

ROLE = "adjudicate"
REPORTS_FILE = "reports.jsonl"
DROPPED_FILE = "dropped.jsonl"
ESTIMATES_FILE = "estimates.jsonl"
FIGURES_DIR = "figures"
# What OpenAI-style and Anthropic servers use when a request sends no temperature, as the
# hosted providers do; recorded because `AgentModel.temperature` cannot say "not sent".
HOSTED_TEMPERATURE = 1.0
# pack kind -> the kind version 3's `inputs.kind_of` gives the same file
V3_KIND: dict[str, str] = {
    "metrics": "metrics", "rtc_log": "rtc_log", "qa_reports": "qa_reports",
    "dataset_report": "dataset_report", "episodes": "episodes",
    "replay_reports": "replay_reports", "probe_p1": "probe", "probe_p3": "probe",
}
# pack kind -> the file name DA-08's `load_job` looks for beside metrics.jsonl
TRAIN_COMPANIONS: dict[str, str] = {
    "action_layout": LAYOUT_NAME, "probe_p3": PROBE_P3_NAME, "probe_p4": PROBE_P4_NAME,
    "probe_p4_parent": PROBE_P4_PARENT_NAME,
}


def adjudicable(entries: Sequence[PackEntry]) -> list[PackEntry]:
    """The entries that are sources of a version 3 subject (module docstring)."""
    return [e for e in entries if e.kind in V3_KIND]


class CodeFloorModel:
    """The code layer as a version 3 model: the reply `--no-model` stands on.

    Keeps every candidate a lane detector raised (origin `code`), drops every hint and
    writes one sentence citing the candidate's first fact. Adds nothing, estimates nothing.
    """

    name = "code-floor"
    revision = "v3"
    temperature = 0.0

    def complete(self, messages: Sequence[Message]) -> str:
        payload = json.loads(str(messages[1]["content"]))
        decisions = [{
            "cid": c["cid"], "keep": c["origin"] == "code",
            "priority": 1 if c["code"][:1] in ("T", "R") else 2,
            "insight": (f"{c['code']} on {c['target']}: {{{c['evidence'][0]}}}."
                        if c["evidence"] else f"{c['code']} on {c['target']}."),
            "suggestion": "Raised by a lane detector; no model reviewed it.",
            "evidence": list(c["evidence"][:1]),
        } for c in payload["candidates"]]
        return json.dumps({"decisions": decisions, "added": [], "estimates": []})


class GatewayChatModel:
    """Version 3's `ChatModel` on top of `Gateway.call("adjudicate", ...)`; one per subject.

    One `complete` is one gateway call. `review_subject` sends a batch as [system, user]
    and resends it once as [system, user, assistant, user]: the number of assistant turns
    is the resend count, so attempt = 1 + that count, and a first attempt starts a new
    batch. `unit` is `<subject>#<batch>`. The gateway takes one user text, so a resend's
    turns are joined into it under labels.

    A refused, failed or budget-stopped call raises `EndpointError`, a cut reply
    `ReplyCut`, as a dead or cutting endpoint does: `review_subject` then records the
    batch as a problem and the report is `broken` (or splits a cut batch).
    """

    def __init__(self, gateway: Gateway, subject: str, max_tokens: int) -> None:
        profile, provider = gateway.routed(ROLE)
        self._gateway, self._subject, self._max_tokens = gateway, subject, max_tokens
        self._batch = 0
        self.name = provider.model or "-"
        self.revision = provider.revision or "-"
        local = getattr(provider, "temperature", None)
        self.temperature = (HOSTED_TEMPERATURE if profile.hosted or not isinstance(
            local, (int, float)) else float(local))
        self.call_ids: list[str] = []

    def complete(self, messages: Sequence[Message]) -> str:
        resends = sum(1 for m in messages if m["role"] == "assistant")
        if resends > 1:
            raise EndpointError("the gateway sends a batch at most twice; set limits.retries "
                                "to 1 or less in agent.yaml")
        if resends == 0:
            self._batch += 1
        system, first = str(messages[0]["content"]), str(messages[1]["content"])
        user = first if not resends else "\n\n".join(
            [first] + [f"[{m['role']}]\n{m['content']}" for m in messages[2:]])
        reply = self._gateway.call(ROLE, ModelRequest(
            unit=f"{self._subject}#{self._batch}", attempt=2 if resends else 1,
            system=system, user=user, max_tokens=self._max_tokens))
        self.call_ids.append(reply.call_id)
        if reply.status == "ok":
            return reply.text
        if reply.status == "cut":
            raise ReplyCut(f"gateway call {reply.call_id}: reply cut at max_tokens "
                           f"{self._max_tokens}", reply.text)
        raise EndpointError(f"gateway call {reply.call_id} {reply.status}: {reply.error}")


@dataclass
class AdjudicateResult:
    reports: list[AgentReport] = field(default_factory=list)
    dropped: dict[str, tuple[DroppedCandidate, ...]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def _job_key(entry: PackEntry) -> str:
    return entry.subject.get("job") or PurePosixPath(entry.ref).parent.as_posix()


def _stage(root: Path, entry: PackEntry, target: Path) -> None:
    """Copy an admitted file to `target`, refusing it if it is not the file packed."""
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / entry.ref, target)
    if sha256_of(target) != entry.sha256:
        raise PackRefused(f"{entry.ref}: the file changed after it was packed")


def _loaded(root: Path, staging: Path, entries: Sequence[PackEntry],
            admitted: Admitted) -> list[Loaded]:
    """The sources as version 3 loads them; a train job's files staged together."""
    companions: dict[str, list[PackEntry]] = {}
    for e in entries:
        if e.kind in TRAIN_COMPANIONS:
            companions.setdefault(_job_key(e), []).append(e)
    out: list[Loaded] = []
    for n, entry in enumerate(entries):
        if entry.kind not in V3_KIND:
            continue
        path = root / entry.ref
        if entry.kind == "metrics":
            # The job's directory name is its unit (`train/<job>`), as in version 3.
            job_dir = staging / str(n) / PurePosixPath(entry.ref).parent.name
            path = job_dir / METRICS_NAME
            _stage(root, entry, path)
            for c in companions.get(_job_key(entry), []):
                _stage(root, c, job_dir / TRAIN_COMPANIONS[c.kind])
        records = tuple(admitted.records[entry.ref])  # checks the sha256 the pack records
        out.append(Loaded(path, entry.ref, V3_KIND[entry.kind], entry.sha256, records))
    return sorted(out, key=lambda x: x.ref)


def adjudicate(out: Path, root: Path, pack: Pack, admitted: Admitted,
               gateway: Callable[[], Gateway] | None, *, config: AgentConfig | None = None,
               train_config: Path = DEFAULT_TRAIN_CONFIG,
               system_config: Path = DEFAULT_SYSTEM_CONFIG,
               now: datetime | None = None) -> AdjudicateResult:
    """Review every version 3 subject of the admitted pack rooted at `root` into `out`.

    `gateway` builds the gateway when the first subject needs it (None: the code floor),
    so a pack with no source builds none and writes nothing. A `broken` report is a
    problem line of the result, for the run to be `degraded`.
    """
    result = AdjudicateResult()
    accepted = set(admitted.admission.accepted)
    entries = adjudicable([e for e in pack.entries if e.ref in accepted])
    if not entries:
        return result
    config = config or load_agent_config(AGENT_CONFIG)
    gate = gateway() if gateway is not None else None
    offline = OfflineThresholds(**(config.raw.get("offline") or {}))
    with tempfile.TemporaryDirectory(prefix="agentqa-adjudicate-") as staging:
        accepted_entries = [e for e in pack.entries if e.ref in accepted]
        found = InputSet(_loaded(root, Path(staging), accepted_entries, admitted))
        analyses = subjects(found, offline, train_config, system_config)
        for n, analysis in enumerate(analyses, start=1):
            analysis.figures = draw_figures(analysis, found, out / FIGURES_DIR, n)
            model = (CodeFloorModel() if gate is None
                     else GatewayChatModel(gate, analysis.subject_ref, config.reply_tokens))
            reviewed = review_subject(analysis, model, config, now=now)
            report = reviewed.report
            result.reports.append(report)
            result.dropped[report.report_id] = reviewed.dropped
            record_estimates(report, out / ESTIMATES_FILE)
            if report.status == "broken":
                result.problems.append(f"{report.subject_ref}: report broken: "
                                       f"{'; '.join(report.problems)[:300]}")
    write_reports(result.reports, out / REPORTS_FILE)
    write_dropped(result.reports, result.dropped, out / DROPPED_FILE)
    return result


__all__ = ["DROPPED_FILE", "ESTIMATES_FILE", "FIGURES_DIR", "REPORTS_FILE", "ROLE",
           "AdjudicateResult", "CodeFloorModel", "GatewayChatModel", "adjudicable",
           "adjudicate"]

"""Builders the Agent QA/QC tests (DA-20) import by name: artifacts on disk, scripted models.

Everything is built in the test from the contracts, on CPU; nothing here imports
the data lane or a model runtime. `ScriptedModel` puts the testkit's `FakeLLM`
behind the `ChatModel` protocol; `EchoModel` answers like a model that keeps
every code candidate, drops every hint and cites the candidate's first fact.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flywheel.contracts.artifacts import Episode, QACheck, QAReport, RTCInferenceRecord
from flywheel.contracts.training import TrainingMetric
from flywheel.eval.agentqa.endpoint import Message
from flywheel.testkit.fakes.llm import FakeLLM

if TYPE_CHECKING:  # imported lazily in config(), so the endpoint tests need only endpoint.py
    from flywheel.eval.agentqa.agent import AgentConfig

REPO = Path(__file__).resolve().parents[5]
AGENT_YAML = REPO / "configs" / "eval" / "agentqa" / "agent.yaml"
TRAIN_YAML = REPO / "configs" / "eval" / "diagnosis" / "train.yaml"
SYSTEM_YAML = REPO / "configs" / "eval" / "diagnosis" / "system.yaml"


class ScriptedModel:
    """Replies given in advance, through the testkit's FakeLLM; requests are kept."""

    name = "fake"
    revision = "r0"
    temperature = 0.0

    def __init__(self, replies: Sequence[str | dict[str, Any]]) -> None:
        self.llm = FakeLLM(r if isinstance(r, str) else json.dumps(r) for r in replies)
        self.messages: list[list[Message]] = []

    def complete(self, messages: Sequence[Message]) -> str:
        self.messages.append(list(messages))
        return self.llm.complete(str(messages[-1]["content"]))


class EchoModel:
    name = "echo"
    revision = "r0"
    temperature = 0.0

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: Sequence[Message]) -> str:
        self.calls += 1
        payload = json.loads(str(messages[1]["content"]))
        decisions = [
            {
                "cid": c["cid"],
                "keep": c["origin"] == "code",
                "priority": 1 if c["code"][0] in "TR" else 2,
                "insight": f"{c['code']} on {c['target']}: {{{c['evidence'][0]}}}.",
                "suggestion": "Quarantine and look at the job.",
                "evidence": c["evidence"][:1],
            }
            for c in payload["candidates"]
        ]
        return json.dumps({"decisions": decisions, "added": [], "estimates": []})


def config() -> AgentConfig:
    from flywheel.eval.agentqa.agent import load_agent_config

    return load_agent_config(AGENT_YAML)


def write_lines(path: Path, rows: Sequence[Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(r.model_dump_json() + "\n" for r in rows), encoding="utf-8")
    return path


def train_job(
    job: Path,
    loss: Callable[[int], float | str] = lambda step: 1.0 / (step + 1),
    steps: Sequence[int] = range(0, 100, 10),
    **extra: Any,
) -> Path:
    """A train job's metrics.jsonl; `extra` sets more fields on every row (pred_std...)."""
    rows = [
        TrainingMetric(
            run_plan_id="rp", job_id=job.name, checkpoint_id="ck", release_id="rel", attempt=0,
            step=step, epoch=0, split="train", loss=loss(step), lr=1e-4, vlm_frozen=True,
            wall_time_s=float(step), **extra,
        )
        for step in steps
    ]
    return write_lines(job / "metrics.jsonl", rows)


def rtc_job(job: Path, latency: float = 0.05, delay_steps: int = 2, n: int = 50) -> Path:
    rows = [
        RTCInferenceRecord(
            job_id=job.name, trace_id="t", chunk_index=i, observation_sent_s=i * 0.5,
            chunk_received_s=i * 0.5 + latency, delay_steps=delay_steps, buffer_level=0,
            boundary_jump=0.0,
        )
        for i in range(n)
    ]
    return write_lines(job / "rtc.jsonl", rows)


def qa_work(
    root: Path,
    n: int,
    reasons: Mapping[int, Sequence[str]] | None = None,
    values: Mapping[int, float] | None = None,
) -> Path:
    """A `fw data qa` work dir; `reasons` maps an episode index to its QA reasons."""
    text = (files("flywheel.testkit") / "fixtures/artifacts/Episode.json").read_text()
    base = Episode.model_validate_json(text)
    reasons, values = reasons or {}, values or {}
    episodes, index, reports = [], {}, []
    for i in range(n):
        eid = f"ep_{i:016x}"
        episodes.append(base.model_copy(update={"episode_id": eid}))
        index[eid] = i
        why = list(reasons.get(i, []))
        value = values.get(i, 0.001 * (i + 1))
        checks = [
            QACheck(name="finite_values", value=1.0 if why else 0.0, threshold=0.0,
                    passed=not why),
            QACheck(name="action_jump", value=value, threshold=0.5, passed=True),
            QACheck(name="timestamp_step", value=value / 2, threshold=1.0, passed=True),
        ]
        reports.append(QAReport(report_id=f"qa_{i}", episode_id=eid, threshold_version="v1",
                                decision="reject" if why else "pass", reasons=why,
                                checks=checks))
    write_lines(root / "episodes.jsonl", episodes)
    (root / "episode_index.json").write_text(json.dumps(index))
    write_lines(root / "qa" / "reports.jsonl", reports)
    return root

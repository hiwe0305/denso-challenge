"""Hand-built run directories and answer files for the case bench tests.

Chosen over running the real pipeline: the files are written with the real record classes
of `agentqa/round`, so each test states exactly the run it scores.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from flywheel.eval.agentqa.round.records import (
    Assembly,
    CheckRef,
    ClusterRef,
    ClusterView,
    FactRecord,
    HypothesisView,
    Pack,
    PackEntry,
    RunRecord,
    StepRecord,
)

SHA = "0" * 64
NOW = datetime(2026, 11, 22, tzinfo=timezone.utc)
PLACE = {"run": "C_70", "step": "approach_a", "label": "L-PLACE-POSE", "level": 2}
TIMEOUT = {"run": "C_70", "step": "approach_a", "label": "L-TIMEOUT", "level": 1}


def hyp(diagnosis: str, rank: int, note: str = "n") -> HypothesisView:
    return HypothesisView(hypothesis_id=f"H{rank}", rule_id=f"r_{diagnosis}", title=diagnosis,
                          group="data", diagnosis=diagnosis, note=note, rank=rank,  # type: ignore[arg-type]
                          source="code")


def view(key: dict[str, Any], order: list[tuple[str, str]], *, blocked: bool = False,
         intervention: str | None = "repair_ticket", check: str | None = "chk_a") -> ClusterView:
    ref = ClusterRef(cluster_id="/".join(map(str, key.values())), size=3, **key)
    return ClusterView(
        cluster=ref, hypotheses=[hyp(d, i, n) for i, (d, n) in enumerate(order, 1)],
        blocked_data_spend=blocked, intervention=intervention,
        check=CheckRef(check_id=check, cost_key="k", cost_rank=1) if check else None)


def default_clusters() -> list[ClusterView]:
    return [view(PLACE, [("unknown", "scorer_threshold"), ("weak_skill", "x")]),
            view(TIMEOUT, [("controller", "x"), ("weak_skill", "y")], blocked=True)]


def fact(name: str, value: Any, ref: str = "C_70/scores.jsonl") -> FactRecord:
    return FactRecord(fact_id=f"F_{name}", name=name, value=value, source_ref=ref,
                      provenance="code", tool_call_id="T1")


def make_run(root: Path, name: str = "run", *, clusters: list[ClusterView] | None = None,
             facts: list[FactRecord] | None = None, pack_id: str = "p1",
             run_id: str | None = None, steps_status: str = "ok", assembly: bool = True,
             pack_refs: list[str] | None = None, agent_hash: str = "h1") -> Path:
    out = root / name
    out.mkdir(parents=True)
    steps = [StepRecord(name="assemble", status=steps_status, seconds=0, rows=1)]  # type: ignore[arg-type]
    (out / "run.json").write_text(RunRecord(
        run_id=run_id or f"run_{name}", started_at=NOW, pack_id=pack_id, status="ok",
        steps=steps, agent_hash=agent_hash).model_dump_json())
    refs = pack_refs or ["C_70/scores.jsonl"]
    (out / "pack.json").write_text(Pack(
        pack_id=pack_id, task_id="tray", created_at=NOW, declared_by="t",
        entries=[PackEntry(ref=r, kind="scores", sha256=SHA, bytes=1, data_class="public")
                 for r in refs]).model_dump_json())
    (out / "facts.jsonl").write_text("".join(
        f.model_dump_json() + "\n" for f in (facts if facts is not None else [])))
    if assembly:
        views = clusters if clusters is not None else default_clusters()
        (out / "assembly.json").write_text(Assembly(
            run_id=f"run_{name}", pack_id=pack_id, task_id="tray", data_class="public",
            status="ok", agent_version="v", agent_hash=agent_hash, clusters=views
        ).model_dump_json())
    return out


def write_answer(root: Path, points: list[dict[str, Any]], *, name: str = "case.yaml",
                 folder: str = "answers") -> Path:
    path = root / folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({
        "case_id": "tray-c70-step4", "set": "dev", "task_id": "tray", "focus_run": "C_70",
        "written_by": "t", "points": points}))
    return path

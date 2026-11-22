"""Builders of the round tests: a 4-run pack from the tool tests' rollouts, and readers.

A plain module (not a conftest): mypy refuses two `conftest` modules in one run.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.contracts.entities import Score, Source
from flywheel.eval.agentqa.round.admit import write_admission
from flywheel.eval.agentqa.round.pack import build_pack, write_pack
from flywheel.eval.agentqa.round.providers import ProviderReply
from flywheel.eval.agentqa.round.records import (
    Admission,
    DataClass,
    FactRecord,
    ToolCallRecord,
)

PLAN = Path("configs") / "eval" / "agentqa" / "plans" / "tray.yaml"  # from the repo root
PackMaker = Callable[..., Path]
DATA = Path(__file__).parents[1] / "tools" / "data" / "pair60k_stage1.jsonl"
SHA = "0" * 64
NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)


def _status(flags: str) -> list[str]:
    out, failed = [], False
    for flag in flags:
        if flag == "1":
            out.append("pass")
        elif not failed:
            out.append("fail")
            failed = True
        else:
            out.append("not_attempted")
    return out


def _score_line(row: dict[str, object]) -> str:
    status = _status(str(row["steps"]))
    run = row["run"]
    return Score(
        episode_id=f"{run}/l{row['level']}-s{row['seed']}", task_id="tray",
        config_sha256=SHA, trace_sha256=SHA, success=bool(row["success"]),
        step_status=status,  # type: ignore[arg-type]
        first_failed_step=next((k for k, s in enumerate(status) if s == "fail"), None),
        failure_kind=row["failure"], level=row["level"],  # type: ignore[arg-type]
    ).model_dump_json()


def pack_maker(tmp_path: Path) -> PackMaker:
    """`make(name, scores=True)` -> path of a `pack.json` under tmp_path/name."""

    def make(name: str = "round", *, scores: bool = True,
             rename: dict[str, str] | None = None, snapshot_of: Path | None = None,
             snapshot_class: DataClass = "internal", link_snapshot: bool = False) -> Path:
        root = tmp_path / name
        root.mkdir()
        by_run: dict[str, list[str]] = defaultdict(list)
        for line in DATA.read_text().splitlines():
            row = json.loads(line)
            by_run[row["run"]].append(_score_line(row))
        (root / "sources.jsonl").write_text(Source(
            uri="hf://psi-data", sha256=SHA, downloaded_at="2026-11-01",
            data_class="public").model_dump_json() + "\n")
        entries: list[dict[str, object]] = [{"path": "sources.jsonl", "kind": "sources"}]
        links = []
        for run, lines in by_run.items() if scores else []:
            (root / run).mkdir()
            (root / run / "scores.jsonl").write_text("\n".join(lines) + "\n")
            entries.append({"path": f"{run}/scores.jsonl", "kind": "scores",
                            "subject": {"run": (rename or {}).get(run, run)}})
            links.append({"source": f"{run}/scores.jsonl", "target": "sources.jsonl",
                          "relation": "data_of"})
        declared: dict[str, object] = {
            "task_id": "tray", "declared_by": "test", "data_class": "public",
            "entries": entries, "links": links}
        if snapshot_of is not None:  # copy the ledger and fix-rate rows of that store in
            declared["store_snapshot"] = {"data_class": snapshot_class,
                                          "tables": ["ledger", "fix_rate"]}
            if link_snapshot:
                links.append({"source": "store_snapshot/ledger.jsonl",
                              "target": "sources.jsonl", "relation": "data_of"})
                links.append({"source": "store_snapshot/fix_rate.jsonl",
                              "target": "sources.jsonl", "relation": "data_of"})
        decl = root / "round.yaml"
        decl.write_text(yaml.safe_dump(declared))
        return write_pack(build_pack(decl, store=snapshot_of), root)

    return make


@pytest.fixture(autouse=True)
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rounds append ledger entries; none may reach the real store."""
    monkeypatch.setenv("FW_ROOT", str(tmp_path / "fwroot"))


def facts_of(out: Path) -> dict[str, FactRecord]:
    lines = (out / "facts.jsonl").read_text().splitlines()
    return {f.name: f for f in map(FactRecord.model_validate_json, lines)}


def calls_of(out: Path) -> list[ToolCallRecord]:
    return [ToolCallRecord.model_validate_json(x)
            for x in (out / "tool_calls.jsonl").read_text().splitlines()]


def edited_plan(tmp_path: Path, edit: object) -> Path:
    plan = yaml.safe_load(PLAN.read_text())
    edit(plan)  # type: ignore[operator]
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(plan))
    return path


class ScriptedChat:
    """A provider of the round's `ChatModel` that answers from a script.

    Each item is a reply text, a `ProviderReply`, or an exception to raise. Calls are
    kept as (system, user, max_tokens, timeout_s).
    """

    def __init__(self, script: list[str | ProviderReply | Exception], *,
                 model: str = "fake", revision: str = "r0", host: str = "127.0.0.1",
                 key_env: str | None = None) -> None:
        self.script = list(script)
        self.calls: list[tuple[str, str, int, float]] = []
        self.model, self.revision, self.host, self.key_env = model, revision, host, key_env

    def chat(self, system: str, user: str, *, reply_schema: dict[str, Any] | None,
             max_tokens: int, timeout_s: float) -> ProviderReply:
        self.calls.append((system, user, max_tokens, timeout_s))
        if not self.script:
            raise AssertionError("ScriptedChat: no scripted reply left")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, ProviderReply):
            return item
        return ProviderReply(text=item, tokens_in=100, tokens_out=20)


def admitted_run(tmp_path: Path, data_class: DataClass = "public", *,
                 confirmed: bool = True, name: str = "run") -> Path:
    """A run directory holding only an `admission.json` of the given class."""
    out = tmp_path / name
    out.mkdir()
    public = data_class == "public"
    write_admission(Admission(
        pack_id="p1", pack_sha256=SHA, accepted=["sources.jsonl", "scores.jsonl"],
        data_class=data_class,
        data_class_basis=["sources.jsonl"] if public and confirmed else [],
        unconfirmed=[] if confirmed else ["scores.jsonl"],
        hosted_allowed=public and confirmed), out)
    return out

"""Run the bench from a spec file: read every layer, open the keys, score, write.

    uv run python -m flywheel.eval.agentqa.bench --spec bench.json \\
        --answers fwdata/inject/answers --answers fwdata/inject-logs/answers \\
        --out fwdata/bench/<name>

The spec names the copies and where each layer's results are; paths in it are
relative to the spec file. It holds no path to an answer key: those come only on
the command line, and only this command reads them.

    {
      "copies": [
        {"group": "data", "dataset_id": "bench-1e258c0a78ca",
         "job_finished_at": "2026-11-04T10:00:00+00:00",
         "code": {"qa_work": "work/bench-1e258c0a78ca"},
         "agent_reports": ["agent/bench-1e258c0a78ca.jsonl"]},
        {"group": "logs", "dataset_id": "bench-...",
         "code": {"log_root": "fwdata/inject-logs/copies/bench-..."},
         "agent_reports": ["agent/logs-a.json"]}
      ],
      "reviews": ["reviews/r1.json"]
    }

An agent report file is one `AgentReport` (.json) or one per line (.jsonl). Like
every job, the run writes an estimated and a measured `LedgerEntry` (cpu_seconds,
activity `agent_qa`) to the store's ledger before and after it works.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from flywheel.contracts.agentqa import AgentReport, AgentReview
from flywheel.contracts.base import new_ulid
from flywheel.contracts.entities import LedgerEntry
from flywheel.eval.agentqa.bench.answers import AnswerKeyError
from flywheel.eval.agentqa.bench.detections import (
    BenchInputError,
    LayerRun,
    agent_run,
    read_qa_work,
)
from flywheel.eval.agentqa.bench.layers import agent_quality, split_by_layer
from flywheel.eval.agentqa.bench.logs import run_log_checks
from flywheel.eval.agentqa.bench.report import (
    GroupReport,
    ModelUse,
    bench_result,
    model_uses,
    write_bench,
)
from flywheel.eval.agentqa.bench.score import score_group
from flywheel.eval.agentqa.bench.session import AnswerLeak, BenchIncomplete, BenchSession
from flywheel.eval.api import DEFAULT_SYSTEM_CONFIG, DEFAULT_TRAIN_CONFIG
from flywheel.store.ledger_append import append_ledger_entry
from flywheel.store.paths import StorePaths

STORY = "DA-31"
# Assumed, not measured: scoring is a pass over small JSON files; the log
# detectors read one metrics.jsonl per job. The measured row says what it took.
SECONDS_PER_UNIT = 0.05


def run_bench(
    spec_path: Path,
    answer_roots: Sequence[Path],
    out: Path,
    *,
    train_config: Path = DEFAULT_TRAIN_CONFIG,
    system_config: Path = DEFAULT_SYSTEM_CONFIG,
    store: Path | None = None,
    run_plan_id: str | None = None,
) -> str:
    """Score the bench the spec describes; return the sha256 of the result."""
    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes)
    base = spec_path.parent
    copies = spec.get("copies") or []
    if not copies:
        raise BenchInputError(f"{spec_path}: no copies")
    paths = StorePaths(store)
    plan = run_plan_id or f"g0-{STORY}-{date.today():%Y%m%d}"
    job_id = f"job_bench_{new_ulid()}"
    estimate = _ledger(plan, job_id, SECONDS_PER_UNIT * 200 * len(copies), "estimated",
                       f"assumed {SECONDS_PER_UNIT:g} s per unit x 200 units per copy", None)
    append_ledger_entry(estimate, paths)
    start, outcome, notes = time.monotonic(), "ok", []
    try:
        session = BenchSession([(c["group"], c["dataset_id"]) for c in copies], answer_roots)
        models: dict[str, list[ModelUse]] = {}
        for entry in copies:
            code = _code_run(entry, base, train_config, system_config)
            reports = [r for p in entry.get("agent_reports", []) for r in _reports(base / p)]
            agent = agent_run(reports, entry["dataset_id"], code.units, code.aliases)
            models.setdefault(entry["dataset_id"], []).extend(
                model_uses(entry["dataset_id"], reports))
            finished = entry.get("job_finished_at")
            session.record(code, _when(finished) if finished else None)
            session.record(agent)
            notes.append(f"{entry['dataset_id']}: {len(code.units)} units")
        for review_path in spec.get("reviews", []):
            session.review(AgentReview.model_validate_json((base / review_path).read_text()))
        opened = session.open_answers()
        groups = []
        for group in opened.groups:
            score = score_group(group)
            used = [*models.get(score.injected_id, []), *models.get(score.clean_id, [])]
            groups.append(GroupReport(score, split_by_layer(score),
                                      agent_quality(group, score, opened.reviews),
                                      tuple(sorted(used))))
        result = bench_result(
            groups,
            created_at=datetime.now(timezone.utc),
            manifest_sha256=opened.manifest_sha256,
            inputs={
                "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(),
                "train_config_sha256": _sha(train_config),
                "system_config_sha256": _sha(system_config),
                "ledger": f"{plan}/{job_id}",
            },
        )
        digest = write_bench(out, result)
        notes.append(f"result {digest} at {out}")
        return digest
    except BaseException as error:
        outcome = f"failed: {type(error).__name__}"
        raise
    finally:
        text = "; ".join([f"wall seconds of the DA-31 bench, {outcome}", *notes])
        append_ledger_entry(
            _ledger(plan, job_id, max(time.monotonic() - start, 0.0), "measured", text,
                    estimate.id),
            paths,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m flywheel.eval.agentqa.bench",
        description="Score Agent QA/QC and the QA checks on DA-27's injected defects (DA-31).",
    )
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--answers", type=Path, action="append", required=True,
                        help="an answers/ root of DA-27; give one per benchmark build")
    parser.add_argument("--out", type=Path, required=True, help="a new dir for the result")
    parser.add_argument("--train-config", type=Path, default=DEFAULT_TRAIN_CONFIG)
    parser.add_argument("--system-config", type=Path, default=DEFAULT_SYSTEM_CONFIG)
    parser.add_argument("--store", type=Path, default=None, help="default $FW_ROOT or ./fwdata")
    parser.add_argument("--run-plan-id", default=None)
    args = parser.parse_args(argv)
    try:
        digest = run_bench(args.spec, args.answers, args.out, train_config=args.train_config,
                           system_config=args.system_config, store=args.store,
                           run_plan_id=args.run_plan_id)
    except (BenchInputError, BenchIncomplete, AnswerLeak, AnswerKeyError, FileExistsError,
            FileNotFoundError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(f"bench result {digest}: {args.out / 'index.html'}")
    return 0


def _code_run(entry: dict[str, Any], base: Path, train: Path, system: Path) -> LayerRun:
    code = entry.get("code") or {}
    if entry["group"] == "data" and "qa_work" in code:
        return read_qa_work(base / code["qa_work"], entry["dataset_id"])
    if entry["group"] == "logs" and "log_root" in code:
        run = run_log_checks(base / code["log_root"], train, system)
        if run.dataset_id != entry["dataset_id"]:
            raise BenchInputError(
                f"{code['log_root']} is copy {run.dataset_id}, not {entry['dataset_id']}"
            )
        return run
    raise BenchInputError(
        f"{entry['dataset_id']}: a data copy needs code.qa_work, a log copy code.log_root"
    )


def _reports(path: Path) -> list[AgentReport]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [AgentReport.model_validate_json(line) for line in text.splitlines() if line.strip()]
    return [AgentReport.model_validate_json(text)]


def _when(text: str) -> datetime:
    """An ISO time with its zone; a trailing Z is read as UTC (Python 3.10 does not)."""
    when = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    if when.tzinfo is None:
        raise BenchInputError(f"job_finished_at {text!r} has no time zone")
    return when


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ledger(plan: str, job_id: str, seconds: float, kind: str, note: str,
            estimate_id: str | None) -> LedgerEntry:
    return LedgerEntry.model_validate({
        "activity": "agent_qa",
        "resource_type": "cpu_seconds",
        "quantity": seconds,
        "unit": "s",
        "usd_amount": 0.0,
        "measure_kind": kind,
        "estimate_entry_id": estimate_id,
        "run_plan_id": plan,
        "job_id": job_id,
        "note": note,
    })

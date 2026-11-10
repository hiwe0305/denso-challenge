"""One Agent QA/QC run over the artifacts under some paths (DA-20 AC 2-6).

Subjects are found by what the paths hold:

    a dataset work dir   (qa/reports.jsonl, episodes.jsonl, dataset_report.json, replay*.jsonl)
                         -> one `dataset` report, findings per episode
    train/<job>/metrics.jsonl   -> one `train` report per job
    rtc/<job>/rtc.jsonl         -> one `inference` report per job
    probe*.json (P1, P3)        -> one `stage1` or `stage3` report each
    scores.jsonl, clusters.jsonl -> one `eval` report

Output, in a new directory (never overwritten):

    reports.jsonl        every AgentReport, one per line (what DA-31 reads)
    dropped.jsonl        each candidate a lane detector raised that the model dropped,
                         with its reason (#175); empty when none was dropped
    <n>-<stage>.html     one page per report; index.html lists them
    figures/*.svg        the figures the pages show
    estimates.jsonl      the estimates of this run (append-only rows)

Like every job, the run writes an estimated and a measured `LedgerEntry`
(`agent_qa`, wall seconds) to the store's ledger.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from flywheel.contracts.agentqa import AgentReport
from flywheel.contracts.base import new_ulid
from flywheel.contracts.entities import LedgerEntry
from flywheel.eval.agentqa import figures
from flywheel.eval.agentqa.agent import AgentConfig, review_subject
from flywheel.eval.agentqa.analyze import (
    OfflineThresholds,
    analyze_dataset,
    analyze_eval,
    analyze_rtc,
    analyze_stage1,
    analyze_stage3,
    analyze_train,
    job_unit,
)
from flywheel.eval.agentqa.endpoint import ChatModel
from flywheel.eval.agentqa.estimates import record_estimates
from flywheel.eval.agentqa.facts import Analysis, DroppedCandidate
from flywheel.eval.agentqa.html import render_index, render_report
from flywheel.eval.agentqa.inputs import InputSet, Loaded, collect, refuse_forbidden
from flywheel.eval.agentqa.vision import observe
from flywheel.eval.api import DEFAULT_SYSTEM_CONFIG, DEFAULT_TRAIN_CONFIG
from flywheel.store.ledger_append import append_ledger_entry
from flywheel.store.paths import StorePaths

STORY = "DA-20"
# Assumed, not measured: one model call of ~20 s per subject on the 3060 (Nemotron Q4).
SECONDS_PER_SUBJECT = 20.0
DATASET_KINDS = ("dataset_report", "qa_reports", "episodes", "episode_index", "replay_reports")


@dataclass
class RunResult:
    out: Path
    reports: list[AgentReport] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    # report_id -> code candidates the model dropped in that report
    dropped: dict[str, tuple[DroppedCandidate, ...]] = field(default_factory=dict)


def subjects(found: InputSet, offline: OfflineThresholds,
             train_config: Path, system_config: Path) -> list[Analysis]:
    """Every subject the loaded artifacts hold, analysed by code, in a stable order."""
    out: list[Analysis] = []
    dataset = InputSet([x for x in found.loaded if x.kind in DATASET_KINDS])
    if dataset.of("qa_reports") or dataset.of("dataset_report"):
        main = dataset.one("qa_reports") or dataset.one("dataset_report")
        assert main is not None
        out.append(analyze_dataset(dataset, main.ref))
    for item in found.of("metrics"):
        out.append(analyze_train(item, job_unit(item.path, "train"), train_config))
    for item in found.of("rtc_log"):
        out.append(analyze_rtc(item, job_unit(item.path, "rtc"), system_config))
    for item in found.of("probe"):
        probe = item.records[0].probe
        if probe == "P1":
            out.append(analyze_stage1(item))
        elif probe == "P3":
            out.append(analyze_stage3(item, offline))
    evals = InputSet([x for x in found.loaded if x.kind in ("scores", "clusters")])
    if evals.loaded:
        out.append(analyze_eval(evals, evals.loaded[0].ref))
    return out


def _figures(analysis: Analysis, found: InputSet, fig_dir: Path, n: int) -> list[str]:
    """Draw the subject's figures; return their paths relative to the report dir."""
    drawn: list[tuple[str, str]] = []
    if analysis.stage == "dataset":
        report = found.one("dataset_report")
        qa = found.one("qa_reports")
        if report is not None:
            drawn.append(("dataset", figures.dataset_figure(
                report.records[0].failed_checks_by_source)))
        elif qa is not None:
            failed: dict[str, int] = {}
            for r in qa.records:
                for c in r.checks:
                    if not c.passed:
                        failed[c.name] = failed.get(c.name, 0) + 1
            drawn.append(("dataset", figures.dataset_figure({"all": failed})))
    elif analysis.stage == "train":
        item = _by_ref(found, analysis.subject_ref)
        if item is not None:
            rows = item.records
            train = [(float(r.step), float(r.loss)) for r in rows if r.split == "train"]
            val = [(float(r.step), float(r.loss)) for r in rows if r.split == "val"]
            drawn.append(("loss", figures.train_figure(train, val)))
    elif analysis.stage == "inference":
        item = _by_ref(found, analysis.subject_ref)
        if item is not None:
            chunks = [r for r in item.records if r.chunk_index > 0]
            tau = next((f.value for f in analysis.book.facts if f.name == "R1_threshold"), None)
            drawn.append(("rtc", figures.rtc_figure(
                [r.chunk_index for r in chunks],
                [r.chunk_received_s - r.observation_sent_s for r in chunks],
                [r.delay_steps for r in chunks],
                float(tau) if isinstance(tau, (int, float)) else 0.1,
            )))
    paths = []
    for name, svg in drawn:
        path = fig_dir / f"{n:03d}-{name}.svg"
        figures.write(svg, path)
        paths.append(f"figures/{path.name}")
    return paths


def _by_ref(found: InputSet, ref: str) -> Loaded | None:
    return next((x for x in found.loaded if x.ref == ref), None)


def run(
    paths: Sequence[Path],
    out: Path,
    model: ChatModel,
    config: AgentConfig,
    *,
    vision_model: ChatModel | None = None,
    images: Sequence[Path] = (),
    train_config: Path = DEFAULT_TRAIN_CONFIG,
    system_config: Path = DEFAULT_SYSTEM_CONFIG,
    store: Path | None = None,
    run_plan_id: str | None = None,
    now: datetime | None = None,
) -> RunResult:
    if out.exists():
        raise FileExistsError(f"{out} exists: each run writes a new directory")
    found = collect(paths)
    for image in images:
        refuse_forbidden(image)  # before any model call or ledger row
    offline = OfflineThresholds(**(config.raw.get("offline") or {}))
    analyses = subjects(found, offline, train_config, system_config)
    ledger = StorePaths(store)
    plan = run_plan_id or f"g0-{STORY}-{date.today():%Y%m%d}"
    job_id = f"job_agentqa_{new_ulid()}"
    estimate = _ledger(plan, job_id, SECONDS_PER_SUBJECT * max(1, len(analyses)), "estimated",
                       f"assumed {SECONDS_PER_SUBJECT:g} s per subject on the 3060", None)
    append_ledger_entry(estimate, ledger)
    start, outcome = time.monotonic(), "ok"
    result = RunResult(out, skipped=list(found.skipped))
    try:
        out.mkdir(parents=True)
        pages: list[tuple[str, AgentReport]] = []
        for n, analysis in enumerate(analyses, start=1):
            analysis.figures = _figures(analysis, found, out / "figures", n)
            if vision_model is not None and images:
                observe(analysis, [(p, p.as_posix()) for p in images], vision_model,
                        int((config.raw.get("vision") or {}).get("max_images", 6)))
            reviewed = review_subject(analysis, model, config, now=now)
            report = reviewed.report
            result.reports.append(report)
            result.dropped[report.report_id] = reviewed.dropped
            page = f"{n:03d}-{analysis.stage}.html"
            inline = [(out / f).read_text(encoding="utf-8") for f in analysis.figures]
            (out / page).write_text(
                render_report(report, inline_svgs=inline, dropped=reviewed.dropped),
                encoding="utf-8",
            )
            pages.append((page, report))
            record_estimates(report, out / "estimates.jsonl")
        with (out / "reports.jsonl").open("w", encoding="utf-8") as f:
            for report in result.reports:
                f.write(report.model_dump_json() + "\n")
        _write_dropped(result, out / "dropped.jsonl")
        counts = {k: len(v) for k, v in result.dropped.items()}
        (out / "index.html").write_text(render_index(pages, counts), encoding="utf-8")
        return result
    except BaseException as error:
        outcome = f"failed: {type(error).__name__}"
        raise
    finally:
        broken = sum(1 for r in result.reports if r.status == "broken")
        note = (f"wall seconds of Agent QA/QC, {outcome}; {len(result.reports)} reports, "
                f"{broken} broken; model {model.name}@{model.revision}")
        append_ledger_entry(
            _ledger(plan, job_id, max(time.monotonic() - start, 0.0), "measured", note,
                    estimate.id),
            ledger,
        )


def _write_dropped(result: RunResult, path: Path) -> None:
    """One row per dropped code candidate, with the facts it cited, for the reviewer."""
    with path.open("w", encoding="utf-8") as f:
        for report in result.reports:
            facts = {x.fact_id: x for x in report.facts}
            for d in result.dropped.get(report.report_id, ()):
                row = {
                    "report_id": report.report_id,
                    "subject_ref": report.subject_ref,
                    "stage": report.stage,
                    "cid": d.cid,
                    "code": d.code,
                    "target": d.target,
                    "detail": d.detail,
                    "reason": d.reason,
                    "evidence": [
                        {"id": e, "name": facts[e].name, "value": facts[e].value,
                         "unit": facts[e].unit}
                        for e in d.evidence if e in facts
                    ],
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")


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


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

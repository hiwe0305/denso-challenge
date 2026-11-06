"""The `fw agentqa` commands (DA-20).

    fw agentqa run --input <dir|file> ... --out <dir>      reports, pages, figures, estimates
        [--record replies.jsonl | --replay replies.jsonl]  keep or reuse the model's replies
        [--vision --image <png> ...]                       Qwen3.5-4B second pass (task 6)
    fw agentqa review --reports <reports.jsonl> --report-id <id> --reviewer <name>
        --decide find_001=agree --decide find_002=override:"reason"   writes AgentReview
    fw agentqa html --reports <reports.jsonl> --out <dir> [--reviews <dir>]
    fw agentqa estimates --path <estimates.jsonl> [--measure <ref>=<value> --source <ref>]

Errors exit 2 with one line, as `fw eval` does. A run whose model part broke a
report still writes everything and exits 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from flywheel.contracts.agentqa import AgentReport, AgentReview
from flywheel.eval.agentqa import estimates as est
from flywheel.eval.agentqa.agent import load_agent_config
from flywheel.eval.agentqa.endpoint import (
    DEFAULT_AGENT_CONFIG,
    ChatModel,
    RecordingModel,
    ReplayModel,
    load_endpoint,
)
from flywheel.eval.agentqa.html import render_index, render_report
from flywheel.eval.agentqa.review import make_review, write_review
from flywheel.eval.agentqa.run import run as run_agentqa

app = typer.Typer(no_args_is_help=True)


@app.callback()
def root() -> None:
    """Agent QA/QC: reports on datasets, train logs, probes, inference and eval (DA-20)."""


def _fail(message: str) -> None:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(2)


def _read_reports(path: Path) -> list[AgentReport]:
    text = path.read_text(encoding="utf-8")
    return [AgentReport.model_validate_json(line) for line in text.splitlines() if line.strip()]


@app.command("run")
def run_command(
    inputs: list[Path] = typer.Option(..., "--input", help="Artifact file or directory."),
    out: Path = typer.Option(..., "--out", help="New directory for this run."),
    config: Path = typer.Option(DEFAULT_AGENT_CONFIG, "--config"),
    record: Path | None = typer.Option(None, "--record", help="Append model replies here."),
    replay: Path | None = typer.Option(None, "--replay", help="Use recorded replies."),
    vision: bool = typer.Option(False, "--vision", help="Second pass with the vision model."),
    images: list[Path] = typer.Option([], "--image", help="Image for the vision pass."),
    store: Path | None = typer.Option(None, "--store"),
) -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        agent_config = load_agent_config(config)
        model: ChatModel
        if replay is not None:
            model = ReplayModel.from_file(replay)
        else:
            model = load_endpoint("agent", config)
            if record is not None:
                model = RecordingModel(model, record)
        enabled = vision or bool((agent_config.raw.get("vision") or {}).get("enabled"))
        vision_model = load_endpoint("vision", config) if enabled else None
        result = run_agentqa(inputs, out, model, agent_config, vision_model=vision_model,
                             images=images, store=store)
    except (OSError, ValueError, KeyError) as exc:
        _fail(str(exc))
        return
    for report in result.reports:
        top = report.findings[0] if report.findings else None
        head = f"{top.code} {top.target_ref}" if top else "-"
        typer.echo(f"{report.stage:9} {report.status:6} {len(report.findings):3} findings  "
                   f"top {head}  {report.subject_ref}")
    typer.echo(f"{len(result.reports)} reports in {out}; {len(result.skipped)} files skipped")
    broken = sum(1 for r in result.reports if r.status == "broken")
    if broken:
        # The run is kept; a script still has to see that the model part failed.
        typer.echo(f"{broken} report(s) broken; see problems in reports.jsonl", err=True)
        raise typer.Exit(1)


@app.command("review")
def review_command(
    reports: Path = typer.Option(..., "--reports"),
    report_id: str = typer.Option(..., "--report-id"),
    reviewer: str = typer.Option(..., "--reviewer"),
    decide: list[str] = typer.Option(..., "--decide", help="find_001=agree or =override:why"),
    out: Path = typer.Option(Path("reviews"), "--out"),
) -> None:
    found = [r for r in _read_reports(reports) if r.report_id == report_id]
    if not found:
        _fail(f"{reports}: no report {report_id}")
    decisions: dict[str, tuple[str, str]] = {}
    for item in decide:
        finding, _, rest = item.partition("=")
        decision, _, reason = rest.partition(":")
        decisions[finding] = (decision, reason)
    try:
        path = write_review(make_review(found[0], reviewer, decisions), out)
    except ValueError as exc:
        _fail(str(exc))
        return
    typer.echo(f"review written: {path}")


@app.command("html")
def html_command(
    reports: Path = typer.Option(..., "--reports"),
    out: Path = typer.Option(..., "--out"),
    reviews: Path | None = typer.Option(None, "--reviews"),
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    pages = []
    for n, report in enumerate(_read_reports(reports), start=1):
        review = None
        path = reviews / f"{report.report_id}.review.json" if reviews is not None else None
        if path is not None and path.is_file():
            review = AgentReview.model_validate_json(path.read_text(encoding="utf-8"))
        page = f"{n:03d}-{report.stage}.html"
        (out / page).write_text(render_report(report, review), encoding="utf-8")
        pages.append((page, report))
    (out / "index.html").write_text(render_index(pages), encoding="utf-8")
    typer.echo(f"{len(pages)} pages in {out}")


@app.command("estimates")
def estimates_command(
    path: Path = typer.Option(..., "--path"),
    measure: str | None = typer.Option(None, "--measure", help="<report_id>/<est_id>=<value>"),
    source: str | None = typer.Option(None, "--source"),
) -> None:
    if measure is not None:
        ref, _, value = measure.partition("=")
        if not source:
            _fail("--measure needs --source (the artifact the value was measured in)")
        try:
            est.record_measurement(path, ref, float(value), str(source))
        except (KeyError, ValueError) as exc:
            _fail(str(exc))
    for c in est.compare(path):
        verdict = "unmeasured" if c.inside is None else ("inside" if c.inside else "outside")
        typer.echo(f"{c.estimate_ref}  {c.quantity}  [{c.low:g}, {c.high:g}]  "
                   f"measured {c.measured}  {verdict}")

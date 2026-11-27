"""The `fw agentqa` commands (DA-20).

    fw agentqa run --input <dir|file> ... --out <dir>      reports, pages, figures, estimates
        [--record replies.jsonl | --replay replies.jsonl]  keep or reuse the model's replies
        [--vision --image <png> ...]                       Qwen3.5-4B second pass (task 6)
    fw agentqa review --reports <reports.jsonl> --report-id <id> --reviewer <name>
        --decide find_001=agree --decide find_002=override:"reason"   writes AgentReview
    fw agentqa html --reports <reports.jsonl> --out <dir> [--reviews <dir>]
    fw agentqa estimates --path <estimates.jsonl> [--measure <ref>=<value> --source <ref>]
    fw agentqa pack --round <round.yaml> [--store <dir>]   freeze a round into pack.json (DA-43)
    fw agentqa round --pack <pack.json> --out <dir> [--no-model] [--from <step>]
        [--plan <yaml>] [--store <dir>] [--gateway-config <dir>] [--disable-rule <id> ...]
        [--investigate]
                                                           run a round into index.html (DA-43)
    fw agentqa mcp --pack <pack.json> [--log <file>]       the tools over MCP on stdio (DA-49)
        [--record <dir> [--run <run dir>]]                 with the record tools (DA-54)
    fw agentqa chat --pack <pack.json> --record <dir> [--run <run dir>] [--session <id>]
        [TASK | -] [--dsh <path>] [--harness-home <dir>] [--patch <file>]
        [--key-env NAME ...] [--timeout S] [--json]        one turn through the harness (DA-54)
    fw agentqa chat-page --run <run dir> --record <dir> --out <dir>
                                                           a chat record on the run's page

Errors exit 2 with one line, as `fw eval` does. A run whose model part broke a
report still writes everything and exits 1.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer
from flywheel.contracts.agentqa import AgentReport, AgentReview
from flywheel.eval.agentqa import estimates as est
from flywheel.eval.agentqa.agent import load_agent_config
from flywheel.eval.agentqa.chat import harness as chat_harness
from flywheel.eval.agentqa.chat.page import PageRefused, record_page
from flywheel.eval.agentqa.endpoint import (
    DEFAULT_AGENT_CONFIG,
    ChatModel,
    OpenAIEndpoint,
    RecordingModel,
    ReplayModel,
    load_endpoint,
)
from flywheel.eval.agentqa.html import render_index, render_report
from flywheel.eval.agentqa.mcp import server as mcp_server
from flywheel.eval.agentqa.review import make_review, write_review
from flywheel.eval.agentqa.round.hypotheses import RulesRefused
from flywheel.eval.agentqa.round.measure import PlanRefused
from flywheel.eval.agentqa.round.pack import PackRefused, build_pack, write_pack
from flywheel.eval.agentqa.round.pipeline import RunRefused, failure, run_round
from flywheel.eval.agentqa.round.records import Assembly
from flywheel.eval.agentqa.round.render import INDEX_FILE
from flywheel.eval.agentqa.run import read_dropped
from flywheel.eval.agentqa.run import run as run_agentqa

app = typer.Typer(no_args_is_help=True)


@app.callback()
def root() -> None:
    """Agent QA/QC: reports on datasets, train logs, probes, inference and eval (DA-20)."""


def _fail(message: str) -> None:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(2)


def _recorded_broken(out: Path) -> bool:
    try:
        return bool(json.loads((out / "run.json").read_text(encoding="utf-8"))
                    .get("status") == "broken")
    except (OSError, ValueError, AttributeError):
        return False


def _read_reports(path: Path) -> list[AgentReport]:
    text = path.read_text(encoding="utf-8")
    return [AgentReport.model_validate_json(line) for line in text.splitlines() if line.strip()]


@app.command("pack")
def pack_command(
    declaration: Path = typer.Option(..., "--round", help="The round.yaml of the round."),
    store: Path | None = typer.Option(
        None, "--store", help="The site store the store_snapshot block copies rows from."),
) -> None:
    """Step B0: check and hash the files `round.yaml` names, write pack.json beside it."""
    try:
        pack = build_pack(declaration, store=store)
        out = write_pack(pack, declaration.parent)
    except PackRefused as error:
        _fail(str(error))
    typer.echo(f"{pack.pack_id}: {len(pack.entries)} files, {len(pack.links)} links -> {out}")


@app.command("round")
def round_command(
    pack: Path = typer.Option(..., "--pack", help="The pack.json of the round."),
    out: Path = typer.Option(..., "--out", help="New directory for this run."),
    from_step: str | None = typer.Option(None, "--from", help="Redo from this step."),
    plan: Path | None = typer.Option(None, "--plan", help="Plan yaml instead of the task's."),
    no_model: bool = typer.Option(
        False, "--no-model", help="Code floor only: no judge, no verify. With --from, the "
        "run directory's recorded mode is used when this is not given."),
    store: Path | None = typer.Option(None, "--store"),
    gateway_config: Path | None = typer.Option(
        None, "--gateway-config", help="Directory with routing.yaml and hosted.yaml."),
    disable_rule: list[str] = typer.Option(
        [], "--disable-rule", help="Switch a rule off by id for this run (repeatable); "
        "added to agent.yaml's disabled_rules, recorded in run.json and the agent hash."),
    investigate: bool = typer.Option(
        False, "--investigate", help="Run the investigate loop after hypothesize (DA-52; a "
        "model run only). With --from, the run directory's recorded choice is used when "
        "this is not given."),
) -> None:
    """Run a round: pack, admit, measure, hypothesize, adjudicate, judge, verify, assemble,
    render."""
    mode: bool | None = True if no_model else (None if from_step is not None else False)
    try:
        record = run_round(pack, out, plan_path=plan, from_step=from_step,
                           command="fw agentqa round", no_model=mode, store=store,
                           gateway_root=gateway_config, disable_rules=disable_rule,
                           investigate=True if investigate else (
                               None if from_step is not None else False))
    except (PackRefused, PlanRefused, RulesRefused, RunRefused, FileExistsError) as error:
        _fail(str(error))
        return
    except Exception as error:
        # A step that failed is recorded in run.json as broken: one line, no traceback.
        # A failure the runner did not record is a bug and keeps its traceback.
        if not _recorded_broken(out):
            raise
        _fail(f"{failure(error)} (recorded in {out / 'run.json'})")
        return
    assembly = (out / "assembly.json").read_text(encoding="utf-8")
    clusters = len(json.loads(assembly)["clusters"])
    typer.echo(f"{record.run_id}: {record.status}, {clusters} clusters -> {out / INDEX_FILE}")


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
        items = result.dropped.get(report.report_id, ())
        n = sum(1 for d in items if d.kind == "dropped_by_model")
        gone = f"  {n} code candidate(s) dropped" if n else ""
        if len(items) > n:
            gone += f"  {len(items) - n} addition(s) refused"
        typer.echo(f"{report.stage:9} {report.status:6} {len(report.findings):3} findings  "
                   f"top {head}  {report.subject_ref}{gone}")
    typer.echo(f"{len(result.reports)} reports in {out}; {len(result.skipped)} files skipped")
    endpoint = getattr(model, "inner", model)
    if isinstance(endpoint, OpenAIEndpoint) and endpoint.context_tokens:
        window = endpoint.served_window
        typer.echo(f"server window {window} tokens, budget {endpoint.context_tokens}"
                   if window else f"server window not reported; budget assumes "
                   f"{endpoint.context_tokens} tokens", err=window is None)
    dropped = sum(len(d) for d in result.dropped.values())
    if dropped:
        # Not a failure: the model may judge a detector wrong. It must not go unseen (#175).
        typer.echo(f"{dropped} item(s) did not become findings (dropped by the model or "
                   "refused by code); see dropped.jsonl", err=True)
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
    gone = read_dropped(reports.parent / "dropped.jsonl")  # beside reports.jsonl, if any
    for n, report in enumerate(_read_reports(reports), start=1):
        review = None
        path = reviews / f"{report.report_id}.review.json" if reviews is not None else None
        if path is not None and path.is_file():
            review = AgentReview.model_validate_json(path.read_text(encoding="utf-8"))
        page = f"{n:03d}-{report.stage}.html"
        dropped = gone.get(report.report_id, ())
        (out / page).write_text(render_report(report, review, dropped=dropped),
                                encoding="utf-8")
        pages.append((page, report))
    counts = {k: len(v) for k, v in gone.items()}
    (out / "index.html").write_text(render_index(pages, counts), encoding="utf-8")
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


@app.command("mcp")
def mcp_command(
    pack: Path = typer.Option(..., "--pack", help="The pack.json of the round."),
    log: Path | None = typer.Option(None, "--log", help=mcp_server.LOG_HELP),
    record: Path | None = typer.Option(None, "--record", help=mcp_server.RECORD_HELP),
    run: Path | None = typer.Option(None, "--run", help=mcp_server.RUN_HELP),
) -> None:
    """Serve the analysis tools of one round pack to a chat shell over MCP on stdio.

    Only a pack that admit confirms public is served; no option overrides this check.
    """
    raise typer.Exit(mcp_server.run(pack, log, record, run))


def _chat_lines(result: chat_harness.ChatTurn) -> list[str]:
    lines = [f"{call.tool}: {call.status}" for call in result.tool_calls]
    for answer in result.answers:
        lines += ["", "CHECKED ANSWER (numbers filled in by code)",
                  str(answer.get("rendered", ""))]
    if not result.answers:
        lines.append("No checked answer: answer_submit accepted nothing in this turn.")
    for verdict in result.verdicts:
        lines.append(f"{verdict['hypothesis']}: {verdict['verdict']}")
    if result.text:
        lines += ["", "UNCHECKED (the model's own words, not verified)", result.text]
    lines += [f"{kind}: {text}" for kind, text in
              [*(("error", e) for e in result.errors),
               *(("note", d) for d in result.diagnostics)]]
    usage = ""
    if result.usage:
        usage = ", tokens " + " ".join(f"{k} {v}" for k, v in result.usage.items())
    hint = f"; continue with --session {result.session_id}" if result.session_id else ""
    lines.append(f"session {result.session_id or '-'}: {result.finish_reason}, "
                 f"{result.steps} model calls{usage}, {result.seconds:g} s{hint}")
    return lines


@app.command("chat")
def chat_command(
    task: str = typer.Argument("-", help="The task; - or nothing reads it from stdin."),
    pack: Path = typer.Option(..., "--pack", help="The pack.json of the round."),
    record: Path = typer.Option(..., "--record", help="The record directory of the session."),
    run: Path | None = typer.Option(
        None, "--run", help="Bind the record directory to this run directory of the same "
        "pack (its fact ids continue the run's), so chat-page can show it on the run's page."),
    session: str | None = typer.Option(None, "--session", help="Continue this session."),
    dsh: Path | None = typer.Option(
        None, "--dsh", help="The harness executable (default: env AGENTQA_DSH_BIN)."),
    harness_home: Path | None = typer.Option(
        None, "--harness-home", help="The harness's own home (default: env AGENTQA_DSH_HOME)."),
    patch: Path = typer.Option(chat_harness.DEFAULT_PATCH, "--patch",
                               help="The harness profile patch."),
    key_env: list[str] = typer.Option(
        list(chat_harness.DEFAULT_KEY_ENV), "--key-env",
        help="Name of a key variable handed to the harness (repeatable)."),
    timeout: float = typer.Option(chat_harness.DEFAULT_TIMEOUT, "--timeout", min=1),
    as_json: bool = typer.Option(False, "--json", help="Print the turn as one JSON object."),
) -> None:
    """One chat turn through the agent harness. Only a text that answer_submit accepted
    is shown as checked; the model's own words are labelled unchecked."""
    dsh_path = dsh or (Path(os.environ["AGENTQA_DSH_BIN"])
                       if os.environ.get("AGENTQA_DSH_BIN") else None)
    home = harness_home or (Path(os.environ["AGENTQA_DSH_HOME"])
                            if os.environ.get("AGENTQA_DSH_HOME") else None)
    if dsh_path is None:
        _fail("no harness executable: set --dsh or AGENTQA_DSH_BIN")
        return
    if home is None:
        _fail("no harness home: set --harness-home or AGENTQA_DSH_HOME")
        return
    text = sys.stdin.read() if task == "-" else task
    try:
        result = chat_harness.turn(text, pack=pack, record=record, dsh=dsh_path,
                                harness_home=home, patch=patch, repo=Path.cwd(),
                                session=session, key_env=key_env, timeout=timeout, run=run)
    except chat_harness.ChatRefused as error:
        _fail(str(error))
        return
    if as_json:
        typer.echo(json.dumps(result.to_json(), ensure_ascii=False))
    else:
        typer.echo("\n".join(_chat_lines(result)))
    raise typer.Exit(0 if result.completed and result.answers else 1)


@app.command("chat-page")
def chat_page_command(
    run: Path = typer.Option(..., "--run", help="The run directory the record is bound to."),
    record: Path = typer.Option(..., "--record", help="The record directory of the chat."),
    out: Path = typer.Option(..., "--out", help="New directory for the page."),
) -> None:
    """Show a chat record's hypotheses and checked answers on a copy of the run's page.

    verify, assemble and render of the round run again on the copy; the run and the
    record directories are only read.
    """
    try:
        index = record_page(run, record, out)
    except PageRefused as error:
        _fail(str(error))
        return
    assembly = Assembly.model_validate_json((out / "assembly.json").read_text(encoding="utf-8"))
    model = sum(1 for c in assembly.clusters for h in c.hypotheses if h.origin == "model")
    typer.echo(f"{assembly.run_id}: {model} model hypotheses shown, "
               f"{len(assembly.chat_answers)} checked answers -> {index}")

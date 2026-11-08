"""`fw egocentric ingest | deid | pose | annotate | qa | report | review | trial` (DA-04).

One work directory per source, by default `$FW_ROOT/pipeline/<source_id>/` (ingest
prints it); its layout is the one DA-18 reads (`ingest/egocentric/episodes.py`).
In order:

    fw egocentric ingest egodex                    pinned EgoDex subset (egocentric.yaml)
    fw egocentric ingest video --root <dir>        the team's recordings (EgoVideoSource)
    fw egocentric deid <work>                      faces covered on this machine (YuNet);
                                                   first, before anything reads a frame
    fw egocentric pose <work>                      E-B from the HDF5
    fw egocentric pose <work> --job jobs.json      manifest for the E-A job (rtx3060)
    fw egocentric pose <work> --estimates <dir>    E-A from the job's .npz, against E-B
    fw egocentric annotate <work> [--endpoint ...] de-identification gate, segments
    fw egocentric qa <work>
    fw egocentric report <work>
    fw egocentric review <work> --sample | --apply <sheet>
    fw egocentric trial <work> --simple <psi-data> --reference <marks> --robobrain --molmo

Every command is one job with its estimated and measured LedgerEntry (`job_ledger`);
the estimate is an assumed cost per frame, named in its note. A refusal (the
de-identification gate, a changed source, a config error) exits 2 with the reason,
after the measured row is written.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import Annotated, Any

import typer
from flywheel.data.annotate.deid.blur import FaceDetector, YuNet
from flywheel.data.annotate.deid.gate import unpinned_videos
from flywheel.data.api import ConfigError, dataset_report, job_ledger, render_html
from flywheel.data.config import store_root
from flywheel.data.ingest.egocentric import api
from flywheel.data.ingest.egocentric import review as reviewing
from flywheel.data.ingest.egocentric import trial as trials
from flywheel.data.ingest.egocentric.config import EgoConfig, load_config
from flywheel.data.ingest.egocentric.episodes import (
    COMPARE,
    SEGMENTS,
    bundle_dir,
    read_bundle,
    read_episodes,
)
from flywheel.data.ingest.egocentric.report import summarize_ego, write_page
from flywheel.data.ingest.egocentric.segments import read_segment_rows
from flywheel.data.ingest.egocentric.source import register_egodex
from flywheel.data.ingest.egocentric.video_source import register_videos, select_videos
from flywheel.data.ingest.egocentric.vlm import ModelLabeler, ModelSuggester, OpenAIVision

app = typer.Typer(no_args_is_help=True)

CONFIG = Path("configs/data/egocentric.yaml")
STORY = "DA-04"
# Assumptions for the estimated ledger rows, not measurements: seconds per unit.
ESTIMATE = {"ingest": (1e-3, "frame"), "deid": (5e-2, "frame"), "pose": (2e-3, "frame"),
            "annotate": (5e-3, "frame"),
            "qa": (1e-3, "frame"), "report": (1e-2, "episode"), "review": (1e-2, "episode"),
            "trial": (20.0, "query")}
EPISODE_FRAMES = 300  # assumed frames of an episode, before ingest has read the files

Work = Annotated[Path, typer.Argument(help="work directory that `fw egocentric ingest` printed")]
Config = Annotated[Path, typer.Option(help="egocentric pipeline config")]
RunPlan = Annotated[str | None, typer.Option(help="RunPlan id; default g0-DA-04-<yyyymmdd>")]
Endpoint = Annotated[str | None, typer.Option(help="OpenAI-compatible base URL, .../v1")]


@app.callback()
def root() -> None:
    """Egocentric data commands: EgoDex and the team's recordings through six tiers."""


@app.command()
def ingest(
    source: Annotated[str, typer.Argument(help="egodex or video")],
    root_dir: Annotated[Path | None, typer.Option("--root", help="video: recording root")] = None,
    split: Annotated[str, typer.Option(help="train or dev")] = "train",
    work: Annotated[Path | None, typer.Option(help="default $FW_ROOT/pipeline/<source_id>")] = None,
    config: Config = CONFIG,
    run_plan_id: RunPlan = None,
) -> None:
    """Pick and hash the episodes of a source; write source.json, episodes and bundles."""

    with _refusals():
        cfg = load_config(config)
        store = store_root()
        if source == "egodex":
            spec = cfg.sources["egodex"]
            planned = len(spec.tasks) * (spec.episodes_per_task or 0)
            register = partial(register_egodex, store, cfg)
        elif source == "video":
            if root_dir is None:
                raise ValueError("ingest video needs --root <recording dir>")
            planned = len(select_videos(root_dir))
            register = partial(register_videos, root_dir, cfg)
        else:
            raise ValueError(f"source {source!r} is not egodex or video")
        # hashing the files is most of the work, so it runs inside the job
        with _job("ingest", planned * EPISODE_FRAMES, run_plan_id) as job:
            record = register()
            out = work or store / "pipeline" / record.source_id
            episodes = api.ingest(record, out, cfg, store, split)
            job.notes.append(f"{len(episodes)} episodes of {record.source_id}")
    if record.deid_waiver:
        waiver = f"waived (D2; videos match {record.deid_waiver_manifest})"
    else:
        waiver = "not waived: run `fw egocentric deid` before E-A and annotate"
        if record.source_detail == "egodex":
            waiver += f" ({len(unpinned_videos(record.files))} videos not in the pinned sample)"
    _say(f"{record.source_id}: {len(episodes)} episodes, {len(record.files)} files,"
         f" {record.total_bytes / 1e6:.1f} MB; de-identification {waiver}")
    _say(f"work: {out}")
    _say(f"ledger: {job.run_plan_id}/{job.job_id}")


@app.command()
def deid(work: Work, config: Config = CONFIG, run_plan_id: RunPlan = None) -> None:
    """Cover faces in a <i>.deid.mp4 beside each raw video; later steps read only the copy."""

    with _refusals():
        cfg = load_config(config)
        source = api.read_source(work)
        with _job("deid", _frames(work), run_plan_id) as job:
            done = api.deid(work, _detector(cfg), cfg.deid.params, {
                "name": cfg.deid.model.name, "revision": cfg.deid.model.revision,
                "sha256": cfg.deid.sha256, "runtime": cfg.deid.model.served})
            faces = sum(d.video.frames_with_faces for d in done)
            message = (f"{source.source_id}: waived (D2), nothing to blur" if not done else
                       f"{len(done)} videos blurred, faces found in {faces} of"
                       f" {sum(d.video.frames for d in done)} frames; episodes are blurred")
            job.notes.append(message)
    _say(message)
    for item in done:
        _say(f"  {item.copy}: {item.video.frames_blurred} frames covered,"
             f" {item.video.seconds:.1f} s")
    _say(f"ledger: {job.run_plan_id}/{job.job_id}")


@app.command()
def pose(
    work: Work,
    job_file: Annotated[Path | None, typer.Option("--job", help="write the E-A job manifest")]
    = None,
    estimates: Annotated[Path | None, typer.Option(help="dir of the E-A job's .npz")] = None,
    run_plan_id: RunPlan = None,
) -> None:
    """E-B from tracking; or the E-A job manifest; or E-A from the job, compared with E-B."""

    with _refusals():
        source = api.read_source(work)
        frames = _frames(work)
        with _job("pose", frames, run_plan_id) as job:
            if job_file is not None:
                jobs = api.estimate_jobs(work, source)
                job_file.write_text(json.dumps(jobs, indent=1) + "\n")
                message = f"E-A job manifest: {len(jobs)} episodes -> {job_file}"
            elif estimates is not None:
                deviations = api.import_estimates(work, estimates)
                message = f"E-A read for {len(deviations)} episodes with E-B; compare.json"
            else:
                message = f"E-B pose of {api.write_eb_poses(work)} episodes"
            job.notes.append(message)
    _say(message)
    _say(f"ledger: {job.run_plan_id}/{job.job_id}")


@app.command()
def annotate(
    work: Work,
    endpoint: Endpoint = None,
    config: Config = CONFIG,
    run_plan_id: RunPlan = None,
) -> None:
    """Gate, then cut every episode into steps with sentences (rules, then the model)."""

    with _refusals():
        cfg = load_config(config)
        with _job("annotate", _frames(work), run_plan_id) as job:
            models = _models(cfg, endpoint)
            cuts = api.annotate(work, cfg, models)
            segments = sum(len(c.segments) for c in cuts.values())
            open_events = sum(e.unresolved for c in cuts.values() for e in c.events)
            job.notes.append(f"{segments} segments, {open_events} events left ambiguous")
    _say(f"{len(cuts)} episodes, {segments} segments; {open_events} events the rules left"
         f" open{' and the model did not settle' if endpoint else ' (no model given)'}")
    _say(f"ledger: {job.run_plan_id}/{job.job_id}")


@app.command()
def qa(work: Work, config: Config = CONFIG, run_plan_id: RunPlan = None) -> None:
    """Egocentric QA of every episode: qa/egocentric.jsonl."""

    with _refusals():
        cfg = load_config(config)
        with _job("qa", _frames(work), run_plan_id) as job:
            reports = api.qa(work, cfg)
            counts = {d: sum(r.decision == d for r in reports) for d in ("pass", "flag",
                                                                           "reject")}
            job.notes.append(json.dumps(counts))
    _say(f"{len(reports)} QAReports: {counts}; thresholds {cfg.threshold_version}")
    _say(f"ledger: {job.run_plan_id}/{job.job_id}")


@app.command()
def report(work: Work, config: Config = CONFIG, run_plan_id: RunPlan = None) -> None:
    """DatasetReport and the page with its egocentric part: report/."""
    with _refusals():
        cfg = load_config(config)
        episodes = read_episodes(work)
        with _job("report", len(episodes), run_plan_id) as job:
            source = api.read_source(work)
            reports = api.read_reports(work)
            dataset_id = f"ego_{source.source_id}"
            segments, frames, deviations = {}, {}, {}
            for e in episodes:
                folder = bundle_dir(work, e.episode_id)
                bundle = read_bundle(work, e.episode_id)
                frames[e.episode_id] = (bundle.frames, bundle.fps)
                if (folder / SEGMENTS).is_file():
                    segments[e.episode_id] = read_segment_rows(folder / SEGMENTS)
                if (folder / COMPARE).is_file():
                    deviations[e.episode_id] = json.loads((folder / COMPARE).read_text())
            contract = dataset_report(dataset_id, episodes, reports)
            summary = summarize_ego(dataset_id, source, episodes, reports, segments, frames,
                                    deviations, {k: r.on_fail for k, r in cfg.qa.items()})
            out = work / "report"
            out.mkdir(exist_ok=True)
            (out / "dataset_report.json").write_text(contract.model_dump_json(indent=2) + "\n")
            (out / "egocentric.json").write_text(summary.to_json() + "\n")
            page = render_html(contract, out / "index.html")
            write_page(page, summary)
            job.notes.append(f"{summary.segments} segments, decisions {summary.decisions}")
    _say(f"page: {page}")
    _say(f"ledger: {job.run_plan_id}/{job.job_id}")


@app.command()
def review(
    work: Work,
    sample: Annotated[bool, typer.Option("--sample", help="write review/sheet.jsonl")] = False,
    apply_sheet: Annotated[Path | None, typer.Option("--apply", help="filled sheet")] = None,
    config: Config = CONFIG,
    run_plan_id: RunPlan = None,
) -> None:
    """Sample segments for a person, or write their decisions back (label_source human)."""

    with _refusals():
        cfg = load_config(config)
        episodes = read_episodes(work)
        with _job("review", len(episodes), run_plan_id) as job:
            if sample == (apply_sheet is not None):
                raise ValueError("give exactly one of --sample and --apply <sheet>")
            if apply_sheet is None:
                rows = reviewing.sample(work, [e.episode_id for e in episodes],
                                        cfg.review_share, cfg.review_seed)
                sheet = work / "review" / "sheet.jsonl"
                reviewing.write_sheet(sheet, rows)
                message = f"{len(rows)} segments to review: {sheet}"
            else:
                counts = reviewing.apply(work, reviewing.read_sheet(apply_sheet),
                                         [e.episode_id for e in episodes])
                message = f"review applied: {counts}; run `fw egocentric qa` again"
            job.notes.append(message)
    _say(message)
    _say(f"ledger: {job.run_plan_id}/{job.job_id}")


@app.command()
def trial(
    work: Work,
    simple: Annotated[Path, typer.Option(help="psi-data two-table LeRobot dataset with videos")],
    reference: Annotated[Path, typer.Option(help="grasp points marked on the SIMPLE frames")],
    robobrain: Endpoint = None,
    molmo: Endpoint = None,
    out: Annotated[Path | None, typer.Option(help="default <work>/trial")] = None,
    vram: Annotated[list[str] | None, typer.Option(
        help="model=what nvidia-smi showed while it was loaded, e.g. robobrain=3.3 GB")] = None,
    timeout_s: Annotated[float | None, typer.Option(
        help="seconds per query; default the config's timeout_s (a CPU model needs more)")]
    = None,
    boundary: Annotated[list[str] | None, typer.Option(
        help="models asked for the grasp frame (robobrain, molmo); default both")] = None,
    config: Config = CONFIG,
    run_plan_id: RunPlan = None,
) -> None:
    """The labelling-model trial (design 6.7.4): 30 EgoDex + 30 SIMPLE frames, Decision."""

    with _refusals():
        cfg = load_config(config)
        if robobrain is None or molmo is None:
            raise ValueError("the trial needs --robobrain and --molmo endpoints")
        target = out or work / "trial"
        with _job("trial", 4 * trials.FRAMES, run_plan_id) as job:
            timeout = timeout_s or cfg.timeout_s
            models = {
                "robobrain": OpenAIVision(robobrain, cfg.models["segment_suggester"].served,
                                          timeout, local_hosts=cfg.local_hosts),
                "molmo": OpenAIVision(molmo, cfg.models["grasp_pointer"].served, timeout,
                                      local_hosts=cfg.local_hosts),
            }
            measured = dict(v.split("=", 1) for v in vram or [])
            result = trials.run(work, simple, reference, models, cfg, target, measured,
                                boundary)
            job.notes.append(f"trial written to {target}")
    _say(json.dumps(result["summary"], indent=1))
    _say(f"decision: {target / 'decision.json'}")
    _say(f"ledger: {job.run_plan_id}/{job.job_id}")


@contextmanager
def _refusals() -> Iterator[None]:
    """A refusal of a command: one line on stderr, exit 2. The gate's DeidBlocked and
    ConfigError are ValueErrors; a model that does not answer raises URLError, an OSError,
    and the step has written nothing (files.py)."""
    try:
        yield
    except (ConfigError, ValueError, OSError) as error:
        typer.echo(str(error), err=True)
        sys.exit(2)


def _job(command: str, units: int, run_plan_id: str | None) -> Any:
    per, unit = ESTIMATE[command]
    note = f"assumed {per:g} s per {unit} x {units} {unit}s"
    activity = "qa" if command == "qa" else "pipeline"
    return job_ledger(activity, f"ego_{command}", per * units, note=note,
                      run_plan_id=run_plan_id, story=STORY)


def _frames(work: Path) -> int:

    return sum(read_bundle(work, e.episode_id).frames for e in read_episodes(work))


def _detector(cfg: EgoConfig) -> FaceDetector:
    """YuNet from the store; a missing file says where the pinned one is published."""
    path = store_root() / cfg.deid.path
    if not path.is_file():
        raise FileNotFoundError(f"{path}: no face model; fetch it once with\n  mkdir -p"
                                f" {path.parent} && curl -L -o {path} {cfg.deid.url}")
    return YuNet(path, cfg.deid.sha256, cfg.deid.params)


def _models(cfg: EgoConfig, endpoint: str | None) -> api.Models:

    if endpoint is None:
        return api.Models()
    roles = cfg.models
    suggester = OpenAIVision(endpoint, roles["segment_suggester"].served, cfg.timeout_s,
                             local_hosts=cfg.local_hosts)
    labeler = OpenAIVision(endpoint, roles["labeler"].served, cfg.timeout_s,
                           local_hosts=cfg.local_hosts)
    return api.Models(ModelSuggester(suggester), ModelLabeler(labeler), {
        role: f"{roles[role].name}@{roles[role].revision[:12]}"
        for role in ("segment_suggester", "labeler")})


def _say(text: str) -> None:
    typer.echo(text)

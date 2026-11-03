"""`fw data ingest | qa | release | report`: the robot-source pipeline (DA-03 AC 6).

The four commands share one work directory per registered source, by default
`$FW_ROOT/pipeline/<source_id>/` (ingest prints it):

    source.json         SourceRecord: file hashes, licence, lineage per episode
    episodes.jsonl      one contract Episode per line
    episode_index.json  episode_id -> episode_index of the dataset
    ingest.json         counts and the source's own index findings (Q7)
    qa/reports.jsonl    one QAReport per episode
    qa/summary.json     what the dataset page shows beyond the DatasetReport
    report/dataset_report.json, report/index.html

`release` freezes into `$FW_ROOT/releases/<name>/` (or `--out`). Every command
is one job and writes its estimated and measured LedgerEntry (`job_ledger`,
PO 4/11/2026); the estimate is an assumed cost per frame, named in its note.
`qa` re-hashes the source's parquet files first and refuses a source that
changed since ingest. A refused release, a config error or a changed source exit
2 with the reason; the measured ledger row is still written.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any

import typer
from flywheel.contracts.artifacts import Episode, QAReport, ReplayReport
from flywheel.data.config import load_layout, load_qa_config, store_root
from flywheel.data.ingest.lerobot import iter_episodes, read_info
from flywheel.data.ingest.sources import (
    SourceRecord,
    dump_source,
    load_source,
    register_source,
    to_episode,
)
from flywheel.data.inject.api import mark_copy_episode
from flywheel.data.ledger import job_ledger
from flywheel.data.qa.checks import calibrate_action_jump, dataset_checks, run_qa
from flywheel.data.release.build import build_release
from flywheel.data.release.report import DatasetSummary, dataset_report, render_html, summarize

app = typer.Typer(no_args_is_help=True)

QA_YAML = Path("configs/data/qa.yaml")
LAYOUT = Path("configs/embodiments/g1.yaml")
SPLIT_PLAN = Path("configs/splits/default.yaml")
# Assumptions for the estimated ledger rows, not measurements: CPU seconds per unit.
ESTIMATE = {"ingest": (2e-5, "frame"), "qa": (5e-5, "frame"), "release": (1e-3, "episode"),
            "report": (1e-3, "episode")}

RunPlan = Annotated[str | None, typer.Option(help="RunPlan id; default g0-DA-03-<yyyymmdd>")]
Work = Annotated[Path, typer.Argument(help="work directory that `fw data ingest` printed")]


@app.callback()
def root() -> None:
    """Data lane commands: ingest, QA, release and report of the robot sources."""


@app.command()
def ingest(
    dataset: Annotated[Path, typer.Argument(help="LeRobot v2.1 dataset under $FW_ROOT")],
    source_detail: Annotated[str, typer.Option(help="psi_data, planner_wbc or teleop_pico")],
    license: Annotated[str, typer.Option(help="licence of the data; 'unknown' if not known")],
    data_class: Annotated[str, typer.Option(help="public, internal or restricted")],
    split: Annotated[str, typer.Option(help="train or dev")] = "train",
    work: Annotated[Path | None, typer.Option(help="default $FW_ROOT/pipeline/<source_id>")] = None,
    run_plan_id: RunPlan = None,
) -> None:
    """Register a dataset as a source and write its Episodes (tier 1)."""
    frames = _total_frames(dataset)
    with _refusals(), _job("ingest", frames, run_plan_id) as job:
        source = register_source(dataset, source_detail, license, data_class)  # type: ignore[arg-type]
        indices = {}
        episodes = []
        for f in iter_episodes(dataset):
            episode = mark_copy_episode(to_episode(f, source, split), dataset)
            indices[episode.episode_id] = f.episode_index
            episodes.append(episode)
        out = work or store_root() / "pipeline" / source.source_id
        out.mkdir(parents=True, exist_ok=True)
        (out / "source.json").write_text(dump_source(source) + "\n")
        _write_lines(out / "episodes.jsonl", episodes)
        (out / "episode_index.json").write_text(json.dumps(indices, indent=2) + "\n")
        summary = {
            "source_id": source.source_id,
            "store_path": source.store_path,
            "episodes": len(episodes),
            "frames": frames,
            "files": len(source.files),
            "bytes": source.total_bytes,
            "index_findings": len(source.index_findings),
            "benchmark_copies": sum(e.meta.benchmark_copy_id is not None for e in episodes),
        }
        (out / "ingest.json").write_text(json.dumps(summary, indent=2) + "\n")
        job.notes.append(f"{len(episodes)} episodes, {frames} frames")
    _say(f"{source.source_id}: {len(episodes)} episodes, {frames} frames, {len(source.files)}"
         f" files; index off LeRobot v2.1 in {len(source.index_findings)} episodes (Q7)")
    _say(f"work: {out}")
    _say(f"ledger: {job.run_plan_id}/{job.job_id}")


@app.command()
def qa(
    work: Work,
    config: Annotated[Path, typer.Option(help="QA thresholds")] = QA_YAML,
    layout: Annotated[Path, typer.Option(help="embodiment with the action_layout")] = LAYOUT,
    split_plan: Annotated[Path, typer.Option(help="SplitPlan")] = SPLIT_PLAN,
    replay: Annotated[Path | None, typer.Option(help="dir of ReplayReport .json files")] = None,
    calibrate: Annotated[bool, typer.Option(help="print action_jump thresholds only")] = False,
    run_plan_id: RunPlan = None,
) -> None:
    """Run QA on every episode of the source: qa/reports.jsonl and qa/summary.json (tier 4)."""
    source, episodes, indices = _read_work(work)
    dataset = store_root() / source.store_path
    with _refusals(), _job("qa", _total_frames(dataset), run_plan_id) as job:
        cfg = load_qa_config(config, load_layout(layout), split_plan)
        _check_unchanged(source, dataset)
        fps = float(read_info(dataset)["fps"])
        frames = list(iter_episodes(dataset))
        if calibrate:
            thresholds = calibrate_action_jump(
                frames, cfg.groups, cfg.action_jump_quantile, cfg.action_jump_wrapped
            )
            job.notes.append(f"calibration over {len(frames)} episodes")
            _say(f"# action_jump.thresholds, q{cfg.action_jump_quantile} over {len(frames)}"
                 f" episodes of {source.source_id}")
            for group, value in thresholds.items():
                _say(f"    {group}: {value:.6g}")
            return
        by_index = {f.episode_index: f for f in frames}
        replays = _read_replays(replay)
        reports = [
            run_qa(by_index[indices[e.episode_id]], e, replays.get(e.episode_id), cfg, fps=fps,
                   lineage=source.lineage[indices[e.episode_id]])
            for e in episodes
        ]
        findings = dataset_checks(dataset, frames, cfg)
        seeds = _seeds(source, indices)
        notes = []
        if source.index_findings:
            notes.append(
                f"index column off LeRobot v2.1 in {len(source.index_findings)} of"
                f" {len(episodes)} episodes; renumbered on write (Q7)"
            )
        summary = summarize(
            source.source_id, episodes, reports,
            {e.episode_id: by_index[indices[e.episode_id]] for e in episodes},
            cfg, fps=fps, seeds=seeds, findings=findings, notes=notes,
        )
        (work / "qa").mkdir(exist_ok=True)
        _write_lines(work / "qa" / "reports.jsonl", reports)
        (work / "qa" / "summary.json").write_text(summary.to_json() + "\n")
        counts = {d: sum(r.decision == d for r in reports) for d in ("pass", "flag",
                                                                    "quarantine", "reject")}
        job.notes.append(f"{len(reports)} reports {counts}")
    _say(f"{source.source_id}: {len(reports)} QAReports ({cfg.threshold_version}): {counts}")
    for finding in findings:
        verdict = "ok" if finding.check.passed else f"FAIL ({finding.code})"
        _say(f"  {finding.check.name}: {verdict}, {finding.detail}")


@app.command()
def release(
    work: Work,
    name: Annotated[str | None, typer.Option(help="default <source_detail>_<source_id>")] = None,
    out: Annotated[Path | None, typer.Option(help="default $FW_ROOT/releases/<name>")] = None,
    split_plan: Annotated[Path, typer.Option(help="SplitPlan")] = SPLIT_PLAN,
    run_plan_id: RunPlan = None,
) -> None:
    """Freeze the QA'd episodes into a hashed release, or say why it is refused (tier 5)."""
    source, episodes, indices = _read_work(work)
    name = name or f"{source.source_detail}_{source.source_id}"
    target = out or store_root() / "releases" / name
    with _refusals(), _job("release", len(episodes), run_plan_id) as job:
        reports = _read_reports(work / "qa" / "reports.jsonl")
        manifest = build_release(episodes, reports, split_plan, target, name=name,
                                 seeds=_seeds(source, indices))
        job.notes.append(f"{manifest.release_id} at {target}")
    _say(f"{manifest.release_id}: frozen at {target}")


@app.command()
def report(
    work: Work,
    out: Annotated[Path | None, typer.Option(help="default <work>/report/index.html")] = None,
    run_plan_id: RunPlan = None,
) -> None:
    """Write the DatasetReport and the static page of design 6.5."""
    source, episodes, _ = _read_work(work)
    page = out or work / "report" / "index.html"
    with _refusals(), _job("report", len(episodes), run_plan_id) as job:
        reports = _read_reports(work / "qa" / "reports.jsonl")
        summary = DatasetSummary.from_json((work / "qa" / "summary.json").read_text())
        dataset = dataset_report(source.source_id, episodes, reports)
        page.parent.mkdir(parents=True, exist_ok=True)
        (page.parent / "dataset_report.json").write_text(dataset.model_dump_json(indent=2) + "\n")
        render_html(dataset, page, summary=summary)
        job.notes.append(str(page))
    _say(f"{dataset.dataset_id}: {dataset.episode_count} episodes;"
         f" failed checks {dataset.failed_checks_by_source}")
    _say(f"page: {page}")


class Refused(Exception):
    """A command that cannot do what was asked; the message says why."""


@contextmanager
def _refusals() -> Iterator[None]:
    """Turn the refusals of a command into one line on stderr and exit 2.

    ReleaseRefused, ConfigError and LeRobotFormatError are ValueErrors. Opened
    outside the job, so the job's measured ledger row is written first.
    """
    try:
        yield
    except (Refused, ValueError, FileExistsError, FileNotFoundError) as error:
        typer.echo(str(error), err=True)
        sys.exit(2)


def _job(command: str, units: int, run_plan_id: str | None) -> Any:
    per, unit = ESTIMATE[command]
    note = f"assumed {per:g} s per {unit} x {units} {unit}s"
    return job_ledger("qa" if command == "qa" else "pipeline", f"data_{command}", per * units,
                      note=note, run_plan_id=run_plan_id)


def _read_work(work: Path) -> tuple[SourceRecord, list[Episode], dict[str, int]]:
    if not (work / "source.json").is_file():
        typer.echo(f"{work}: no source.json; run `fw data ingest` first", err=True)
        sys.exit(2)
    source = load_source((work / "source.json").read_text())
    episodes = [Episode.model_validate_json(line)
                for line in (work / "episodes.jsonl").read_text().splitlines() if line]
    indices = {k: int(v) for k, v in json.loads((work / "episode_index.json").read_text()).items()}
    return source, episodes, indices


def _total_frames(dataset: Path) -> int:
    return int(read_info(dataset).get("total_frames", 0))


def _check_unchanged(source: SourceRecord, dataset: Path) -> None:
    changed = [
        name for name, digest in source.files.items()
        if name.endswith(".parquet") or name.startswith("meta/")
        if not (dataset / name).is_file()
        or hashlib.sha256((dataset / name).read_bytes()).hexdigest() != digest
    ]
    if changed:
        raise Refused(f"{dataset}: {len(changed)} files changed since ingest, e.g."
                      f" {changed[0]}; ingest it again")


def _seeds(source: SourceRecord, indices: dict[str, int]) -> dict[str, int | None]:
    return {episode_id: source.lineage[index].seed for episode_id, index in indices.items()}


def _read_reports(path: Path) -> list[QAReport]:
    if not path.is_file():
        raise Refused(f"{path}: no QA reports; run `fw data qa` first")
    return [QAReport.model_validate_json(line) for line in path.read_text().splitlines() if line]


def _read_replays(directory: Path | None) -> dict[str, list[ReplayReport]]:
    replays: dict[str, list[ReplayReport]] = defaultdict(list)
    for path in sorted(directory.glob("*.json")) if directory else []:
        report = ReplayReport.model_validate_json(path.read_text())
        replays[report.episode_id].append(report)
    return replays


def _write_lines(path: Path, records: list[Episode] | list[QAReport]) -> None:
    path.write_text("".join(r.model_dump_json() + "\n" for r in records))


def _say(text: str) -> None:
    typer.echo(text)


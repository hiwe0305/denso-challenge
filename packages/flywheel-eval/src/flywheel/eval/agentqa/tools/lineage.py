"""`lineage`: which checkpoint, job, release and dataset report stand behind an eval run (3.2).

The chain is eval run -> checkpoint -> train job -> release -> dataset report, and each
link is made only from an id the admitted records carry:

- run -> checkpoint: the `checkpoint` the pack declares on the run's scores entry, or the
  `checkpoint_id` of the `Episode` records of its rollouts; if both exist they must agree;
- checkpoint -> job: the `job_id` of the `TrainingMetric` rows with that `checkpoint_id`;
- job -> release: the `release_id` of those rows;
- release -> dataset report: the `dataset_report` entry whose declared subject is that
  `release`. No contract links a release to a dataset id, so the pack must declare it.

A link that cannot be made, or can be made two ways, is a `not_judged` fact that names the
id and the kind that is missing. Only the first such link of a run is a fact; the links
behind it show as `blocked` in the table. Nothing is guessed from a file name.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from flywheel.contracts.artifacts import DatasetReport, Episode
from flywheel.eval.agentqa.facts import FactBook, FactValue
from flywheel.eval.agentqa.tools.base import (
    EntryView,
    JobMetrics,
    Row,
    RunScores,
    ToolResult,
)

TOOL = "lineage"
LINKS = ("checkpoint", "job", "release", "dataset")


def _one(found: set[str | None], missing: str, ambiguous: str) -> tuple[str | None, str]:
    """The single id of `found`, or None and why not; an empty or None id is no id."""
    ids = {i for i in found if i}
    if len(ids) == 1:
        return next(iter(ids)), ""
    return None, missing if not ids else f"{ambiguous}: {', '.join(sorted(ids))}"


def _by_checkpoint(jobs: Mapping[str, JobMetrics]) -> dict[str, set[tuple[str, str]]]:
    """checkpoint_id -> the (job_id, release_id) of its rows, over one read of every log."""
    out: dict[str, set[tuple[str, str]]] = {}
    for j in jobs.values():
        for r in j.iter_rows():
            out.setdefault(r.checkpoint_id, set()).add((r.job_id, r.release_id))
    return out


def lineage(book: FactBook, runs: Sequence[RunScores], entries: Sequence[EntryView],
            episodes: Sequence[Episode], jobs: Mapping[str, JobMetrics],
            reports: Mapping[str, DatasetReport]) -> ToolResult:
    facts: list[str] = []
    rows: list[Row] = []
    reasons: list[str] = []
    by_ref = {e.ref: e for e in entries}
    complete = 0
    index: dict[str, set[tuple[str, str]]] | None = None  # read once, when first needed
    for run in runs:
        got: dict[str, str | None] = {}
        why: dict[str, str] = {}
        refs = dict.fromkeys(LINKS, run.ref)
        ids = {s.episode_id for s in run.scores}
        declared = by_ref[run.ref].subject.get("checkpoint") if run.ref in by_ref else None
        recorded: set[str | None] = {e.checkpoint_id for e in episodes
                    if e.episode_id in ids and e.checkpoint_id}
        got["checkpoint"], why["checkpoint"] = _one(
            recorded | {declared}, f"run {run.run}: no checkpoint is declared on its scores "
            "entry and no Episode record of its rollouts carries one",
            f"run {run.run}: declared and recorded checkpoints disagree")
        # Each link is made from the one before it; once one is missing nothing is computed
        # behind it, so no id of None is ever looked up.
        checkpoint = got["checkpoint"]
        rows_of: set[tuple[str, str]] = set()  # (job_id, release_id) of its rows
        if checkpoint:
            if index is None:
                index = _by_checkpoint(jobs)
            rows_of = index.get(checkpoint, set())
            got["job"], why["job"] = _one(
                {job_id for job_id, _ in rows_of},
                f"checkpoint {checkpoint}: no TrainingMetric row "
                "carries it", f"checkpoint {checkpoint} is in more than one job")
        job = got.get("job")
        if job:
            refs["job"] = refs["release"] = jobs[job].ref
            got["release"], why["release"] = _one(
                {release for job_id, release in rows_of if job_id == job},
                f"job {job}: no release_id", f"job {job} has several releases")
        release = got.get("release")
        if release:
            wanted = [e for e in entries if e.kind == "dataset_report"
                      and e.subject.get("release") == release]
            got["dataset"], why["dataset"] = _one(
                {reports[e.ref].dataset_id for e in wanted if e.ref in reports},
                f"release {release}: no dataset_report entry declares it as its release",
                f"release {release} has several dataset reports")
            if wanted:
                refs["dataset"] = wanted[0].ref
        broken = False
        row: dict[str, FactValue] = {"run": run.run}
        for link in LINKS:
            value = got.get(link)
            if broken:
                row[link] = "blocked"
            elif value:
                facts.append(book.add(f"{TOOL}_{run.run}_{link}", value, refs[link]))
                row[link] = value
            else:
                broken = True
                facts.append(book.add(f"{TOOL}_{run.run}_{link}_not_judged", why[link],
                                      refs[link]))
                reasons.append(why[link])
                row[link] = "-"
        complete += not broken
        rows.append(row)
    facts.append(book.add(f"{TOOL}_complete_runs", complete, "pack.json", "runs"))
    return ToolResult(TOOL, tuple(facts), tuple(rows), tuple(reasons))

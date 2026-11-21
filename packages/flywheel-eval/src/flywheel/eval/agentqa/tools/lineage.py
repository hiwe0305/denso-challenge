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


def _one(found: set[str], missing: str, ambiguous: str) -> tuple[str | None, str]:
    """The single value of `found`, or None and why not."""
    if len(found) == 1:
        return next(iter(found)), ""
    return None, missing if not found else f"{ambiguous}: {', '.join(sorted(found))}"


def lineage(book: FactBook, runs: Sequence[RunScores], entries: Sequence[EntryView],
            episodes: Sequence[Episode], jobs: Mapping[str, JobMetrics],
            reports: Mapping[str, DatasetReport]) -> ToolResult:
    facts: list[str] = []
    rows: list[Row] = []
    reasons: list[str] = []
    by_ref = {e.ref: e for e in entries}
    complete = 0
    for run in runs:
        got: dict[str, str | None] = {}
        why: dict[str, str] = {}
        refs = dict.fromkeys(LINKS, run.ref)
        ids = {s.episode_id for s in run.scores}
        declared = by_ref[run.ref].subject.get("checkpoint") if run.ref in by_ref else None
        recorded = {e.checkpoint_id for e in episodes
                    if e.episode_id in ids and e.checkpoint_id}
        found = recorded | ({declared} if declared else set())
        got["checkpoint"], why["checkpoint"] = _one(
            found, f"run {run.run}: no checkpoint is declared on its scores entry and no "
            "Episode record of its rollouts carries one",
            f"run {run.run}: declared and recorded checkpoints disagree")
        rows_of = [r for j in jobs.values() for r in j.rows
                   if r.checkpoint_id == got["checkpoint"]]
        job_ids = {r.job_id for r in rows_of}
        got["job"], why["job"] = _one(
            job_ids, f"checkpoint {got['checkpoint']}: no TrainingMetric row carries it",
            f"checkpoint {got['checkpoint']} is in more than one job")
        job = got["job"]
        if job:
            refs["job"] = refs["release"] = jobs[job].ref
        got["release"], why["release"] = _one(
            {r.release_id for r in rows_of if r.job_id == got["job"]},
            f"job {got['job']}: no release_id", f"job {got['job']} has several releases")
        wanted = [e for e in entries if e.kind == "dataset_report"
                  and e.subject.get("release") == got["release"]]
        got["dataset"], why["dataset"] = _one(
            {reports[e.ref].dataset_id for e in wanted if e.ref in reports},
            f"release {got['release']}: no dataset_report entry declares it as its release",
            f"release {got['release']} has several dataset reports")
        if wanted:
            refs["dataset"] = wanted[0].ref
        broken = False
        row: dict[str, FactValue] = {"run": run.run}
        for link in LINKS:
            value = got[link]
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

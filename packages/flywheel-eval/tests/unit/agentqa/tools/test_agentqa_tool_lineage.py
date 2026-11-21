"""`lineage`: eval run -> checkpoint -> job -> release -> dataset report (DA-43 task 3.2)."""

from __future__ import annotations

from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import EntryView
from flywheel.eval.agentqa.tools.lineage import lineage
from helpers_tools import episode, job_of, metric, report, run_of

JOBS = {"J": job_of("J", [metric("J", 10, 1.0)])}
RUN = run_of("R", {"l1-s1": True, "l1-s2": False})


def entries(checkpoint: str | None = "ckpt-1", release: str | None = "rel-1") -> list[EntryView]:
    scores = {"checkpoint": checkpoint} if checkpoint else {}
    sub = {"release": release} if release else {}
    return [EntryView("R/scores.jsonl", "scores", scores),
            EntryView("ds/report.json", "dataset_report", sub)]


def run(es: list[EntryView], eps: list = [], jobs=JOBS, runs=(RUN,)):  # type: ignore[no-untyped-def,type-arg]
    book = FactBook()
    result = lineage(book, list(runs), es, eps, jobs, {"ds/report.json": report("ds-9")})
    return result, {book.get(f).name: book.get(f).value for f in result.facts}


def test_the_whole_chain_from_declared_and_logged_ids() -> None:
    result, got = run(entries())
    assert [got[f"lineage_R_{k}"] for k in ("checkpoint", "job", "release", "dataset")] == [
        "ckpt-1", "J", "rel-1", "ds-9"]
    assert got["lineage_complete_runs"] == 1 and result.judged
    assert dict(result.rows[0]) == {"run": "R", "checkpoint": "ckpt-1", "job": "J",
                                    "release": "rel-1", "dataset": "ds-9"}


def test_episodes_give_the_checkpoint_when_the_pack_declares_none() -> None:
    _, got = run(entries(checkpoint=None), [episode("R/l1-s1", "ckpt-1")])
    assert got["lineage_R_checkpoint"] == "ckpt-1" and got["lineage_complete_runs"] == 1


def test_no_checkpoint_anywhere_is_one_fact_and_the_rest_is_blocked() -> None:
    result, got = run(entries(checkpoint=None))
    assert got["lineage_complete_runs"] == 0 and "lineage_R_checkpoint" not in got
    assert "checkpoint" in str(got["lineage_R_checkpoint_not_judged"])
    assert [n for n in got if n.endswith("_not_judged")] == ["lineage_R_checkpoint_not_judged"]
    assert len(result.not_judged) == 1 and not result.judged
    assert dict(result.rows[0]) == {"run": "R", "checkpoint": "-", "job": "blocked",
                                    "release": "blocked", "dataset": "blocked"}


def test_a_declared_and_a_recorded_checkpoint_that_disagree_are_not_picked() -> None:
    _, got = run(entries(), [episode("R/l1-s1", "ckpt-2")])
    assert "disagree" in str(got["lineage_R_checkpoint_not_judged"])
    assert "lineage_R_job" not in got


def test_a_checkpoint_no_training_log_carries_names_the_missing_kind() -> None:
    _, got = run(entries(checkpoint="ckpt-9"))
    assert "ckpt-9: no TrainingMetric row" in str(got["lineage_R_job_not_judged"])


def test_a_release_without_a_dataset_report_is_not_judged() -> None:
    _, got = run(entries(release="rel-2"))
    assert got["lineage_R_job"] == "J" and got["lineage_R_release"] == "rel-1"
    assert "release rel-1: no dataset_report" in str(got["lineage_R_dataset_not_judged"])
    assert got["lineage_complete_runs"] == 0
    _, got = run(entries(release=None))
    assert "lineage_R_dataset" not in got


def test_a_checkpoint_in_two_jobs_is_ambiguous() -> None:
    jobs = {**JOBS, "K": job_of("K", [metric("K", 10, 1.0)])}
    _, got = run(entries(), jobs=jobs)
    assert "more than one job" in str(got["lineage_R_job_not_judged"])


def _unset(job: str, **ids: str | None):  # type: ignore[no-untyped-def]
    """A log row whose ids are None, as a record that skipped validation would be."""
    row = metric(job, 10, 1.0)
    return job_of(job, [type(row).model_construct(**{**row.model_dump(), **ids})])


def test_a_broken_link_is_not_followed_by_rows_whose_id_is_none() -> None:
    jobs = {"N": _unset("N", checkpoint_id=None, release_id=None)}
    result, got = run(entries(checkpoint=None), jobs=jobs)  # no checkpoint anywhere
    assert [n for n in got if n.endswith("_not_judged")] == ["lineage_R_checkpoint_not_judged"]
    assert "lineage_R_job" not in got and "lineage_R_job_not_judged" not in got
    assert dict(result.rows[0])["job"] == "blocked"


def test_a_release_id_of_none_is_a_reason_not_an_empty_string() -> None:
    jobs = {"N": _unset("N", release_id=None)}
    result, got = run(entries(), jobs=jobs)
    assert got["lineage_R_job"] == "N" and "lineage_R_release" not in got
    assert str(got["lineage_R_release_not_judged"]).strip()
    assert all(r.strip() for r in result.not_judged)
    assert all(str(book_value).strip() for book_value in got.values())

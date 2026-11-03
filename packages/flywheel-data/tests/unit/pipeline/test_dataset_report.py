"""DatasetReport and the static page of design 6.5 (DA-03 AC 5)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from flywheel.contracts.artifacts import DatasetReport, Episode, QAReport
from flywheel.data.config import QAConfig
from flywheel.data.ingest.lerobot import EpisodeFrames
from flywheel.data.qa.checks import run_qa
from flywheel.data.release.report import DatasetSummary, dataset_report, render_html, summarize
from qa_data import FPS, clean_frames, episode_of, lineage_of

Batch = tuple[list[Episode], list[QAReport], dict[str, EpisodeFrames], dict[str, int | None]]


@pytest.fixture
def batch(qa_config: QAConfig) -> Batch:
    psi = [episode_of("psi_data", f"ep_p{i}") for i in range(3)]
    s1 = [episode_of("planner_wbc", f"ep_s{i}") for i in range(2)]
    frames = {e.episode_id: clean_frames(length=20 + i) for i, e in enumerate(psi + s1)}
    jumped = frames["ep_s1"].action.copy()
    jumped[10:, 20] = 0.3
    frames["ep_s1"] = dataclasses.replace(frames["ep_s1"], action=jumped)
    frames["ep_p2"] = dataclasses.replace(frames["ep_p2"], task="")
    seeds: dict[str, int | None] = {"ep_s0": 5, "ep_s1": 6}
    reports = [
        run_qa(frames[e.episode_id], e, None, qa_config, fps=FPS,
               lineage=lineage_of(seed=seeds[e.episode_id]) if e.episode_id in seeds else None)
        for e in psi + s1
    ]
    return psi + s1, reports, frames, seeds


def test_the_report_counts_sources_and_failed_checks(batch: Batch) -> None:
    episodes, reports, _, _ = batch
    report = dataset_report("ds_demo", episodes, reports)

    assert report.counts_by_source == {"psi_data": 3, "planner_wbc": 2}
    assert report.failed_checks_by_source == {
        "planner_wbc": {"action_jump.arm": 1},
        "psi_data": {"task_instruction": 1},
    }
    assert DatasetReport.model_validate_json(report.model_dump_json()) == report


def test_a_report_for_an_episode_not_given_is_refused(batch: Batch) -> None:
    episodes, reports, _, _ = batch
    with pytest.raises(ValueError, match="not given"):
        dataset_report("ds_demo", episodes[:2], reports)


def test_the_page_shows_what_design_6_5_asks(
    batch: Batch, qa_config: QAConfig, tmp_path: Path
) -> None:
    episodes, reports, frames, seeds = batch
    report = dataset_report("ds_demo", episodes, reports)
    summary = summarize("ds_demo", episodes, reports, frames, qa_config, fps=FPS, seeds=seeds,
                        notes=["index renumbered in 95/99 episodes (Q7)"])
    assert DatasetSummary.from_json(summary.to_json()) == summary
    s1 = summary.sources["planner_wbc"]
    assert s1.decisions == {"pass": 1, "flag": 1} and s1.seeds == {"in_train": 2}
    assert summary.sources["psi_data"].seeds == {"unknown": 3}
    assert "replay_success" in s1.not_run and "split_seed" not in s1.not_run
    assert s1.action["arm"]["max"] == pytest.approx(0.3)
    assert s1.frames == [23, 24]

    page = render_html(report, tmp_path / "report" / "index.html", summary=summary).read_text()
    for text in ("Episodes by source", "Failed checks", "action_jump.arm", "D3",
                 "Episode length", "Condition seeds", "Action stats by group", "planner_wbc",
                 "Dataset checks", "index renumbered", qa_config.threshold_version):
        assert text in page, text
    assert "<script" not in page


def test_the_page_escapes_what_it_shows(tmp_path: Path) -> None:
    report = DatasetReport(dataset_id="<ds>", episode_count=0)
    page = render_html(report, tmp_path / "x.html").read_text()
    assert "&lt;ds&gt;" in page and "<ds>" not in page

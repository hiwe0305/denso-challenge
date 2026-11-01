"""The two lists a detector answers with (DA-08 task 2)."""

from __future__ import annotations

import dataclasses

import pytest
from flywheel.eval.diagnosis.train.finding import DetectorResult, Finding, Skipped


def test_a_clean_result_and_a_skipped_one_are_not_the_same_answer() -> None:
    # the reason the detectors return two lists: an empty findings list on its own
    # would read as "clean" on a checkpoint nothing could be judged on (FR21)
    clean = DetectorResult()
    unjudged = DetectorResult(skipped=[Skipped(code="T7", reason="thiếu P4 của checkpoint cha")])
    assert clean.findings == unjudged.findings == []
    assert clean.skipped == [] and [s.code for s in unjudged.skipped] == ["T7"]


def test_only_a_finding_that_says_so_stops_a_job() -> None:
    assert not Finding("T3", 600, None, None, 0.4, 0.3).stop_job
    assert Finding("T1", 500, None, None, float("inf"), 10.0, stop_job=True).stop_job


def test_findings_and_skips_cannot_be_rewritten_in_place() -> None:
    finding = Finding("T5", 1000, "hand", 14, 1e-9, 1e-6)
    with pytest.raises(dataclasses.FrozenInstanceError):
        finding.value = 0.0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        Skipped("T8a", "log cũ không có vlm_frozen").reason = ""  # type: ignore[misc]

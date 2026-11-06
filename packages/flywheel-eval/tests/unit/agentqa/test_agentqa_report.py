"""DA-20 AC 5: the HTML page built from an AgentReport, and the engineer's review."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

import pytest
from flywheel.contracts.agentqa import AgentReport
from flywheel.eval.agentqa.html import render_report
from flywheel.eval.agentqa.review import ReviewError, make_review, write_review

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)
FIXTURE = files("flywheel.testkit") / "fixtures/artifacts/AgentReport.json"



def _fixture() -> AgentReport:
    return AgentReport.model_validate_json(FIXTURE.read_text())


def test_the_page_puts_fact_values_in_place_of_placeholders() -> None:
    page = render_report(_fixture())
    assert "{F1}" not in page
    assert "4.5 %" in page and 'title="F1 · drop_rate_pct"' in page


def test_a_broken_report_says_so_at_the_top() -> None:
    text = (files("flywheel.testkit") / "fixtures/artifacts/AgentReport-broken.json").read_text()
    page = render_report(AgentReport.model_validate_json(text))
    assert "Report broken" in page


def test_a_review_answers_every_finding_once(tmp_path: Path) -> None:
    report = _fixture()
    ids = [f.finding_id for f in report.findings]
    with pytest.raises(ReviewError, match="no decision"):
        make_review(report, "hieu", {ids[0]: ("agree", "")})
    with pytest.raises(ReviewError, match="no finding"):
        make_review(report, "hieu", {i: ("agree", "") for i in [*ids, "find_999"]})
    with pytest.raises(ValueError, match="override needs a reason"):
        make_review(report, "hieu", {i: ("override", "") for i in ids})
    review = make_review(report, "hieu", {ids[0]: ("agree", ""),
                                          **{i: ("override", "sensor blip") for i in ids[1:]}},
                         now=NOW)
    path = write_review(review, tmp_path)
    with pytest.raises(ReviewError, match="append-only"):
        write_review(review, tmp_path)
    page = render_report(report, review)
    assert 'class="agree"' in page and "sensor blip" in page
    assert json.loads(path.read_text())["reviewer"] == "hieu"

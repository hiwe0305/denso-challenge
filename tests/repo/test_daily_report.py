"""Tests for rule R10 and the per-author count of scripts/repo/daily_report.py (08 version 0.5)."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "repo"))

import daily_report  # noqa: E402
from storylib import Story, load_stories  # noqa: E402

# Rows copied from 07 section 2.4 (version 1.8), cut to the cases the parser must get right.
TABLE = """\
### 2.4 Lịch hoàn thiện 13/11/2026 [Đã chốt 3/11/2026]

| Người | Việc | Hạn cũ | Hạn mới |
|---|---|---|---|
| Hiếu | DA-03 PR 1: bộ đọc LeRobot v2.1 và ingest (bản 1.6, thay Thông) | 9/11 | 5/11 |
| Hiếu | DA-03 PR 2: QA, release, báo cáo dataset (bản 1.6, thay Thông) | 9/11 | 9/11 |
| Hiếu | S1-03, S1-04: chỉ phần DA-26 cần (serve Ψ₀; bản 1.2) | S1 | 8/11 |
| Hiếu | DA-19: `Psi0Trainer` stage 3 | S1–S2 | `metrics.jsonl` đầu tiên 6/11; fine-tune 8/11 |
| Hiếu | DA-34: vòng Failure → Data, sinh nhắm lỗi bằng DA-33, fine-tune và eval C+ | — | 12/11 |
| Long | DA-23 runner eval; DA-28 lệnh và kịch bản demo | S2 | 10/11; chạy thử 12/11 |
| Hưng | DA-04 nhiệm vụ 1, 2, 3, 4, 6 | 10/11 | 7/11 |
| Hưng | DA-18: export EgoDex cho stage 1 (để Hiếu chạy DA-30) | 10/11 | 8/11 |
| Hưng | DA-20 nhiệm vụ 1–5 | 13/11 | 10/11 |
| Sau 13/11 | DA-37 hiệu chỉnh scorer (story 3.5), DA-21 (v3, chưa có chủ) | | sau demo |

**Cắt phạm vi của Hiếu.** DA-09 sau 13/11.

### 2.5 Mục sau

| Người | DA-40 | — | 1/11 |
"""

NOW = dt.datetime(2026, 11, 4, 2, 0, tzinfo=dt.timezone.utc)  # 9:00 in Vietnam
TODAY = NOW.astimezone(daily_report.ICT).date()


def story(story_id: str, owner: str = "Hưng", done: int = 0, total: int = 5) -> Story:
    path = ROOT / "docs" / "product" / "stories" / f"{story_id}-x.md"
    return Story(story_id, path, owner, "?", 10.0, done, total, [])


def nov(day: int) -> dt.date:
    return dt.date(2026, 11, day)


def test_deadline_is_the_earliest_new_date_of_every_row_naming_the_story() -> None:
    deadlines = daily_report.internal_deadlines(TABLE, 2026)
    assert deadlines["DA-03"] == nov(5)  # PR 1 before PR 2
    assert deadlines["DA-19"] == nov(6)  # first of two dates in one cell
    assert deadlines["S1-03"] == deadlines["S1-04"] == nov(8)
    assert deadlines["DA-23"] == deadlines["DA-28"] == nov(10)
    assert (deadlines["DA-04"], deadlines["DA-18"], deadlines["DA-20"]) == (nov(7), nov(8), nov(10))


def test_ids_inside_prose_and_rows_without_a_date_are_not_deadlines() -> None:
    deadlines = daily_report.internal_deadlines(TABLE, 2026)
    assert "DA-26" not in deadlines  # "chỉ phần DA-26 cần" is a dependency
    assert "DA-33" not in deadlines  # "sinh nhắm lỗi bằng DA-33"
    assert "DA-30" not in deadlines  # "(để Hiếu chạy DA-30)"
    assert not {"DA-37", "DA-21"} & set(deadlines)  # "sau demo"
    assert not {"DA-40", "DA-09"} & set(deadlines)  # outside the table of 2.4


def test_missing_section_is_an_error_not_an_empty_table() -> None:
    with pytest.raises(ValueError):
        daily_report.internal_deadlines("### 2.3 Tải theo người\n", 2026)


def test_the_real_table_parses_to_known_stories() -> None:
    text = daily_report.TEAM_WORKFLOW.read_text(encoding="utf-8")
    deadlines = daily_report.internal_deadlines(text, 2026)
    assert deadlines
    assert set(deadlines) <= set(load_stories())


@pytest.mark.parametrize(
    ("started", "done", "due", "expected"),
    [
        (False, 0, nov(7), 3),  # the threshold itself fires
        (False, 0, nov(8), None),  # 4 days left
        (False, 0, nov(2), -2),  # overdue
        (True, 0, nov(7), None),  # has a commit: R4 territory
        (False, 5, nov(7), None),  # finished
        (False, 0, None, None),  # not in 07 section 2.4
    ],
)
def test_unstarted_days_left(
    started: bool, done: int, due: dt.date | None, expected: int | None
) -> None:
    left = daily_report.unstarted_days_left(story("DA-04", done=done), started, due, TODAY)
    assert left == expected


def test_collect_raises_r10_for_stories_without_commits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workflow = tmp_path / "07.md"
    workflow.write_text(TABLE, encoding="utf-8")
    owned = (story("DA-04"), story("DA-18"), story("DA-20"), story("DA-03", "Hiếu"))
    stories = {s.id: s for s in owned}

    def fake_git(*args: str) -> str:
        # Only DA-03 has a commit, two days ago; nothing else exists in the history.
        if "--grep=^DA-03/" in args:
            return str(int((NOW - dt.timedelta(days=2)).timestamp()))
        return ""

    monkeypatch.setattr(daily_report, "git", fake_git)
    monkeypatch.setattr(daily_report, "load_stories", lambda: stories)
    monkeypatch.setattr(daily_report, "TEAM_WORKFLOW", workflow)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    report = daily_report.collect(NOW + dt.timedelta(days=3))  # 7/11
    r10 = [r["text"] for r in report["rules"] if r["rule"] == "R10"]
    assert [text.split()[0] for text in r10] == ["DA-04", "DA-18", "DA-20"]
    assert "còn 0 ngày" in r10[0] and "còn 3 ngày" in r10[2]
    assert {u["id"] for u in report["unstarted"]} == {"DA-04", "DA-18", "DA-20"}

    report = daily_report.collect(NOW)  # 4/11: only DA-04 is within 3 days
    r10 = [r["text"] for r in report["rules"] if r["rule"] == "R10"]
    assert [text.split()[0] for text in r10] == ["DA-04"]



def test_a_broken_deadline_table_is_reported_and_r4_still_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workflow = tmp_path / "07.md"
    workflow.write_text("# 07 without section 2.4\n", encoding="utf-8")
    stale = str(int((NOW - dt.timedelta(days=5)).timestamp()))
    monkeypatch.setattr(
        daily_report, "git", lambda *args: stale if "--grep=^DA-03/" in args else ""
    )
    monkeypatch.setattr(daily_report, "load_stories", lambda: {"DA-03": story("DA-03", "Hiếu")})
    monkeypatch.setattr(daily_report, "TEAM_WORKFLOW", workflow)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    report = daily_report.collect(NOW)
    assert [r["rule"] for r in report["rules"]] == ["R4"]
    assert any(error.startswith("deadlines (R10):") for error in report["errors"])
    assert report["stories"]


def commit(author: str, story_id: str, subtask: str, hours: float) -> dict[str, Any]:
    return {"author": author, "story": story_id, "subtask": subtask, "title": "Do it",
            "hours": hours}


def test_yesterday_counts_by_git_author_not_story_owner() -> None:
    stories = {
        "DA-13": story("DA-13", "Châu"),
        "DA-01": story("DA-01", "Long (chủ story, 07 mục 2.2); phần g1"),
    }
    commits = [
        commit("hiwe0305", "DA-13", "4", 2.0),
        commit("hiwe0305", "DA-13", "5", 1.5),
        commit("HoangChau6179", "DA-13", "6", 1.0),
        commit("hiwe0305", "DA-01", "3", 0.5),
        commit("hiwe0305", "XX-99", "1", 0.0),
    ]
    people = daily_report.by_author(commits, stories)
    assert set(people) == {"hiwe0305", "HoangChau6179"}
    assert len(people["hiwe0305"]["subtasks"]) == 4 and people["hiwe0305"]["hours"] == 4.0
    assert people["HoangChau6179"]["subtasks"] == ["DA-13/6: Do it (story của Châu)"]
    assert people["HoangChau6179"]["hours"] == 1.0
    assert "DA-01/3: Do it (story của Long)" in people["hiwe0305"]["subtasks"]
    assert "XX-99/1: Do it (story của ?)" in people["hiwe0305"]["subtasks"]


def test_render_says_how_yesterday_is_counted() -> None:
    item = "DA-13/4: Do it (story của Châu)"
    report = {
        "generated_at": NOW.isoformat(),
        "rules": [],
        "errors": [],
        "yesterday": {"hiwe0305": {"subtasks": [item], "hours": 2.0}},
    }
    markdown = daily_report.render(report)
    assert "Theo tác giả git của commit" in markdown
    assert "- **hiwe0305**: 1 nhiệm vụ con, 2 giờ" in markdown

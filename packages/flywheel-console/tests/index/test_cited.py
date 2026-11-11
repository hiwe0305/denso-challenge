from __future__ import annotations

from pathlib import Path

from flywheel.console.index import cited
from flywheel.console.paths import ConsolePaths

REPO = Path(__file__).resolve().parents[4]


def _paths() -> ConsolePaths:
    return ConsolePaths(repo=REPO, fw_root=REPO / "fwdata")


def test_cited_quotes_present_in_docs() -> None:
    assert cited.verify(_paths()) == []


def test_cited_eval_numbers() -> None:
    ev = cited.eval_block(_paths())
    both = next(lv for lv in ev["levels"] if lv["level"] == "L1–2")
    assert both["succ"] == "20/240"
    assert both["wilson"] == "5.5–12.5"
    assert set(ev) >= {"source", "policy", "levels", "stages", "failure_labels", "place_error_cm"}
    assert ev["failure_labels"]["L-PLACE-POSE"]["L1"] == 68


def test_loop_chain() -> None:
    assert cited.loop_chain(_paths()) == [240, 131, 262, 229, 177]


def test_verify_flags_bad_quote(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "he").mkdir()
    (tmp_path / "docs" / "he" / "tray.md").write_text("nothing here", encoding="utf-8")
    seed = REPO / "packages/flywheel-console/src/flywheel/console/seed"
    p = ConsolePaths(repo=tmp_path, fw_root=tmp_path / "fw")
    assert p.seed == seed
    assert "loop.kept" in cited.verify(p)

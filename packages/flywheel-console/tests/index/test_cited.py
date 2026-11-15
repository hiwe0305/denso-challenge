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


def test_loop_in_cut_is_cited() -> None:
    assert cited.loop_in_cut(_paths()) == 160
    assert cited.verify(_paths()) == []


def test_round_block_is_cited() -> None:
    rb = cited.round_block(_paths())
    assert rb["plan"] == "rp_aae292bc79da"
    assert rb["chain"] == {
        "targets": 23, "generated": 290, "recorded": 262,
        "qa_pass": 261, "quality": 204, "selected": 181,
    }  # fmt: skip
    assert [c["id"] for c in rb["clusters"]] == ["c1", "c2", "c3", "c8", "c4", "c5", "c6", "c7"]
    assert rb["per_case"] == {"approach_a": 30, "place": 10}
    pf = rb["planner_failures"]
    # failures = attempts that were not recorded
    assert pf["L-ONE-HAND"] == 8 and sum(pf.values()) == 290 - 262
    assert cited.verify(_paths()) == []


def _numbers(v: object) -> list[float]:
    if isinstance(v, bool):
        return []
    if isinstance(v, (int, float)):
        return [float(v)]
    if isinstance(v, dict):
        return [n for x in v.values() for n in _numbers(x)]
    if isinstance(v, list):
        return [n for x in v for n in _numbers(x)]
    return []


def test_demo_numbers_appear_in_their_quote() -> None:
    """Each number of a ``demo.*`` value is written in its quote (Vietnamese decimal comma)."""
    bad: list[str] = []
    for c in cited.load(_paths()):
        if not c.key.startswith("demo."):
            continue
        text = c.quote.replace(" ", "").replace(" ", "")
        for n in _numbers(c.value):
            forms = {f"{n:g}", f"{n:g}".replace(".", ",")}
            if not any(f in text for f in forms):
                bad.append(f"{c.key}: {n:g}")
    assert bad == []
    assert cited.verify(_paths()) == []

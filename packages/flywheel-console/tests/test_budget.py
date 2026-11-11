from pathlib import Path

from flywheel.console import budget

WEB = Path(budget.__file__).parent / "web"


def test_word_budget_within_limits() -> None:
    counts = budget.count(WEB)
    assert counts, "no files counted"
    for name, (words, limit) in counts.items():
        assert words <= limit, f"{name}: {words} words > budget {limit}"


def test_budget_covers_expected_files() -> None:
    names = set(budget.count(WEB))
    assert {"app.js", "pages_data.js", "pages_ops.js", "pages_story.js", "index.html"} <= names


def test_long_literal_detected(tmp_path: Path) -> None:
    (tmp_path / "app.js").write_text('const a = "one two three four five six seven eight nine";\n')
    assert budget.long_literals(tmp_path)
    (tmp_path / "app.js").write_text('const a = "one two three";\n')
    assert not budget.long_literals(tmp_path)
    assert budget.count(tmp_path)["app.js"] == (3, 130)


def test_no_long_literals_in_web() -> None:
    assert budget.long_literals(WEB) == []


def test_skip_markers_and_tooltips(tmp_path: Path) -> None:
    src = (
        "const t = {title: 'a very long tooltip text with many many many words inside here'};\n"
        "/* @budget-skip-start */ const d = 'x y z'; /* @budget-skip-end */\n"
        "const u = 'ok now';\n"
    )
    (tmp_path / "ring.js").write_text(src)
    assert budget.count(tmp_path)["ring.js"] == (2, 25)

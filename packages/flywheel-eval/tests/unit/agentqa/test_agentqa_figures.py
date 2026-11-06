"""DA-20 AC 4: the figures the pages show, as plain SVG."""

from __future__ import annotations

from flywheel.eval.agentqa import figures


def test_figures_are_byte_stable_and_mark_non_finite_points() -> None:
    a = figures.train_figure([(0, 1.0), (10, float("nan")), (20, 0.5)], [])
    assert a == figures.train_figure([(0, 1.0), (10, float("nan")), (20, 0.5)], [])
    assert a.startswith("<svg") and 'stroke="#d00"' in a
    grid = figures.stage1_grid([
        figures.P1Item("f/0.png", "object", "what is held?", "box", "box"),
        figures.P1Item("f/1.png", "relation", "left of the box?", "cup", "plate"),
    ])
    assert grid.count("<img") == 2 and "#d9534f" in grid
    action = figures.action_figure([0.0, 0.1], [0.0, 0.2], "arm_3", 50.0, "replay/ep1.mp4")
    assert 'href="replay/ep1.mp4"' in action

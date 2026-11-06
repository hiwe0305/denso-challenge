"""DA-04 task 6: the egocentric part of the dataset report (AC 7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from flywheel.data.ingest.egocentric.report import aggregate_deviation, write_page


def deviation(pixel: float, rotation: float, left: bool = True) -> dict[str, Any]:
    hand = {"pixel_median": pixel, "wrist_pixel_median": 2 * pixel, "point_median_m": 0.05,
            "depth_median_m": 0.04, "detection": 0.9, "frames": 100}
    return {"hands": {"left": hand if left else None, "right": hand},
            "rotation_median_deg": rotation, "rotation_p90_deg": 2 * rotation,
            "eb_rotation_median_deg": 0.1, "translation_direction_median_deg": None}


def test_deviations_are_medians_over_episodes() -> None:
    out = aggregate_deviation({"a": deviation(10, 0.1), "b": deviation(30, 0.3, left=False),
                               "c": deviation(50, 0.5)})
    assert out["episodes"] == 3
    assert out["right"]["pixel_median"] == 30 and out["right"]["frames"] == 300
    assert out["left"]["pixel_median"] == 30 and out["left"]["frames"] == 200
    assert out["rotation_median_deg"] == pytest.approx(0.3)
    assert out["translation_direction_median_deg"] is None
    assert aggregate_deviation({}) == {}


def test_the_section_only_goes_into_a_rendered_page(tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    page.write_text("<html><body>no end tag")
    with pytest.raises(ValueError, match="render_html"):
        write_page(page, None)  # type: ignore[arg-type]

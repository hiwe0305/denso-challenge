"""The relaxed-tolerance ladder of the 60-rollout comparison (``story.jig.compare60.ladder``;
Hiếu, 28/11/2026): one rule (``place_error.py tolerance_curve``) for both rounds, counts only,
never C70_R1."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from flywheel.console.index import jig, story
from flywheel.console.paths import ConsolePaths

REPO = Path(__file__).resolve().parents[4]


def _fwdata() -> Path | None:
    """The real fwdata: ``$FW_ROOT``, the worktree's, or the main checkout's."""
    env = os.environ.get("FW_ROOT")
    cands = [Path(env)] if env else []
    cands += [REPO / "fwdata", REPO.parents[2] / "fwdata"]
    for c in cands:
        if (c / "tray" / "pair60k" / "stage1-60k" / "place-error-C_70.json").is_file():
            return c
    return None


def _row(success: bool = False, failure: str | None = "L-PLACE-POSE", reach_b: bool = True,
         dist_cm: float | None = 6.0, yaw_deg: float | None = 4.0) -> dict[str, Any]:  # fmt: skip
    return {"success": success, "failure": failure, "reach_b": reach_b, "dist_cm": dist_cm,
            "yaw_deg": yaw_deg}  # fmt: skip


def test_rule_needs_place_pose_and_yaw_but_not_reach_b() -> None:
    rows = [
        _row(success=True, failure=None, dist_cm=1.0, yaw_deg=1.0),
        _row(dist_cm=6.0, yaw_deg=4.0),  # in at 7.5 cm
        _row(dist_cm=6.0, yaw_deg=10.5),  # yaw over 10°: never in
        _row(dist_cm=4.0, yaw_deg=2.0, reach_b=False),  # off table B still counts (no reach_b)
        _row(failure="L-TRAY-TILT", dist_cm=1.0, yaw_deg=1.0),  # another label: never in
        _row(dist_cm=None, yaw_deg=None, reach_b=False),
    ]
    out = jig._ladder_run("X", "r", "s", "bản 1", rows)
    assert out["success"] == 1
    assert out["relaxed"] == {"5": 2, "7.5": 3, "10": 3, "15": 3, "20": 3}
    assert out["reach_b"] == 4
    # dev: reached table B with a distance (rows 0, 1, 2, 4)
    assert out["dev"]["n"] == 4 and out["dev"]["yaw_le_10"] == 3


def test_percentile_is_the_sorted_index_round_p_n_minus_1() -> None:
    xs = [5.0, 1.0, 3.0, 2.0, 4.0, 10.0, 7.0, 6.0, 9.0, 8.0]
    # sorted = 1..10; index round(0.5 * 9) = round(4.5) = 4 (Python rounds half to even)
    assert jig._pct(xs, 0.5) == 5.0
    assert jig._pct(xs, 0.9) == 9.0  # index round(8.1) = 8
    assert jig._pct([], 0.5) is None
    assert jig._pct([1.234567], 0.9) == 1.23


EXPECTED = {
    #       success relaxed 5..20          reach_b dist p50/p90  yaw p50/p90   yaw<=10
    "C_ALL": (5, (5, 9, 12, 14, 17), 39, (10.8, 42.81), (10.91, 22.47), 18),
    "C_70": (10, (10, 14, 19, 23, 23), 46, (5.65, 15.99), (8.41, 18.55), 26),
    "B_ALL": (6, (6, 10, 15, 18, 18), 37, (7.07, 19.32), (7.03, 17.44), 24),
    "B_70": (7, (7, 11, 15, 19, 20), 47, (7.41, 23.0), (6.83, 13.0), 34),
    "M": (47, (47, 50, 51, 53, 53), 60, (2.08, 7.91), (1.69, 9.61), 55),
}


@pytest.mark.skipif(_fwdata() is None, reason="needs the real fwdata (place-error rows)")
def test_ladder_of_the_real_index_matches_hieus_numbers(tmp_path: Path) -> None:
    fwdata = _fwdata()
    assert fwdata is not None
    story.build(ConsolePaths(repo=REPO, fw_root=fwdata), tmp_path)
    d = json.loads((tmp_path / "story.json").read_text(encoding="utf-8"))
    lad = d["jig"]["compare60"]["ladder"]
    assert list(lad) == ["rule", "n", "thresholds_cm", "repeats_range", "runs", "sources"]
    assert lad["n"] == 60 and lad["thresholds_cm"] == ["5", "7.5", "10", "15", "20"]
    assert lad["repeats_range"] == [42, 47]
    assert "reach_b not required" in lad["rule"]
    by = {r["run"]: r for r in lad["runs"]}
    assert list(by) == ["C_ALL", "C_70", "B_ALL", "B_70", "M"]  # never C70_R1
    for run, (ok, relaxed, reach_b, dist, yaw, yaw10) in EXPECTED.items():
        r = by[run]
        assert r["success"] == ok, run
        assert tuple(r["relaxed"].values()) == relaxed, run
        assert r["reach_b"] == reach_b, run
        assert (r["dev"]["dist_cm"]["p50"], r["dev"]["dist_cm"]["p90"]) == dist, run
        assert (r["dev"]["yaw_deg"]["p50"], r["dev"]["yaw_deg"]["p90"]) == yaw, run
        assert (r["dev"]["yaw_le_10"], r["dev"]["n"]) == (yaw10, reach_b), run
    assert [by[r]["scene"] for r in ("C_70", "M")] == ["không đồ gá", "jig2"]
    assert [by[r]["scorer"] for r in ("C_70", "M")] == ["bản 1", "bản 2"]
    # the same rule as the cited demo ladder: equal counts for the four round-1 runs
    demo = d["demo"]["ladder"]["runs"]
    for run in ("C_ALL", "C_70", "B_ALL", "B_70"):
        assert by[run]["relaxed"] == demo[run]["relaxed"], run
    assert "C70_R1" not in json.dumps(lad)


def test_serving_drops_a_hidden_run_from_the_ladder() -> None:
    from flywheel.console.index import hidden, tasks

    h = hidden.from_manifest(tasks.load(ConsolePaths(repo=REPO, fw_root=REPO / "fwdata")))
    lad = {"rule": "r", "n": 60, "thresholds_cm": ["5"], "repeats_range": [42, 47],
           "runs": [{"run": "C_70"}, {"run": "N"}, {"run": "M"}],
           "sources": ["fwdata/tray/pair60k/stage1-60k/place-error-C_70.json rows",
                       "fwdata/tray/jig-n/eval rows", "story.jig.rollouts (repeat 0)"]}  # fmt: skip
    doc = {"jig": {"runs": [], "evals": [], "compare60": {"run": "M", "earlier": [{"run": "C_70"}],
                                                          "ladder": lad}}}  # fmt: skip
    out = hidden.story(doc, h)["jig"]["compare60"]["ladder"]
    assert [r["run"] for r in out["runs"]] == ["C_70", "M"]
    assert not any("jig-n" in s for s in out["sources"]) and len(out["sources"]) == 2

from __future__ import annotations

import json
from pathlib import Path

from conftest import write_mp4
from flywheel.console.index import egocentric
from flywheel.console.paths import ConsolePaths


def test_ego_poster_only_from_deid(fw: ConsolePaths, work: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    counts = egocentric.build(fw, out, [])
    assert counts == {"src_test": 2}
    d = out / "ds/src_test"
    assert (d / "posters/ep_deid.jpg").read_bytes()[:2] == b"\xff\xd8"
    assert not (d / "posters/ep_raw.jpg").exists()
    eps = {e["id"]: e for e in json.loads((d / "episodes.json").read_text())}
    assert (
        eps["ep_deid"]["poster"] == "/data/ds/src_test/posters/ep_deid.jpg"
        and eps["ep_deid"]["ego"] is True
    )
    assert eps["ep_raw"]["poster"] is None and eps["ep_raw"]["ego"] is False
    assert eps["ep_deid"]["n"] == 30.0 and eps["ep_deid"]["s"] == 1.0
    for name in ("qa", "quality", "method"):
        assert (d / f"{name}.json").is_file()
    assert json.loads((d / "method.json").read_text())["data_class"] == "public"


def test_ego_never_reads_outside_fw_root(fw: ConsolePaths, work: Path, tmp_path: Path) -> None:
    outside = write_mp4(tmp_path / "elsewhere" / "z.deid.mp4")
    b = work / "egocentric" / "ep_raw" / "bundle.json"
    b.write_text(json.dumps({"mp4": str(outside)}))
    egocentric.build(fw, tmp_path / "out", [])
    assert not (tmp_path / "out/ds/src_test/posters/ep_raw.jpg").exists()


def test_ego_viewer_row(fw: ConsolePaths, tmp_path: Path) -> None:
    viewer = fw.fw_root / "human1m" / "v" / "viewer"
    (viewer / "data").mkdir(parents=True)
    (viewer / "posters").mkdir()
    (viewer / "posters" / "ep_a.jpg").write_bytes(b"\xff\xd8jpg")
    eps = [
        {"id": "ep_a", "title": "A", "seconds": 3.0, "qa": "pass", "hands": 0.9, "pose": "E-A",
         "n_subtasks": 2, "source": "Team", "poster": "posters/ep_a.jpg"},
        {"id": "ep_b", "title": "B", "seconds": 4.0, "qa": "flag", "hands": 0.5, "pose": "E-A",
         "n_subtasks": 1, "source": "Other", "poster": "posters/ep_b.jpg"},
    ]  # fmt: skip
    (viewer / "data" / "index.json").write_text(json.dumps({"episodes": eps}))
    out = tmp_path / "out"
    rows = [{"id": "h1m-team", "ego_viewer": "human1m/v/viewer", "ego_source": "Team"}]
    assert egocentric.build(fw, out, rows) == {"h1m-team": 1}
    got = json.loads((out / "ds/h1m-team/episodes.json").read_text())
    assert [e["id"] for e in got] == ["ep_a"] and got[0][
        "poster"
    ] == "/data/ds/h1m-team/posters/ep_a.jpg"
    assert (out / "ds/h1m-team/posters/ep_a.jpg").is_file()
    q = json.loads((out / "ds/h1m-team/quality.json").read_text())
    assert q["qa"] == {"pass": 1}


def test_rows_none_reads_seed_catalog(fw: ConsolePaths, tmp_path: Path) -> None:
    assert egocentric.build(fw, tmp_path / "out") == {}

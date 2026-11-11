from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel.console import index
from flywheel.console.index import story
from flywheel.console.paths import ConsolePaths


def test_build_all_on_empty_fw_root(fw: ConsolePaths) -> None:
    counts = index.build_all(fw)
    assert set(counts) == {"catalog", "robot", "ego", "story"}
    assert (fw.index / "catalog.json").is_file()
    assert (fw.index / "story.json").is_file()
    assert [p.name for p in fw.console_dir.iterdir()] == ["index"]


def test_build_all_atomic(fw: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    index.build_all(fw)
    before = (fw.index / "story.json").read_text()
    (fw.index / "marker").write_text("keep")

    def boom(paths: ConsolePaths, out: Path) -> dict[str, int]:
        raise RuntimeError("boom")

    monkeypatch.setattr(story, "build", boom)
    with pytest.raises(RuntimeError):
        index.build_all(fw)
    assert (fw.index / "story.json").read_text() == before
    assert (fw.index / "marker").read_text() == "keep"
    assert [p.name for p in fw.console_dir.iterdir()] == ["index"]


def test_build_all_only_keeps_other_parts(fw: ConsolePaths) -> None:
    index.build_all(fw)
    (fw.index / "story.json").write_text(json.dumps({"sentinel": 1}))
    counts = index.build_all(fw, {"catalog"})
    assert set(counts) == {"catalog"}
    assert json.loads((fw.index / "story.json").read_text()) == {"sentinel": 1}


def test_build_all_rejects_unknown_part(fw: ConsolePaths) -> None:
    with pytest.raises(ValueError):
        index.build_all(fw, {"nope"})


def test_post_pass_fills_thumbs_qa_counts_and_rsync(fw: ConsolePaths) -> None:
    viewer = fw.fw_root / "human1m" / "ego-h1m-20261111" / "viewer"
    (viewer / "data").mkdir(parents=True)
    (viewer / "posters").mkdir()
    eps = []
    for k in range(6):
        (viewer / "posters" / f"e{k}.jpg").write_bytes(b"\xff\xd8jpg")
        eps.append({"id": f"e{k}", "title": "t", "seconds": 3.0, "qa": "pass" if k < 4 else "flag",
                    "hands": 0.9, "pose": "E-A", "n_subtasks": 1, "source": "Team tray",
                    "poster": f"posters/e{k}.jpg"})  # fmt: skip
    (viewer / "data" / "index.json").write_text(json.dumps({"episodes": eps}))
    index.build_all(fw)
    rows = {r["id"]: r for r in json.loads((fw.index / "catalog.json").read_text())["rows"]}
    team = rows["h1m-team"]
    assert len(team["thumbs"]) == 4
    assert all(t.startswith("/data/ds/h1m-team/posters/") for t in team["thumbs"])
    assert team["qa_counts"] == {"pass": 4, "flag": 2}
    cmax = rows["cut-CMAX"]
    assert cmax["rsync"] == (
        "rsync -a rtx3060:~/denso-da34-pool/fwdata/cut-cmax-draft/sets/CMAX/meta "
        "./fwdata/remote/cut-CMAX/"
    )
    assert cmax["rsync_full"].startswith(
        "rsync -a rtx3060:~/denso-da34-pool/fwdata/cut-cmax-draft/sets/CMAX/ "
        "./fwdata/remote/cut-CMAX/"
    )
    assert "rsync" not in rows["h1m-team"]


def test_post_pass_on_partial_run_patches_kept_catalog(fw: ConsolePaths) -> None:
    index.build_all(fw)
    d = fw.index / "ds" / "h1m-team"
    (d / "posters").mkdir(parents=True)
    (d / "posters" / "a.jpg").write_bytes(b"\xff\xd8")
    (d / "quality.json").write_text(json.dumps({"qa": {"pass": 3}}))
    index.build_all(fw, {"story"})
    rows = {r["id"]: r for r in json.loads((fw.index / "catalog.json").read_text())["rows"]}
    assert rows["h1m-team"]["thumbs"] == ["/data/ds/h1m-team/posters/a.jpg"]
    assert rows["h1m-team"]["qa_counts"] == {"pass": 3}

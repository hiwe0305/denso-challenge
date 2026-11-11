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

"""The EgoDex stand-in: which episodes, read by range out of a zip, in Psi0's layout."""

from __future__ import annotations

import io
import json
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import pytest
from flywheel_psi0.stage1 import egodex_sample
from flywheel_psi0.stage1.egodex_sample import fetch, layout_problems, select

URL = "https://example.invalid/egodex/test.zip"


def archive_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("test/", b"")
        for task, indices in {"pour": [0, 1, 10, 2], "wrap": [3, 5], "zip_bag": [0]}.items():
            for index in indices:
                archive.writestr(f"test/{task}/{index}.hdf5", f"h{task}{index}".encode())
                archive.writestr(f"test/{task}/{index}.mp4", f"m{task}{index}".encode() * 50)
        archive.writestr("test/zip_bag/7.hdf5", b"no video")  # incomplete: skipped
    return buffer.getvalue()


def test_select_takes_the_lowest_complete_episodes_in_task_order() -> None:
    names = zipfile.ZipFile(io.BytesIO(archive_bytes())).namelist()
    assert select(names, 2) == [("pour", 0), ("pour", 1), ("wrap", 3), ("wrap", 5), ("zip_bag", 0)]


class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes, headers: dict[str, str]) -> None:
        super().__init__(data)
        self.headers = headers

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve `archive_bytes()` at URL with HEAD and Range support; log the ranges."""
    data = archive_bytes()
    ranges: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: float = 0) -> Any:
        assert request.full_url == URL
        if request.get_method() == "HEAD":
            return FakeResponse(b"", {"Content-Length": str(len(data)), "ETag": '"abc-1"'})
        spec = request.get_header("Range")
        ranges.append(spec)
        start, end = (int(x) for x in spec.removeprefix("bytes=").split("-"))
        return FakeResponse(data[start : end + 1], {})

    monkeypatch.setattr(egodex_sample.urllib.request, "urlopen", urlopen)
    return ranges


def test_fetch_writes_the_layout_and_a_manifest(tmp_path: Path, served: list[str]) -> None:
    manifest = fetch(URL, tmp_path, "part1", 1, '"abc-1"')
    assert (manifest["episodes"], manifest["tasks"]) == (3, 3)
    assert (tmp_path / "part1" / "pour" / "0.mp4").read_bytes() == b"mpour0" * 50
    assert sorted(p.name for p in (tmp_path / "part1" / "wrap").iterdir()) == ["3.hdf5", "3.mp4"]
    assert layout_problems(tmp_path, "part1") == []
    written = json.loads((tmp_path / "manifest.json").read_text())
    assert written["source"]["etag"] == '"abc-1"'
    assert {f["member"] for f in written["files"]} >= {"test/pour/0.hdf5", "test/pour/0.mp4"}
    assert served, "read by range requests"


def test_fetch_keeps_intact_files_on_a_second_run(tmp_path: Path, served: list[str]) -> None:
    fetch(URL, tmp_path, "part1", 1, None)
    video = tmp_path / "part1" / "pour" / "0.mp4"
    written = video.stat().st_mtime_ns
    video.with_name("1.mp4").write_bytes(b"stale")  # not chosen at 1 per task: left alone
    fetch(URL, tmp_path, "part1", 1, None)
    assert video.stat().st_mtime_ns == written


def test_fetch_refuses_a_changed_archive(tmp_path: Path, served: list[str]) -> None:
    with pytest.raises(RuntimeError, match="changed"):
        fetch(URL, tmp_path, "part1", 1, '"other-1"')


def test_layout_problems_name_missing_videos(tmp_path: Path) -> None:
    assert layout_problems(tmp_path, "part1") == [f"{tmp_path / 'part1'} is missing"]
    (tmp_path / "part1" / "pour").mkdir(parents=True)
    (tmp_path / "part1" / "pour" / "0.hdf5").write_bytes(b"")
    assert layout_problems(tmp_path, "part1") == [f"{tmp_path / 'part1/pour/0.hdf5'} has no .mp4"]

"""`fw egocentric human1m` and `human1m-check` end to end (DA-04 11.4, 11/11/2026): status
for every clip, a shard that passes its check, the explorer and a small sample of it.
Video goes through a fake encoder (OpenCV mp4v), so no ffmpeg is needed."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from flywheel.data import egocentric_cli
from flywheel.data.egocentric_cli import app
from flywheel.data.export.human1m.check import check_shard
from h1m_data import FakeEncoder, add_hand_joints
from typer.testing import CliRunner

pytest.importorskip("cv2")
runner = CliRunner()
REPO = Path(__file__).resolve().parents[5]
H1M = REPO / "configs" / "data" / "egocentric-human1m.yaml"


def run(*args: str) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    return result.output


@pytest.fixture
def work(store: Path, config_path: Path) -> Path:
    add_hand_joints(store / "egodex")
    out = run("ingest", "egodex", "--config", str(config_path))
    path = Path(out.split("work: ")[1].split()[0])
    for command in ("pose", "annotate", "qa"):  # EgoDex is waived: no deid step
        run(command, str(path), "--config", str(config_path))
    return path


def test_human1m_writes_status_shard_and_explorer(
        work: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(egocentric_cli, "find_ffmpeg", lambda: "fake")
    monkeypatch.setattr(egocentric_cli, "Ffmpeg", lambda binary: FakeEncoder())
    out = tmp_path / "h1m"
    printed = run("human1m", str(out), "--work", str(work), "--h1m-config", str(H1M),
                  "--sample", "2", "--workers", "2")
    status = json.loads((out / "status.json").read_text())
    assert len(status) == 4 and {r["source"] for r in status} == {"egodex"}
    assert all(r["deid"].startswith("waived") for r in status)
    exported = [r for r in status if r["decision"] == "exported"]
    assert exported, printed
    assert all(r["decision"] in ("exported", "rejected_qa") for r in status)
    shard = out / "egodex"
    assert check_shard(shard) == []
    run("human1m-check", str(shard))
    info = json.loads((shard / "meta/info.json").read_text())
    assert info["codebase_version"] == "v3.0" and info["total_episodes"] == len(exported)
    assert info["missing_fields"] == {} and "egodex-llm" in info["annotation_sources"]
    episodes = pq.read_table(shard / "meta/episodes/chunk-000/file-000.parquet").to_pylist()
    assert all(e["camera_intrinsics/main"][0] > 0 and e["vendor_id"].startswith("vendor_")
               for e in episodes)
    subtasks = pq.read_table(shard / "meta/subtasks.parquet").to_pylist()
    assert any("right hand" in s["subtask"] for s in subtasks)
    summary = json.loads((out / "summary.json").read_text())
    assert summary["all"]["clips"] == 4 and summary["shards"]["egodex"]["problems"] == []
    viewer = out / "viewer"
    assert (viewer / "index.html").is_file() and (viewer / "data/index.js").is_file()
    index = json.loads((viewer / "data/index.json").read_text())
    assert len(index["episodes"]) == len(exported) and len(index["status"]) == 4
    one = index["episodes"][0]["id"]
    payload = (viewer / "data/ep" / f"{one}.js").read_text()
    assert '"space":"world"' in payload and (viewer / "media" / f"{one}.mp4").is_file()
    assert (viewer / "posters" / f"{one}.jpg").is_file()
    sample = json.loads((out / "viewer-sample/data/index.json").read_text())
    assert len(sample["episodes"]) == min(2, len(exported))

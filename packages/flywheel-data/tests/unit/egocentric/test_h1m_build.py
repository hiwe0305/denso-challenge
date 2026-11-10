"""The Human-1M build on a small EgoDex-like sample (DA-04 11.3, 11/11/2026): a shard
that passes its check, a broken one that does not, an excluded source and a recording
that was not de-identified, which is `blocked_deid` and never read."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from ego_data import make_videos
from flywheel.data.annotate.deid.gate import DeidBlocked
from flywheel.data.egocentric_cli import app
from flywheel.data.export.human1m import build as h1m
from flywheel.data.export.human1m.check import check_shard
from flywheel.data.ingest.egocentric import api
from flywheel.data.ingest.egocentric.episodes import read_bundle
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


def test_build_writes_a_shard_that_passes_its_check(work: Path, tmp_path: Path) -> None:
    result = h1m.build(tmp_path / "h1m", [work], [], {}, h1m.load_h1m_config(H1M),
                       FakeEncoder(), say=lambda _: None)
    shard = tmp_path / "h1m" / "egodex"
    assert result.problems["egodex"] == []
    info = json.loads((shard / "meta/info.json").read_text())
    exported = [i for i in result.items if i.row.decision == "exported"]
    assert info["codebase_version"] == "v3.0" and info["total_episodes"] == len(exported) > 0
    assert info["missing_fields"] == {} and "egodex-llm" in info["annotation_sources"]
    episodes = pq.read_table(shard / "meta/episodes/chunk-000/file-000.parquet").to_pylist()
    assert all(e["camera_intrinsics/main"][0] > 0 and e["vendor_id"].startswith("vendor_")
               for e in episodes)
    subtasks = pq.read_table(shard / "meta/subtasks.parquet").to_pylist()
    assert any("right hand" in s["subtask"] for s in subtasks)
    status = json.loads((tmp_path / "h1m" / "status.json").read_text())
    assert len(status) == 4 and all(r["deid"].startswith("waived") for r in status)


def test_check_finds_a_broken_shard(work: Path, tmp_path: Path) -> None:
    h1m.build(tmp_path / "h1m", [work], [], {}, h1m.load_h1m_config(H1M), FakeEncoder(),
              say=lambda _: None)
    shard = tmp_path / "h1m" / "egodex"
    path = shard / "meta/subtasks.parquet"
    table = pq.read_table(path)
    pq.write_table(table.slice(1), path)
    assert any("do not tile" in p for p in check_shard(shard, count_video=False))


def test_an_excluded_source_is_kept_out_with_its_reason(work: Path, tmp_path: Path) -> None:
    cfg = h1m.load_h1m_config(H1M)
    source_id = api.read_source(work).source_id
    cfg = h1m.H1MConfig(**{**cfg.__dict__, "exclude": {source_id: "badge in view"}})
    rows = [i.row for i in h1m.survey([work], cfg)]
    assert {(r.decision, r.reason) for r in rows} == {("excluded", "badge in view")}


def test_a_recording_without_deid_is_blocked_and_never_read(
        store: Path, config_path: Path, tmp_path: Path) -> None:
    root = make_videos(tmp_path / "rec")
    out = run("ingest", "video", "--root", str(root), "--config", str(config_path))
    path = Path(out.split("work: ")[1].split()[0])
    cfg = h1m.load_h1m_config(H1M)
    items = h1m.survey([path], cfg)
    assert [i.row.decision for i in items] == ["blocked_deid"]
    assert items[0].row.deid.startswith("blocked")
    with pytest.raises(DeidBlocked):
        api.video_of(read_bundle(path, items[0].row.episode_id), items[0].source)

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from conftest import write_mp4
from flywheel.console.paths import ConsolePaths, set_active
from flywheel.console.server import media

ROWS = [{"id": "S70", "lerobot": "cut/S70"}, {"id": "vwr", "ego_viewer": "viewer"}]


@pytest.fixture(autouse=True)
def _rows(fw: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    set_active(fw)
    monkeypatch.setattr(media, "seed_rows", lambda: ROWS)
    media._layout.clear()


def test_deid_path_never_returns_raw(work: Path) -> None:
    d = media.work_dir("src_test")
    assert media.deid_path(d, "ep_deid") is not None
    assert media.deid_path(d, "ep_raw") is None
    with pytest.raises(ValueError):
        media.deid_path(d, "../x")


def test_deid_path_refuses_paths_outside_fwdata(
    fw: ConsolePaths, work: Path, tmp_path: Path
) -> None:
    out = write_mp4(tmp_path / "elsewhere.deid.mp4")
    b = work / "egocentric" / "ep_deid" / "bundle.json"
    b.write_text(json.dumps({"mp4": str(out)}))
    assert media.deid_path(media.work_dir("src_test"), "ep_deid") is None


def test_episode_video_prefers_pipeline_then_viewer(fw: ConsolePaths, work: Path) -> None:
    assert media.episode_video("src_test", "ep_deid").name == "a.deid.mp4"
    with pytest.raises(KeyError):
        media.episode_video("src_test", "ep_raw")
    v = write_mp4(fw.fw_root / "viewer" / "media" / "ep_v1.mp4")
    assert media.episode_video("vwr", "ep_v1") == v
    with pytest.raises(KeyError):
        media.episode_video("other", "ep_v1")


def test_poster_cache_lives_under_console_cache(fw: ConsolePaths, work: Path) -> None:
    media.poster_jpeg("src_test", "ep_deid", 100)
    media.ego_strip_jpeg("src_test", "ep_deid", 3)
    names = sorted(p.name for p in (fw.cache / "posters").iterdir())
    assert names == ["src_test_ep_deid_100.jpg", "strip_src_test_ep_deid_3.jpg"]


def test_episode_json_downsamples(fw: ConsolePaths, lerobot: Path) -> None:
    (lerobot / "meta" / "action_layout.json").write_text(
        json.dumps({"dimensions": [{"group": "hand", "name": "h0"}, {"group": "arm"}]})
    )
    n = 20
    cols = {
        "action": [[float(i), 2.0 * i] for i in range(n)],
        "timestamp": [i / 50 for i in range(n)],
        "observation.hand_joints": [[1.0] for _ in range(n)],
        "observation.arm_joints": [[1.0, 2.0] for _ in range(n)],
        "observation.leg_joints": [[0.0] for _ in range(n)],
        "observation.prev_torso_rpy": [[0.0, 0.0, 0.0] for _ in range(n)],
    }
    pq.write_table(pa.table(cols), lerobot / "data" / "chunk-000" / "episode_000001.parquet")
    out = json.loads(media.episode_json("S70", 1))
    assert out["n"] == 20 and out["hz"] == 10 and len(out["t"]) == 4
    assert out["action"]["hand"]["names"] == ["h0"]
    assert out["action"]["arm"]["names"] == ["arm[1]"]
    assert out["action"]["hand"]["v"] == [[0.0, 5.0, 10.0, 15.0]]
    assert out["action"]["arm"]["v"] == [[0.0, 10.0, 20.0, 30.0]]
    assert (fw.cache / "ep_S70_000001.json").is_file()
    with pytest.raises(FileNotFoundError):
        media.episode_json("S70", 9)
    with pytest.raises(KeyError):
        media.episode_json("nope", 1)
    with pytest.raises(ValueError):
        media.episode_json("S70", 10**6)

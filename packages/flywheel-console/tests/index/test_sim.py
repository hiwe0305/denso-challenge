from __future__ import annotations

import io
import json
import os
import tarfile
import zipfile
from pathlib import Path

from conftest import write_mp4
from flywheel.console.index import sim
from flywheel.console.paths import ConsolePaths

ROOT = "C70_R1/G1WholebodyTrayTransferTeleop-v0"
TELE = "G1WholebodyLocomotionPickBetweenTablesTeleop-v0"


def _ep(i: int, purpose: str, cluster: str | None, cls: str = "public") -> dict[str, object]:
    cfg = {
        "tray": {
            "sample": {
                "level": 1,
                "seed": 500 + i,
                "tray_pose": {"x": 1.0, "y": 0.0, "yaw": 0.1},
                "target_pose": {"x": -1.0, "y": 0.0, "yaw": 0.0},
                "robot_spawn": {"x": 0.45, "y": 0.0, "yaw": 0.0},
            },
            "report": {"steps": [True] * 7, "success": True},
        },
        "flywheel": {
            "seed": 500 + i,
            "level": 1,
            "purpose": purpose,
            "cluster_id": cluster,
            "data_class": cls,
        },
    }
    return {"episode_index": i, "length": 100 + i, "environment_config": json.dumps(cfg)}


def _add(t: tarfile.TarFile, name: str, data: bytes) -> None:
    ti = tarfile.TarInfo(name)
    ti.size = len(data)
    t.addfile(ti, io.BytesIO(data))


def _cut(fw: ConsolePaths, tmp: Path) -> Path:
    eps = [
        _ep(0, "coverage", None),
        _ep(1, "coverage", None, cls="internal"),
        _ep(2, "failure_targeted", "place-L2-1000120"),
        _ep(3, "failure_targeted", "place-L1-1000107"),
    ]
    subset = {
        "base": {
            "marker_sha256": "5" * 64,
            "from_cut": {"marker_sha256": "a" * 64},
            "parts": [
                {"release_id": "r_cov", "n": 2, "first_episode_index": 0},
                {"release_id": "r_prev", "n": 1, "first_episode_index": 2},
            ],
        },
        "targeted": {"release_id": "r_round", "n": 1, "first_episode_index": 3},
    }
    tar = fw.fw_root / "tray/pair-cuts/C70_R1.tar"
    tar.parent.mkdir(parents=True)
    vid = write_mp4(tmp / "v.mp4").read_bytes()
    with tarfile.open(tar, "w") as t:
        _add(t, f"{ROOT}/meta/episodes.jsonl", "\n".join(json.dumps(e) for e in eps).encode())
        _add(t, f"{ROOT}/meta/flywheel_subset.json", json.dumps(subset).encode())
        _add(t, f"{ROOT}/meta/info.json", json.dumps({"codebase_version": "v2.1"}).encode())
        _add(
            t,
            f"{ROOT}/meta/batch_summary.json",
            json.dumps({"attempts": 9, "failures": {"L-ONE-HAND": 2}}).encode(),
        )
        for i in range(4):
            _add(t, f"{ROOT}/videos/chunk-000/egocentric/episode_{i:06d}.mp4", vid)
    (tar.parent / "C70_R1.tar.json").write_text(json.dumps({"sha256": "e84ec995" + "0" * 56}))
    z = fw.fw_root / f"psi-data/simple/{TELE}.zip"
    z.parent.mkdir(parents=True)
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr(
            f"{TELE}/meta/episodes.jsonl",
            "\n".join(json.dumps({"episode_index": i, "length": 50}) for i in range(2)),
        )
        for i in range(2):
            zf.writestr(f"{TELE}/videos/chunk-000/egocentric/episode_{i:06d}.mp4", vid)
    return tar


def test_sim_labels_episodes_and_extracts_sample_videos(fw: ConsolePaths, tmp_path: Path) -> None:
    _cut(fw, tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    counts = sim.build(fw, out)
    d = json.loads((out / "sim.json").read_text())
    assert d["sha8"] == "e84ec995"
    assert [e["label"] for e in d["episodes"]] == ["coverage", "coverage", "prev", "round"]
    assert [(p["label"], p["n"]) for p in d["parts"]] == [
        ("coverage", 2),
        ("prev", 1),
        ("round", 1),
    ]
    assert (
        d["cuts"]["C70_R1"]["sha256"].startswith("e84ec995") and d["cuts"]["S70"]["of"] == "marker"
    )
    e3 = d["episodes"][3]
    assert e3["for"] == [1, 1000107] and e3["tray"]["x"] == 1.0 and e3["steps"] == [True] * 7
    # first sampled episode of its group: poster cut at the first POSTER_AT position
    assert e3["video"] == "e84ec995/ep_000003.mp4" and e3["poster"] == "e84ec995/ep_000003.p03.jpg"
    media = fw.console_dir / "media" / "sim"
    assert (media / "e84ec995/ep_000003.mp4").is_file() and (
        media / "e84ec995/ep_000003.p03.jpg"
    ).is_file()
    assert d["episodes"][1]["video"] is None  # not public: never extracted
    assert [x["video"] for x in d["teleop"]] == ["teleop/ep_000000.mp4", "teleop/ep_000001.mp4"]
    # posters of one group step through the episode, so neighbouring cards differ
    assert [x["poster"] for x in d["teleop"]] == [
        "teleop/ep_000000.p03.jpg",
        "teleop/ep_000001.p30.jpg",
    ]
    assert d["batch"]["attempts"] == 9 and d["format"] == "LeRobot v2.1"
    assert {x["task"] for x in d["teleop"]} == {"two_table"}  # not tray carrying
    assert counts["sim_episodes"] == 4 and counts["sim_media"] == 5
    before = (media / "e84ec995/ep_000003.mp4").stat().st_mtime_ns
    os.utime(media / "e84ec995/ep_000003.mp4", ns=(before - 10**9, before - 10**9))
    sim.build(fw, out)
    assert (
        media / "e84ec995/ep_000003.mp4"
    ).stat().st_mtime_ns == before - 10**9  # kept, not rewritten


def test_sim_without_the_cut_writes_an_empty_index(fw: ConsolePaths, tmp_path: Path) -> None:
    counts = sim.build(fw, tmp_path)
    d = json.loads((tmp_path / "sim.json").read_text())
    assert (
        d["episodes"] == [] and d["teleop"] == [] and counts == {"sim_episodes": 0, "sim_media": 0}
    )


def test_spread_picks_evenly() -> None:
    assert sim._spread(list(range(100)), 4) == [0, 25, 50, 75]
    assert sim._spread([1, 2], 5) == [1, 2]


def test_unreadable_video_gets_no_poster_and_does_not_abort(tmp_path: Path) -> None:
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    assert sim._poster(bad) is None and not list(tmp_path.glob("*.jpg"))


def test_poster_position_is_in_the_name_and_existing_files_are_kept(tmp_path: Path) -> None:
    v = write_mp4(tmp_path / "ep_000007.mp4")
    assert sim._poster(v, 0.3) == "ep_000007.p30.jpg"
    jpg = tmp_path / "ep_000007.p30.jpg"
    jpg.write_bytes(b"kept")
    assert sim._poster(v, 0.3) == "ep_000007.p30.jpg" and jpg.read_bytes() == b"kept"
    assert (
        sim._poster(v, 0.97) == "ep_000007.p97.jpg"
        and (tmp_path / "ep_000007.p97.jpg").stat().st_size > 100
    )

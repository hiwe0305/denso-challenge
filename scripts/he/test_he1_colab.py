"""Checks of the HE-1 Colab driver and the demo-set cut, on CPU. Run: uv run pytest scripts/he -q"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from demo_subset import MARKER, build_subset
from flywheel.data.ingest.lerobot import EpisodeFrames, iter_episodes, write_episode
from flywheel_psi0.tray.demo_sets import EXPORT_META, MANIFEST, DemoSet, DemoSets, set_hash
from he1_colab import PLAN, hash_problems, job_id, load_point, persist, unmounted_drive

TASK = "pick up the box"
RELEASE = "a" * 64


def fake_dataset(root: Path, lengths: list[int]) -> Path:
    """A LeRobot v2.1 dataset in psi-data's layout: episode i has action and states all i."""
    meta = root / "meta"
    meta.mkdir(parents=True)
    scalar = {"dtype": "int64", "shape": [1]}
    info = {
        "codebase_version": "v2.1",
        "fps": 50,
        "chunks_size": 1000,
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/egocentric/episode_{episode_index:06d}.mp4",
        "splits": {"train": f"0:{len(lengths)}"},
        "features": {
            "observation.images.egocentric": {"dtype": "video", "shape": [180, 320, 3]},
            "states": {"dtype": "float32", "shape": [32]},
            "action": {"dtype": "float32", "shape": [36]},
            "timestamp": {"dtype": "float32", "shape": [1]},
            **{k: scalar for k in ("frame_index", "episode_index", "index", "task_index")},
            "next.done": {"dtype": "bool", "shape": [1]},
        },
    }
    (meta / "info.json").write_text(json.dumps(info))
    (meta / "tasks.jsonl").write_text(json.dumps({"task_index": 0, "task": TASK}) + "\n")
    (meta / "lang_map.json").write_text("{}")
    for i, n in enumerate(lengths):
        write_episode(
            root,
            EpisodeFrames(
                episode_index=i,
                task=TASK,
                timestamp=np.arange(n) / 50.0,
                frame_index=np.arange(n, dtype=np.int64),
                states=np.full((n, 32), i, dtype=np.float32),
                action=np.full((n, 36), i, dtype=np.float32),
                video_frames={},
            ),
        )
    return root


def demo_sets(kept: list[int], name: str = "N2") -> DemoSets:
    demo = DemoSet(n=len(kept), set_hash=set_hash(RELEASE, kept), seeds=kept, episode_indices=kept)
    return DemoSets(
        release_id="psi-data@test", release_hash=RELEASE, salt="test", sets={name: demo}
    )


def test_a_cut_holds_its_episodes_renumbered_with_its_own_stats(tmp_path: Path) -> None:
    src = fake_dataset(tmp_path / "src", [3, 4, 5, 6, 7])
    out = tmp_path / "N2"
    build_subset(src, out, demo_sets([1, 3]), "N2")
    episodes = list(iter_episodes(out))
    assert [e.episode_index for e in episodes] == [0, 1]
    assert [float(e.action[0, 0]) for e in episodes] == [1.0, 3.0]  # source order kept
    assert [len(e.timestamp) for e in episodes] == [4, 6]
    info = json.loads((out / "meta/info.json").read_text())
    assert (info["total_episodes"], info["total_frames"], info["splits"]) == (
        2,
        10,
        {"train": "0:2"},
    )
    stats = json.loads((out / "meta/stats_psi0.json").read_text())
    assert stats["action"]["mean"][0] == pytest.approx((4 * 1 + 6 * 3) / 10)  # not over all 5
    assert stats["action"]["max"][0] == 3.0
    marker = json.loads((out / "meta" / MARKER).read_text())
    assert [e["source_episode_index"] for e in marker["episodes"]] == [1, 3]
    assert (out / "meta/lang_map.json").is_file()


def test_a_cut_refuses_a_set_whose_hash_does_not_hold(tmp_path: Path) -> None:
    src = fake_dataset(tmp_path / "src", [3, 4, 5])
    sets = demo_sets([0, 1])
    forged = sets.sets["N2"].model_copy(update={"episode_indices": [0, 2], "seeds": [0, 2]})
    with pytest.raises(ValueError, match="set hash"):
        build_subset(src, tmp_path / "out", sets.model_copy(update={"sets": {"N2": forged}}), "N2")


def test_a_cut_is_never_written_over(tmp_path: Path) -> None:
    src = fake_dataset(tmp_path / "src", [3, 4])
    (tmp_path / "out").mkdir()
    with pytest.raises(FileExistsError):
        build_subset(src, tmp_path / "out", demo_sets([0, 1]), "N2")


def digest(root: Path) -> str:
    """One sha256 over every file's path and bytes."""
    rows = sorted(
        f"{p.relative_to(root)} {hashlib.sha256(p.read_bytes()).hexdigest()}"
        for p in root.rglob("*")
        if p.is_file()
    )
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def test_an_he1_cut_is_byte_identical_to_the_cut_before_seeds(tmp_path: Path) -> None:
    # Pinned from master 5fe3d0b's demo_subset.py, which hashed episode indices, on
    # this fixture (pyarrow of uv.lock); psi-data's seeds are its indices, no export.
    src = fake_dataset(tmp_path / "src", [3, 4, 5, 6, 7])
    build_subset(src, tmp_path / "out", demo_sets([1, 3]), "N2")
    assert digest(tmp_path / "out") == (
        "a4842e184071a4bb07a83d541d78e3644380cbafc74a61133b1e8adc34cb8449"
    )


def test_without_an_export_the_indices_must_be_the_seeds(tmp_path: Path) -> None:
    src = fake_dataset(tmp_path / "src", [3, 4, 5])
    sets = demo_sets([0, 1])
    moved = sets.sets["N2"].model_copy(update={"episode_indices": [0, 2]})
    with pytest.raises(ValueError, match="indices are not the seeds"):
        build_subset(src, tmp_path / "out", sets.model_copy(update={"sets": {"N2": moved}}), "N2")


SEEDS = [1000, 1003, 1004, 1009, 1010]  # episode i of the release has seed SEEDS[i]


def tray_release(root: Path) -> str:
    """fake_dataset plus the export and manifest of a tray release; its release hash."""
    fake_dataset(root, [3, 4, 5, 6, 7])
    rows = [{"episode_index": i, "seed": seed} for i, seed in enumerate(SEEDS)]
    (root / EXPORT_META).write_text(json.dumps({"episodes": rows}))
    files = [
        {
            "path": EXPORT_META,
            "sha256": hashlib.sha256((root / EXPORT_META).read_bytes()).hexdigest(),
        }
    ]
    release_hash = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    (root / MANIFEST).write_text(json.dumps({"release_hash": release_hash, "files": files}))
    return release_hash


def tray_sets(release_hash: str, seeds: list[int], indices: list[int]) -> DemoSets:
    demo = DemoSet(
        n=len(seeds), set_hash=set_hash(release_hash, seeds), seeds=seeds, episode_indices=indices
    )
    return DemoSets(release_id="tray@test", release_hash=release_hash, salt="t", sets={"C": demo})


def test_a_tray_cut_takes_each_seeds_index_from_the_release_export(tmp_path: Path) -> None:
    release_hash = tray_release(tmp_path / "src")
    # the file's indices are not read: the export says seed 1003 is 1, 1009 is 3
    sets = tray_sets(release_hash, [1003, 1009], [0, 4])
    marker = build_subset(tmp_path / "src", tmp_path / "C", sets, "C")
    assert marker["set_hash"] == set_hash(release_hash, [1003, 1009])
    assert [e["source_episode_index"] for e in marker["episodes"]] == [1, 3]
    assert [float(e.action[0, 0]) for e in iter_episodes(tmp_path / "C")] == [1.0, 3.0]
    assert not (tmp_path / "C" / EXPORT_META).exists()  # the release's numbering stays out


def test_a_tray_cut_refuses_another_release_or_a_seed_it_lacks(tmp_path: Path) -> None:
    release_hash = tray_release(tmp_path / "src")
    other = tray_sets("b" * 64, [1003, 1009], [1, 3])
    with pytest.raises(ValueError, match="is release"):
        build_subset(tmp_path / "src", tmp_path / "a", other, "C")
    lacking = tray_sets(release_hash, [1003, 1005], [1, 2])
    with pytest.raises(ValueError, match=r"seeds \[1005\] are not in"):
        build_subset(tmp_path / "src", tmp_path / "b", lacking, "C")
    sets = tray_sets(release_hash, [1003, 1009], [1, 3])
    forged = sets.sets["C"].model_copy(update={"seeds": [1003, 1010]})  # hash kept
    with pytest.raises(ValueError, match="seeds do not give the set hash"):
        build_subset(
            tmp_path / "src", tmp_path / "c", sets.model_copy(update={"sets": {"C": forged}}), "C"
        )


def test_only_the_preliminary_points_of_the_frozen_plan_run() -> None:
    _, point, run_plan = load_point("V-EGO/N20/0")
    assert job_id(point) == "da26-t2-ft-vego-n20-s0"
    assert run_plan == "rp_95c98a476499"
    assert job_id(load_point("V-NOEGO/N20/0")[1]) == "da26-t2-ft-vnoego-n20-s0"
    with pytest.raises(SystemExit, match="full point"):
        load_point("V-EGO/N80/0")
    with pytest.raises(SystemExit, match="not a point"):
        load_point("V-EGO/N20/7")
    assert PLAN.is_file()


def test_a_wrong_or_missing_file_stops_setup(tmp_path: Path) -> None:
    good = tmp_path / "good.bin"
    good.write_bytes(b"weights")
    pinned = "4c1e2f0bd5e7c9c4a0c9d8b2c6a0b5e40d5f6b6b1c0a6a3e4d1c2b3a4f5e6d7c"
    problems = hash_problems({good: pinned, tmp_path / "gone.bin": pinned})
    assert len(problems) == 2 and "missing" in problems[1]
    import hashlib

    assert hash_problems({good: hashlib.sha256(b"weights").hexdigest()}) == []


def test_persist_copies_complete_checkpoints_only(tmp_path: Path) -> None:
    job = tmp_path / "work/runs/da26-t2-ft-vego-n20-s0"
    ckpts = job / "psi0/run/x/checkpoints"
    for step in (10000, 20000):
        (ckpts / f"ckpt_{step}").mkdir(parents=True)
        (ckpts / f"ckpt_{step}/model.safetensors").write_text(str(step))
    (job / "metrics.jsonl").write_text("{}\n")
    (job / "result.json").write_text(json.dumps({"checkpoint_step": 10000}))  # 20000 mid-write
    persist(tmp_path / "work", tmp_path / "drive")
    copied = tmp_path / "drive/da26-t2-ft-vego-n20-s0"
    assert (copied / "metrics.jsonl").is_file()
    assert (copied / "psi0/run/x/checkpoints/ckpt_10000/model.safetensors").is_file()
    assert not (copied / "psi0/run/x/checkpoints/ckpt_20000").exists()


def test_persist_refuses_an_unmounted_drive(tmp_path: Path) -> None:
    drive = Path("/content/drive/MyDrive/denso/da26")
    assert unmounted_drive(drive, mounted=lambda path: False)
    assert not unmounted_drive(drive, mounted=lambda path: path == "/content/drive")
    assert not unmounted_drive(tmp_path / "drive", mounted=lambda path: False)
    with pytest.raises(SystemExit, match="not mounted"):
        persist(tmp_path / "work", drive)

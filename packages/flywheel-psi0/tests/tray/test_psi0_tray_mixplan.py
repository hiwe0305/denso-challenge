"""One run on N joined demo sets (DA-48 task 2.2), on CPU with four tiny fake parts."""

from __future__ import annotations

import copy
import json
import shutil
import struct
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from flywheel.data.ingest.lerobot import EpisodeFrames, iter_episodes, write_episode
from flywheel.data.inject.stats import write_stats
from flywheel_psi0.tray import mixplan, pair_cut
from flywheel_psi0.tray.cplus_cut import join_cuts
from flywheel_psi0.tray.demo_sets import set_hash
from flywheel_psi0.tray.mixplan import (
    TrayMixPlan,
    check,
    cut_problems,
    freeze,
    launch_problems,
    pending,
)
from flywheel_psi0.tray.runplan import lock_path, rules_sha256

REPO = Path(__file__).resolve().parents[4]
PAIR = REPO / "configs/runplans/tray/he-tray-pair60k.yaml"
RECIPE = "configs/models/psi0-stage3.yaml"
TASK = "carry the tray into the jig"
ENV = JIG_ENV_NAME = "G1WholebodyTrayTransferJigTeleop-v0"
DOC = "docs/he/tray-jig.md"
RULES = "\n<!-- jig-m-rules -->\n\n(m1) M is read at ckpt 100000.\n\n<!-- /jig-m-rules -->\n"
# Four parts, as run M joins them: two full releases, two place cuts. Seeds in release
# order are not ascending, so a positional zip of seeds and indices would name wrong seeds.
PARTS: list[dict[str, Any]] = [
    {"id": "tray_s1_full1", "seeds": [500007, 500001, 500004], "lengths": [9, 7, 8]},
    {"id": "tray_s1_full2", "seeds": [501003, 501000], "lengths": [6, 5]},
    {"id": "tray_s1place_cut1", "seeds": [510002, 510009, 510005], "lengths": [3, 4, 2]},
    {"id": "tray_s1place_cut2", "seeds": [511001, 511000], "lengths": [4, 3]},
]


def _box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def _mp4(path: Path, frames: int, tag: bytes) -> None:
    hdlr = _box(b"hdlr", bytes(8) + b"vide" + bytes(12) + b"\0")
    stsz = _box(b"stsz", bytes(4) + struct.pack(">II", 0, frames) + bytes(4 * frames))
    trak = _box(b"trak", _box(b"mdia", hdlr + _box(b"minf", _box(b"stbl", stsz))))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_box(b"ftyp", b"isom" + bytes(4)) + _box(b"moov", trak) + _box(b"mdat", tag))


def _release_hash(i: int) -> str:
    return f"{i + 1}" * 64


def _part(root: Path, i: int) -> Path:
    """Part i as demo_subset writes it: episode k has action values seed, its own seed row."""
    spec = PARTS[i]
    meta = root / "meta"
    meta.mkdir(parents=True)
    scalar = {"dtype": "int64", "shape": [1]}
    info = {
        "codebase_version": "v2.1",
        "fps": 50,
        "chunks_size": 1000,
        "robot_type": "g1",
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": (
            "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4"
        ),
        "splits": {"train": f"0:{len(spec['seeds'])}"},
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
    for k, (seed, n) in enumerate(zip(spec["seeds"], spec["lengths"], strict=True)):
        video = root / f"videos/chunk-000/observation.images.egocentric/episode_{k:06d}.mp4"
        _mp4(video, n, f"{spec['id']}-{seed}".encode())
        write_episode(
            root,
            EpisodeFrames(
                episode_index=k,
                task=TASK,
                timestamp=np.arange(n) / 50.0,
                frame_index=np.arange(n, dtype=np.int64),
                states=np.full((n, 32), seed, dtype=np.float32),
                action=np.full((n, 36), seed, dtype=np.float32),
                video_frames={},
            ),
        )
    lines = (meta / "episodes.jsonl").read_text().splitlines()
    rows = []
    for line, seed in zip(lines, spec["seeds"], strict=True):
        config = {"uid": "tray_jig", "flywheel": {"seed": seed}}
        rows.append(json.dumps({**json.loads(line), "environment_config": json.dumps(config)}))
    (meta / "episodes.jsonl").write_text("\n".join(rows) + "\n")
    write_stats(root)
    marker = {
        "demo_set": "Q",
        "set_hash": set_hash(_release_hash(i), spec["seeds"]),
        "release_id": spec["id"],
        "release_hash": _release_hash(i),
        "n": len(spec["seeds"]),
        "episodes": [
            {"episode_index": k, "source_episode_index": 20 + k} for k in range(len(spec["seeds"]))
        ],
    }
    (meta / pair_cut.MARKER).write_text(json.dumps(marker))
    return root


def _raw_plan(repo: Path, cut: Path | None) -> dict[str, Any]:
    """A draft M plan whose parts pin the fake demo-set files (and the cut's totals if given)."""
    pair = yaml.safe_load(PAIR.read_text(encoding="utf-8"))
    parts = []
    for i, spec in enumerate(PARTS):
        seeds = spec["seeds"]
        demo = {
            "n": len(seeds),
            "set_hash": set_hash(_release_hash(i), seeds),
            "seeds": sorted(seeds),
            "episode_indices": [20 + k for k in range(len(seeds))],
        }
        file = f"configs/runplans/tray/demo_sets-{spec['id']}.json"
        sets = {"release_id": spec["id"], "release_hash": _release_hash(i), "salt": "test"}
        (repo / file).write_text(json.dumps({**sets, "sets": {"Q": demo}}))
        parts.append(
            {
                "release_id": spec["id"],
                "n": len(seeds),
                "release": {
                    "id": spec["id"],
                    "release_hash": _release_hash(i),
                    "location": "here",
                    "data_class": "public",
                },
                "demo_sets": {
                    "file": file,
                    "file_sha256": pair_cut.sha256(repo / file),
                    "salt": "test",
                    "hashes": {"Q": demo["set_hash"]},
                },
                "set_name": "Q",
            }
        )
    totals: dict[str, Any] = {}
    if cut is not None:
        info = json.loads((cut / "meta/info.json").read_text())
        totals = {
            "frames": info["total_frames"],
            "stats_sha256": pair_cut.sha256(cut / "meta" / pair_cut.STATS),
        }
    baseline = "psi0-baseline-egodex-he"
    return {
        "name": "test-jig-m",
        "purpose": "mix_train",
        "story": "DA-48",
        "status": "draft",
        "site_id": "local",
        "task": {"id": "jig", "env_id": f"simple/{ENV}", "config": "configs/sim/tray_jig.yaml"},
        "embodiment": pair["embodiment"],
        "code": pair["code"],
        "psi_model": pair["psi_model"],
        "parents": {baseline: pair["parents"][baseline]},
        "cut": {
            "name": "M",
            "rule": "set Q of each release",
            "parts": parts,
            "episodes": sum(len(p["seeds"]) for p in PARTS),
            **totals,
        },
        "recipe": {
            **pair["recipe"],
            "overrides": {"train.validation_steps": 2000, "train.max_training_steps": 100000},
        },
        "train_seeds": [0],
        "branches": {"M": {"parent": baseline, "role": "run M"}},
        "checkpoints": {"primary": 100000, "reads": [60000, 80000]},
        "interpretation": {"doc": DOC, "rules_marker": "jig-m-rules"},
        "pricebook": pair["pricebook"],
        "budget": {
            "ceiling_cu": 150,
            "cap_cu_per_run": 150,
            "runs": ["M"],
            "watcher": "scripts/colab/cu_watch.py session --gpu A100 --cap 150 --floor 14",
        },
        "schedule": {"mode": "sequential", "floor_cu": 14, "persist": "persist --watch 600"},
        "drive": {"cuts": "denso/da48/cuts", "runs": "denso/da48/runs"},
    }


def _setup(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    """(repo copy, joined cut M, its plan pinning the cut) with four joined fake parts."""
    repo = tmp_path / "repo"
    (repo / "configs/runplans/tray").mkdir(parents=True)
    (repo / "configs/models").mkdir(parents=True)
    shutil.copy(REPO / RECIPE, repo / RECIPE)
    parts = [_part(tmp_path / f"part{i}" / ENV, i) for i in range(len(PARTS))]
    cut = tmp_path / "sets" / "M" / ENV
    join_cuts(parts, cut, "M")
    return repo, cut, _raw_plan(repo, cut)


def _frozen(repo: Path, raw: dict[str, Any]) -> Path:
    """Rules written and pinned, draft dropped, plan frozen: what the freeze PR does."""
    (repo / DOC).parent.mkdir(parents=True, exist_ok=True)
    (repo / DOC).write_text("# M\n\n[Đề xuất]" + RULES)
    raw["interpretation"]["rules_sha256"] = rules_sha256(RULES, "jig-m-rules")
    raw.pop("status", None)
    path = repo / "configs/runplans/tray/he-tray-jig-m.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False))
    freeze(path, repo)
    return path


def test_a_four_part_join_holds_against_the_plan(tmp_path: Path) -> None:
    repo, cut, raw = _setup(tmp_path)
    plan = TrayMixPlan.model_validate(raw)
    assert check(plan, repo) == []
    assert cut_problems(cut, plan, repo) == []
    assert pending(plan) == [
        "interpretation.rules_sha256: the reading rules are pinned before the run"
    ]
    episodes = sorted(iter_episodes(cut), key=lambda e: e.episode_index)
    seeds = [s for spec in PARTS for s in spec["seeds"]]
    assert [float(e.action[0, 0]) for e in episodes] == [float(s) for s in seeds]
    info = json.loads((cut / "meta/info.json").read_text())
    assert (info["total_episodes"], info["total_frames"]) == (
        10,
        sum(n for spec in PARTS for n in spec["lengths"]),
    )
    marker = pair_cut.read_marker(cut)
    assert marker is not None
    assert [p["first_episode_index"] for p in marker["parts"]] == [0, 3, 5, 8]


def test_the_cut_check_refuses_wrong_parts_stats_and_seeds(tmp_path: Path) -> None:
    repo, cut, raw = _setup(tmp_path)
    plan = TrayMixPlan.model_validate(raw)
    # a plan of three parts against a cut of four
    three = copy.deepcopy(raw)
    three["cut"]["parts"].pop()
    three["cut"]["episodes"] -= len(PARTS[-1]["seeds"])
    assert "cut has 4 parts, the plan 3" in cut_problems(
        cut, TrayMixPlan.model_validate(three), repo
    )
    # the stats of another set
    stats = cut / "meta" / pair_cut.STATS
    good = stats.read_bytes()
    stats.write_text("{}")
    assert any("stats_psi0.json sha256" in p for p in cut_problems(cut, plan, repo))
    stats.write_bytes(good)
    # rows whose own seeds are another part's
    rows = pair_cut.read_rows(cut)
    rows[0]["environment_config"], rows[3]["environment_config"] = (
        rows[3]["environment_config"],
        rows[0]["environment_config"],
    )
    (cut / "meta/episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    problems = cut_problems(cut, plan, repo)
    assert any("tray_s1_full1: the episodes' own seeds are not set Q's" in p for p in problems)
    assert any("tray_s1_full2: the episodes' own seeds" in p for p in problems)
    # an unpinned part is refused before any read of the data
    raw["cut"]["parts"][1].update(release=None, demo_sets=None, set_name=None)
    assert cut_problems(cut, TrayMixPlan.model_validate(raw), repo) == [
        "cut parts ['tray_s1_full2'] are not pinned yet"
    ]


def test_check_refuses_counts_steps_and_reads_that_do_not_hold(tmp_path: Path) -> None:
    repo, _, raw = _setup(tmp_path)

    def problems(edit: dict[str, Any]) -> list[str]:
        changed = copy.deepcopy(raw)
        for path, value in edit.items():
            *keys, last = path.split(".")
            node = changed
            for key in keys:
                node = node[int(key)] if key.isdigit() else node[key]
            node[last] = value
        return check(TrayMixPlan.model_validate(changed), repo)

    assert any("parts sum to 10" in p for p in problems({"cut.episodes": 11}))
    assert any("has 3 episodes, the plan 4" in p for p in problems({"cut.parts.0.n": 4}))
    assert any(
        "past the step count 80000" in p
        for p in problems({"recipe.overrides": {"train.max_training_steps": 80000}})
    )
    assert any("saves every 10000" in p for p in problems({"checkpoints.reads": [65000]}))
    assert any("before the primary" in p for p in problems({"checkpoints.reads": [100000]}))
    assert any(
        "may set only" in p for p in problems({"recipe.overrides": {"train.learning_rate": 1}})
    )
    assert any(
        "data_class internal" in p for p in problems({"cut.parts.2.release.data_class": "internal"})
    )
    assert any("pins release other" in p for p in problems({"cut.parts.3.release.id": "other"}))
    assert any(
        "does not train on cut M" in p for p in problems({"branches": {"K": raw["branches"]["M"]}})
    )
    assert any("not pinned" in p for p in problems({"cut.parts.0.demo_sets.file_sha256": None}))
    assert any("drive.runs" in p for p in problems({"drive": {"cuts": "a", "runs": "../x"}}))
    # the plan may change its step count before the freeze, with its reads
    edit = {
        "recipe.overrides": {"train.max_training_steps": 80000},
        "checkpoints.primary": 80000,
        "checkpoints.reads": [60000],
    }
    assert problems(edit) == []


def test_freeze_refuses_a_draft_or_null_pins_then_locks(tmp_path: Path) -> None:
    repo, cut, raw = _setup(tmp_path)
    path = repo / "configs/runplans/tray/he-tray-jig-m.yaml"
    draft = _raw_plan(repo, None)
    path.write_text(yaml.safe_dump(draft, sort_keys=False))
    with pytest.raises(ValueError, match="status draft") as refused:
        freeze(path, repo)
    assert "frames is not pinned yet" in str(refused.value)
    assert "rules_sha256" in str(refused.value)
    assert not lock_path(path).exists()
    plan = TrayMixPlan.load(path)
    assert any("is not frozen" in p for p in launch_problems(plan, path))
    assert any(p.startswith("DRAFT") for p in launch_problems(plan, path))

    path = _frozen(repo, raw)
    plan = TrayMixPlan.load(path)
    assert launch_problems(plan, path) == []
    assert json.loads(lock_path(path).read_text())["plan"]["cut"]["name"] == "M"
    # any later edit, the step count included, is caught at launch
    raw["recipe"]["overrides"]["train.max_training_steps"] = 90000
    raw["checkpoints"]["primary"] = 90000
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False))
    assert any(
        "changed since it was frozen" in p for p in launch_problems(TrayMixPlan.load(path), path)
    )
    assert cut_problems(cut, plan, repo) == []


def test_cli_checks_the_draft_and_packs_only_a_holding_cut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, cut, raw = _setup(tmp_path)
    monkeypatch.setattr(mixplan, "REPO", repo)
    path = repo / "configs/runplans/tray/he-tray-jig-m.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False))
    assert mixplan.main(["check", str(path), "--data", str(cut)]) == 0
    out = capsys.readouterr().out
    assert "4 parts, 10 episodes, 100000 steps" in out and "draft, 1 pins pending" in out
    assert mixplan.main(["check", str(path), "--launch"]) == 1
    assert "DRAFT" in capsys.readouterr().err
    drive = tmp_path / "drive" / "denso/da48/cuts"
    drive.mkdir(parents=True)
    with pytest.raises(SystemExit):  # the VM fetches <cut name>.tar
        mixplan.main(["pack", str(path), "--data", str(cut), "--out", str(drive / "X.tar")])
    # a pending pin (the rules) stops the pack
    assert mixplan.main(["pack", str(path), "--data", str(cut), "--out", str(drive / "M.tar")]) == 1
    path = _frozen(repo, raw)
    stats = cut / "meta" / pair_cut.STATS
    good = stats.read_bytes()
    stats.write_text("{}")
    assert mixplan.main(["pack", str(path), "--data", str(cut), "--out", str(drive / "M.tar")]) == 1
    assert not (drive / "M.tar").exists()
    stats.write_bytes(good)
    assert mixplan.main(["pack", str(path), "--data", str(cut), "--out", str(drive / "M.tar")]) == 0
    meta = json.loads(Path(f"{drive / 'M.tar'}.json").read_text())
    assert (meta["root"], meta["stats_sha256"]) == (f"M/{ENV}", raw["cut"]["stats_sha256"])
    # the VM side: fetched, extracted under sets/M/<env>, and the same check holds there
    fetched = pair_cut.fetch(drive / "M.tar", tmp_path / "vm" / "sets")
    assert fetched["sha256"] == meta["sha256"]
    assert cut_problems(tmp_path / "vm/sets/M" / ENV, TrayMixPlan.load(path), repo) == []

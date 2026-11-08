"""Freezing the C+ round with its targets, and training it on the VM, on CPU (DA-34 task 5).

A synthetic targeted set (two seeds) on a fake targeted release, in a copy of the repo:
the real round freezes only once its 160 episodes exist.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel_psi0.tray import colab_train
from flywheel_psi0.tray.demo_sets import (
    EXPORT_META,
    MANIFEST,
    DemoSet,
    DemoSets,
    canonical_sha256,
    set_hash,
)
from flywheel_psi0.tray.runplan import (
    TrayRoundPlan,
    TrayRunPlan,
    check_round,
    check_targets_release,
    freeze,
    lock_path,
    main,
    run_plan_id,
)

REPO = Path(__file__).resolve().parents[4]
TRAY = "configs/runplans/tray"
V2 = f"{TRAY}/he-tray-v2.yaml"
ROUND = f"{TRAY}/round-tray-cplus.yaml"
SEEDS = [100007, 152959]
INDICES = [3, 0]  # the targeted release's export order, not the seeds'


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fake_release(root: Path) -> str:
    """A release the size of its manifest and export: seed -> episode index."""
    (root / "meta").mkdir(parents=True)
    export = {"episodes": [{"episode_index": i, "seed": s} for s, i in zip(SEEDS, INDICES)]}
    export["episodes"] += [{"episode_index": 1, "seed": 100008}]
    (root / EXPORT_META).write_text(json.dumps(export))
    files = [{"path": EXPORT_META, "sha256": _sha(root / EXPORT_META)}]
    release_hash = canonical_sha256(files)
    (root / MANIFEST).write_text(json.dumps({"release_hash": release_hash, "files": files}))
    return release_hash


def frozen_round(tmp_path: Path) -> tuple[Path, Path]:
    """A repo copy whose round plan is frozen on a synthetic targeted set; and the release."""
    repo = tmp_path / "repo"
    v2 = TrayRunPlan.load(REPO / V2)
    for rel in [
        "configs/models/psi0-stage3.yaml",
        "configs/splits/default.yaml",
        f"{TRAY}/demo_sets-v2.json",
        f"{TRAY}/quality-s1-pool-1104.jsonl",
        f"{TRAY}/cplus-conditions.jsonl",
        V2,
        f"{TRAY}/he-tray-v2.lock.json",
        "docs/he/tray.md",
        *(v2.pinned_files or {}),
    ]:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, repo / rel)
    release = tmp_path / "tray_s1_targeted"
    release_hash = fake_release(release)
    sets = DemoSets(
        release_id=release.name,
        release_hash=release_hash,
        salt="DA-34/demo-sets/v1",
        sets={
            "T2": DemoSet(
                n=2,
                set_hash=set_hash(release_hash, SEEDS),
                seeds=SEEDS,
                episode_indices=sorted(INDICES),
            )
        },
    )
    (repo / TRAY / "demo_sets-cplus.json").write_text(sets.model_dump_json(indent=1) + "\n")
    selection = repo / TRAY / "cplus-selection.jsonl"
    selection.write_text(
        "".join(json.dumps({"cluster_id": f"c{s}", "seed": s}) + "\n" for s in SEEDS)
    )
    raw = yaml.safe_load((REPO / ROUND).read_text())
    raw["status"] = "frozen"
    raw["targets"].update(
        n_add=2,
        seeds=SEEDS,
        set_hash=set_hash(release_hash, SEEDS),
        set_name="T2",
        conditions={
            "file": f"{TRAY}/cplus-conditions.jsonl",
            "sha256": _sha(repo / TRAY / "cplus-conditions.jsonl"),
        },
        selection={"file": f"{TRAY}/cplus-selection.jsonl", "sha256": _sha(selection)},
        release={
            "id": release.name,
            "release_hash": release_hash,
            "location": "rtx3060:~/denso-da34-pool/fwdata/releases",
            "data_class": "public",
        },
        demo_sets={
            "file": f"{TRAY}/demo_sets-cplus.json",
            "file_sha256": _sha(repo / TRAY / "demo_sets-cplus.json"),
            "salt": "DA-34/demo-sets/v1",
            "hashes": {"T2": set_hash(release_hash, SEEDS)},
        },
    )
    (repo / ROUND).write_text(yaml.safe_dump(raw, sort_keys=False))
    freeze(repo / ROUND, repo)
    return repo, release


def test_a_round_with_its_targets_freezes_and_checks(tmp_path: Path) -> None:
    repo, release = frozen_round(tmp_path)
    round_plan = TrayRoundPlan.load(repo / ROUND)
    assert check_round(round_plan, repo) == []
    lock = json.loads(lock_path(repo / ROUND).read_text())
    assert lock["run_plan_id"] == run_plan_id(round_plan)
    assert check_targets_release(round_plan.targets, release, repo) == []


def test_a_frozen_round_needs_every_pin(tmp_path: Path) -> None:
    repo, _ = frozen_round(tmp_path)
    raw = yaml.safe_load((repo / ROUND).read_text())
    del raw["targets"]["selection"]
    problems = check_round(TrayRoundPlan.model_validate(raw), repo)
    assert problems == ["a frozen round pins its targets: selection missing"]


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        ("selection", "cplus-selection.jsonl changed since the round was frozen"),
        ("sets", "demo_sets-cplus.json changed since the round was frozen"),
        ("seeds", "targets.set_hash is not the hash of its seeds"),
    ],
)
def test_a_frozen_round_catches_an_edit(tmp_path: Path, edit: str, expected: str) -> None:
    repo, _ = frozen_round(tmp_path)
    if edit == "selection":
        with (repo / TRAY / "cplus-selection.jsonl").open("a") as f:
            f.write(json.dumps({"cluster_id": "x", "seed": 1}) + "\n")
    elif edit == "sets":
        path = repo / TRAY / "demo_sets-cplus.json"
        path.write_text(path.read_text() + " ")
    else:
        raw = yaml.safe_load((repo / ROUND).read_text())
        raw["targets"]["seeds"] = [100007, 152960]
        (repo / ROUND).write_text(yaml.safe_dump(raw, sort_keys=False))
    problems = check_round(TrayRoundPlan.load(repo / ROUND), repo)
    assert any(expected in p for p in problems), problems


def test_the_targeted_release_must_hold_the_set(tmp_path: Path) -> None:
    repo, release = frozen_round(tmp_path)
    targets = TrayRoundPlan.load(repo / ROUND).targets
    other = tmp_path / "other"
    fake_release(other)
    (other / EXPORT_META).write_text("{}")  # a release whose export is not its manifest's
    assert "not the file the manifest lists" in check_targets_release(targets, other, repo)[0]
    export = json.loads((release / EXPORT_META).read_text())
    export["episodes"][0]["episode_index"] = 7
    moved = tmp_path / "moved"
    shutil.copytree(release, moved)
    (moved / EXPORT_META).write_text(json.dumps(export))
    assert check_targets_release(targets, moved, repo)  # another hash or another index


def test_launch_on_a_round_needs_both_releases(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from flywheel_psi0.tray import runplan

    repo, release = frozen_round(tmp_path)
    monkeypatch.setattr(runplan, "REPO", repo)
    assert main(["check", str(repo / ROUND), "--release", str(tmp_path), "--launch"]) == 1
    assert "--launch on a round needs --targets-release" in capsys.readouterr().err


def _write_joined_cut(data: Path, repo: Path, **override: Any) -> None:
    v2 = TrayRunPlan.load(repo / V2)
    c_sets = DemoSets.model_validate_json((repo / v2.demo_sets.file).read_text())
    t_sets = DemoSets.model_validate_json((repo / TRAY / "demo_sets-cplus.json").read_text())
    c, t = c_sets.sets["C"], t_sets.sets["T2"]
    parts = [
        {
            "demo_set": "C",
            "set_hash": c.set_hash,
            "release_id": c_sets.release_id,
            "release_hash": c_sets.release_hash,
            "n": c.n,
            "first_episode_index": 0,
            "episodes": [
                {"episode_index": n, "source_episode_index": o}
                for n, o in enumerate(c.episode_indices)
            ],
        },
        {
            "demo_set": "T2",
            "set_hash": t.set_hash,
            "release_id": t_sets.release_id,
            "release_hash": t_sets.release_hash,
            "n": t.n,
            "first_episode_index": c.n,
            "episodes": [
                {"episode_index": c.n + n, "source_episode_index": o}
                for n, o in enumerate(t.episode_indices)
            ],
        },
    ]
    marker = {"demo_set": "C_PLUS", "n": c.n + t.n, "parts": parts, **override}
    (data / "meta").mkdir(parents=True)
    (data / "meta" / colab_train.MARKER).write_text(json.dumps(marker))
    (data / "meta" / "stats_psi0.json").write_text("{}")
    (data / "meta" / "info.json").write_text(json.dumps({"total_episodes": c.n + t.n}))
    rows = "".join(json.dumps({"episode_index": i}) + "\n" for i in range(c.n + t.n))
    (data / "meta" / "episodes.jsonl").write_text(rows)


def test_the_vm_trains_c_plus_only_on_the_approved_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _ = frozen_round(tmp_path)
    round_id = json.loads(lock_path(repo / ROUND).read_text())["run_plan_id"]
    with pytest.raises(SystemExit, match=f"holds {round_id}; the C\\+ Decision approved rp_"):
        colab_train.load_round(repo)
    monkeypatch.setattr(colab_train, "CPLUS_FROZEN", round_id)
    plan, round_plan, run_plan = colab_train.load_round(repo)
    assert run_plan == round_id and round_plan.targets.set_name == "T2"

    data = tmp_path / "cut"
    _write_joined_cut(data, repo)
    assert colab_train.cplus_cut_problems(data, plan, round_plan, repo) == []


def test_a_joined_cut_of_other_parts_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _ = frozen_round(tmp_path)
    monkeypatch.setattr(
        colab_train, "CPLUS_FROZEN", json.loads(lock_path(repo / ROUND).read_text())["run_plan_id"]
    )
    plan, round_plan, _ = colab_train.load_round(repo)
    data = tmp_path / "cut"
    _write_joined_cut(data, repo)
    marker_path = data / "meta" / colab_train.MARKER
    marker = json.loads(marker_path.read_text())
    marker["parts"].reverse()  # targeted first: not C's episodes at C's indices
    marker_path.write_text(json.dumps(marker))
    problems = colab_train.cplus_cut_problems(data, plan, round_plan, repo)
    assert any(p.startswith("part C: demo_set is 'T2'") for p in problems)
    marker["parts"] = marker["parts"][:1]
    marker_path.write_text(json.dumps(marker))
    assert any(
        "has 1 parts" in p for p in colab_train.cplus_cut_problems(data, plan, round_plan, repo)
    )


def test_a_draft_round_does_not_train() -> None:
    with pytest.raises(SystemExit, match="round-tray-cplus.yaml is not frozen"):
        colab_train.load_round(REPO)

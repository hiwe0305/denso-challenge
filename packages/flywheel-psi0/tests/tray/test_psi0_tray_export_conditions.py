"""Tray conditions as contract `Condition` records (DA-43 K1)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.contracts.entities import Condition
from flywheel_psi0.tray.export_conditions import (
    COMPONENTS,
    build,
    default_sim,
    main,
    release_items,
)
from flywheel_psi0.tray.pairplan import TrayPairPlan, seeds_sha256
from flywheel_psi0.tray.runplan import REPO

TASK_VIEW = REPO / "configs/eval/agentqa/tasks/tray.yaml"
PAIR_PLAN = REPO / "configs/runplans/tray/he-tray-pair60k.yaml"


def coverage() -> dict[str, Any]:
    block: dict[str, Any] = yaml.safe_load(TASK_VIEW.read_text())["coverage"]
    return block


def eval_set(tmp_path: Path) -> Path:
    folder = tmp_path / "rp_test-abc"
    folder.mkdir()
    rows = [{"level": lv, "seed": 1000100 + i} for lv in (1, 2) for i in range(12)]
    (folder / "conditions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return folder


def release(tmp_path: Path, name: str, pairs: list[tuple[int, int]],
            tamper: bool = False) -> Path:
    sample_of, _ = default_sim()
    folder = tmp_path / name
    (folder / "meta").mkdir(parents=True)
    rows = []
    for i, (level, seed) in enumerate(pairs):
        sample = dataclasses.asdict(sample_of(level, seed))
        if tamper and i == 0:
            sample["table_gap"] += 0.01
        config = {"tray": {"sample": sample}, "flywheel": {"seed": seed, "level": level}}
        rows.append({"episode_index": i, "length": 10, "environment_config": json.dumps(config)})
    (folder / "meta/episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return folder


def test_values_are_the_names_the_task_view_reads() -> None:
    names = [c["name"] for c in coverage()["components"]]
    assert sorted(COMPONENTS) == sorted(names)
    for listed in coverage()["level_components"].values():
        assert set(listed) <= set(COMPONENTS)


def test_eval_set_conditions_of_the_first_chunks(tmp_path: Path) -> None:
    out = tmp_path / "eval.jsonl"
    assert main(["--set", str(eval_set(tmp_path)), "--max-chunks", "2", "--conditions",
                 str(out)]) == 0
    conditions = [Condition.model_validate_json(x) for x in out.read_text().splitlines()]
    # chunk order interleaves the levels: l1-000, l2-000
    assert [(c.level, c.condition_seed) for c in conditions] == (
        [(1, 1000100 + i) for i in range(10)] + [(2, 1000100 + i) for i in range(10)])
    c = conditions[0]
    assert sorted(c.values) == sorted(COMPONENTS)
    assert c.vector == [c.values[n] for n in COMPONENTS]
    assert (c.split, c.origin, c.set_id, c.task_id) == ("dev", "generated", "rp_test-abc", "tray")
    assert c.meta == {"role": "eval"}
    level2 = conditions[10]
    assert level2.values["table_gap"] != 1.8 or level2.values["part_mass"] != 0.05


def test_layout_hash_ignores_level_and_seed() -> None:
    sample_of, split_of = default_sim()
    conditions, _ = build([(0, 1000100, "s", {}, None), (0, 1000101, "s", {}, None),
                           (1, 1000100, "s", {}, None)], sample_of, split_of)
    level0a, level0b, level1 = conditions
    assert level0a.layout_hash == level0b.layout_hash != level1.layout_hash


def test_release_duplicates_are_written_once_and_counted(tmp_path: Path) -> None:
    a = release(tmp_path, "rel_a", [(1, 1000), (1, 1001)])
    b = release(tmp_path, "rel_b", [(1, 1001), (2, 1002)])
    sample_of, split_of = default_sim()
    conditions, duplicates = build(release_items([a, b]), sample_of, split_of)
    assert duplicates == 1
    assert [(c.level, c.condition_seed, c.set_id) for c in conditions] == [
        (1, 1000, "rel_a"), (1, 1001, "rel_a"), (2, 1002, "rel_b")]
    assert all(c.split == "train" and c.meta["role"] == "train" for c in conditions)


def test_a_recorded_sample_off_the_rebuilt_one_is_refused(tmp_path: Path) -> None:
    rel = release(tmp_path, "rel", [(2, 1000)], tamper=True)
    out = tmp_path / "train.jsonl"
    assert main(["--release", str(rel), "--conditions", str(out)]) == 1
    assert not out.exists()


def test_a_holdout_seed_is_refused() -> None:
    sample_of, split_of = default_sim()
    with pytest.raises(ValueError, match="holdout"):
        build([(1, 2_000_000, "s", {}, None)], sample_of, split_of)


def test_the_plan_cut_selects_the_runs_episodes(tmp_path: Path) -> None:
    plan = TrayPairPlan.load(PAIR_PLAN)
    part = plan.cut.parts[0]
    assert part.release is not None and part.demo_sets is not None
    sets = json.loads((REPO / part.demo_sets.file).read_text())
    seeds = sorted(sets["sets"]["ALL"]["seeds"])
    rel = release(tmp_path, part.release.id, [(1, s) for s in [*seeds, 999_999]])
    files = {}
    for cut in ("ALL", "S70"):
        files[cut] = tmp_path / f"{cut}.jsonl"
        assert main(["--release", str(rel), "--plan", str(PAIR_PLAN), "--cut", cut,
                     "--conditions", str(files[cut])]) == 0
    all_seeds = [Condition.model_validate_json(x).condition_seed
                 for x in files["ALL"].read_text().splitlines()]
    s70 = [Condition.model_validate_json(x).condition_seed
           for x in files["S70"].read_text().splitlines()]
    assert sorted(all_seeds) == seeds  # the release's extra episode is not in the cut
    pin = plan.subset("S70").parts[0]  # type: ignore[union-attr]
    assert len(s70) == pin.episodes and seeds_sha256(s70) == pin.seeds_sha256


def test_same_input_same_bytes(tmp_path: Path) -> None:
    folder = eval_set(tmp_path)
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    for f in (a, b):
        assert main(["--set", str(folder), "--conditions", str(f)]) == 0
    assert a.read_bytes() == b.read_bytes()

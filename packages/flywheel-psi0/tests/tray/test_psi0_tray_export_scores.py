"""A tray eval batch as `Score` records (DA-43 task 1.2)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from flywheel.contracts.entities import Score
from flywheel_psi0.tray.eval_batch import Chunk
from flywheel_psi0.tray.export_scores import export, main, step_status

L1 = Chunk("l1-000", 1, 0, (1000100, 1000101, 1000102))


def rollout(out: Path, i: int, success: bool, flags: list[bool] | None, failure: str | None,
            trace: bool = True) -> None:
    folder = out / L1.id / "attempt-0"
    (folder / "eval").mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {"seed": L1.seed_of(i), "level": 1, "success": success,
                           "failure": failure}
    if flags is not None:
        row["scorer_steps"] = flags
    with (folder / "outcomes.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")
    with (folder / "eval/eval_stats.txt").open("a") as f:
        f.write(f"episode_{i}: {success} \n")
    if trace:
        steps = folder / "traces" / f"t{i}" / "steps.jsonl"
        steps.parent.mkdir(parents=True)
        (steps.parent / "rollout_result.json").write_text("{}")
        steps.write_text(json.dumps({"episode_id": f"episode_{i}", "step": 0}) + "\n")


def eval_set(tmp_path: Path) -> Path:
    folder = tmp_path / "set"
    folder.mkdir()
    rows = [{"level": 1, "seed": s} for s in L1.seeds]
    (folder / "conditions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return folder


def config(tmp_path: Path) -> Path:
    path = tmp_path / "tray.yaml"
    path.write_text("r_reach: 0.10\n")
    return path


def test_steps_after_the_first_unlatched_one_were_never_judged() -> None:
    assert step_status([True, True, False, False, False, False, False]) == (
        ["pass", "pass", "fail"] + ["not_attempted"] * 4, None)
    status, _ = step_status([False, True] + [False] * 5)
    assert status[:3] == ["fail", "pass", "not_attempted"]  # a later latch is kept, not hidden
    status, reasons = step_status(None)
    assert status == ["unknown"] * 7 and reasons == ["no_verdict"] * 7


def test_export_writes_one_score_per_rollout(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    rollout(out, 0, False, [True] * 5 + [False] * 2, "L-PLACE-POSE")
    rollout(out, 1, True, [False] * 7, None)  # tray.md 20.11 H1: a success, no step latched
    rollout(out, 2, True, [True] * 7, None)
    scores = export(eval_set(tmp_path), out, "C_70", scorer_config=config(tmp_path))
    by_id = {s.episode_id: s for s in scores}
    assert sorted(by_id) == ["C_70/l1-s1000100", "C_70/l1-s1000101", "C_70/l1-s1000102"]
    place = by_id["C_70/l1-s1000100"]
    assert (place.success, place.first_failed_step, place.failure_kind, place.level) == (
        False, 5, "L-PLACE-POSE", 1)
    h1 = by_id["C_70/l1-s1000101"]
    assert h1.success is True and h1.first_failed_step == 0 and h1.failure_kind is None
    assert by_id["C_70/l1-s1000102"].first_failed_step is None
    assert place.config_sha256 == hashlib.sha256(b"r_reach: 0.10\n").hexdigest()
    assert all(s.task_id == "tray" for s in scores)


def test_a_rollout_without_a_trace_is_refused(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    for i in range(3):
        rollout(out, i, True, [True] * 7, None, trace=i != 1)
    scores_file = tmp_path / "scores.jsonl"
    code = main(["--set", str(eval_set(tmp_path)), "--out", str(out), "--run", "C_70",
                 "--scores", str(scores_file), "--scorer-config", str(config(tmp_path))])
    assert code == 1 and not scores_file.exists()


def test_main_writes_valid_score_lines(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    for i in range(3):
        rollout(out, i, False, [True, False] + [False] * 5, "L-TIMEOUT")
    scores_file = tmp_path / "scores.jsonl"
    assert main(["--set", str(eval_set(tmp_path)), "--out", str(out), "--run", "B_70",
                 "--scores", str(scores_file), "--scorer-config", str(config(tmp_path))]) == 0
    lines = scores_file.read_text().splitlines()
    assert len(lines) == 3
    assert all(Score.model_validate_json(line).first_failed_step == 1 for line in lines)

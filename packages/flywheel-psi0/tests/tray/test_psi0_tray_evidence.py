"""Evidence pack of the paired 60k plan (docs/he/tray.md 19.6): one command, any state."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel_psi0.tray.eval_batch import Chunk, chunk_plan
from flywheel_psi0.tray.eval_results import Rollout
from flywheel_psi0.tray.evidence import Inputs, build, parse_pairs, pick_videos
from flywheel_psi0.tray.pairplan import TrayPairPlan
from flywheel_psi0.tray.runplan import run_plan_id

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "configs/runplans/tray/he-tray-pair60k.yaml"
TARGET = (1.0, 0.0, 0.0)  # every condition's target pose (x, y, yaw) in these tests


def chunks_of(tmp_path: Path) -> list[Chunk]:
    rows = [
        {"level": lv, "seed": 1000100 + i}
        for lv, n in ((0, 30), (1, 120), (2, 120))
        for i in range(n)
    ]
    (tmp_path / "set").mkdir(exist_ok=True)
    (tmp_path / "set/conditions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return chunk_plan(rows, 10)


def rollout(
    out: Path, chunk: Chunk, i: int, success: bool, failure: str = "L-TIMEOUT", off: float = 0.3
) -> None:
    """One finished episode; a failure ends `off` m from the target, yaw on target."""
    folder = out / chunk.id / "attempt-0"
    (folder / "eval").mkdir(parents=True, exist_ok=True)
    row = {
        "seed": chunk.seed_of(i),
        "level": chunk.level,
        "success": success,
        "failure": None if success else failure,
        "scorer_steps": [k < (7 if success else 5) for k in range(7)],
        "tray_pos": [TARGET[0] + (0.0 if success else off), 0.0, 0.8],
        "tray_quat": [1.0, 0.0, 0.0, 0.0],
    }
    with (folder / "outcomes.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")
    with (folder / "eval/eval_stats.txt").open("a") as f:
        f.write(f"episode_{i}: {success} \n")


def run(out: Path, chunks: list[Chunk], wins_per_chunk: int, place_pose: int = 0) -> None:
    """Stage 1 of a run: per chunk, the first episodes win, the next fail as L-PLACE-POSE."""
    for chunk in chunks[:6]:
        for i in range(10):
            win = i < wins_per_chunk
            pose = not win and i < wins_per_chunk + place_pose
            rollout(out, chunk, chunk.start + i, win, "L-PLACE-POSE" if pose else "L-TIMEOUT", 0.08)


def target_of(level: int, seed: int) -> tuple[float, float, float]:
    return TARGET


def test_an_empty_pack_names_what_is_missing(tmp_path: Path) -> None:
    chunks_of(tmp_path)
    pack = build(Inputs(PLAN, tmp_path / "set"), tmp_path / "pack")
    assert pack["provenance"]["run_plan_id"] == run_plan_id(TrayPairPlan.load(PLAN))
    assert [(r["step"], r["pending"]) for r in pack["reads"]] == [
        (40000, "chưa có eval nào"),
        (60000, "chưa có eval nào"),
    ]
    readme = (tmp_path / "pack/README.md").read_text()
    assert "Chưa có: chưa có eval nào" in readme and "chưa đóng băng" in readme
    assert "Chưa có `metrics.jsonl`" in readme and "Chưa có video." in readme
    assert json.loads((tmp_path / "pack/evidence.json").read_text())["lock"] is False


def test_stage1_of_the_primary_checkpoint_gives_the_outcome_and_rule_b(tmp_path: Path) -> None:
    chunks = chunks_of(tmp_path)
    run(tmp_path / "b60", chunks, wins_per_chunk=8, place_pose=1)  # 48/60
    run(tmp_path / "c60", chunks, wins_per_chunk=1)  # 6/60
    evals = {("B_ALL", 60000): tmp_path / "b60", ("C_ALL", 60000): tmp_path / "c60"}
    pack = build(Inputs(PLAN, tmp_path / "set", evals), tmp_path / "pack", target_of, (0.05, 10.0))
    read = pack["reads"][1]
    assert (read["step"], read["role"], read["stage"]) == (60000, "primary", "stage1")
    b, c = read["by_run"]["B_ALL"], read["by_run"]["C_ALL"]
    assert (b["successes"], b["n"], c["successes"]) == (48, 60, 6)
    assert b["goal"] == "chưa rõ" and c["goal"] == "chưa đạt"  # Wilson 0.68-0.88 holds 0.80
    assert read["paired"]["variant_only"] == 42 and read["stage1_outcome"] == "E1"
    # rule (c): the 6 L-PLACE-POSE of B end 8 cm off, relaxed from 10 cm on; others never
    assert [p["relaxed_successes"] for p in b["relaxed"]] == [48, 48, 54, 54, 54]
    assert [p["relaxed_successes"] for p in c["relaxed"]] == [6] * 5
    readme = (tmp_path / "pack/README.md").read_text()
    assert "Kết quả giai đoạn 1: **E1**" in readme and "Thành công **nới**" in readme
    assert "Checkpoint 60000 (số chính)" in readme


def test_the_early_read_is_labelled_and_gives_no_outcome(tmp_path: Path) -> None:
    chunks = chunks_of(tmp_path)
    run(tmp_path / "b40", chunks, wins_per_chunk=8)
    run(tmp_path / "c40", chunks, wins_per_chunk=0)
    evals = {("B_ALL", 40000): tmp_path / "b40", ("C_ALL", 40000): tmp_path / "c40"}
    pack = build(Inputs(PLAN, tmp_path / "set", evals), tmp_path / "pack")
    early = pack["reads"][0]
    assert (early["role"], early["label"]) == ("early", "đọc sớm, 40k")
    assert "paired" in early and "stage1_outcome" not in early and "rule" not in early
    readme = (tmp_path / "pack/README.md").read_text()
    assert "Checkpoint 40000 (đọc sớm, 40k)" in readme
    assert "Đọc sớm: không cho E1, E3, F hay đi tiếp" in readme
    assert pack["reads"][1]["pending"] == "chưa có eval nào"


def test_an_unfinished_stage_1_is_not_read(tmp_path: Path) -> None:
    chunks = chunks_of(tmp_path)
    run(tmp_path / "b60", chunks, wins_per_chunk=5)
    for chunk in chunks[:3]:
        for i in range(10):
            rollout(tmp_path / "c60", chunk, chunk.start + i, success=False)
    evals = {("B_ALL", 60000): tmp_path / "b60", ("C_ALL", 60000): tmp_path / "c60"}
    read = build(Inputs(PLAN, tmp_path / "set", evals), tmp_path / "pack")["reads"][1]
    assert read["stage"] == "incomplete" and read["done_stage1"] == {"B_ALL": 60, "C_ALL": 30}
    assert "by_run" not in read and "paired" not in read


def test_one_run_alone_is_described_not_paired(tmp_path: Path) -> None:
    chunks = chunks_of(tmp_path)
    run(tmp_path / "b60", chunks, wins_per_chunk=5)
    evals = {("B_ALL", 60000): tmp_path / "b60"}
    read = build(Inputs(PLAN, tmp_path / "set", evals), tmp_path / "pack")["reads"][1]
    assert read["pending"] == "chưa có eval của C_ALL"
    assert read["by_run"]["B_ALL"]["successes"] == 30 and "paired" not in read


def test_videos_loss_and_ledger(tmp_path: Path) -> None:
    chunks = chunks_of(tmp_path)
    run(tmp_path / "b60", chunks, wins_per_chunk=5)
    first = chunks[0]
    for i, outcome in ((first.start, "success"), (first.start + 5, "failed")):
        video = (
            tmp_path / "b60" / first.id / "attempt-0/data/evals/psi0_decoupled_wbc/ckpt.env"
            / f"dr-level-{first.level}/episode_{i}/head_stereo_left_{outcome}.mp4"
        )  # fmt: skip
        video.parent.mkdir(parents=True)
        video.write_bytes(b"mp4")
    job = tmp_path / "job-b"
    job.mkdir()
    lines = [{"step": s, "split": "train", "loss": 1.0 / s} for s in range(1, 1001)]
    lines += [{"step": 1000, "split": "val", "loss": 0.5}]
    (job / "metrics.jsonl").write_text("".join(json.dumps(r) + "\n" for r in lines))
    (job / "result.json").write_text(json.dumps({"checkpoint_step": 60000}))
    inputs = Inputs(
        PLAN, tmp_path / "set", {("B_ALL", 60000): tmp_path / "b60"}, {"B_ALL": job}, videos=1
    )
    pack = build(inputs, tmp_path / "pack")
    assert pack["videos"]["B_ALL@60000"] == [
        f"videos/B_ALL-60000/l1-{first.seeds[0]}-success.mp4",
        f"videos/B_ALL-60000/l1-{first.seeds[5]}-L-TIMEOUT.mp4",
    ]
    assert (tmp_path / "pack/videos/B_ALL-60000").is_dir()
    assert pack["loss"] == {"B_ALL": {"train": 2, "val": 1}}
    assert (tmp_path / "pack/loss.svg").read_text().startswith("<svg")
    assert pack["provenance"]["jobs"]["B_ALL"]["checkpoint_step"] == 60000
    assert {r["job"] for r in pack["ledger"]} >= {"job_da34_ft_B_ALL", "job_da34_ft_C_ALL"}


def test_pick_videos_shows_each_failure_label_first() -> None:
    def r(i: int, success: bool, failure: str | None) -> Rollout:
        return Rollout(1, i, i, "l1-000", 0, {"success": success, "failure": failure})

    rollouts = [r(0, False, "A"), r(1, False, "A"), r(2, False, "B"), r(3, True, None)]
    assert [x.seed for x in pick_videos(rollouts, 2)] == [3, 0, 2]


def test_steps_and_branches_outside_the_plan_are_refused(tmp_path: Path) -> None:
    chunks_of(tmp_path)
    with pytest.raises(ValueError, match="not read by the plan"):
        build(Inputs(PLAN, tmp_path / "set", {("B_ALL", 50000): tmp_path}), tmp_path / "p")
    with pytest.raises(ValueError, match="not branches"):
        build(Inputs(PLAN, tmp_path / "set", {("B", 60000): tmp_path}), tmp_path / "p")
    assert parse_pairs(["B_ALL@60000=/x"], keyed=True) == {("B_ALL", 60000): Path("/x")}
    with pytest.raises(ValueError, match="BRANCH@STEP"):
        parse_pairs(["B_ALL=/x"], keyed=True)


def test_once_all_chunks_ran_a_stopped_stage_1_stays_the_verdict(tmp_path: Path) -> None:
    chunks = chunks_of(tmp_path)
    for k, chunk in enumerate(chunks):
        for i in range(len(chunk.seeds)):
            # stage 1: equal (F); the rest: B wins every condition, C none
            later = k >= 6 and chunk.level > 0
            rollout(tmp_path / "b", chunk, chunk.start + i, success=later)
            rollout(tmp_path / "c", chunk, chunk.start + i, success=False)
    evals = {("B_ALL", 60000): tmp_path / "b", ("C_ALL", 60000): tmp_path / "c"}
    read = build(Inputs(PLAN, tmp_path / "set", evals), tmp_path / "pack")["reads"][1]
    assert (read["stage"], read["stage1_outcome"]) == ("full", "F")
    assert read["paired"]["n"] == 240 and read["paired"]["ci_vs_0"] == "above"
    assert read["rule_descriptive"] == 1 and "rule" not in read
    assert "chỉ để mô tả" in (tmp_path / "pack/README.md").read_text()

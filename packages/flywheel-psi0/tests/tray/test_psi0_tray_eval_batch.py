"""Chunk order, finished episodes, reruns and resume of the eval batch, on CPU (DA-34 task 3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from flywheel_psi0.tray.eval_batch import (
    Chunk,
    chunk_plan,
    finished,
    missing,
    phases_for,
    run_batch,
    with_repeats,
)


def rows(counts: dict[int, int]) -> list[dict[str, Any]]:
    """Condition rows in plan order: level 0 first, seeds from 1000100."""
    return [
        {"level": level, "seed": 1000100 + i}
        for level in sorted(counts)
        for i in range(counts[level])
    ]


def test_levels_1_and_2_interleave_before_level_0() -> None:
    plan = chunk_plan(rows({0: 30, 1: 120, 2: 120}), 10)
    assert len(plan) == 27 and sum(len(c.seeds) for c in plan) == 270
    assert [c.id for c in plan[:4]] == ["l1-000", "l2-000", "l1-010", "l2-010"]
    assert [c.id for c in plan[-3:]] == ["l0-000", "l0-010", "l0-020"]
    assert plan[2].seeds == tuple(range(1000110, 1000120)) and plan[2].start == 10


def test_a_short_last_chunk_and_unequal_levels() -> None:
    plan = chunk_plan(rows({0: 3, 1: 25, 2: 10}), 10)
    assert [(c.id, len(c.seeds)) for c in plan] == [
        ("l1-000", 10),
        ("l2-000", 10),
        ("l1-010", 10),
        ("l1-020", 5),
        ("l0-000", 3),
    ]


def test_a_level_outside_the_phases_is_refused() -> None:
    with pytest.raises(ValueError, match="levels"):
        chunk_plan(rows({0: 3, 1: 3, 3: 3}), 10)


def write_episode(attempt: Path, chunk: Chunk, episode: int, stats: bool = True) -> None:
    attempt.mkdir(parents=True, exist_ok=True)
    (attempt / "eval").mkdir(exist_ok=True)
    row = {"seed": chunk.seed_of(episode), "level": chunk.level, "success": False}
    with (attempt / "outcomes.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")
    if stats:
        with (attempt / "eval/eval_stats.txt").open("a") as f:
            f.write(f"episode_{episode}: False \n")


CHUNK = Chunk("l1-010", 1, 10, tuple(range(1000110, 1000114)))


def test_an_episode_is_finished_with_both_its_stats_line_and_its_outcome(tmp_path: Path) -> None:
    attempt = tmp_path / "attempt-0"
    write_episode(attempt, CHUNK, 10)
    write_episode(attempt, CHUNK, 11, stats=False)  # cut short: logged on close, no stats line
    assert sorted(finished(CHUNK, attempt)) == [10]


def test_an_outcome_of_another_condition_is_an_error(tmp_path: Path) -> None:
    attempt = tmp_path / "attempt-0"
    write_episode(attempt, Chunk("l2-010", 2, 10, CHUNK.seeds), 10)
    with pytest.raises(ValueError, match="level 2"):
        finished(CHUNK, attempt)


def test_a_crash_reruns_from_the_first_missing_episode(tmp_path: Path) -> None:
    calls: list[tuple[str, int, int, str]] = []

    def launch(chunk: Chunk, start: int, n: int, attempt: Path) -> int:
        calls.append((chunk.id, start, n, attempt.name))
        last = start + n if attempt.name != "attempt-0" else start + 2  # first attempt crashes
        for episode in range(start, last):
            write_episode(attempt, chunk, episode)
        return 0 if last == start + n else 139

    assert run_batch(tmp_path, [CHUNK], launch, log=lambda _: None) == 0
    assert calls == [("l1-010", 10, 4, "attempt-0"), ("l1-010", 12, 2, "attempt-1")]
    runs = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text().splitlines()]
    assert [(r["exit"], r["finished"], r["missing"]) for r in runs] == [
        (139, [10, 11], [12, 13]),
        (0, [12, 13], []),
    ]
    assert runs[1]["seeds"] == [1000112, 1000113]
    assert missing(tmp_path, CHUNK) == []
    assert run_batch(tmp_path, [CHUNK], launch, log=lambda _: None) == 0  # resume: nothing left
    assert len(calls) == 2


def test_the_batch_stops_when_a_chunk_keeps_failing(tmp_path: Path) -> None:
    later = Chunk("l2-010", 2, 10, CHUNK.seeds)
    seen = []

    def launch(chunk: Chunk, start: int, n: int, attempt: Path) -> int:
        seen.append(chunk.id)
        attempt.mkdir(parents=True)
        return 1

    assert run_batch(tmp_path, [CHUNK, later], launch, max_attempts=2, log=lambda _: None) == 1
    assert seen == ["l1-010", "l1-010"]


def test_phases_are_cut_to_the_levels_of_a_smaller_set() -> None:
    assert phases_for([{"level": 1}, {"level": 1}]) == ((1,),)
    assert phases_for([{"level": 0}, {"level": 2}]) == ((2,), (0,))
    with pytest.raises(ValueError):
        phases_for([{"level": 3}])


def test_max_chunks_runs_the_first_chunks_of_the_order_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # branch B's stage 1 (tray.md 18.2): the first 6 chunks, 30 level 1 and 30 level 2
    from flywheel_psi0.tray import eval_batch
    from flywheel_psi0.tray.eval_set import conditions_sha256

    conditions = [
        row | {"environment_config": {"flywheel": {"run_plan_id": "rp_a04c14e79dfd"}}}
        for row in rows({0: 30, 1: 120, 2: 120})
    ]
    (tmp_path / "conditions.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in conditions)
    )
    common = [
        "--set", str(tmp_path), "--conditions-sha256", conditions_sha256(conditions),
        "--out", str(tmp_path / "out"), "--simple-python", "python", "--pythonpath", "x",
        "--dry-run",
    ]  # fmt: skip
    assert eval_batch.main([*common, "--max-chunks", "6"]) == 0
    printed = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in printed] == [
        "l1-000", "l2-000", "l1-010", "l2-010", "l1-020", "l2-020",
    ]  # fmt: skip
    assert {line.split()[1] for line in printed} == {"1000100", "1000110", "1000120"}
    assert eval_batch.main(common) == 0
    assert len(capsys.readouterr().out.splitlines()) == 27  # without it: the whole order
    with pytest.raises(SystemExit):
        eval_batch.main([*common, "--max-chunks", "0"])


def test_chunks_splits_stage_1_into_lanes_that_share_one_out_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # tray.md 20.15: stage 1 of C70_R1 on three serve lanes, two chunks each
    from flywheel_psi0.tray import eval_batch
    from flywheel_psi0.tray.eval_set import conditions_sha256

    conditions = [
        row | {"environment_config": {"flywheel": {"run_plan_id": "rp_a04c14e79dfd"}}}
        for row in rows({0: 30, 1: 120, 2: 120})
    ]
    (tmp_path / "conditions.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in conditions)
    )
    common = [
        "--set", str(tmp_path), "--conditions-sha256", conditions_sha256(conditions),
        "--out", str(tmp_path / "out"), "--simple-python", "python", "--pythonpath", "x",
        "--dry-run", "--max-chunks", "6",
    ]  # fmt: skip
    lanes = []
    for lane in ("l2-000,l1-000", "l1-010,l2-010", "l1-020,l2-020"):
        assert eval_batch.main([*common, "--chunks", lane]) == 0
        lanes.append([line.split()[0] for line in capsys.readouterr().out.splitlines()])
    assert lanes[0] == ["l1-000", "l2-000"]  # the plan's order, not the flag's
    assert sorted(c for lane in lanes for c in lane) == sorted(
        ["l1-000", "l2-000", "l1-010", "l2-010", "l1-020", "l2-020"]
    )
    with pytest.raises(SystemExit):
        eval_batch.main([*common, "--chunks", "l1-030"])  # past --max-chunks: not stage 1
    with pytest.raises(SystemExit):
        eval_batch.main([*common, "--chunks", "l1-000,l1-000"])


# --- DA-42 4.1: repeats ------------------------------------------------------------


def test_repeats_follow_their_chunk_and_one_repeat_is_the_old_order() -> None:
    plan = chunk_plan(rows({1: 20, 2: 10}), 10, phases_for(rows({1: 20, 2: 10})))
    assert with_repeats(plan, 1) == plan
    assert [c.dir_id for c in plan] == [c.id for c in plan]  # repeat 0: the old directories
    assert [c.dir_id for c in with_repeats(plan, 3)] == [
        "l1-000", "l1-000.r1", "l1-000.r2", "l2-000", "l2-000.r1", "l2-000.r2",
        "l1-010", "l1-010.r1", "l1-010.r2",
    ]  # fmt: skip
    assert {c.seeds for c in with_repeats(plan, 3) if c.id == "l1-000"} == {plan[0].seeds}
    with pytest.raises(ValueError):
        with_repeats(plan, 0)


def test_each_repeat_runs_and_resumes_in_its_own_directory(tmp_path: Path) -> None:
    calls: list[tuple[str, int]] = []

    def launch(chunk: Chunk, start: int, n: int, attempt: Path) -> int:
        calls.append((chunk.dir_id, chunk.repeat))
        for episode in range(start, start + n):
            write_episode(attempt, chunk, episode)
        return 0

    chunks = with_repeats([CHUNK], 2)
    assert run_batch(tmp_path, chunks, launch, log=lambda _: None) == 0
    assert calls == [("l1-010", 0), ("l1-010.r1", 1)]
    assert (tmp_path / "l1-010/attempt-0").is_dir() and (tmp_path / "l1-010.r1/attempt-0").is_dir()
    runs = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text().splitlines()]
    assert [(r["chunk"], r["repeat"]) for r in runs] == [("l1-010", 0), ("l1-010", 1)]
    assert run_batch(tmp_path, chunks, launch, log=lambda _: None) == 0  # resume: nothing left
    assert len(calls) == 2


def test_repeats_on_the_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from flywheel_psi0.tray import eval_batch
    from flywheel_psi0.tray.eval_set import conditions_sha256

    conditions = [
        row | {"environment_config": {"flywheel": {"run_plan_id": "rp_a04c14e79dfd"}}}
        for row in rows({1: 20, 2: 20})
    ]
    (tmp_path / "conditions.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in conditions)
    )
    common = [
        "--set", str(tmp_path), "--conditions-sha256", conditions_sha256(conditions),
        "--out", str(tmp_path / "out"), "--simple-python", "python", "--pythonpath", "x",
        "--dry-run", "--max-chunks", "2",
    ]  # fmt: skip
    assert eval_batch.main([*common, "--repeats", "2"]) == 0
    printed = [line.split()[0] for line in capsys.readouterr().out.splitlines()]
    assert printed == ["l1-000", "l1-000.r1", "l2-000", "l2-000.r1"]
    assert eval_batch.main([*common, "--chunks", "l2-000", "--repeats", "2"]) == 0
    assert [line.split()[0] for line in capsys.readouterr().out.splitlines()] == [
        "l2-000",
        "l2-000.r1",
    ]
    with pytest.raises(SystemExit):
        eval_batch.main([*common, "--repeats", "0"])


# --- DA-47 2.2: scene ----------------------------------------------------------------

ZONE1_COMMAND = [
    "py/simple", "-m", "flywheel_psi0.tray.eval_driver",
    "simple/G1WholebodyTrayTransferTeleop-v0", "psi0_decoupled_wbc",
    "--host", "127.0.0.1", "--port", "22186", "--data-format", "lerobot",
    "--data-dir", "SET/dr-level-1", "--sim-mode", "mujoco", "--headless",
    "--num-episodes", "4", "--episode-start", "10", "--eval-dir", "ATTEMPT/eval",
]  # fmt: skip  # the command before DA-47, with SET and ATTEMPT for the paths
OLD_RUN_KEYS = [
    "chunk", "repeat", "level", "attempt", "start", "n", "seeds", "began", "wall_s", "exit",
    "finished", "missing",
]  # fmt: skip


def captured_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **setup: Any
) -> tuple[list[list[str]], list[dict[str, Any]]]:
    """Runs CHUNK through the real launcher with subprocess stubbed: client commands, runs rows."""
    from flywheel_psi0.tray import eval_batch

    commands: list[list[str]] = []

    class Proxy:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def terminate(self) -> None:
            pass

        def wait(self, timeout: float) -> int:
            return 0

    def run(command: list[str], cwd: Path, **kwargs: Any) -> Any:
        commands.append(command)
        for episode in range(10, 14):
            write_episode(cwd, CHUNK, episode)
        return type("Done", (), {"returncode": 0})()

    monkeypatch.setattr(eval_batch, "TIME_V", tmp_path / "no-time")
    monkeypatch.setattr(eval_batch, "wait_for_port", lambda port: None)
    monkeypatch.setattr(eval_batch.subprocess, "Popen", Proxy)
    monkeypatch.setattr(eval_batch.subprocess, "run", run)
    scene = setup.pop("scene", None)
    base = eval_batch.Setup(
        set_dir=Path("SET"),
        server="127.0.0.1:22185",
        listen=22186,
        simple_python=Path("py/simple"),
        proxy_python=Path("py/proxy"),
        pythonpath="x",
        run_plan_id="rp_x",
        **setup,
    )
    kwargs = {} if scene is None else {"scene": scene}
    out = tmp_path / "out"
    assert run_batch(out, [CHUNK], eval_batch.launcher(base), log=lambda _: None, **kwargs) == 0
    attempt = str(out / "l1-010/attempt-0")
    paths = [[a.replace(attempt, "ATTEMPT") for a in c] for c in commands]
    runs = [json.loads(line) for line in (out / "runs.jsonl").read_text().splitlines()]
    return paths, runs


def test_zone1_is_the_command_and_runs_rows_of_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands, runs = captured_commands(tmp_path, monkeypatch)
    assert commands == [ZONE1_COMMAND]
    assert list(runs[0]) == OLD_RUN_KEYS


def test_jig2_runs_the_jig_env_and_records_its_scene(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from flywheel_psi0.tray.eval_batch import SCENES

    commands, runs = captured_commands(tmp_path, monkeypatch, env_id=SCENES["jig2"], scene="jig2")
    jig = [*ZONE1_COMMAND]
    jig[3] = "simple/G1WholebodyTrayTransferJigTeleop-v0"
    assert commands == [jig]
    assert list(runs[0]) == [*OLD_RUN_KEYS, "scene"] and runs[0]["scene"] == "jig2"


def scene_set(tmp_path: Path, scene: str | None) -> list[str]:
    """A 20 + 20 condition set of `scene` (None: no recorded scene), dry-run arguments."""
    from flywheel_psi0.tray.eval_set import conditions_sha256

    flywheel: dict[str, Any] = {"run_plan_id": "rp_a410d01efa62"}
    if scene is not None:
        flywheel["scene"] = scene
    tmp_path.mkdir()
    conditions = [
        row | {"environment_config": {"flywheel": flywheel}} for row in rows({1: 20, 2: 20})
    ]
    (tmp_path / "conditions.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in conditions)
    )
    return [
        "--set", str(tmp_path), "--conditions-sha256", conditions_sha256(conditions),
        "--out", str(tmp_path / "out"), "--simple-python", "python", "--pythonpath", "x",
        "--dry-run", "--max-chunks", "2",
    ]  # fmt: skip


def test_dry_run_prints_the_scene_and_a_set_of_another_scene_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from flywheel_psi0.tray import eval_batch

    def no_subprocess(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("no subprocess before the scene check")

    monkeypatch.setattr(eval_batch.subprocess, "Popen", no_subprocess)
    monkeypatch.setattr(eval_batch.subprocess, "run", no_subprocess)
    jig = scene_set(tmp_path / "jig", "jig2")
    assert eval_batch.main([*jig, "--scene", "jig2"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "l1-000 1000100 1000109 10 jig2"
    assert eval_batch.main(jig) == 1  # default zone1: refused
    assert eval_batch.main([*jig, "--scene", "zone1"]) == 1
    old = scene_set(tmp_path / "old", None)  # no recorded scene: zone1
    assert eval_batch.main(old) == 0
    assert capsys.readouterr().out.splitlines()[0].endswith(" zone1")
    assert eval_batch.main([*old, "--scene", "jig2"]) == 1
    assert "set is for scene ['zone1'], --scene is jig2" in capsys.readouterr().err

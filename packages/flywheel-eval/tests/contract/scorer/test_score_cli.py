"""`fw eval score` end to end (DA-36 task 5, AC 5).

The command is driven over the task definition the testkit ships, not the one
the unit tests build, so what is exercised here is the path an engineer takes:
name a task on the command line, point at a trace, read the table. The testkit
task predates `StageSpec.signals` (#101), which the scorer now requires, so it
is named through `ToyWithSignals`, the same task with its step signals declared.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]
import pytest
from flywheel.contracts import ScorerParams, StageEvaluation, StageSpec
from flywheel.eval.cli import app, load_task
from flywheel.eval.scorer.artifact import STORE_RECORDS
from flywheel.eval.scorer.status import ScorerError
from flywheel.testkit.fakes.task import ToyPickPlace
from typer.testing import CliRunner

THIS = "test_score_cli"
TOY_TASK = f"{THIS}:ToyWithSignals"
runner = CliRunner()

TOY_SIGNALS: dict[str, tuple[str, ...]] = {
    "approach": ("gripper_x", "gripper_y", "part_x", "part_y"),
    "grasp": ("gripper_x", "gripper_y", "part_x", "part_y"),
    "place": ("part_x", "part_y", "target_x", "target_y"),
}


class ToyWithSignals(ToyPickPlace):
    """The testkit task with the step signals #101 lets a stage declare."""

    def stages(self) -> tuple[StageSpec, ...]:
        return tuple(
            stage.model_copy(update={"signals": TOY_SIGNALS[stage.name]})
            for stage in super().stages()
        )


class RaisingTask(ToyWithSignals):
    """A task whose predicates blow up, named on the command line like any other."""

    def evaluate(self, signals: pa.Table, params: ScorerParams) -> StageEvaluation:
        raise RuntimeError("vị từ hỏng")


class TaskNeedingArguments(ToyPickPlace):
    """A task that cannot be built by name alone."""

    def __init__(self, calibration: str) -> None:
        self.calibration = calibration


class TwoTableByName(ToyPickPlace):
    """Only its `task_id` matters: it is what the default config is named after."""

    task_id = "two-table"


@pytest.fixture
def config(tmp_path: Path) -> Path:
    path = tmp_path / "toy-pick-place.yaml"
    path.write_text(
        "task_id: toy-pick-place\n"
        "scorer_version: '0.1.0'\n"
        "thresholds: {distance: 0.05}\n"
        "balance: {min_height: 0.5, max_tilt: 0.4, height_signal: torso_height, "
        "tilt_signal: torso_tilt}\n"
        "episode_signals: []\n"
        "class_from_failed_step: []\n",
        encoding="utf-8",
    )
    return path


def toy_rows(place_x: float = 1.0) -> list[dict[str, object]]:
    """A toy episode: the gripper closes on the part and carries it to the target.

    The default run ends with the part on the target, so the three steps of
    `ToyPickPlace` all pass; a `place_x` the part never reaches makes it fail at
    the last step instead.
    """
    rows = []
    for step in range(6):
        held = step >= 2
        rows.append(
            {
                "episode_id": "ep_toy",
                "gripper_x": 0.5 + 0.1 * step,
                "gripper_y": 0.5,
                "part_x": 0.7 if not held else 0.5 + 0.1 * step,
                "part_y": 0.5,
                "target_x": place_x,
                "target_y": 0.5,
                "torso_height": 0.95,
                "torso_tilt": 0.02,
            }
        )
    return rows


def write(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


def test_scores_an_episode_and_prints_every_step(tmp_path: Path, config: Path) -> None:
    trace = write(tmp_path / "ep.jsonl", toy_rows())

    result = runner.invoke(
        app, ["score", "--trace", str(trace), "--task", TOY_TASK, "--config", str(config)]
    )

    assert result.exit_code == 0, result.output
    assert "episode: ep_toy" in result.output
    assert "config_sha256:" in result.output
    # The three steps the toy task declares, named in Vietnamese as spec
    # section 5.1 names them.
    assert "approach" in result.output
    assert "đạt" in result.output
    assert "thành công theo scorer: đạt" in result.output


def test_a_failure_prints_its_kind_and_step(tmp_path: Path, config: Path) -> None:
    trace = write(tmp_path / "ep.jsonl", toy_rows(place_x=5.0))

    result = runner.invoke(
        app, ["score", "--trace", str(trace), "--task", TOY_TASK, "--config", str(config)]
    )

    assert result.exit_code == 0, result.output
    assert "thành công theo scorer: trượt" in result.output
    assert "kiểu lỗi: misplaced (place); hỏng trước ở: bước 2" in result.output
    assert "trượt" in result.output


def test_writes_the_record_only_when_a_store_is_given(tmp_path: Path, config: Path) -> None:
    trace = write(tmp_path / "ep.jsonl", toy_rows())
    store = tmp_path / "store"

    without = runner.invoke(
        app, ["score", "--trace", str(trace), "--task", TOY_TASK, "--config", str(config)]
    )
    assert not (store / STORE_RECORDS).exists()
    assert "ghi vào" not in without.output

    with_store = runner.invoke(
        app,
        [
            "score",
            "--trace",
            str(trace),
            "--task",
            TOY_TASK,
            "--config",
            str(config),
            "--store",
            str(store),
            "--level",
            "1",
        ],
    )

    assert with_store.exit_code == 0, with_store.output
    record = json.loads((store / STORE_RECORDS).read_text(encoding="utf-8").strip())
    assert record["episode_id"] == "ep_toy"
    assert record["level"] == 1
    assert record["step_status"] == ["pass", "pass", "pass"]


def test_an_episode_id_can_be_overridden(tmp_path: Path, config: Path) -> None:
    trace = write(tmp_path / "ep.jsonl", toy_rows())

    result = runner.invoke(
        app,
        [
            "score",
            "--trace",
            str(trace),
            "--task",
            TOY_TASK,
            "--config",
            str(config),
            "--episode-id",
            "ep_from_catalog",
        ],
    )

    assert "episode: ep_from_catalog" in result.output


@pytest.mark.parametrize(
    "arguments",
    [
        ["--trace", "absent.jsonl", "--task", TOY_TASK],
        ["--trace", "ep.jsonl", "--task", "flywheel.testkit.fakes.task:NoSuchTask"],
        ["--trace", "ep.jsonl", "--task", "not-a-reference"],
        # Each of these exited 1 with a traceback before the review of #58.
        ["--trace", "ep.jsonl", "--task", f"{THIS}:RaisingTask"],
        ["--trace", "ep.jsonl", "--task", f"{THIS}:TaskNeedingArguments"],
    ],
)
def test_what_cannot_be_scored_exits_two_and_writes_nothing(
    tmp_path: Path, config: Path, arguments: list[str]
) -> None:
    write(tmp_path / "ep.jsonl", toy_rows())
    store = tmp_path / "store"
    resolved = [str(tmp_path / value) if value.endswith(".jsonl") else value for value in arguments]

    result = runner.invoke(
        app, ["score", *resolved, "--config", str(config), "--store", str(store)]
    )

    assert result.exit_code == 2
    assert "không chấm được" in result.output
    # Nothing was scored, so nothing may be left behind looking like a score.
    assert not (store / STORE_RECORDS).exists()


@pytest.mark.parametrize("body", [None, "task_id: [\n", "- a\n- b\n"])
def test_a_config_that_is_absent_or_broken_exits_two(tmp_path: Path, body: str | None) -> None:
    trace = write(tmp_path / "ep.jsonl", toy_rows())
    broken = tmp_path / "broken.yaml"
    if body is not None:
        broken.write_text(body, encoding="utf-8")

    result = runner.invoke(
        app, ["score", "--trace", str(trace), "--task", TOY_TASK, "--config", str(broken)]
    )

    assert result.exit_code == 2, result.output
    assert "không chấm được" in result.output


def test_a_store_that_cannot_be_written_exits_two_after_scoring(
    tmp_path: Path, config: Path
) -> None:
    trace = write(tmp_path / "ep.jsonl", toy_rows())
    # A file where the store directory would go: the episode scores, the write
    # does not, and the engineer has to be told which of the two happened.
    blocked = tmp_path / "store"
    blocked.write_text("not a directory", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "score",
            "--trace",
            str(trace),
            "--task",
            TOY_TASK,
            "--config",
            str(config),
            "--store",
            str(blocked),
        ],
    )

    assert result.exit_code == 2, result.output
    assert "không ghi được" in result.output
    # The score itself was printed: it is the writing that failed.
    assert "thành công theo scorer: đạt" in result.output


def test_the_default_config_is_found_from_the_repo_not_the_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `fw eval score` run from a subdirectory used to look for `configs/` under
    # that subdirectory and fail (review of #58, point 5).
    from flywheel.eval.cli import _config_for

    monkeypatch.chdir(Path(__file__).parent)
    found = _config_for(TwoTableByName())

    assert found.is_file()
    assert found.name == "two-table.yaml"


def test_a_class_that_is_not_a_task_definition_is_refused() -> None:
    with pytest.raises(ScorerError, match="không phải `TaskDefinition`"):
        load_task("pathlib:Path")


def test_the_toy_task_loads_through_the_protocol_check() -> None:
    assert load_task(TOY_TASK).task_id == "toy-pick-place"

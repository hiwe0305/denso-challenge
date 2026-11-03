"""`fw eval diag-system` end to end (DA-13 AC 1, 2).

The command is driven the way an engineer runs it: point at an episode
directory, read the table, and optionally append to a store. What is checked
here is the part the unit tests cannot see - that a file nobody can read exits
with one line instead of a traceback, that the record is append-only, and that
a clean episode and an unjudged one print differently.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.eval.cli import app
from flywheel.eval.diagnosis.system.artifact import SYSTEM_RECORDS
from typer.testing import CliRunner

CONFIGS = Path(__file__).resolve().parents[6] / "configs" / "eval" / "diagnosis"
SYSTEM_YAML = CONFIGS / "system.yaml"
REFERENCE_SHA = "b" * 64

runner = CliRunner()


def _trace_row(step: int, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "trace_id": "trace_1",
        "episode_id": "ep_cli",
        "run_plan_id": "rp_1",
        "step": step,
        "t_state": 0.1 * step,
        "t_image": 0.1 * step + 0.002,
        "cmd_upper": [0.1, 0.2, 0.3],
        "meas_upper": [0.1, 0.2, 0.3],
        "cmd_lower": [0.5, 0.0],
        "meas_lower": [0.5, 0.0],
        "dropped_frames": 0,
    }
    row.update(overrides)
    return row


@pytest.fixture
def pinned_config(tmp_path: Path) -> Path:
    """`system.yaml` as it ships, with the camera reference pinned so R5 runs."""
    shipped = yaml.safe_load(SYSTEM_YAML.read_text(encoding="utf-8"))
    shipped["r5"] = {
        **shipped["r5"],
        "reference_sha256": REFERENCE_SHA,
        "cameras": {
            "head": {
                "mount": "head_link",
                "width": 640,
                "height": 480,
                "fx": 400.0,
                "fy": 400.0,
                "cx": 320.0,
                "cy": 240.0,
                "pose": [0.0, 0.0, 1.5, 1.0, 0.0, 0.0, 0.0],
            }
        },
    }
    path = tmp_path / "system.yaml"
    path.write_text(yaml.safe_dump(shipped, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture
def write_episode(tmp_path: Path):
    """Write an episode directory; `rows` replaces the healthy trace."""

    def build(name: str = "ep", rows: list[dict[str, Any]] | None = None) -> Path:
        folder = tmp_path / name
        folder.mkdir(parents=True, exist_ok=True)
        trace = rows if rows is not None else [_trace_row(step) for step in range(20)]
        (folder / "trace.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in trace), encoding="utf-8"
        )
        (folder / "rtc.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "job_id": "job_1",
                        "trace_id": "trace_1",
                        "chunk_index": index,
                        "observation_sent_s": 0.5 * index,
                        "chunk_received_s": 0.5 * index + 0.02,
                        "delay_steps": 1,
                        "buffer_level": 6,
                        "boundary_jump": 0.01,
                    }
                )
                + "\n"
                for index in range(10)
            ),
            encoding="utf-8",
        )
        (folder / "camera_params.json").write_text(
            json.dumps(
                {
                    "episode_id": "ep_cli",
                    "uid": "head",
                    "mount": "head_link",
                    "width": 640,
                    "height": 480,
                    "fx": 400.0,
                    "fy": 400.0,
                    "cx": 320.0,
                    "cy": 240.0,
                    "pose": [0.0, 0.0, 1.5, 1.0, 0.0, 0.0, 0.0],
                    "reference_sha256": REFERENCE_SHA,
                }
            ),
            encoding="utf-8",
        )
        (folder / "episode.json").write_text(
            json.dumps({"infra_status": "ok"}), encoding="utf-8"
        )
        return folder

    return build


def _run(*args: str):
    return runner.invoke(app, ["diag-system", *args])


def test_a_clean_episode_prints_no_finding_and_no_skip(write_episode, pinned_config) -> None:
    result = _run("--episode", str(write_episode()), "--config", str(pinned_config))

    assert result.exit_code == 0, result.output
    assert "không thấy lỗi hệ thống" in result.output
    assert "phát hiện: 0; bỏ qua: 0" in result.output


def test_an_injected_camera_delay_prints_the_sync_label(write_episode, pinned_config) -> None:
    rows = [_trace_row(step, t_image=0.1 * step - 0.06) for step in range(20)]

    result = _run("--episode", str(write_episode(rows=rows)), "--config", str(pinned_config))

    assert result.exit_code == 0, result.output
    assert "LỖI ĐỒNG BỘ" in result.output
    assert "R4" in result.output


def test_the_shipped_config_prints_an_unjudged_calibration(write_episode) -> None:
    # Until G0 pins the reference the command says CHƯA RÕ with R5 skipped,
    # which has to be visible without opening the record.
    result = _run("--episode", str(write_episode()), "--config", str(SYSTEM_YAML))

    assert result.exit_code == 0, result.output
    assert "CHƯA RÕ" in result.output
    assert "bỏ qua R5" in result.output


def test_the_record_is_appended_not_replaced(write_episode, pinned_config, tmp_path) -> None:
    episode = write_episode()
    store = tmp_path / "store"

    for _ in range(2):
        result = _run(
            "--episode", str(episode), "--config", str(pinned_config), "--store", str(store)
        )
        assert result.exit_code == 0, result.output

    lines = (store / SYSTEM_RECORDS).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["episode_id"] == "ep_cli"
    assert len(json.loads(lines[0])["config_sha256"]) == 64


def test_an_episode_without_a_trace_exits_two_with_one_line(tmp_path, pinned_config) -> None:
    empty = tmp_path / "nothing"
    empty.mkdir()

    result = _run("--episode", str(empty), "--config", str(pinned_config))

    assert result.exit_code == 2
    assert "không kiểm được" in result.output
    assert "Traceback" not in result.output


def test_a_config_that_is_not_there_exits_two_with_one_line(write_episode, tmp_path) -> None:
    result = _run("--episode", str(write_episode()), "--config", str(tmp_path / "missing.yaml"))

    assert result.exit_code == 2
    assert "không kiểm được" in result.output
    assert "Traceback" not in result.output


def test_nothing_is_written_when_the_episode_cannot_be_read(tmp_path, pinned_config) -> None:
    empty = tmp_path / "nothing"
    empty.mkdir()
    store = tmp_path / "store"

    _run("--episode", str(empty), "--config", str(pinned_config), "--store", str(store))

    assert not (store / SYSTEM_RECORDS).exists()

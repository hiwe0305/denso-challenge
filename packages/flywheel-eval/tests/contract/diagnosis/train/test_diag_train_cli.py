"""`fw eval diag-train` as its callers meet it (DA-08 task 6, AC 5).

The unit tests judge the detectors; this file judges the command. What it
promises is small and has to hold: the command exists under the `fw` entry
point, it prints both the findings and the codes it could not judge, it appends
to the store instead of overwriting it, and a file it cannot read makes it fail
rather than report a clean checkpoint.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points
from io import StringIO
from pathlib import Path
from typing import Any

from conftest import TRAIN_YAML, record
from flywheel.contracts.training import TrainDiagnosis
from flywheel.eval.cli import app, use_utf8
from typer.testing import CliRunner

runner = CliRunner()
JobWriter = Callable[..., Path]


def run(*args: str | Path) -> Any:
    return runner.invoke(app, [str(one) for one in args])


class TestRegistration:
    def test_the_lane_registers_itself_under_fw(self) -> None:
        """`fw eval` is an entry point, so the command does not need wiring in the CLI."""
        registered = {point.name: point for point in entry_points(group="flywheel.commands")}

        assert "eval" in registered
        assert registered["eval"].load() is app

    def test_the_command_has_help(self) -> None:
        result = run("diag-train", "--help")

        assert result.exit_code == 0
        assert "--job" in result.output
        assert "--config" in result.output
        assert "--store" in result.output


class TestOutput:
    def test_a_learning_job_prints_no_finding_and_no_skip(self, write_job: JobWriter) -> None:
        result = run("diag-train", "--job", write_job(), "--config", TRAIN_YAML)

        assert result.exit_code == 0
        assert "phát hiện: 0; bỏ qua: 0" in result.output
        assert "ckpt_example" in result.output

    def test_an_injected_divergence_prints_one_row(self, write_job: JobWriter) -> None:
        job = write_job(faults=[record(step=3010, loss="NaN")])

        result = run("diag-train", "--job", job, "--config", TRAIN_YAML)

        rows = [line for line in result.output.splitlines() if line.startswith("T1")]
        assert len(rows) == 1
        assert "NaN" in rows[0]
        assert rows[0].endswith("yes")  # T1 is the one code that may stop a job
        assert "phát hiện: 1; bỏ qua: 0" in result.output

    def test_a_job_missing_its_probes_prints_the_skipped_codes(self, write_job: JobWriter) -> None:
        """What the command must never print is a clean verdict on unjudged codes."""
        job = write_job()
        for name in ("probe_p3.json", "probe_p4.json", "probe_p4_parent.json"):
            (job / name).unlink()

        result = run("diag-train", "--job", job, "--config", TRAIN_YAML)

        assert result.exit_code == 0
        assert "phát hiện: 0; bỏ qua: 5" in result.output
        for code in ("O1", "O2", "O3", "O4", "T7"):
            assert f"bỏ qua {code}:" in result.output


class TestStore:
    def test_the_store_grows_by_one_record_per_run(
        self, write_job: JobWriter, tmp_path: Path
    ) -> None:
        job = write_job()
        store = tmp_path / "store"

        first = run("diag-train", "--job", job, "--config", TRAIN_YAML, "--store", store)
        second = run("diag-train", "--job", job, "--config", TRAIN_YAML, "--store", store)

        assert first.exit_code == second.exit_code == 0
        records = (store / "diagnosis" / "train.jsonl").read_text(encoding="utf-8")
        lines = records.strip().splitlines()
        assert len(lines) == 2
        assert all(TrainDiagnosis.model_validate_json(line) for line in lines)

    def test_nothing_is_written_without_a_store(self, write_job: JobWriter, tmp_path: Path) -> None:
        result = run("diag-train", "--job", write_job(), "--config", TRAIN_YAML)

        assert "ghi vào" not in result.output
        assert not (tmp_path / "store").exists()


class TestWindowsConsole:
    def test_the_streams_are_put_on_utf8(self, tmp_path: Path) -> None:
        """A cp1252 console cannot encode a skip reason; the command must not die on one."""
        path = tmp_path / "console.txt"
        with path.open("w", encoding="cp1252") as console:
            use_utf8(console)
            console.write("bỏ qua T7: không có kết quả probe P4")

        assert "bỏ qua T7" in path.read_text(encoding="utf-8")

    def test_a_stream_that_cannot_be_reconfigured_is_left_alone(self) -> None:
        use_utf8(StringIO())  # no reconfigure method; must not raise


class TestRefusals:
    def test_a_job_without_a_log_fails_instead_of_passing_it(self, tmp_path: Path) -> None:
        (tmp_path / "nothing").mkdir()

        result = run("diag-train", "--job", tmp_path / "nothing", "--config", TRAIN_YAML)

        assert result.exit_code == 2
        assert "metrics.jsonl" in result.output

    def test_a_broken_threshold_file_fails_instead_of_using_a_default(
        self, write_job: JobWriter, tmp_path: Path
    ) -> None:
        """A missing threshold is a config error, never a number chosen in code (AC 3)."""
        broken = tmp_path / "broken.yaml"
        broken.write_text("t1:\n  k: 10.0\n", encoding="utf-8")

        result = run("diag-train", "--job", write_job(), "--config", broken)

        assert result.exit_code == 2
        assert "không chẩn được" in result.output

    def test_a_malformed_log_line_fails(self, write_job: JobWriter) -> None:
        job = write_job()
        (job / "metrics.jsonl").write_text('{"job_id": "job"}\n', encoding="utf-8")

        result = run("diag-train", "--job", job, "--config", TRAIN_YAML)

        assert result.exit_code == 2
        assert "sai schema" in result.output

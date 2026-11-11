from pathlib import Path

import pytest
from flywheel.cli.main import app
from typer.testing import CliRunner


def test_fw_console_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "console" in result.output


def test_fw_console_index_prints_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FW_ROOT", str(tmp_path))
    result = CliRunner().invoke(app, ["console", "index", "--only", "catalog"])
    assert result.exit_code == 0, result.output
    assert "catalog: rows=" in result.output
    assert str(tmp_path / "console" / "index") in result.output


def test_fw_console_bench_tunnel_down_is_one_line(monkeypatch: pytest.MonkeyPatch) -> None:
    from flywheel.console.chat import bench

    def down(tag: str | None = None) -> None:
        raise RuntimeError("model tunnel to rtx3060 is down; bench not run, no file written")

    monkeypatch.setattr(bench, "run", down)
    result = CliRunner().invoke(app, ["console", "bench", "--tag", "x"])
    assert result.exit_code == 1
    assert "tunnel to rtx3060 is down" in result.output
    assert "Traceback" not in result.output

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


def test_fw_console_index_bad_only_is_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FW_ROOT", str(tmp_path))
    result = CliRunner().invoke(app, ["console", "index", "--only", "nope"])
    assert result.exit_code == 1
    assert "index: " in result.output and "Traceback" not in result.output


def test_fw_console_serve_busy_port_and_prints_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import socket

    monkeypatch.setenv("FW_ROOT", str(tmp_path))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        result = CliRunner().invoke(app, ["console", "serve", "--port", str(port)])
    assert result.exit_code == 1
    assert "serve: " in result.output and "Traceback" not in result.output
    assert f"fw_root: {tmp_path}" in result.output and "repo: " in result.output

"""Tests for CLI version reporting."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from click import unstyle
from flywheel.cli.main import app, build_version
from typer.testing import CliRunner

runner = CliRunner()


def test_fw_version_reports_package_repo_when_called_outside_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    expected_suffix = "-dirty" if status else ""
    assert result.stdout == f"0.1.0+{sha}{expected_suffix}\n"
    assert re.fullmatch(r"0\.1\.0\+[0-9a-f]{40}(?:-dirty)?\n", result.stdout)


def test_build_version_reports_clean_repository(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    (tmp_path / "tracked.txt").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=tmp_path, check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert build_version(tmp_path) == f"0.1.0+{sha}"


def test_fw_help_is_available() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--version" in unstyle(result.stdout)

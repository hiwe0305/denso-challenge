from flywheel.cli.main import app
from typer.testing import CliRunner


def test_fw_console_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "console" in result.output

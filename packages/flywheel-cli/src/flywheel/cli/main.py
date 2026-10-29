"""Command-line entry point for the Flywheel core."""

from __future__ import annotations

import subprocess
from importlib.metadata import PackageNotFoundError, entry_points, version
from pathlib import Path

import typer

app = typer.Typer(
    add_completion=False,
    help="Operate the DENSO Humanoid Data Flywheel.",
    no_args_is_help=True,
)
PACKAGE_DIRECTORY = Path(__file__).resolve().parent


def _package_version() -> str:
    """Return the installed package version, including editable installations."""
    try:
        return version("flywheel-cli")
    except PackageNotFoundError:
        return "0.1.0"


def _git_output(*args: str, cwd: Path | None = None) -> str | None:
    """Run a read-only Git command, returning ``None`` outside a repository."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def build_version(cwd: Path | None = None) -> str:
    """Combine the package version with the current Git SHA and dirty state."""
    repository_location = cwd if cwd is not None else PACKAGE_DIRECTORY
    sha = _git_output("rev-parse", "HEAD", cwd=repository_location)
    if sha is None:
        return f"{_package_version()}+unknown"

    status = _git_output(
        "status",
        "--porcelain",
        "--untracked-files=normal",
        cwd=repository_location,
    )
    dirty = "-dirty" if status else ""
    return f"{_package_version()}+{sha}{dirty}"


def version_callback(value: bool) -> None:
    """Print version metadata and exit before command dispatch."""
    if value:
        typer.echo(build_version())
        raise typer.Exit


@app.callback()
def root(
    version_requested: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the package version, Git SHA, and dirty state.",
    ),
) -> None:
    """Operate the DENSO Humanoid Data Flywheel."""
    del version_requested


for command in entry_points(group="flywheel.commands"):
    app.add_typer(command.load(), name=command.name)


def main() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    main()

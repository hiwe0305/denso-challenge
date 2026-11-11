"""``fw console`` commands. Heavy modules are imported inside each command."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, help="Local flywheel console.")


@app.command()
def index(
    only: str = typer.Option("", help="Comma list: catalog,robot,ego,story."),
) -> None:
    """Build the console index."""
    from flywheel.console.index import build_all
    from flywheel.console.paths import ConsolePaths

    paths = ConsolePaths.from_env()
    parts = [s for s in only.split(",") if s]
    try:
        counts = build_all(paths, only=parts or None)
    except (ValueError, OSError) as e:
        typer.echo(f"index: {e}", err=True)
        raise typer.Exit(1) from e
    for name, part in counts.items():
        typer.echo(f"{name}: " + " ".join(f"{k}={v}" for k, v in part.items()))
    typer.echo(f"index: {paths.index}")


@app.command()
def serve(port: int = typer.Option(4178, help="Port on 127.0.0.1.")) -> None:
    """Serve the console on 127.0.0.1."""
    from flywheel.console.paths import ConsolePaths
    from flywheel.console.server.app import serve as run

    paths = ConsolePaths.from_env()
    typer.echo(f"repo: {paths.repo}")
    typer.echo(f"fw_root: {paths.fw_root}")
    try:
        run(paths, port=port)
    except OSError as e:
        typer.echo(f"serve: {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def bench(tag: str = typer.Option("", help="Label for this run.")) -> None:
    """Run the chat benchmark."""
    from flywheel.console.chat import bench as chat_bench

    try:
        chat_bench.run(tag=tag)
    except RuntimeError as e:  # tunnel down: one line, no traceback
        typer.echo(f"bench: {e}", err=True)
        raise typer.Exit(1) from e

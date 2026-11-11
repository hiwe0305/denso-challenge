"""``fw console`` commands. Heavy modules are imported inside each command."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, help="Local flywheel console.")


@app.command()
def index(
    only: str = typer.Option("", help="Comma list: catalog,robot,ego,story."),
) -> None:
    """Build the console index."""
    from flywheel.console.index import build_all  # type: ignore[import-not-found,import-untyped,unused-ignore]

    parts = [s for s in only.split(",") if s]
    build_all(only=parts or None)


@app.command()
def serve(port: int = typer.Option(4178, help="Port on 127.0.0.1.")) -> None:
    """Serve the console on 127.0.0.1."""
    from flywheel.console.server.app import (  # type: ignore[import-not-found,import-untyped,unused-ignore]
        serve as run,
    )

    run(port=port)


@app.command()
def bench(tag: str = typer.Option("", help="Label for this run.")) -> None:
    """Run the chat benchmark."""
    from flywheel.console.chat.bench import run  # type: ignore[import-not-found,import-untyped,unused-ignore]

    run(tag=tag)

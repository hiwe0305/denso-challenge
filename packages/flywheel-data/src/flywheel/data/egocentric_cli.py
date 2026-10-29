"""Command group scaffold."""

import typer

app = typer.Typer()


@app.callback()
def root() -> None:
    """Egocentric data commands."""

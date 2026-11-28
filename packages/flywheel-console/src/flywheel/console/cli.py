"""``fw console`` commands. Heavy modules are imported inside each command."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, help="Local flywheel console.")


@app.command()
def index(
    only: str = typer.Option("", help="Comma list: catalog,robot,ego,story,sim,tasks."),
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


def _autoload_dotenv_for_serve(paths: object) -> None:
    """Load local .env from repo or fw_root parent and map CKEY_* gateway vars to FW_CHAT_*."""
    import os
    from pathlib import Path

    candidates: list[Path] = []
    repo_p = getattr(paths, "repo", None)
    fw_p = getattr(paths, "fw_root", None)
    if isinstance(repo_p, Path):
        candidates.append(repo_p / ".env")
    if isinstance(fw_p, Path):
        candidates.append(fw_p.parent / ".env")

    for env_file in candidates:
        if not env_file.is_file():
            continue
        try:
            for raw_ln in env_file.read_text(encoding="utf-8").splitlines():
                ln = raw_ln.strip()
                if not ln or ln.startswith("#") or "=" not in ln:
                    continue
                k, v = ln.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and v and not os.environ.get(k):
                    os.environ[k] = v
        except OSError:
            pass

    ckey_url = os.environ.get("CKEY_BASE_MODEL", "").strip()
    ckey_key = os.environ.get("CKEY_API_KEY", "").strip()
    if ckey_url and ckey_key and not os.environ.get("FW_CHAT_BASE_URL"):
        os.environ["FW_CHAT_BASE_URL"] = ckey_url
        os.environ.setdefault("FW_CHAT_API_KEY", ckey_key)
        default_ckey_model = os.environ.get("CKEY_MODEL", "").strip() or "gpt-5.5"
        os.environ.setdefault("FW_CHAT_MODEL", default_ckey_model)
        os.environ.setdefault("FW_CHAT_NAME", "CKEY Gateway")


@app.command()
def serve(
    port: int = typer.Option(4178, help="Port on 127.0.0.1."),
    lock: bool = typer.Option(False, "--lock", help="Read-only: refuse jobs, uploads, chat."),
    chat: bool = typer.Option(
        False, "--chat", help="With --lock: keep the chat on (it only reads)."
    ),
) -> None:
    """Serve the console on 127.0.0.1."""
    from flywheel.console.paths import ConsolePaths
    from flywheel.console.server.app import serve as run

    paths = ConsolePaths.from_env()
    _autoload_dotenv_for_serve(paths)
    typer.echo(f"repo: {paths.repo}")
    typer.echo(f"fw_root: {paths.fw_root}")
    try:
        run(paths, port=port, lock=lock, chat=chat)
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

"""Lệnh `fwsync` (DESIGN.md §5.5).

Chạy: ``uv run python -m web.fwsync.cli <lệnh> ...``

Bốn lệnh, mỗi lệnh là một vỏ mỏng trên `runner.py`: phân tích tham số, in
kết quả, chọn mã thoát. Mọi logic nằm ở `runner.py` để test không phải gọi
CLI.

`--sink jsonl` là mặc định vì máy dev chưa cài Postgres (§9.3). Nó **không**
phải một database: nó không kiểm được CHECK, trigger hay quyền, nên nó không
thay được nghiệm thu mốc M1. Nó chứng minh đường đọc và ánh xạ đúng.

Mã thoát: 0 khi `ok`, 1 khi `partial` (có nạp được nhưng có dòng bị từ chối),
2 khi `failed` hoặc không đọc được nguồn. Một lần nạp có dòng bị từ chối mà
thoát 0 là cách để lỗi đó không ai thấy trong cron.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO

import typer

from web.fwsync.runner import (
    SyncResult,
    digest_of,
    run_export,
    run_fake_core,
    run_import,
    run_verify,
)
from web.fwsync.sink import JsonlSink, PostgresSink, Sink
from web.fwsync.source import SourceError

app = typer.Typer(help="Bộ nạp giữa lõi flywheel và tầng web.")

EXIT_CODE = {"ok": 0, "partial": 1, "failed": 2}


def use_utf8(*streams: TextIO) -> None:
    """Đặt stream ra UTF-8, để một lý do tiếng Việt không giết cả lần chạy.

    Đội chạy trên Windows, nơi console trao Python một stream cp1252 không mã
    hoá được tiếng Việt. Không có dòng này thì lệnh chết nửa đường khi in một
    lý do đã tính xong.
    """
    for stream in streams or (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


def _sink(kind: str, directory: Path, dsn: str | None) -> Sink:
    if kind == "jsonl":
        return JsonlSink(directory=directory)
    if kind == "postgres":
        if not dsn:
            raise typer.BadParameter("`--sink postgres` cần `--dsn`")
        return PostgresSink(dsn=dsn)
    raise typer.BadParameter(f"`--sink {kind}` không có; chỉ `jsonl` hoặc `postgres`")


def _report(result: SyncResult) -> None:
    typer.echo(f"{result.direction}: {result.source_dir}")
    typer.echo(f"trạng thái: {result.status}")
    for table, counts in result.counts.items():
        if any(counts.values()):
            typer.echo(
                f"  {table:<28} thêm {counts['inserted']:>5}  "
                f"sửa {counts['updated']:>5}  đã có {counts.get('unchanged', 0):>5}  "
                f"từ chối {counts['rejected']:>5}"
            )
    if result.ignored:
        typer.echo(f"bỏ qua {len(result.ignored)} file không nhận ra: {result.ignored[:5]}")
    # Trường lạ là tin, không phải lỗi: lõi thêm trường trước khi web biết là
    # chuyện bình thường. Nhưng im lặng thì không ai biết (§9.4).
    for table, names in result.unknown_fields.items():
        typer.echo(f"trường lạ ở `{table}`, đã bỏ: {', '.join(names)}")
    for error in result.errors:
        typer.echo(f"từ chối {error['table']} {error['ref']}: {error['message']}", err=True)


@app.command("import")
def import_(
    source: Path = typer.Option(..., "--from", help="Thư mục artifact của lõi."),
    sink: str = typer.Option("jsonl", "--sink", help="`jsonl` (mặc định) hoặc `postgres`."),
    out: Path = typer.Option(
        Path("fwdata/web-sink"), "--out", help="Thư mục ra của sink `jsonl`."
    ),
    dsn: str | None = typer.Option(None, "--dsn", help="Chuỗi kết nối cho sink `postgres`."),
    origin: str = typer.Option(
        "core",
        "--origin",
        help="`core` cho output thật của lõi, `mock` cho bộ mock. Đóng dấu lên mọi dòng.",
    ),
) -> None:
    """Nạp artifact vào bảng nhóm P. Chạy lại từ đầu cho cùng kết quả."""
    use_utf8()
    try:
        target = _sink(sink, out, dsn)
        result = run_import(source, target, origin=origin)
    except ValueError as error:
        typer.echo(f"không nạp được: {error}", err=True)
        raise typer.Exit(code=2) from error
    except SourceError as error:
        typer.echo(f"không nạp được: {error}", err=True)
        raise typer.Exit(code=2) from error
    except NotImplementedError as error:
        typer.echo(f"sink chưa dựng: {error}", err=True)
        raise typer.Exit(code=2) from error
    _report(result)
    raise typer.Exit(code=EXIT_CODE[result.status])


@app.command("export")
def export(
    actions: Path = typer.Option(
        ..., "--actions", help="File JSONL các `human_actions` đang PENDING."
    ),
    outbox: Path = typer.Option(..., "--to", help="Thư mục outbox cho lõi."),
) -> None:
    """Xuất hành động đang chờ thành artifact mang `source_action_id`."""
    use_utf8()
    try:
        rows = [
            json.loads(line)
            for line in actions.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        typer.echo(f"không đọc được `{actions}`: {error}", err=True)
        raise typer.Exit(code=2) from error
    result = run_export(rows, outbox)
    _report(result)
    raise typer.Exit(code=EXIT_CODE[result.status])


@app.command("verify")
def verify(
    source: Path = typer.Option(..., "--from", help="Thư mục artifact của lõi."),
    loaded: Path = typer.Option(
        ..., "--loaded", help="File JSON {bảng: số dòng} của những gì đã nạp."
    ),
) -> None:
    """So số dòng giữa nguồn và những gì đã nạp. Báo chênh, không tự sửa."""
    use_utf8()
    try:
        counts = json.loads(loaded.read_text(encoding="utf-8"))
        result = run_verify(source, counts)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        typer.echo(f"không đọc được `{loaded}`: {error}", err=True)
        raise typer.Exit(code=2) from error
    except SourceError as error:
        typer.echo(f"không kiểm được: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(f"hash nguồn: {digest_of(source)[:16]}…")
    _report(result)
    raise typer.Exit(code=EXIT_CODE[result.status])


@app.command("fake-core")
def fake_core(
    outbox: Path = typer.Option(..., "--outbox", help="Thư mục outbox để đọc."),
    destination: Path = typer.Option(..., "--to", help="Thư mục ghi artifact kết quả."),
) -> None:
    """Lõi giả: đọc outbox, sinh kết quả mang `source_action_id` (mốc M4).

    Không phải lõi. Nó chỉ đủ để chứng minh vòng ghi khép lại khi lõi thật
    chưa sẵn sàng.
    """
    use_utf8()
    if not outbox.is_dir():
        typer.echo(f"`{outbox}` không phải thư mục", err=True)
        raise typer.Exit(code=2)
    result = run_fake_core(outbox, destination)
    _report(result)
    raise typer.Exit(code=EXIT_CODE[result.status])


if __name__ == "__main__":
    app()

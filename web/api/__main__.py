"""Run the web API on the JSONL sink of `fwsync`.

    uv run python -m web.api --sink fwdata/web-sink --state fwdata/web-state
    uv run python -m web.api --import-from mock/demo-17-11 --origin mock

`--import-from` runs `fwsync import` into the sink first, so one command
brings up the API on the demo mock. The FE talks to it with
`VITE_API_MODE=real npm run dev` (Vite proxies `/api` to port 8000).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from web.api.actions import ActionStore
from web.api.app import create_app
from web.api.readmodel import SinkReadModel, SinkTables


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m web.api", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sink", type=Path, default=Path("fwdata/web-sink"),
                        help="thư mục JSONL mà `fwsync import --out` đã ghi")
    parser.add_argument("--state", type=Path, default=Path("fwdata/web-state"),
                        help="nơi ghi human_actions.jsonl (đầu vào của `fwsync export`)")
    parser.add_argument("--import-from", type=Path, default=None,
                        help="chạy `fwsync import` từ thư mục này vào --sink trước khi mở API")
    parser.add_argument("--origin", choices=("core", "mock"), default="core")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    if args.import_from is not None:
        from web.fwsync.runner import run_import
        from web.fwsync.sink import JsonlSink

        result = run_import(args.import_from, JsonlSink(directory=args.sink), origin=args.origin)
        if result.status != "ok":
            print(f"fwsync import: {result.status}, {len(result.errors)} dòng bị từ chối",
                  file=sys.stderr)
            return 1
    if not args.sink.is_dir():
        print(f"không thấy sink `{args.sink}`; chạy `fwsync import --out {args.sink}` trước "
              "hoặc thêm --import-from", file=sys.stderr)
        return 2

    import uvicorn

    app = create_app(SinkReadModel(SinkTables(args.sink)), ActionStore(args.state))
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

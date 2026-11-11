"""Run the web API on the JSONL sink of `fwsync`.

    uv run python -m web.api --sink fwdata/web-sink --state fwdata/web-state
    uv run python -m web.api --import-from mock/demo-17-11 --origin mock

`--import-from` runs `fwsync import` into the sink first, so one command
brings up the API on the demo mock. The FE talks to it with
`VITE_API_MODE=real npm run dev` (Vite proxies `/api` to port 8000).

The chat pane needs a model on a machine of ours (R6), e.g. the Ollama that
serves Agent QA/QC: `--chat-url http://127.0.0.1:11434/v1 --chat-model <name>`.
Without `--chat-url` the API runs and the chat answers 503.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from web.api.actions import ActionStore
from web.api.app import SyncConfig, create_app
from web.api.chat import LocalEndpoint
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
    parser.add_argument("--outbox", type=Path, default=Path("fwdata/outbox"),
                        help="nơi `POST /sync/run` xuất hành động cho lõi")
    parser.add_argument("--inbox", type=Path, default=Path("fwdata/inbox"),
                        help="nơi lõi (hoặc lõi giả) ghi kết quả để nạp lại")
    parser.add_argument("--fake-core", action="store_true",
                        help="để lõi giả trả lời outbox ngay trong `POST /sync/run` (mốc M4)")
    parser.add_argument("--chat-url", default=os.environ.get("FW_WEB_CHAT_URL"),
                        help="endpoint OpenAI-style (…/v1) của model chat, chỉ máy của đội (R6)")
    parser.add_argument("--chat-model", default=os.environ.get("FW_WEB_CHAT_MODEL"),
                        help="tên model mà endpoint phục vụ")
    parser.add_argument("--chat-local-host", action="append", default=[],
                        help="tên host trong mạng của đội được coi là máy của ta (lặp được)")
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
            for error in result.errors[:10]:
                print(f"  {error['table']} {error['ref']}: {error['message']}", file=sys.stderr)
        # A rejected row is reported, not a reason to keep the whole web down:
        # only an import that loaded nothing stops here.
        if result.status == "failed":
            return 1
    if not args.sink.is_dir():
        print(f"không thấy sink `{args.sink}`; chạy `fwsync import --out {args.sink}` trước "
              "hoặc thêm --import-from", file=sys.stderr)
        return 2

    import uvicorn

    chat_model = None
    if args.chat_url:
        if not args.chat_model:
            print("--chat-url cần --chat-model", file=sys.stderr)
            return 2
        try:
            chat_model = LocalEndpoint(base_url=args.chat_url, model=args.chat_model,
                                       local_hosts=tuple(args.chat_local_host))
        except ValueError as error:
            print(error, file=sys.stderr)
            return 2

    sync = SyncConfig(outbox=args.outbox, inbox=args.inbox, sink=args.sink,
                      fake_core=args.fake_core, origin=args.origin)
    app = create_app(SinkReadModel(SinkTables(args.sink)), ActionStore(args.state), sync,
                     chat_model)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

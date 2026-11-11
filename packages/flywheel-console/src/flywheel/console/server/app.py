"""Console HTTP server: static files with Range, read-only media mounts, JSON API, SSE chat.

Bound to 127.0.0.1 only. POST needs a ``Host`` and ``Origin`` that name the console itself.
Writes only under ``<fw_root>/console/`` (jobs, cache, exports, uploads, config, chat).
"""

from __future__ import annotations

import importlib
import json
import mimetypes
import os
import re
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from flywheel.console.paths import ConsolePaths, PathDenied, active, guard, set_active
from flywheel.console.server import media, runner

MAX_JSON = 1 << 20
MAX_UPLOAD = 8 << 30
_lock = threading.Lock()


def _chat(mod: str) -> Any:
    """Lazy import of ``flywheel.console.chat.<mod>`` (Task 6 module; absent until it lands)."""
    return importlib.import_module(f"flywheel.console.chat.{mod}")


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, paths: ConsolePaths, port: int) -> None:
        self.paths = paths
        super().__init__(("127.0.0.1", port), Handler)

    @property
    def port(self) -> int:
        return int(self.server_address[1])


def _safe_join(root: Path, rel: str) -> Path | None:
    try:
        return guard(root / rel, [root])
    except (PathDenied, ValueError, OSError):
        return None


class Handler(BaseHTTPRequestHandler):
    server: ConsoleServer
    server_version = "console"
    protocol_version = "HTTP/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        if os.environ.get("CONSOLE_LOG"):
            super().log_message(format, *args)

    # ------------------------------------------------------------ helpers
    @property
    def paths(self) -> ConsolePaths:
        return self.server.paths

    def host_ok(self) -> bool:
        p = self.server.port
        return self.headers.get("Host", "") in (f"127.0.0.1:{p}", f"localhost:{p}")

    def origin_ok(self) -> bool:
        p = self.server.port
        return self.headers.get("Origin") in (f"http://localhost:{p}", f"http://127.0.0.1:{p}")

    def send_bytes(self, body: bytes, code: int = 200, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def jerr(self, code: int, msg: str) -> None:
        self.send_bytes(json.dumps({"error": msg}, ensure_ascii=False).encode(), code)

    def jok(self, obj: Any, code: int = 200) -> None:
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode(), code)

    # ------------------------------------------------------------ POST
    def do_POST(self) -> None:
        u = urlparse(self.path)
        if not u.path.startswith("/api/"):
            return self.jerr(404, "not found")
        if not self.host_ok() or not self.origin_ok():
            return self.jerr(403, "forbidden origin")
        try:
            if u.path == "/api/upload":
                return self.upload(u)
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_JSON:
                return self.jerr(413, "body too large")
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            parts = u.path.strip("/").split("/")
            if u.path == "/api/chat":
                return self.chat_sse(body)
            if u.path == "/api/models/prewarm":
                return self.jok(_chat("llm").prewarm())
            if u.path == "/api/jobs":
                job = runner.submit(str(body.get("kind")), body.get("params") or {})
                return self.jok(runner.pub(job), 201)
            if len(parts) == 4 and parts[1] == "jobs" and parts[3] == "cancel":
                return self.jok(runner.cancel(parts[2]))
            if u.path == "/api/models/connect":
                runner.TUNNEL.ensure(15)
                return self.jok(runner.models_info())
            return self.jerr(404, "unknown api")
        except ModuleNotFoundError:
            return self.jerr(503, "chat module not available")
        except KeyError:
            return self.jerr(404, "not found")
        except ValueError as e:
            return self.jerr(400, str(e))
        except Exception as e:
            return self.jerr(500, str(e))

    def chat_sse(self, body: dict[str, Any]) -> None:
        """text/event-stream; the client closing the socket stops the turn."""
        llm = _chat("llm")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        gen = llm.stream(body)
        try:
            for chunk in gen:
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            close = getattr(gen, "close", None)
            if close:
                close()
        except Exception as e:
            err = json.dumps({"message": str(e), "fallback": "slash"}, ensure_ascii=False)
            try:
                self.wfile.write(f"event: error\ndata: {err}\n\n".encode())
                self.wfile.flush()
            except Exception:
                pass
        self.close_connection = True

    def upload(self, u: Any) -> None:
        q = parse_qs(u.query)
        batch = q.get("dir", [""])[0]
        if not re.match(r"^upload-\d{8}-\d{4}$", batch):
            return self.jerr(400, "dir must look like upload-YYYYMMDD-HHMM")
        task = q.get("task", ["two_table"])[0]
        if not re.match(r"^[A-Za-z0-9_]{1,40}$", task):
            return self.jerr(400, "bad task")
        name = runner.safe_name(unquote(self.headers.get("X-Filename", "")))
        ext = os.path.splitext(name)[1].lower()
        if ext not in runner.VIDEO_EXT:
            return self.jerr(400, "chỉ nhận " + " ".join(runner.VIDEO_EXT))
        n = int(self.headers.get("Content-Length") or -1)
        if n < 0:
            return self.jerr(411, "Content-Length required")
        if n > MAX_UPLOAD:
            return self.jerr(413, "file > 8 GB")
        d = self.paths.uploads / batch
        td = d / task
        td.mkdir(parents=True, exist_ok=True)
        with _lock:
            stems = [int(p.stem) for p in td.glob("*.*") if p.stem.isdigit()]
            dest = td / f"{1 + max(stems or [0])}{ext}"
            dest.touch()
        tmp = Path(str(dest) + ".part")
        left = n
        try:
            with open(tmp, "wb") as f:
                while left > 0:
                    b = self.rfile.read(min(1 << 20, left))
                    if not b:
                        break
                    f.write(b)
                    left -= len(b)
            if left:
                tmp.unlink()
                dest.unlink(missing_ok=True)
                return self.jerr(400, "upload bị cắt giữa chừng")
            os.replace(tmp, dest)
        except Exception:
            tmp.unlink(missing_ok=True)
            dest.unlink(missing_ok=True)
            raise
        runner.ensure_device(d, dest)
        rel = str(dest.relative_to(d))
        with _lock:
            names = runner.jread(d / "names.json", {})
            names[rel] = name
            (d / "names.json").write_text(json.dumps(names, ensure_ascii=False, indent=1))
        self.jok({"saved": str(dest), "dir": str(d), "name": name, "as": rel, "size": n}, 201)

    # ------------------------------------------------------------ GET and static files
    def do_HEAD(self) -> None:
        self.do_GET()

    def resolve(self, urlpath: str) -> Path | None:
        up = unquote(urlpath)
        if "\x00" in up:
            return None
        mounts: list[tuple[str, Path]] = [
            ("/data/", self.paths.index),
            ("/vendor/", self.paths.web / "vendor"),
        ]
        ego = media.ego_viewer_dir()
        if ego is not None:
            mounts.append(("/ego/", ego))
        if up.startswith("/media/"):
            ds, _, rest = up[len("/media/") :].partition("/")
            try:
                return _safe_join(media.media_root(ds), rest)
            except KeyError:
                return None
        for pre, root in mounts:
            if up.startswith(pre):
                return _safe_join(root, up[len(pre) :])
        if up == "/":
            up = "/index.html"
        return _safe_join(self.paths.web, up.lstrip("/"))

    def do_GET(self) -> None:
        u = urlparse(self.path)
        if not self.host_ok():
            return self.jerr(403, "forbidden host")
        if u.path.startswith("/api/"):
            return self.api(u)
        fp = self.resolve(u.path)
        if fp is None or not fp.is_file():
            return self.jerr(404, "not found")
        self.send_file(fp)

    def send_file(self, fp: Path) -> None:
        size = fp.stat().st_size
        ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
        if fp.suffix == ".js":
            ctype = "text/javascript"
        rng = self.headers.get("Range")
        start, end, code = 0, size - 1, 200
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                else:
                    start = max(0, size - int(m.group(2)))
                end = min(end, size - 1)
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                code = 206
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if fp.suffix in (".json", ".html", ".js", ".css"):
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            with open(fp, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    b = f.read(min(1 << 16, left))
                    if not b:
                        break
                    self.wfile.write(b)
                    left -= len(b)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ------------------------------------------------------------ API
    def api(self, u: Any) -> None:
        q = parse_qs(u.query)
        parts = u.path.strip("/").split("/")
        try:
            handled = self.api_get(u.path, parts, q)
            if handled:
                return
            if u.path in ("/api/episode", "/api/strip"):
                return self.api_robot(u.path, q)
            return self.jerr(404, "unknown api")
        except ModuleNotFoundError:
            return self.jerr(503, "chat module not available")
        except FileNotFoundError:
            return self.jerr(404, "episode not on disk")
        except KeyError:
            return self.jerr(404, "not found")
        except (ValueError, OSError) as e:
            return self.jerr(400, str(e))
        except Exception as e:
            return self.jerr(500, str(e))

    def api_robot(self, path: str, q: dict[str, list[str]]) -> None:
        ds = q.get("ds", [""])[0]
        ep = int(q.get("ep", ["-1"])[0])
        if path == "/api/episode":
            return self.send_bytes(media.episode_json(ds, ep))
        return self.send_bytes(media.strip_jpeg(ds, ep), ctype="image/jpeg")

    def api_get(self, path: str, parts: list[str], q: dict[str, list[str]]) -> bool:
        def arg(k: str, d: str = "") -> str:
            return q.get(k, [d])[0]

        simple: dict[str, Callable[[], Any]] = {
            "/api/status": runner.status,
            "/api/artifacts": runner.list_artifacts,
            "/api/works": runner.list_works,
            "/api/estimates": runner.list_estimates,
            "/api/exports": runner.list_exports,
            "/api/agent_stats": runner.agent_stats,
        }
        if path in simple:
            self.jok(simple[path]())
        elif path == "/api/jobs":
            self.jok(runner.list_jobs(int(arg("limit", "100"))))
        elif len(parts) == 3 and parts[1] == "jobs":
            j = runner.JOBREG.get(parts[2])
            if not j:
                self.jerr(404, "no such job")
            else:
                d = runner.pub(j)
                d["tail"] = runner.last_line(j)
                self.jok(d)
        elif len(parts) == 4 and parts[1] == "jobs" and parts[3] == "log":
            self.jok(runner.read_log(parts[2], max(0, int(arg("offset", "0")))))
        elif path == "/api/models":
            d = runner.models_info()
            try:
                d["nemotron"] = _chat("llm").nemotron_status()
            except ModuleNotFoundError:
                d["nemotron"] = "down"
            self.jok(d)
        elif path == "/api/work_episodes":
            self.jok(media.work_episodes(arg("work")))
        elif path == "/api/poster":
            try:
                jpg = media.poster_jpeg(arg("work"), arg("ep"), int(arg("w", "320")))
            except KeyError:
                self.jerr(404, "no deid video for this episode")
                return True
            self.send_bytes(jpg, ctype="image/jpeg")
        elif path == "/api/ego_strip":
            try:
                jpg = media.ego_strip_jpeg(arg("work"), arg("ep"), int(arg("n", "8")))
            except KeyError:
                self.jerr(404, "no deid video for this episode")
                return True
            self.send_bytes(jpg, ctype="image/jpeg")
        elif path == "/api/tool":
            try:
                a = json.loads(arg("args", "{}") or "{}")
            except ValueError:
                self.jerr(400, "args must be url-encoded JSON")
                return True
            self.jok(_chat("registry").call(arg("name"), a, {"route": arg("route")}))
        elif path == "/api/tools":
            self.jok(_chat("registry").describe(q.get("route", [None])[0]))
        elif path == "/api/chat/bench":
            b = _chat("llm").latest_bench()
            self.jok(b) if b else self.jerr(404, "no bench run yet")
        elif path == "/api/chat/traces":
            self.jok(_chat("llm").list_traces(int(arg("limit", "20"))))
        elif len(parts) == 4 and parts[1] == "chat" and parts[2] == "traces":
            t = _chat("llm").get_trace(parts[3])
            self.jok(t) if t else self.jerr(404, "no such turn")
        elif len(parts) == 3 and parts[1] == "exports":
            self.export_zip(parts[2])
        elif path == "/api/agent_result":
            self.jok(runner.agent_results(arg("out")))
        elif path == "/api/fs":
            self.jok(runner.fs_list(arg("path")))
        elif path == "/api/dir_check":
            self.jok(runner.dir_check(arg("path")))
        else:
            return False
        return True

    def export_zip(self, name: str) -> None:
        fn = os.path.basename(unquote(name))
        fp = runner.exports_dir() / fn
        if not fn.endswith(".zip") or not fp.is_file():
            return self.jerr(404, "not found")
        data = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{fn}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_server(paths: ConsolePaths | None = None, port: int = 4178) -> ConsoleServer:
    """Bind the console to ``127.0.0.1:port`` (0 = any free port) and init the job runner."""
    paths = paths if paths is not None else active()
    set_active(paths)
    runner.init(paths)
    return ConsoleServer(paths, port)


def serve(paths: ConsolePaths | None = None, port: int = 4178) -> None:
    srv = make_server(paths, port)
    print(f"console on http://127.0.0.1:{srv.port}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()

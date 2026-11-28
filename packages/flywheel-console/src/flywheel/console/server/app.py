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
import signal
import sys
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from flywheel.console.index import catalog, hidden
from flywheel.console.paths import ConsolePaths, PathDenied, active, guard, set_active
from flywheel.console.server import kinds, media, probe, runner, withhold

MAX_JSON = 1 << 20
MAX_UPLOAD = 8 << 30
BODY_TIMEOUT_S = 60.0  # a request body that stops arriving; not applied to responses (video)
CACHE_TTL_S = 3.0  # /api/status and /api/kinds: every page polls them, and each takes 40-80 ms
# the client closed or stopped reading: nothing to answer and nothing to log
GONE = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)
# GETs that expose machine internals; refused with every POST when the server runs with --lock
# the only POSTs a locked server takes, and only when it was started with ``chat``
CHAT_POST = ("/api/chat", "/api/models/prewarm", "/api/models/connect")
LOCKED_GET = ("/api/fs", "/api/dir_check", "/api/tool", "/api/chat/traces")
# home directories (home or Users, then the user name) in JSON answers of a locked server
_HOME = re.compile(r"/(?:home|Users)/[^/\s\"]+/")
_lock = threading.Lock()


def _chat_missing(e: ModuleNotFoundError) -> bool:
    """True only when the missing module is a ``flywheel.console.chat`` one."""
    return (e.name or "").startswith("flywheel.console.chat")


def _chat(mod: str) -> Any:
    """Lazy import of ``flywheel.console.chat.<mod>`` (Task 6 module; absent until it lands)."""
    return importlib.import_module(f"flywheel.console.chat.{mod}")


class _Unfilterable(Exception):
    """An index file needed to tell what to hide cannot be used; the request is refused."""


def _checked(doc: Any, hide: hidden.Hidden) -> Any:
    """``doc`` when it has the shape of a catalog. The filters of ``hidden`` leave a shape
    they do not know as it is, which here would mean unfiltered, so it is refused while a run
    is hidden."""
    if hide and not (isinstance(doc, dict) and isinstance(doc.get("rows"), list)):
        raise _Unfilterable("not a catalog document")
    return doc


def _read_catalog(index: Path, hide: hidden.Hidden) -> Any:
    try:
        doc = json.loads((index / "catalog.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise _Unfilterable("catalog.json cannot be read") from e
    return _checked(doc, hide)


def _task_datasets(doc: Any, index: Path, hide: hidden.Hidden) -> Any:
    """``tasks[].catalog_rows`` cut to the datasets the filtered ``catalog.json`` shows, and
    ``catalog_totals`` counted again. The trimmed rows carry no story or notes to judge by; an
    id the catalog does not show is hidden or left over from an older build."""
    tasks = doc.get("tasks") if isinstance(doc, dict) else None
    if not hide or not isinstance(tasks, list) or not any(t.get("catalog_rows") for t in tasks):
        return doc
    cat = hidden.catalog_doc(_read_catalog(index, hide), hide)
    shown = {str(r.get("id")): r for r in cat["rows"]}
    out = []
    for t in tasks:
        rows = t.get("catalog_rows") or []
        kept = [r for r in rows if str(r.get("id")) in shown]
        if len(kept) < len(rows):
            totals = catalog.totals([shown[str(r["id"])] for r in kept])
            t = {**t, "catalog_rows": kept, "catalog_totals": totals}
        out.append(t)
    return {**doc, "tasks": out}


class _Cache:
    """Values kept for a few seconds; requests that arrive together wait for one computation."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[float, Any]] = {}
        self._locks: dict[str, threading.Lock] = {}

    def get(self, key: str, make: Callable[[], Any]) -> Any:
        with self._locks.setdefault(key, threading.Lock()):
            hit = self._items.get(key)
            if hit is None or time.monotonic() - hit[0] >= CACHE_TTL_S:
                hit = self._items[key] = (time.monotonic(), make())
            return hit[1]

    def clear(self) -> None:
        self._items.clear()


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True
    # the default of 5 drops connections when a page opens many at once (HTTP/1.0: one each)
    request_queue_size = 128

    def __init__(
        self, paths: ConsolePaths, port: int, lock: bool = False, chat: bool = False
    ) -> None:
        self.paths = paths
        self.locked = lock
        # the chat is on unless the server is locked; ``chat`` keeps it on while locked: it reads
        # the index and starts nothing, so a recording can use one read-only server
        self.chat_on = (not lock) or chat
        self.cache = _Cache()
        super().__init__(("127.0.0.1", port), Handler)

    def handle_error(self, request: Any, client_address: Any) -> None:
        if isinstance(sys.exc_info()[1], (*GONE, TimeoutError)):
            return
        super().handle_error(request, client_address)

    def unredact(self, value: str) -> str:
        """Inverse of ``redact`` for a path a page sends back (e.g. ``out=fwdata/console/...``)."""
        if value == "fwdata" or value.startswith("fwdata/"):
            return str(self.paths.fw_root) + value[len("fwdata") :]
        if value.startswith("~/"):
            return str(Path.home()) + value[1:]
        return value

    def redact(self, text: str) -> str:
        """Machine paths out of a JSON answer: fw_root becomes ``fwdata``, any home dir ``~``."""
        root = json.dumps(str(self.paths.fw_root))[1:-1]
        return _HOME.sub("~/", text.replace(root, "fwdata"))

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
        text = json.dumps({"error": msg}, ensure_ascii=False)
        if self.server.locked:  # error messages can carry the path that was refused
            text = self.server.redact(text)
        self.send_bytes(text.encode(), code)

    def jok(self, obj: Any, code: int = 200) -> None:
        text = json.dumps(obj, ensure_ascii=False)
        if self.server.locked:
            text = self.server.redact(text)
        self.send_bytes(text.encode(), code)

    # ------------------------------------------------------------ POST
    def do_POST(self) -> None:
        u = urlparse(self.path)
        if not u.path.startswith("/api/"):
            return self.jerr(404, "not found")
        if not self.host_ok() or not self.origin_ok():
            return self.jerr(403, "forbidden origin")
        if self.server.locked and not (self.server.chat_on and u.path in CHAT_POST):
            return self.jerr(403, "locked")
        self.server.cache.clear()  # a POST can start or cancel work: show it at once
        try:
            if u.path == "/api/upload":
                return self.upload(u)
            n = self.content_length()
            if n > MAX_JSON:
                return self.jerr(413, "body too large")
            body = self.read_json(n)
            parts = u.path.strip("/").split("/")
            if u.path == "/api/chat":
                return self.chat_sse(body)
            if u.path == "/api/chat/config":
                # the setting lives in the chat layer only: the environment keeps what the
                # operator set, so FW_CHAT_API_KEY and FW_CHAT_SELF_HOSTED stay with the start-up
                # URL, and a new host needs its own key (A3, S-P0-3, 28/11/2026)
                return self.jok(_chat("providers").set_runtime_config(body))
            if u.path == "/api/models/prewarm":
                return self.jok(probe.prewarm(_chat("llm"), _chat("providers")))
            if u.path == "/api/jobs":
                params = body.get("params") or {}
                if not isinstance(params, dict):
                    return self.jerr(400, "params must be a JSON object")
                job = runner.submit(str(body.get("kind")), params)
                return self.jok(runner.pub(job), 201)
            if len(parts) == 4 and parts[1] == "jobs" and parts[3] == "cancel":
                return self.jok(runner.cancel(parts[2]))
            if u.path == "/api/models/connect":
                runner.TUNNEL.ensure(15)
                return self.jok(runner.models_info())
            return self.jerr(404, "unknown api")
        except ModuleNotFoundError as e:
            if _chat_missing(e):
                return self.jerr(503, "chat module not available")
            return self.jerr(500, str(e))
        except runner.NotFound:
            return self.jerr(404, "not found")
        except ValueError as e:
            return self.jerr(400, str(e))
        except GONE:
            raise
        except Exception as e:
            return self.jerr(500, str(e))

    def content_length(self, missing: int = 0) -> int:
        raw = (self.headers.get("Content-Length") or "").strip()
        if not raw:
            return missing
        if not re.fullmatch(r"[0-9]{1,18}", raw):
            raise ValueError("Content-Length must be a non-negative integer")
        return int(raw)

    def read_json(self, n: int) -> dict[str, Any]:
        """The JSON object of a POST (``{}`` without a body)."""
        if not n:
            return {}
        self.connection.settimeout(BODY_TIMEOUT_S)
        try:
            raw = self.rfile.read(n)
        except TimeoutError:
            raw = b""
        finally:
            self.connection.settimeout(None)
        if len(raw) < n:
            raise ValueError("body shorter than Content-Length")
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise ValueError("body must be a JSON object")
        return body

    def chat_sse(self, body: dict[str, Any]) -> None:
        """text/event-stream; the client closing the socket stops the turn."""
        llm = _chat("llm")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        gen = None
        try:
            gen = llm.stream(body)
            for chunk in gen:
                if self.server.locked:  # tool results (a job's argv, a log) can carry machine paths
                    chunk = self.server.redact(chunk.decode("utf-8")).encode("utf-8")
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
        n = self.content_length(missing=-1)
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
            self.connection.settimeout(BODY_TIMEOUT_S)
            with open(tmp, "wb") as f:
                while left > 0:
                    try:
                        b = self.rfile.read(min(1 << 20, left))
                    except TimeoutError:
                        b = b""
                    if not b:
                        break
                    f.write(b)
                    left -= len(b)
            self.connection.settimeout(None)
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
            ("/simmedia/", self.paths.sim_media),
            ("/demomedia/", self.paths.demo_media),
        ]
        ego = media.ego_viewer_dir()
        if ego is not None:
            mounts.append(("/ego/", ego))
        if up.startswith("/media/"):
            ds, _, rest = up[len("/media/") :].partition("/")
            try:
                return _safe_join(media.media_root(ds), rest)
            except runner.NotFound:
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
        try:
            fp = self.resolve(u.path)
            # a mounted folder asked for by its own URL (/ego/, the viewer's home) serves its
            # index.html
            if fp is not None and fp.is_dir() and u.path.endswith("/"):
                fp = fp / "index.html"
            found = fp is not None and fp.is_file()
        except (OSError, ValueError):  # a name the file system refuses (too long)
            fp, found = None, False
        # before anything answers for a dataset, the 204 of a missing qa.json included
        if fp is not None and self.refused_dataset(fp):
            return
        if fp is None or not found:
            if fp is not None and self.no_qa(fp):
                self.send_response(204)  # the pages ask for every dataset; this one has no checks
                return self.end_headers()
            return self.jerr(404, "not found")
        # filtered by the file that would be sent, not by the URL: /data/./story.json,
        # /data/story.json/ and the like name the same file
        index = self.paths.index.resolve()
        if fp in (index / n for n in ("catalog.json", "story.json", "tasks.json")):
            return self.send_index(fp)
        self.send_file(fp)

    def refused_dataset(self, fp: Path) -> bool:
        """Answer 404 for any file of a hidden run's dataset (``ds/<id>/``), or 500 when the
        seed or ``catalog.json`` cannot say which those are; ``False`` when ``fp`` may be
        served. The dataset cards are asked too: a folder left by an older build has no row in
        a catalog built since."""
        ds = (self.paths.index / "ds").resolve()
        if ds not in fp.parents:
            return False
        try:
            hide = runner.hidden_runs()
            if not hide:
                return False
            gone = hidden.catalog_hidden_ids(_read_catalog(self.paths.index, hide), hide)
            gone |= runner.hidden_data_names(hide)
        except (runner.ManifestUnreadable, _Unfilterable) as e:
            self.jerr(500, str(e))
            return True
        except Exception:  # unfiltered is worse than unavailable
            self.jerr(500, "the hidden datasets cannot be told apart")
            return True
        if fp.relative_to(ds).parts[0] not in gone:
            return False
        self.jerr(404, "not found")
        return True

    def no_qa(self, fp: Path) -> bool:
        """``fp`` is the missing ``qa.json`` of an indexed dataset."""
        return (
            fp.name == "qa.json"
            and fp.parent.parent == self.paths.index.resolve() / "ds"
            and (fp.parent / "quality.json").is_file()
        )

    def send_index(self, fp: Path) -> None:
        """``catalog.json`` / ``story.json`` / ``tasks.json`` without the runs a round does not
        present.

        ``withhold_runs`` (hidden.py): nothing of the run, even from an index built before the
        switch, the datasets of its story included. ``withhold_eval`` (withhold.py): the result
        blocks of a held run never reach the browser. Both lists come from the seed; the file
        is never sent as it is, and a list or a file that cannot be read refuses the request.
        """
        try:
            hide = runner.hidden_runs()
            held = runner._withheld_runs() if fp.name == "story.json" else set()
        except runner.ManifestUnreadable as e:
            return self.jerr(500, str(e))
        try:
            doc = json.loads(fp.read_text(encoding="utf-8"))
        except ValueError:
            return self.jerr(500, "index file is not valid JSON")
        try:
            if fp.name == "catalog.json":
                doc = hidden.catalog_doc(_checked(doc, hide), hide)
            elif fp.name == "tasks.json":
                doc = _task_datasets(hidden.tasks_doc(doc, hide), self.paths.index, hide)
            else:
                if not isinstance(doc, dict):
                    raise TypeError("story.json is not an object")
                doc = withhold.story(hidden.story(doc, hide), held)
                if doc.get("ds") is not None:  # the catalog the story page draws from
                    doc = {**doc, "ds": hidden.catalog_doc(_checked(doc["ds"], hide), hide)}
        except _Unfilterable as e:
            return self.jerr(500, str(e))
        except Exception:  # unfiltered is worse than unavailable
            return self.jerr(500, "index file has an unexpected shape")
        self.send_bytes(json.dumps(doc, ensure_ascii=False).encode())

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
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
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
        except (*GONE, TimeoutError):
            pass

    # ------------------------------------------------------------ API
    def api(self, u: Any) -> None:
        q = parse_qs(u.query)
        if self.server.locked:  # pages send back the redacted paths they were given
            q = {k: [self.server.unredact(v) for v in vs] for k, vs in q.items()}
        parts = u.path.strip("/").split("/")
        if self.server.locked and (
            u.path in LOCKED_GET
            or (len(parts) == 3 and parts[1] == "exports")
            or u.path.startswith("/api/chat/traces/")
        ):
            return self.jerr(403, "locked")
        try:
            handled = self.api_get(u.path, parts, q)
            if handled:
                return
            if u.path in ("/api/episode", "/api/strip"):
                return self.api_robot(u.path, q)
            return self.jerr(404, "unknown api")
        except ModuleNotFoundError as e:
            if _chat_missing(e):
                return self.jerr(503, "chat module not available")
            return self.jerr(500, str(e))
        except GONE:
            raise
        except runner.ManifestUnreadable as e:
            return self.jerr(500, str(e))
        except FileNotFoundError:
            return self.jerr(404, "episode not on disk")
        except runner.NotFound:
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
            "/api/status": lambda: self.server.cache.get("status", lambda: runner.status())
            | {"locked": self.server.locked, "chat_on": self.server.chat_on},
            "/api/artifacts": runner.list_artifacts,
            "/api/works": runner.list_works,
            "/api/estimates": runner.list_estimates,
            "/api/exports": runner.list_exports,
            "/api/agent_stats": runner.agent_stats,
            "/api/kinds": lambda: self.server.cache.get(
                "kinds", lambda: kinds.catalog(self.server.locked)
            ),
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
                llm = _chat("llm")
                d["nemotron"] = llm.nemotron_status()
                if hasattr(llm, "provider"):
                    p = llm.provider()
                    prob = (  # asks the model itself, unless the chat is off
                        probe.check(llm, _chat("providers"), p)
                        if self.server.chat_on
                        else "chat is off"
                    )
                    if prob and p.kind != "ollama":
                        d["nemotron"] = "down"
                    d["chat"] = {
                        "provider": p.name,
                        "kind": p.kind,
                        "model": p.model,
                        "hosted": p.hosted,
                        "ready": prob is None,
                        "problem": prob,
                    }
            except ModuleNotFoundError as e:
                if not _chat_missing(e):
                    raise
                d["nemotron"] = "down"
            self.jok(d)
        elif path == "/api/chat/config":
            llm = _chat("llm")
            prov_mod = _chat("providers")
            self.jok(prov_mod.get_runtime_config(llm.ENDPOINT, llm.MODEL))
        elif path == "/api/chat/remote_models":
            p = _chat("llm").provider()
            if not self.server.chat_on or p.kind == "ollama" or not p.key:
                self.jok({"models": []})
                return True
            try:
                self.jok({"models": probe.model_ids(p, arg("q"))})
            except Exception:
                self.jok({"models": [p.model] if p.model else []})
        elif path == "/api/work_episodes":
            self.jok(media.work_episodes(arg("work")))
        elif path == "/api/poster":
            try:
                jpg = media.poster_jpeg(arg("work"), arg("ep"), int(arg("w", "320")))
            except runner.NotFound:
                self.jerr(404, "no deid video for this episode")
                return True
            self.send_bytes(jpg, ctype="image/jpeg")
        elif path == "/api/ego_strip":
            try:
                jpg = media.ego_strip_jpeg(arg("work"), arg("ep"), int(arg("n", "8")))
            except runner.NotFound:
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
            self.jok(_chat("llm").list_traces(int(arg("limit", "20")), runner._withheld_runs()))
        elif len(parts) == 4 and parts[1] == "chat" and parts[2] == "traces":
            t = _chat("llm").get_trace(parts[3], runner._withheld_runs())
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


def make_server(
    paths: ConsolePaths | None = None, port: int = 4178, lock: bool = False, chat: bool = False
) -> ConsoleServer:
    """Bind the console to ``127.0.0.1:port`` (0 = any free port) and init the job runner.

    ``lock`` refuses every POST and the internal GETs in ``LOCKED_GET`` (demo laptop)."""
    paths = paths if paths is not None else active()
    set_active(paths)
    runner.init(paths)
    return ConsoleServer(paths, port, lock, chat)


def _warm_chat() -> None:
    """Open the tunnel and load the chat model once, so the first question does not wait for it."""
    try:
        probe.prewarm(_chat("llm"), _chat("providers"))
    except Exception:  # the chat is optional: a model that is down must not stop the server
        pass


def serve(
    paths: ConsolePaths | None = None, port: int = 4178, lock: bool = False, chat: bool = False
) -> None:
    srv = make_server(paths, port, lock, chat)

    def stop(signum: int, frame: Any) -> None:  # `kill`: close the ssh tunnel like Ctrl+C does
        signal.signal(signal.SIGTERM, signal.SIG_IGN)  # a second kill must not cut the cleanup
        raise KeyboardInterrupt

    on_main = threading.current_thread() is threading.main_thread()
    mode = " (locked, chat on)" if lock and chat else " (locked)" if lock else ""
    try:
        # inside the try: the handler raises wherever the program is, the banner included
        if on_main:
            signal.signal(signal.SIGTERM, stop)
        print(f"console on http://127.0.0.1:{srv.port}" + mode, flush=True)
        if srv.chat_on:
            threading.Thread(target=_warm_chat, daemon=True).start()
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        runner.TUNNEL.close()
        if on_main:  # nothing left to protect: a process stuck in exit can still be killed
            signal.signal(signal.SIGTERM, signal.SIG_DFL)

"""Render the 60-rollout ladder of the eval page in headless Chrome from a copy of the real index
block (``story.jig.compare60``, PR #266) and fail when a cell reads "not available".

The page's ES modules run unchanged: a local HTTP server serves ``web/`` plus a test page that
imports ``pages_story.js``. Skipped when no Chrome is installed.
"""

import functools
import html
import http.server
import json
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import pytest
from flywheel.console import budget

WEB = Path(budget.__file__).parent / "web"
FIXTURE = Path(__file__).parent / "web_fixtures" / "compare60_ladder.json"
CHROME = next(
    (c for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)), None
)

PAGE = """<!doctype html><meta charset="utf-8"><body><pre id="out">pending</pre>
<script>try { localStorage.setItem("fw_lang", "%(lang)s"); } catch (e) {}</script>
<script type="module">
import { compare60Ladder, renderCompare60Ladder } from "/pages_story.js";
const out = document.getElementById("out");
try {
  const c60 = await (await fetch("/__fixture.json")).json();
  const node = renderCompare60Ladder(compare60Ladder({ jig: { compare60: c60 } }));
  out.textContent = JSON.stringify({
    heads: [...node.querySelectorAll("thead th .ladder-run")].map((x) => x.textContent),
    rows: [...node.querySelectorAll("tbody tr")]
      .map((tr) => [...tr.children].map((x) => x.textContent)),
    notes: [...node.querySelectorAll(".ladder-notes li")].map((x) => x.textContent),
  });
} catch (e) { out.textContent = "ERROR " + e; }
</script>"""


MODULES_PAGE = """<!doctype html><meta charset="utf-8"><body><pre id="out">pending</pre>
<script type="module">
const out = document.getElementById("out");
const names = %(names)s;
const bad = [];
for (const name of names) {
  try { await import("/" + name); } catch (e) { bad.push(name + ": " + e); }
}
out.textContent = JSON.stringify({ bad });
</script>"""


class _Handler(http.server.SimpleHTTPRequestHandler):
    lang = "vi"
    page = PAGE

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        if self.path.startswith("/__ladder.html") or self.path.startswith("/__fixture.json"):
            html = self.path.startswith("/__ladder.html")
            body = self.page.encode() if html else FIXTURE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html" if html else "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, *args: object) -> None:
        pass


def _render(lang: str, page: str | None = None) -> dict:
    page = page if page is not None else PAGE % {"lang": lang}
    handler = type("H", (_Handler,), {"lang": lang, "page": page})
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(handler, directory=str(WEB))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory() as profile:
            argv = [str(CHROME), "--headless=new", "--disable-gpu", "--no-sandbox",
                    f"--user-data-dir={profile}", "--virtual-time-budget=10000", "--dump-dom",
                    f"http://127.0.0.1:{server.server_address[1]}/__ladder.html"]  # fmt: skip
            dom = subprocess.run(argv, capture_output=True, text=True, timeout=90).stdout
    finally:
        server.shutdown()
    text = dom.split('<pre id="out">', 1)[1].split("</pre>", 1)[0]
    text = html.unescape(text)
    assert not text.startswith(("ERROR", "pending")), text
    return json.loads(text)


@pytest.mark.skipif(CHROME is None, reason="no headless Chrome")
@pytest.mark.parametrize(
    ("lang", "na", "pct"), [("vi", "Chưa có", "78,3 %"), ("en", "Not available", "78.3%")]
)
def test_ladder_cells_are_filled_from_the_real_block(lang: str, na: str, pct: str) -> None:
    got = _render(lang)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))["ladder"]
    assert got["heads"] == [r["run"] for r in fixture["runs"]]
    # success, relaxed at every threshold but the first, reach B, two deviation rows, yaw <= 10
    assert len(got["rows"]) == 1 + (len(fixture["thresholds_cm"]) - 1) + 1 + 2 + 1
    cells = [c for row in got["rows"] for c in row[1:]]
    assert len(cells) == len(got["rows"]) * len(fixture["runs"])
    assert not [c for c in cells if na in c or not c.strip()], got["rows"]
    assert got["rows"][0][-1] == f"47/60 · {pct}"  # M, success at repeat 0
    assert got["rows"][-1][-1].startswith("55/60 · ")  # M, rotation <= 10 of reached B
    assert "42–47/60" in got["notes"][-1]


@pytest.mark.skipif(CHROME is None, reason="no headless Chrome")
def test_every_page_module_loads() -> None:
    """A syntax error or a missing import in any page module breaks its route; load them all."""
    names = sorted(p.name for p in WEB.glob("pages_*.js")) + ["core.js", "chat.js"]
    got = _render("vi", MODULES_PAGE % {"names": json.dumps(names)})
    assert got["bad"] == [], got["bad"]

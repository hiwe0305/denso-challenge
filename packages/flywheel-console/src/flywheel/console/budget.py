"""Static-text word budget for the console web UI (port of the v5 word_budget tool).

A literal counts when it is user-visible chrome written in the source: a JS string or template
literal (``${...}`` parts removed) in ``*.js``, or an HTML text node or placeholder/aria-label/alt
attribute in ``index.html``. Words are whitespace tokens with at least one letter. A literal counts
toward the per-file budget when it has two or more words, or one capitalised word, or is the value
of ``text:``/``placeholder:``/``label:``/``textContent``; it is a violation when it has more than
eight words. Tooltips (``title``), CSS/selector/URL/code-like strings, regexes, comments and
anything between ``@budget-skip-start`` and ``@budget-skip-end`` are never counted.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

MAX_WORDS = 8
BUDGET: dict[str, int] = {
    "pages_data.js": 40 + 50 + 30,
    "pages_ops.js": 30 + 40,
    "pages_story.js": 50 + 60 + 50,
    "app.js": 130,
    "chat.js": 60,
    "core.js": 60,
    "index.html": 20,
    "tour.js": 10,
    "ring.js": 25,
}
PREFIX_SKIP = re.compile(
    r"(class|className|style|href|src|id|type|key|name|for|rel|target|role|method|cursor|display|color|background|position|width|height)\s*[:=]\s*$"
    r"|(querySelector|querySelectorAll|getElementById|classList\.\w+|closest|matches|getAttribute|setAttribute|addEventListener|createElement|createElementNS|getPropertyValue|setProperty|\$|\$\$|cssv|fetch|J|api|jget|require|include|startsWith|endsWith|indexOf|includes|replace|split|test|match|go|emit|on)\s*\(\s*$"
)
PREFIX_TITLE = re.compile(r"\btitle\s*[:=]\s*$")
PREFIX_TEXT = re.compile(r"\b(text|placeholder|label|textContent|innerText|alt)\s*[:=]\s*$")
CODEISH = re.compile(r"[=;{}<>\\^|]|=>|^\s*[./#@\[]|https?:|\b[a-z]+\.[a-z]+\(")


def _words(s: str) -> list[str]:
    return [w for w in s.split() if re.search(r"[^\W\d_]", w)]


def _decode(raw: str) -> str:
    out = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), raw)
    return out.replace("\\n", " ").replace('\\"', '"').replace("\\'", "'").replace("\\`", "`")


def _scan_js(src: str) -> list[tuple[int, str, str]]:
    """Return (line, literal text, 40 chars of prefix) for every string/template literal."""
    out: list[tuple[int, str, str]] = []
    n = len(src)

    def line_of(i: int) -> int:
        return src.count("\n", 0, i) + 1

    def code(i: int, stop_brace: bool = False) -> int:
        depth = 0
        while i < n:
            c = src[i]
            if c == "/" and src[i + 1 : i + 2] == "/":
                j = src.find("\n", i)
                i = n if j < 0 else j
            elif c == "/" and src[i + 1 : i + 2] == "*":
                j = src.find("*/", i + 2)
                i = n if j < 0 else j + 2
            elif c in "\"'":
                j = i + 1
                while j < n and src[j] != c:
                    j += 2 if src[j] == "\\" else 1
                out.append((line_of(i), src[i + 1 : j], src[max(0, i - 40) : i]))
                i = j + 1
            elif c == "`":
                i = template(i)
            elif c == "/":
                prev = src[max(0, i - 40) : i].rstrip()[-1:]
                if (
                    prev == ""
                    or prev in "(,=:[!&|?{};"
                    or re.search(r"\b(return|typeof)\s*$", src[max(0, i - 12) : i])
                ):
                    j, cls = i + 1, False
                    while j < n and (src[j] != "/" or cls) and src[j] != "\n":
                        if src[j] == "\\":
                            j += 1
                        elif src[j] == "[":
                            cls = True
                        elif src[j] == "]":
                            cls = False
                        j += 1
                    i = j + 1
                else:
                    i += 1
            elif c == "{":
                depth += 1
                i += 1
            elif c == "}":
                if stop_brace and depth == 0:
                    return i + 1
                depth -= 1
                i += 1
            else:
                i += 1
        return i

    def template(i: int) -> int:
        start, j, buf = i, i + 1, []
        while j < n and src[j] != "`":
            if src[j] == "\\":
                buf.append(src[j : j + 2])
                j += 2
            elif src[j] == "$" and src[j + 1 : j + 2] == "{":
                buf.append(" ")
                j = code(j + 2, True)
            else:
                buf.append(src[j])
                j += 1
        out.append((line_of(start), "".join(buf), src[max(0, start - 40) : start]))
        return j + 1

    code(0)
    return out


def _strip_skips(src: str) -> str:
    def blank(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    return re.sub(r"@budget-skip-start.*?@budget-skip-end", blank, src, flags=re.S)


class _HtmlText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[tuple[int, str]] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.skip += 1
        for k, v in attrs:
            if k in ("placeholder", "aria-label", "alt") and v:
                self.items.append((self.getpos()[0], v))

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip and data.strip():
            self.items.append((self.getpos()[0], data.strip()))


def _literals(path: Path) -> list[tuple[int, str, bool]]:
    """Return (line, text, counted) for every static literal of one file."""
    src = _strip_skips(path.read_text(encoding="utf-8"))
    if path.suffix == ".html":
        p = _HtmlText()
        p.feed(src)
        return [(ln, t, True) for ln, t in p.items]
    lits: list[tuple[int, str, bool]] = []
    for ln, raw, pre in _scan_js(src):
        if PREFIX_TITLE.search(pre) or PREFIX_SKIP.search(pre):
            continue
        t = _decode(raw)
        if CODEISH.search(t) and not PREFIX_TEXT.search(pre):
            continue
        ws = _words(t)
        if not ws:
            continue
        counted = len(ws) >= 2 or ws[0][0].isupper() or bool(PREFIX_TEXT.search(pre))
        lits.append((ln, t, counted))
    return lits


def count(web: Path) -> dict[str, tuple[int, int]]:
    """Map each budgeted file present in ``web`` to ``(words counted, budget)``."""
    result: dict[str, tuple[int, int]] = {}
    for name, limit in BUDGET.items():
        path = web / name
        if path.is_file():
            total = sum(len(_words(t)) for _, t, counted in _literals(path) if counted)
            result[name] = (total, limit)
    return result


def long_literals(web: Path) -> list[tuple[str, int, int, str]]:
    """Return (file, line, words, text) for every literal longer than ``MAX_WORDS`` words."""
    bad: list[tuple[str, int, int, str]] = []
    for name in BUDGET:
        path = web / name
        if path.is_file():
            for ln, t, _ in _literals(path):
                nw = len(_words(t))
                if nw > MAX_WORDS:
                    bad.append((name, ln, nw, t[:90]))
    return bad

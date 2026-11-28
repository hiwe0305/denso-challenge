"""W1 wording in chat answers (docs/he/tray-jig.md §2): "đạt" / "met" is the verdict of a CI
lower bound reaching a mark, never a count.

The prompt says so, yet a live replay on 28/11/2026 still wrote "M đạt 136/180 lượt thành
công" in two answers of three, so the stream rewrites "<x> đạt <k>/<n>" to "<x>: <k>/<n>"
(", <k>/<n>" after a comma). "đạt mốc 80 %" is left as it is, and so are "chưa đạt <k>/<n>"
and a table cell that starts with "đạt", which a rewrite would only make harder to read.
"""

from __future__ import annotations

import re

# " đạt 136/180", ", đạt được 47/60", " met **10/60": the word and its spaces, before a count
_FIX = re.compile(
    r"(?<!chưa)(?<!not)(?<!\|)(,?)[ \t]+(?:đạt(?:[ \t]+được)?|met)[ \t]+"
    r"(?=\**[ \t]*\d+[ \t]*/[ \t]*\d)",
    re.I,
)
# what the stream keeps back: trailing spaces (a "đạt" may follow), the last, unfinished word,
# and a "đạt" still waiting for its count
_TAIL = re.compile(
    r",?[ \t]*(?:(?:đạt(?:[ \t]+được)?|met)\b[ \t]*\**[ \t]*(?:\d+[ \t]*/?[ \t]*)?)?[^\s]*$", re.I
)
_CTX = 4  # released characters kept for the look-behinds ("chưa", "not", "|")


def _sub(m: re.Match[str]) -> str:
    return ", " if m.group(1) else ": "


def fix(text: str) -> str:
    """A whole answer with each count written as a count."""
    return _FIX.sub(_sub, text)


class Stream:
    """The same rewrite on a token stream: ``feed`` returns the text that is safe to send."""

    def __init__(self) -> None:
        self.held = ""
        self.ctx = ""

    def _fix(self, text: str) -> str:
        # a match starts after the context: the context never ends in a space or a comma
        fixed = fix(self.ctx + text)
        return fixed[len(self.ctx) :] if fixed.startswith(self.ctx) else fix(text)

    def feed(self, token: str) -> str:
        text = self._fix(self.held + token)
        m = _TAIL.search(text)
        cut = m.start() if m else len(text)
        self.held = text[cut:]
        self.ctx = (self.ctx + text[:cut])[-_CTX:]
        return text[:cut]

    def flush(self) -> str:
        text, self.held = self._fix(self.held), ""
        self.ctx = (self.ctx + text)[-_CTX:]
        return text

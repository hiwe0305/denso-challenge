"""Chart blocks in chat answers: a fenced ```chart block holding a small, fixed JSON spec.

The model may draw at most two bar or line charts per answer. The spec carries only labels and
numbers, never chart-library options, functions or HTML:

    {"type": "bar" | "line", "title": str, "unit": str, "x": [labels],
     "series": [{"name": str, "data": [numbers]}]}

The web panel draws a valid block and shows an invalid one as a note plus a table; the server
checks every number of a block (data, and the numbers in its labels) the way it checks the text.
web/chat.js ``parseChartSpec`` applies the same rules.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

from .numbers import numbers_any

MAX_CHARTS = 2
MAX_X = 12
MAX_SERIES = 6
TYPES = ("bar", "line")
_TOP_KEYS = {"type", "title", "unit", "x", "series"}
_SERIES_KEYS = {"name", "data"}

# a ```chart fence and its body, up to the closing fence (or the end of an unclosed answer)
FENCE = re.compile(r"^[ \t]*```chart[ \t]*\n(.*?)(?:\n[ \t]*```[ \t]*$|\Z)", re.S | re.M)


@dataclass
class Chart:
    raw: str
    spec: dict[str, Any] | None = None
    error: str | None = None
    numbers: list[str] = field(default_factory=list)


def fmt(v: float) -> str:
    """A data value as the check and the web both write it: 136, 75.6, 0.842."""
    return str(int(v)) if float(v).is_integer() and abs(v) < 1e15 else repr(float(v))


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate(obj: Any) -> str | None:
    """Why ``obj`` is not a chart spec, or None when it is one."""
    if not isinstance(obj, dict):
        return "not an object"
    if set(obj) - _TOP_KEYS:
        return "unknown keys: " + ", ".join(sorted(set(obj) - _TOP_KEYS))
    if obj.get("type") not in TYPES:
        return "type must be bar or line"
    for key in ("title", "unit"):
        if key in obj and not isinstance(obj[key], str):
            return f"{key} must be text"
    x = obj.get("x")
    if not isinstance(x, list) or not x or len(x) > MAX_X:
        return f"x must hold 1 to {MAX_X} labels"
    if not all(isinstance(lb, str) or _is_number(lb) for lb in x):
        return "x labels must be text or numbers"
    series = obj.get("series")
    if not isinstance(series, list) or not series or len(series) > MAX_SERIES:
        return f"series must hold 1 to {MAX_SERIES} entries"
    for s in series:
        if not isinstance(s, dict) or set(s) - _SERIES_KEYS:
            return "each series is {name, data}"
        if not isinstance(s.get("name", ""), str):
            return "each series is {name, data}"
        data = s.get("data")
        if not isinstance(data, list) or len(data) != len(x):
            return "each series needs one value per x label"
        for v in data:
            if not _is_number(v):
                return "data must be numbers"
    return None


def _label_numbers(spec: dict[str, Any]) -> list[str]:
    texts = [spec.get("title") or "", spec.get("unit") or ""]
    texts += [str(lb) for lb in spec["x"]] + [str(s.get("name") or "") for s in spec["series"]]
    return [tok for t in texts for tok in numbers_any(t)]


def parse(raw: str) -> Chart:
    """One block body: the spec and its numbers, or the reason it cannot be drawn."""
    chart = Chart(raw=raw)
    try:
        obj = json.loads(raw)
    except ValueError:
        chart.error = "not valid JSON"
    else:
        chart.error = validate(obj)
        if chart.error is None:
            chart.spec = obj
            data = [fmt(v) for s in obj["series"] for v in s["data"]]
            chart.numbers = _label_numbers(obj) + data
            return chart
    # an invalid block is still checked: its numbers, read apart from the JSON punctuation
    chart.numbers = numbers_any(re.sub(r'[\[\]{}:,"]', " ", raw))
    return chart


def split(answer: str) -> tuple[str, list[Chart]]:
    """The answer without its chart blocks, and the blocks in order (the third on is invalid)."""
    charts: list[Chart] = []
    for m in FENCE.finditer(answer):
        chart = parse(m.group(1).strip())
        if len(charts) >= MAX_CHARTS and chart.spec is not None:
            chart.spec, chart.error = None, f"at most {MAX_CHARTS} charts per answer"
        charts.append(chart)
    return FENCE.sub("\n", answer), charts

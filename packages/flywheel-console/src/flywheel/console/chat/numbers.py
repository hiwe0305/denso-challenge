"""Number grounding for chat answers: which numerals of an answer appear in the turn's evidence.

Same rules as the Agent QA number check (identifiers are not numbers; ``12k`` is twelve
thousand; a percentage may match a fraction), kept here because the console imports no lane.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

_UNITS = "ms|s|sec|min|h|hz|khz|kb|mb|gb|px|cm|mm|m|x|k|fps"
_NUMBER = re.compile(
    r"(?<![\w.\-/])[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?:e[-+]?\d+)?"
    rf"(?:%|(?:{_UNITS})\b)?(?![\w\-/])",
    re.IGNORECASE,
)
_FRACTION = re.compile(r"(?<![\w.\-/])(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)(?![\w\-/])")
_TOKEN = re.compile(r"([-+]?[\d.,]+(?:e[-+]?\d+)?)(%|[a-z]+)?", re.IGNORECASE)


def numbers_in(text: str) -> list[str]:
    """The bare numbers of ``text`` in the order they appear."""
    stripped = _FRACTION.sub(lambda m: f" {m.group(1)} {m.group(2)} ", text)
    return [m.group(0) for m in _NUMBER.finditer(stripped)]


def _parse(token: str) -> tuple[float, bool, int] | None:
    """(value, is_percent, decimals written); a unit is dropped, ``k`` multiplies by 1000."""
    match = _TOKEN.fullmatch(token)
    if match is None:
        return None
    body, suffix = match.group(1).replace(",", ""), (match.group(2) or "").lower()
    try:
        value = float(body)
    except ValueError:
        return None
    mantissa = body.lower().split("e")[0]
    decimals = len(mantissa.split(".")[1]) if "." in mantissa else 0
    if suffix == "k":
        value, decimals = value * 1000.0, decimals - 3
    return value, suffix == "%", decimals


def _matches(written: float, decimals: int, fact: float) -> bool:
    if not math.isfinite(fact):
        return False
    if math.isclose(written, fact, rel_tol=1e-9, abs_tol=1e-12):
        return True
    if round(fact, decimals) == round(written, decimals):
        return True
    if fact != 0 and written != 0:
        digits = max(1, len(re.sub(r"[^0-9]", "", f"{written:g}").lstrip("0")))
        return f"{fact:.{digits}g}" == f"{written:.{digits}g}"
    return False


def unsupported_numbers(text: str, evidence: Iterable[str]) -> list[str]:
    """Numbers in ``text`` that no evidence text backs; empty when the text is clean."""
    values: list[float] = []
    for ev in evidence:
        values += [p[0] for t in numbers_in(ev) if (p := _parse(t)) is not None]
    bad: list[str] = []
    for token in numbers_in(text):
        parsed = _parse(token)
        if parsed is None:
            bad.append(token)
            continue
        written, percent, decimals = parsed
        cands = [written / 100.0, written] if percent else [written]
        prec = [decimals + 2, decimals] if percent else [decimals]
        if not any(_matches(w, d, v) for v in values for w, d in zip(cands, prec)):
            bad.append(token)
    return bad

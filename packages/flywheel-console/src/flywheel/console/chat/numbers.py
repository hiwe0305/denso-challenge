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


# ------------------------------------------------------------------ Vietnamese and English forms
# The chat answers in Vietnamese as often as in English, and its tool rows write numbers the
# Vietnamese way ("75,6 %", "100 000", "1 037"). Grounding reads both forms, one token per
# number: "60.000" = 60000, "49,23" = 49.23, "0,842" = 0.842, "100 000" = 100000. A token with
# one separator followed by three digits ("90.906", "1,037") is ambiguous and matches either
# reading. ``numbers_in`` above keeps the Agent QA rules unchanged (English only).
_NUMBER_ANY = re.compile(
    r"(?<![\w.,\-/])[-+]?"
    r"(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?(?!\d)|\d+(?:[.,]\d+)*|[.,]\d+)(?:e[-+]?\d+)?"
    rf"(?:\s?%|(?:{_UNITS})\b)?(?![\w\-/])",
    re.IGNORECASE,
)
_FRACTION_ANY = re.compile(r"(?<![\w.,\-/])(\d+(?:[.,]\d+)*)/(\d+(?:[.,]\d+)*)(?![\w\-/])")
_TOKEN_ANY = re.compile(r"([-+]?)([\d.,]+)(?:e([-+]?\d+))?\s?(%|[a-z]+)?", re.IGNORECASE)


def numbers_any(text: str) -> list[str]:
    """The numbers of ``text`` in Vietnamese or English form, one token per number."""
    stripped = _FRACTION_ANY.sub(r" \1 | \2 ", text)  # never read "136/180" as "136 180"
    return [m.group(0) for m in _NUMBER_ANY.finditer(stripped)]


def readings(token: str) -> list[tuple[float, bool, int]]:
    """Every (value, is_percent, decimals written) a token can mean; empty when it is no number."""
    m = _TOKEN_ANY.fullmatch(re.sub(r"(?<=\d)[ \u00a0\u202f](?=\d)", "", token.strip()))
    if m is None:
        return []
    sign, body, exp, suffix = m.group(1), m.group(2), m.group(3), (m.group(4) or "").lower()
    seps = [c for c in body if c in ".,"]
    bodies: list[tuple[str, int]] = []
    if not seps:
        bodies = [(body, 0)]
    elif "." in body and "," in body:  # the last separator is the decimal mark
        dec = body[max(body.rfind("."), body.rfind(","))]
        whole, frac = body.rsplit(dec, 1)
        bodies = [(whole.replace("," if dec == "." else ".", "") + "." + frac, len(frac))]
    else:
        groups = body.split(seps[0])
        head = groups[0]
        grouped = head not in ("", "0") and len(head) <= 3 and all(len(g) == 3 for g in groups[1:])
        if len(groups) > 2:
            bodies = [("".join(groups), 0)] if grouped else []
        else:
            bodies = [((groups[0] or "0") + "." + groups[1], len(groups[1]))]
            if grouped:
                bodies.append(("".join(groups), 0))
    out: list[tuple[float, bool, int]] = []
    for b, decimals in bodies:
        try:
            value = float(sign + b) * (10.0 ** int(exp) if exp else 1.0)
        except ValueError:
            continue
        if suffix == "k":
            value, decimals = value * 1000.0, decimals - 3
        out.append((value, suffix == "%", decimals))
    return out


def unsupported_any(text: str, evidence: Iterable[str]) -> list[str]:
    """Like ``unsupported_numbers``, for numbers in Vietnamese or English form."""
    values = [r[0] for ev in evidence for t in numbers_any(ev) for r in readings(t)]

    def backed(token: str) -> bool:
        for written, percent, decimals in readings(token):
            cands = [(written, decimals)]
            if percent:
                cands.insert(0, (written / 100.0, decimals + 2))
            if any(_matches(w, d, v) for v in values for w, d in cands):
                return True
        return False

    bad: list[str] = []
    for token in numbers_any(text):
        parts = re.split(r"[ \u00a0\u202f]+", token.strip())
        # "100 000" is one number; "mức 2 165 episode" is two, each backed on its own
        split_ok = len(parts) > 1 and all(p.isdigit() and backed(p) for p in parts)
        if not backed(token) and not split_ok:
            bad.append(token)
    return bad

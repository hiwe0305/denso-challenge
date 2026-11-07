"""Every number the agent writes must be one the code computed (DA-20 AC 3).

The agent cites facts as `{F3}` and the HTML puts the value in. A bare number in
an insight or a suggestion is allowed only when it is the value of a fact of the
report, written to any precision (0.0449 may be written 0.045 or 4.49e-2), or the
same value as a percentage of a fraction fact. Anything else marks the report
broken with the sentence that carries it, so an invented number never reaches the
engineer as if it were measured.

Digits inside a name are not numbers: `job-cf631ab2655c`, `episode_000012`, `T1`,
`p99`, `F3` are identifiers. A number with a unit glued on (`120ms`, `10x`, `4GB`,
`12k`) is still a number, both sides of `45/90` are numbers, and `12,000` is twelve
thousand. The caller decides which facts may back a sentence: the agent passes only
the facts the sentence's item cites, so a number cannot borrow a fact it did not name.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

from flywheel.contracts.agentqa import AgentFact

_PLACEHOLDER = re.compile(r"\{F[0-9]+\}")
# Units a number may carry glued on; any other trailing letters make the token a name.
_UNITS = "ms|s|sec|min|h|hz|khz|kb|mb|gb|px|cm|mm|m|x|k|fps"
# A number standing alone: not glued to a letter, digit, underscore or hyphen of a name.
# `12,000` (thousands groups) is one number; a unit or `%` may follow.
_NUMBER = re.compile(
    r"(?<![\w.\-/])[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?:e[-+]?\d+)?"
    rf"(?:%|(?:{_UNITS})\b)?(?![\w\-/])",
    re.IGNORECASE,
)
# `45/90`: two numbers. Paths (`train/job-1`) and dates (`6/11/2026`) do not match.
_FRACTION = re.compile(r"(?<![\w.\-/])(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)(?![\w\-/])")
_TOKEN = re.compile(r"([-+]?[\d.,]+(?:e[-+]?\d+)?)(%|[a-z]+)?", re.IGNORECASE)


def numbers_in(text: str) -> list[str]:
    """The bare numbers of `text`, placeholders removed, in the order they appear."""
    stripped = _PLACEHOLDER.sub(" ", text)
    stripped = _FRACTION.sub(lambda m: f" {m.group(1)} {m.group(2)} ", stripped)
    return [m.group(0) for m in _NUMBER.finditer(stripped)]


def _parse(token: str) -> tuple[float, bool, int] | None:
    """(value, is_percent, decimals written); a unit is dropped, `k` multiplies by 1000."""
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
    # Written rounded to its own precision: 0.045 for 0.04485, 12 for 12.4.
    if round(fact, decimals) == round(written, decimals):
        return True
    # Rounded to significant figures: 4.5e-05 for 4.4853e-05.
    if fact != 0 and written != 0:
        digits = max(1, len(re.sub(r"[^0-9]", "", f"{written:g}").lstrip("0")))
        return f"{fact:.{digits}g}" == f"{written:.{digits}g}"
    return False


def _fact_numbers(facts: Iterable[AgentFact]) -> list[float]:
    values: list[float] = []
    for fact in facts:
        value = fact.value
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            values.append(float(value))
        else:
            values += [p[0] for t in numbers_in(str(value)) if (p := _parse(t)) is not None]
    return values


def unsupported_numbers(text: str, facts: Iterable[AgentFact]) -> list[str]:
    """Numbers in `text` that no fact backs; empty when the text is clean."""
    values = _fact_numbers(facts)
    bad = []
    for token in numbers_in(text):
        parsed = _parse(token)
        if parsed is None:
            bad.append(token)
            continue
        written, percent, decimals = parsed
        candidates = [written / 100.0, written] if percent else [written]
        precision = [decimals + 2, decimals] if percent else [decimals]
        if not any(
            _matches(w, d, v) for v in values for w, d in zip(candidates, precision, strict=True)
        ):
            bad.append(token)
    return bad

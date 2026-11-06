"""Every number the agent writes must be one the code computed (DA-20 AC 3).

The agent cites facts as `{F3}` and the HTML puts the value in. A bare number in
an insight or a suggestion is allowed only when it is the value of a fact of the
report, written to any precision (0.0449 may be written 0.045 or 4.49e-2), or the
same value as a percentage of a fraction fact. Anything else marks the report
broken with the sentence that carries it, so an invented number never reaches the
engineer as if it were measured.

Digits inside a name are not numbers: `job-cf631ab2655c`, `episode_000012`, `T1`,
`p99`, `F3` are identifiers.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

from flywheel.contracts.agentqa import AgentFact

_PLACEHOLDER = re.compile(r"\{F[0-9]+\}")
# A number standing alone: not glued to a letter, digit, underscore or hyphen of a name.
_NUMBER = re.compile(r"(?<![\w.\-/])[-+]?(?:\d+(?:[.,]\d+)?|[.,]\d+)(?:e[-+]?\d+)?(%?)(?![\w\-/])")


def numbers_in(text: str) -> list[str]:
    """The bare numbers of `text`, placeholders removed, in the order they appear."""
    stripped = _PLACEHOLDER.sub(" ", text)
    return [m.group(0) for m in _NUMBER.finditer(stripped)]


def _parse(token: str) -> tuple[float, bool, int] | None:
    """(value, is_percent, decimals written)."""
    percent = token.endswith("%")
    body = token.rstrip("%").replace(",", ".")
    try:
        value = float(body)
    except ValueError:
        return None
    mantissa = body.lower().split("e")[0]
    decimals = len(mantissa.split(".")[1]) if "." in mantissa else 0
    return value, percent, decimals


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

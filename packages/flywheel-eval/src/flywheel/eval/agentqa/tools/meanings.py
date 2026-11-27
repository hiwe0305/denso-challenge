"""One line of meaning for a fact name, written by code (DA-52 task 2.3).

A model once read a fact name the wrong way round, and the sentence passed every check
because it held no number. So every fact the investigate role is given carries a line that
says what the name means. The line comes from the structure of the name, as the tool that
makes it documents it (`tools/measures.py`, `tools/clusters.py`); a name of any other tool
falls back to the tool's own description, so no fact is left without a meaning.

Wording is generic: no measure, task or mechanism is named here; the measure and the
reference of a `measure_compare` or `measure_tally` fact are read off the name itself.
"""

from __future__ import annotations

import re

from flywheel.eval.agentqa.tools.measures import COMPARE, TALLY

CLUSTERS = "failure_clusters"
_SLUG = re.compile(r"^(?P<run>.+?)_cluster_(?P<cluster>.+?)_(?P<tool>cmp|tally)__"
                   r"(?P<measure>.+?)__vs__(?P<rest>.+)$")
_PERCENTILE = re.compile(r"_ref_p(?P<p>[0-9]+(?:_[0-9]+)?)$")
_VALUE = re.compile(r"_v(?P<k>[1-9][0-9]*)_(?P<what>value|count|ref_count)$")
_NO_REASON = "The value is the reason, as text."

# Suffixes of a compared measure's facts, longest first so `_ref_median` is not `_median`.
_COMPARE_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("_bounds_not_judged", "why the reference group has no percentile bounds. " + _NO_REASON),
    ("_separated_not_judged", "why separation is not judged for the cluster. " + _NO_REASON),
    ("_ref_beyond_threshold", "rollouts of the reference group whose value is beyond the "
                              "scorer threshold the task maps to the measure"),
    ("_beyond_threshold", "members of the cluster whose value is beyond the scorer threshold "
                          "the task maps to the measure"),
    ("_outside_below", "members of the cluster whose value is below the reference group's "
                       "low percentile"),
    ("_outside_above", "members of the cluster whose value is above the reference group's "
                       "high percentile"),
    ("_outside_total", "members of the cluster whose value is outside the reference group's "
                       "percentile bounds, below and above together"),
    ("_separated", "true when more than half of the cluster's members that carry the measure "
                   "lie outside the reference group's percentile bounds (computed by code)"),
    ("_ref_median", "the median of the measure over the reference group"),
    ("_median", "the median of the measure over the members of the cluster"),
)
_TALLY_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("_values_left_out", "how many distinct values are not listed one by one (summed in the "
                         "other counts)"),
    ("_other_ref_count", "rollouts of the reference group with a value not listed one by one"),
    ("_other_count", "members of the cluster with a value not listed one by one"),
    ("_ref_mode", "the most common value in the reference group (a tie goes to the first "
                  "in text order)"),
    ("_mode", "the most common value among the members of the cluster (a tie goes to the "
              "first in text order)"),
    ("_values", "how many distinct values the cluster and the reference group hold together"),
)
_GROUP_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("_ref_members", "rollouts of the reference group"),
    ("_ref_judged", "rollouts of the reference group that carry the measure"),
    ("_ref_lacking", "rollouts of the reference group that lack the measure (left out of "
                     "its statistics)"),
    ("_members", "rollouts of the cluster"),
    ("_judged", "members of the cluster that carry the measure"),
    ("_lacking", "members of the cluster that lack the measure (left out of its statistics)"),
    ("_not_judged", "why nothing else of the call was judged. " + _NO_REASON),
)
_CONFIG: dict[str, str] = {
    f"{COMPARE}_low_percentile": "the low percentile the reference group's bounds use (a "
                                 "setting of the task view, an assumption)",
    f"{COMPARE}_high_percentile": "the high percentile the reference group's bounds use (a "
                                  "setting of the task view, an assumption)",
    f"{COMPARE}_min_reference": "the fewest reference rollouts with the measure that "
                                "percentile bounds need (a setting of the task view)",
    f"{COMPARE}_min_cluster": "the fewest cluster members with the measure that a separation "
                              "verdict needs (a setting of the task view)",
    f"{TALLY}_max_values": "the most values a tally lists one by one (a setting of the task "
                           "view)",
}
_CLUSTER_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("_in_other_runs", "how many other runs of the pack have a failure cluster with the same "
                       "first failed step, label and level"),
    ("_size", "how many failed rollouts the cluster holds"),
)


def _measure_text(slug: str) -> str:
    """`final__name__i2` -> `final.name[2]`, `final__q__<derived>` -> `final.q.<derived>`."""
    parts = slug.split("__")
    if len(parts) < 2:
        return slug
    where, name, *tail = parts
    text = f"{where}.{name}"
    for part in tail:
        text += f"[{part[1:]}]" if re.fullmatch(r"i[0-9]+", part) else f".{part}"
    return text


def _split(rest: str, suffixes: tuple[tuple[str, str], ...]) -> tuple[str, str] | None:
    """(reference, meaning) when `rest` ends with one of `suffixes`."""
    for suffix, meaning in suffixes:
        if rest.endswith(suffix) and len(rest) > len(suffix):
            return rest[: -len(suffix)], meaning
    return None


def _reference(text: str) -> str:
    if text in ("successes_same_level", "successes_all_levels"):
        return text
    return f"the failure cluster {text} of the same run"


def _measured(name: str) -> str | None:
    """The meaning of a fact of `measure_compare` or `measure_tally`; None if not one."""
    match = _SLUG.match(name.removeprefix(f"{COMPARE}_").removeprefix(f"{TALLY}_"))
    if match is None:
        return None
    rest = match["rest"]
    found: tuple[str, str] | None = None
    percentile = _PERCENTILE.search(rest)
    value = _VALUE.search(rest)
    if percentile is not None:
        found = (rest[: percentile.start()],
                 "a percentile of the measure over the reference group: the k-th, where the "
                 "name ends in p followed by k")
    elif value is not None and match["tool"] == "tally":
        k = value["k"]
        found = (rest[: value.start()], {
            "value": f"value number {k} of the tally (by count over both groups), as text",
            "count": f"members of the cluster whose value is value number {k} of the tally",
            "ref_count": f"rollouts of the reference group whose value is value number {k} "
                         "of the tally"}[value["what"]])
    else:
        own = _COMPARE_SUFFIXES if match["tool"] == "cmp" else _TALLY_SUFFIXES
        found = _split(rest, own) or _split(rest, _GROUP_SUFFIXES)
    if found is None:
        return None
    reference, meaning = found
    return (f"{meaning[0].upper()}{meaning[1:]}; cluster {match['cluster']} of run "
            f"{match['run']}, measure {_measure_text(match['measure'])}, reference "
            f"{_reference(reference)}.")


def _clustered(name: str) -> str | None:
    if "_cluster_" in name:
        run, _, rest = name.partition("_cluster_")
        found = _split(rest, _CLUSTER_SUFFIXES)
        if found is not None:
            return f"{found[1][0].upper()}{found[1][1:]}; cluster {found[0]} of run {run}."
    if name.endswith("_failures"):
        return f"Failed rollouts of run {name.removesuffix('_failures')}."
    if name.endswith("_clusters"):
        return f"Failure clusters of run {name.removesuffix('_clusters')}."
    return None


def _described(tool: str) -> str:
    # The tool descriptions live with the DA-49 bridge; imported here, not copied.
    from flywheel.eval.agentqa.mcp.bridge import DESCRIPTIONS

    text = DESCRIPTIONS.get(tool, "")
    first = text.split(". ")[0].rstrip(".") if text else ""
    return (f"A fact of the tool {tool}: {first}." if first
            else f"A fact of the tool {tool}; its name says what it counts.")


def meaning_of(name: str, tool: str) -> str:
    """One generic line saying what the fact `name` of `tool` means; never empty."""
    if name in _CONFIG:
        return f"{_CONFIG[name][0].upper()}{_CONFIG[name][1:]}."
    if name.startswith("threshold_"):
        return (f"The scorer threshold {name.removeprefix('threshold_')} of the task view, "
                "as the task maps it to a measure.")
    if tool in (COMPARE, TALLY):
        found = _measured(name)
        if found is not None:
            return found
    if tool == CLUSTERS:
        found = _clustered(name)
        if found is not None:
            return found
    if name.endswith("_not_judged"):
        return f"Why the tool {tool} (or a part of it) judged nothing. {_NO_REASON}"
    return _described(tool)


__all__ = ["meaning_of"]

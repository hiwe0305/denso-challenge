"""Runs whose test result a round does not present (manifest ``withhold_eval``), held server-side.

The pages already hide them (``web/core.js``, ``unhide``), but ``/data/story.json`` used to
carry the figures to the browser, where devtools showed them. The server now removes the same
result blocks before the file leaves; training, data cut and cost of the run stay, as on the
pages. Keep this in step with ``filterWithheldStory`` in ``web/core.js``. The ids come from the
seed manifest (``runner._withheld_runs``), never from the index on disk.
"""

from __future__ import annotations

from typing import Any


def _omit(d: Any, ids: set[str]) -> dict[str, Any]:
    return {k: v for k, v in (d or {}).items() if k not in ids} if isinstance(d, dict) else {}


def _off(rows: Any, ids: set[str]) -> Any:
    """``rows`` without those of a held run; anything but a list is left as it is."""
    if not isinstance(rows, list):
        return rows
    return [r for r in rows if not (isinstance(r, dict) and r.get("run") in ids)]


def _jig(jig: dict[str, Any], ids: set[str]) -> dict[str, Any]:
    """The ``jig`` block: the train entries in ``jig.runs`` stay (keyed ``branch``; rows keyed
    ``run`` are eval rows of an older index and go), the result blocks of a held run go."""
    out = dict(jig)
    for key in ("runs", "outcomes", "rollouts", "conditions"):
        if key in out:
            out[key] = _off(out[key], ids)
    if isinstance(out.get("evals"), list):
        out["evals"] = [
            {"run": e.get("run"), "role": e.get("role"), "status": "withheld"}
            if isinstance(e, dict) and e.get("run") in ids
            else e
            for e in out["evals"]
        ]
    for key in ("featured", "best"):
        if out.get(key) in ids:
            out[key] = None
    paired = out.get("paired")
    if isinstance(paired, dict) and (paired.get("variant") in ids or paired.get("baseline") in ids):
        out["paired"] = None
    c60 = out.get("compare60")  # the 60-rollout table (DA-53 AC 11)
    if isinstance(c60, dict):
        held = c60.get("run") in ids
        out["compare60"] = None if held else {**c60, "earlier": _off(c60.get("earlier"), ids)}
    return out


def story(doc: dict[str, Any], ids: set[str]) -> dict[str, Any]:
    """``story.json`` without the result blocks of the runs in ``ids``."""
    if not ids:
        return doc
    out = dict(doc)
    pair = out.get("pair")
    if isinstance(pair, dict):
        out["pair"] = {
            **pair,
            "runs": [r for r in pair.get("runs") or [] if r.get("run") not in ids],
            "comparisons": [c for c in pair.get("comparisons") or []
                            if c.get("variant") not in ids and c.get("baseline") not in ids],
        }  # fmt: skip
    jig = out.get("jig")
    if isinstance(jig, dict):
        out["jig"] = _jig(jig, ids)
    follow = out.get("follow")
    if isinstance(follow, dict):
        out["follow"] = {k: v for k, v in follow.items() if k != "r3"} | {
            "runs": _omit(follow.get("runs"), ids)
        }
    demo = out.get("demo")
    if isinstance(demo, dict):
        d = {k: v for k, v in demo.items() if k != "round1_reading"}
        ladder = d.get("ladder")
        if isinstance(ladder, dict):
            ladder = {**ladder, "runs": _omit(ladder.get("runs"), ids)}
            tb = ladder.get("on_table_b")
            if isinstance(tb, dict):
                # the quoted table row has every run's figure
                ladder["on_table_b"] = {
                    **tb,
                    "value": _omit(tb.get("value"), ids),
                    "check_from_rollouts": _omit(tb.get("check_from_rollouts"), ids),
                    "quote": None,
                }
            d["ladder"] = ladder
        out["demo"] = d
    return out

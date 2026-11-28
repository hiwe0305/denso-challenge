"""Runs whose test result a round does not present (manifest ``withhold_eval``), held server-side.

The pages already hide them (``web/core.js``, ``unhide``), but ``/data/story.json`` used to
carry the figures to the browser, where devtools showed them. The server now removes the same
result blocks before the file leaves; training, data cut and cost of the run stay, as on the
pages. Keep this in step with ``unhide`` in ``web/core.js``.
"""

from __future__ import annotations

from typing import Any


def _omit(d: Any, ids: set[str]) -> dict[str, Any]:
    return {k: v for k, v in (d or {}).items() if k not in ids} if isinstance(d, dict) else {}


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
        out["jig"] = {
            **jig,
            "runs": [r for r in jig.get("runs") or [] if r.get("run") not in ids],
            "rollouts": [r for r in jig.get("rollouts") or [] if r.get("run") not in ids],
            "conditions": [c for c in jig.get("conditions") or [] if c.get("run") not in ids],
        }
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

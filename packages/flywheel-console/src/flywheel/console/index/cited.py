"""Numbers that exist only in docs, each with the quote that proves it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml
from flywheel.console.paths import ConsolePaths

_LEVELS = ("L0", "L1", "L2", "L1–2")


@dataclass(frozen=True)
class Cited:
    key: str
    value: Any
    doc: str
    section: str
    quote: str


def load(paths: ConsolePaths) -> list[Cited]:
    data = yaml.safe_load((paths.seed / "cited.yaml").read_text(encoding="utf-8"))
    return [Cited(**e) for e in data["cited"]]


def verify(paths: ConsolePaths) -> list[str]:
    """Return the keys whose quote is not found verbatim in its doc."""
    bad: list[str] = []
    texts: dict[str, str] = {}
    for c in load(paths):
        if c.doc not in texts:
            f = paths.repo / c.doc
            texts[c.doc] = f.read_text(encoding="utf-8") if f.is_file() else ""
        if c.quote not in texts[c.doc]:
            bad.append(c.key)
    return bad


def eval_block(paths: ConsolePaths) -> dict[str, Any]:
    """Assemble the eval block with the same keys as the v5 ``story.json["eval"]``."""
    by = {c.key: c.value for c in load(paths)}
    labels = {
        k.removeprefix("eval.failure_labels."): v
        for k, v in by.items()
        if k.startswith("eval.failure_labels.")
    }
    names = list(labels["L1"])
    return {
        "source": "docs/he/tray.md §16.6",
        "policy": by["eval.policy"],
        "levels": list(by[f"eval.level.{lv}"] for lv in _LEVELS),
        "stages": by["eval.stages"],
        "failure_labels": {n: {lv: labels[lv][n] for lv in ("L0", "L1", "L2")} for n in names},
        "place_error_cm": {lv: by[f"eval.place_error_cm.{lv}"] for lv in ("L0", "L1", "L2")},
        "clusters": [by["eval.cluster.L-PLACE-POSE"]],
    }


def loop_chain(paths: ConsolePaths) -> list[int]:
    """The Failure → Data chain 240 → 131 → 262 → 229 → 177."""
    by = {c.key: c.value for c in load(paths)}
    return [
        by[k]
        for k in ("loop.eval_n", "loop.failures", "loop.targets", "loop.recorded", "loop.kept")
    ]


def loop_detail(paths: ConsolePaths) -> dict[str, int]:
    """Cited Failure → Data numbers outside the main chain: QA pass count and the cut size."""
    by = {c.key: c.value for c in load(paths)}
    return {"qa_pass": by["loop.qa_pass"], "in_cut": by["loop.in_cut"]}


def round_block(paths: ConsolePaths) -> dict[str, Any]:
    """The cited half of the tray round (tray.md 20.11–20.16); empty when the seed lacks it."""
    by = {c.key: c.value for c in load(paths)}
    if "round.plan" not in by:
        return {}
    return {
        "source": "docs/he/tray.md §20.11–20.16",
        "plan": by["round.plan"],
        "chain": {
            k: by[f"round.{k}"]
            for k in ("targets", "generated", "recorded", "qa_pass", "quality", "selected")
        },
        "clusters": by["round.clusters.data"] + by["round.clusters.tickets"],
        # attempts asked of the planner per failure (by stage) and its failures in this batch
        "per_case": by.get("round.per_case") or {},
        "planner_failures": by.get("round.planner_failures") or {},
    }


def demo_groups(paths: ConsolePaths) -> dict[str, dict[str, dict[str, Any]]]:
    """``demo.<group>.<name>`` entries as ``{group: {name: {value, source, quote}}}``."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for c in load(paths):
        parts = c.key.split(".", 2)
        if len(parts) != 3 or parts[0] != "demo":
            continue
        out.setdefault(parts[1], {})[parts[2]] = {
            "value": c.value,
            "source": f"{c.doc} §{c.section}",
            "quote": c.quote,
        }
    return out


def loop_in_cut(paths: ConsolePaths) -> int:
    return loop_detail(paths)["in_cut"]

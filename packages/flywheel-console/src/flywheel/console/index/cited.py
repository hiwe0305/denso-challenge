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


def _src(c: Cited) -> str:
    return f"{c.doc} §{c.section}"


def diag_block(paths: ConsolePaths) -> dict[str, Any]:
    """Diagnosis of round tray-r1 for the chat (``story.json · diag``; audit 04 B4, F3).

    ``clusters``: c1-c8 of tray.md 20.2 (``diag.cluster.*``), each with the diagnosis of
    ``round.clusters.data`` or ``round.clusters.tickets`` and ``gets_data`` (it is one of the
    data clusters, 20.13). ``step4``: the checks H1-H3 (``diag.step4.*``), each naming the
    ticket its clusters became, if any. ``gen_qa_cost``: the targeted generation and QA on
    rtx3060 (0 CU, tray.md 20.16) beside the round's train and serve CU (20.18). Every part
    carries its ``source``; a part whose cited keys are missing is left empty. Nothing here is
    computed beyond sums of cited values."""
    by = {c.key: c for c in load(paths)}
    data = {x["id"]: x for x in (by["round.clusters.data"].value if "round.clusters.data" in by
                                 else [])}  # fmt: skip
    tickets = {x["id"]: x for x in (by["round.clusters.tickets"].value
                                    if "round.clusters.tickets" in by else [])}  # fmt: skip
    clusters: list[dict[str, Any]] = []
    for key in sorted(k for k in by if k.startswith("diag.cluster.")):
        c = by[key]
        v = c.value
        cid = v["id"]
        dx = data.get(cid) or tickets.get(cid) or {}
        src = [_src(c)]
        if cid in data:
            src.append(_src(by["round.clusters.data"]))
        elif cid in tickets:
            src.append(_src(by["round.clusters.tickets"]))
        clusters.append(
            {
                "id": cid,
                "key": {"step": v["step"], "label": v["label"], "level": v["level"]},
                "n_fail": v["n_fail"],
                "diagnosis": dx.get("diagnosis"),
                "intervention": dx.get("intervention"),
                "gets_data": cid in data,
                "source": src,
                "quote": c.quote,
            }
        )
    step4 = [
        {
            "id": by[k].value["id"],
            "claim": by[k].value["claim"],
            "clusters": list(by[k].value.get("clusters") or []),
            "verdict": by[k].value["verdict"],
            "ticket": by[k].value.get("ticket"),
            "source": _src(by[k]),
            "quote": by[k].quote,
        }
        for k in sorted(k for k in by if k.startswith("diag.step4."))
    ]
    cost: dict[str, Any] = {}
    need = (
        "demo.design.gen_hours", "demo.design.qa_hours", "demo.design.gen_cu",
        "demo.diagnose.cost_cu", "round.qa_pass", "round.quality", "round.selected",
        "demo.cost.train_1", "demo.cost.train_2", "demo.cost.serve", "diag.gen_host",
    )  # fmt: skip
    if all(k in by for k in need):
        gen, qa = by["demo.design.gen_hours"].value, by["demo.design.qa_hours"].value
        parts = {k: by[f"demo.cost.{k}"].value for k in ("train_1", "train_2", "serve")}
        cost = {
            "host": by["diag.gen_host"].value,
            "cu": by["demo.design.gen_cu"].value,  # generation, QA, selection and cut
            "diagnosis_cu": by["demo.diagnose.cost_cu"].value,  # step 4 (H1-H3)
            "generation": {"attempts": gen["attempts"], "recorded": gen["recorded"],
                           "hours": gen["hours"]},  # fmt: skip
            "qa": {"hours": qa["hours"], "qa_pass": by["round.qa_pass"].value,
                   "quality": by["round.quality"].value},  # fmt: skip
            "selected": by["round.selected"].value,
            "train_serve_cu": round(sum(parts.values()), 2),
            "train_serve_parts": parts,
            "source": sorted({_src(by[k]) for k in need}),
        }
    return {
        "round": "tray-r1",
        "source": "docs/he/tray.md §20.2, §20.9, §20.11, §20.13, §20.16, §20.18 (seed/cited.yaml)",
        "clusters": clusters,
        "step4": step4,
        "gen_qa_cost": cost,
    }

"""The bench result as JSON with its hash, and the static HTML page (DA-31 AC 4).

Every number on the page is measured on DA-27's injected defects and the page
says so at the top and in its title; natural defects of the real data are
listed apart (design 27/10/2026 section 9.2: "Báo rõ 'trên lỗi cấy'"). The page
is built from the JSON, never from anything the JSON does not hold, so the hash
of the JSON vouches for the page too. The demo of 17/11 (DA-28) shows this page.

A result is never overwritten: `write_bench` refuses an output dir that exists
(03 section 4.4, append-only); a new run goes to a new dir.
"""

from __future__ import annotations

import hashlib
import html
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from flywheel.eval.agentqa.bench.detections import LAYERS
from flywheel.eval.agentqa.bench.layers import AgentQuality, KindSplit
from flywheel.eval.agentqa.bench.score import GroupScore, Rate

BENCH_VERSION = "da31-2"
RESULT = "bench_result.json"
RESULT_LOCK = "bench_result.sha256"
PAGE = "index.html"
LABEL = "on injected defects (trên lỗi cấy)"
BOUND = "upper (cận trên)"
FALSE_ALARM_NOTE = (
    "upper bound (cận trên): the clean copy still holds the real data's own defects,"
    " and a report of one of them counts as a false alarm"
)


@dataclass(frozen=True)
class GroupReport:
    score: GroupScore
    split: tuple[KindSplit, ...]
    quality: AgentQuality


def bench_result(
    groups: Sequence[GroupReport],
    *,
    created_at: datetime,
    manifest_sha256: Mapping[str, str],
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """The machine-readable result: every number of the page, and what it came from."""
    return {
        "bench_version": BENCH_VERSION,
        "measured_on": "injected defects (DA-27), not natural defects",
        "false_alarm_on_clean": FALSE_ALARM_NOTE,
        "created_at": created_at.isoformat(),
        "manifest_sha256": dict(sorted(manifest_sha256.items())),
        "inputs": dict(inputs),
        "groups": [_group_json(g) for g in groups],
    }


def write_bench(out: Path, result: Mapping[str, Any]) -> str:
    """Write the JSON, its sha256 and the page to a new dir `out`; return the hash."""
    if out.exists():
        raise FileExistsError(f"{out} exists; a bench result is never overwritten")
    out.mkdir(parents=True)
    text = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (out / RESULT).write_text(text, encoding="utf-8")
    (out / RESULT_LOCK).write_text(digest + "\n", encoding="utf-8")
    (out / PAGE).write_text(render_html(result, digest), encoding="utf-8")
    return digest


def render_html(result: Mapping[str, Any], digest: str) -> str:
    parts = [
        f"<h1>Agent QA/QC bench · {_e(LABEL)}</h1>",
        "<p class=banner>Every number on this page is measured on the defects DA-27"
        " injected into copies of the real data, with the answer key sealed before the"
        " run. It says how well the checks find <b>these</b> defects; it is not a rate"
        " on natural defects, which are listed apart.</p>",
        _meta(result, digest),
    ]
    for group in result["groups"]:
        parts.append(_group_html(group))
    body = "".join(parts)
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>Agent QA/QC bench {_e(LABEL)}</title><style>{CSS}</style></head>"
        f"<body>{body}</body></html>\n"
    )


def _group_json(report: GroupReport) -> dict[str, Any]:
    score = report.score
    layers = {}
    for layer in LAYERS:
        s = score.layers[layer]
        layers[layer] = {
            "recall_by_kind": {k: _rate(r) for k, r in s.recall_by_kind.items()},
            "masked_by_kind": dict(s.masked_by_kind),
            "recall_unmasked_by_kind": {k: _rate(r) for k, r in s.recall_unmasked_by_kind.items()},
            "precision_by_code": {c: _rate(r) for c, r in s.precision_by_code.items()},
            "false_alarm_on_clean": {**_rate(s.false_alarm), "bound": BOUND},
            "false_alarm_not_a_unit": list(s.not_a_unit),
            "clean_reports": [list(p) for p in s.clean_reports],
            "natural": [list(p) for p in s.natural],
            "seconds_to_report": dict(s.seconds_to_report),
            "uncoded": {k: list(v) for k, v in s.uncoded.items()},
        }
    quality = report.quality
    return {
        "group": score.group,
        "injected_copy": score.injected_id,
        "clean_copy": score.clean_id,
        "defects": len(score.defects),
        "layers": layers,
        "split": [
            {"kind": r.kind, "code": r.code, "injected": r.injected, "by_code": r.by_code,
             "agent_adds": r.agent_adds, "together": r.together, "agent_alone": r.agent_alone}
            for r in report.split
        ],
        "agent_quality": {
            "ranking": _rate(quality.ranking),
            "reviews": {k: dict(v) for k, v in quality.reviews.items()},
            "findings": [
                {"copy": f.dataset_id, "report_id": f.report_id, "finding_id": f.finding_id,
                 "rank": f.rank, "target": f.target, "code": f.code, "label": f.label,
                 "review": f.review, "reason": f.reason}
                for f in quality.findings
            ],
        },
    }


def _rate(rate: Rate) -> dict[str, Any]:
    return {"hit": rate.hit, "total": rate.total, "value": rate.value}


def _meta(result: Mapping[str, Any], digest: str) -> str:
    rows = [
        ("bench version", result["bench_version"]),
        ("created", result["created_at"]),
        ("result sha256", digest),
        *((f"answer key {k}", v) for k, v in result["manifest_sha256"].items()),
        *((f"input {k}", json.dumps(v, ensure_ascii=False)) for k, v in result["inputs"].items()),
    ]
    return _table("Run", ["", ""], [[k, v] for k, v in rows])


def _group_html(group: Mapping[str, Any]) -> str:
    layers = group["layers"]
    code, agent = layers["code"], layers["agent"]
    title = (f"{group['group']} · copy with defects {group['injected_copy']},"
             f" clean copy {group['clean_copy']}, {group['defects']} defects")
    def masked(kind: str) -> str:
        return f"{code['masked_by_kind'].get(kind, 0)} / {agent['masked_by_kind'].get(kind, 0)}"

    def unmasked(layer: Mapping[str, Any], kind: str) -> str:
        return _shown(layer["recall_unmasked_by_kind"].get(kind))

    split_rows = [
        [r["kind"], r["code"], r["injected"], _frac(r["by_code"], r["injected"]),
         unmasked(code, r["kind"]), _frac(r["agent_adds"], r["injected"]),
         _frac(r["together"], r["injected"]), _frac(r["agent_alone"], r["injected"]),
         unmasked(agent, r["kind"]), masked(r["kind"])]
        for r in group["split"]
    ]
    codes = sorted(set(code["precision_by_code"]) | set(agent["precision_by_code"]))
    precision_rows = [
        [c, _shown(code["precision_by_code"].get(c)), _shown(agent["precision_by_code"].get(c))]
        for c in codes
    ]
    alarm_rows = [
        [layer, _shown(layers[layer]["false_alarm_on_clean"]),
         _listed(layers[layer]["false_alarm_not_a_unit"]),
         ", ".join(f"{t} {c}" for t, c in layers[layer]["clean_reports"]) or "none"]
        for layer in LAYERS
    ]
    time_rows = [
        [layer, copy, "not measured" if s is None else f"{s:.1f} s"]
        for layer in LAYERS
        for copy, s in layers[layer]["seconds_to_report"].items()
    ]
    quality = group["agent_quality"]
    review_rows = [
        [label, counts.get("agree", 0), counts.get("override", 0), counts.get("unreviewed", 0)]
        for label, counts in quality["reviews"].items()
    ]
    finding_rows = [
        [f["copy"], f["report_id"], f["rank"], f["target"], f["code"], f["label"], f["review"],
         f["reason"]]
        for f in quality["findings"]
    ]
    natural_rows = [
        [layer, t, c] for layer in LAYERS for t, c in layers[layer]["natural"]
    ]
    uncoded_rows = [
        [layer, copy, line]
        for layer in LAYERS
        for copy, lines in layers[layer]["uncoded"].items()
        for line in lines
    ]
    return "".join([
        f"<h2>{_e(title)}</h2>",
        _table("Recall per kind: what code catches, what the agent adds",
               ["kind", "code", "injected", "by code", "by code, unmasked", "agent adds",
                "together", "agent alone", "agent alone, unmasked", "masked code / agent"],
               split_rows),
        "<p class=none>unmasked = hit / (injected - masked): the defects whose own"
        " (target, code) also fires on the clean copy are left out of both sides.</p>",
        _table("Precision per code (natural findings left out)",
               ["code", "code checks", "Agent QA/QC"], precision_rows),
        _table("False alarms on the clean copy, upper bound (cận trên):"
               " (units reported + targets that name no unit) / units",
               ["layer", "rate", "not a unit (không gắn đơn vị)", "reports"], alarm_rows),
        f"<p class=none>{_e(FALSE_ALARM_NOTE[0].upper() + FALSE_ALARM_NOTE[1:])}.</p>",
        _table("Time from job end to report", ["layer", "copy", "time"], time_rows),
        f"<h3>Agent QA/QC: ranking {_e(_shown(quality['ranking']))}"
        " (true finding ranked above false, pairs within a report)</h3>",
        _table("Engineer's review by label (agree = insight and suggestion stood)",
               ["label", "agree", "override", "unreviewed"], review_rows),
        _table("Agent findings", ["copy", "report", "rank", "target", "code", "label",
                                  "review", "reason"], finding_rows),
        _table("Natural findings (on both copies; not counted)", ["layer", "target", "code"],
               natural_rows),
        _table("Failures without a code (not counted)", ["layer", "copy", "reason"],
               uncoded_rows),
    ])


def _listed(names: Sequence[str]) -> str:
    return f"{len(names)} ({', '.join(names)})" if names else "0"


def _frac(hit: int, total: int) -> str:
    return f"{hit}/{total}" + (f" ({hit / total:.0%})" if total else "")


def _shown(rate: Mapping[str, Any] | None) -> str:
    if rate is None:
        return "-"
    if not rate["total"]:
        return "0/0"
    return f"{rate['hit']}/{rate['total']} ({rate['value']:.0%})"


def _table(title: str, head: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    cells = "".join(f"<th>{_e(h)}</th>" for h in head)
    if not rows:
        return f"<h3>{_e(title)}</h3><p class=none>none</p>"
    body = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in row) + "</tr>" for row in rows)
    return f"<h3>{_e(title)}</h3><div class=wrap><table><tr>{cells}</tr>{body}</table></div>"


def _e(value: Any) -> str:
    return html.escape(str(value))


CSS = """
:root{--bg:#fff;--fg:#1d1d1f;--muted:#666;--line:#ddd;--warn:#fff4d6}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--muted:#aaa;--line:#333;
--warn:#3a3014}}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0 auto;
max-width:1100px;padding:16px}
h1{font-size:22px}h2{font-size:18px;margin-top:32px;border-top:1px solid var(--line);
padding-top:16px}h3{font-size:15px;margin:20px 0 6px}
.banner{background:var(--warn);padding:10px 12px;border-radius:6px}
.wrap{overflow-x:auto}table{border-collapse:collapse;min-width:50%}
th,td{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}.none{color:var(--muted)}
"""

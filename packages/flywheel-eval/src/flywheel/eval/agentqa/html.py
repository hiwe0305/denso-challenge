"""The static HTML page of an AgentReport, built from the report alone (DA-20 AC 5).

The page shows, per finding in rank order: the design 10 code, the target, the
insight and the suggestion with each `{F#}` replaced by the fact's value and unit
(the raw id stays as a tooltip), the evidence table and the figures. A broken
report says so at the top with its problems. If the engineer's `AgentReview` is
given, each finding shows the decision and the reason.

What did not become a finding is listed at the top when given (#175): candidates
a lane detector raised that the model dropped, with its reason, and findings the
model added on a code a detector cleared. These come from `dropped.jsonl` beside
`reports.jsonl`, not from the report: the contract has no field for them. The
rest of the page holds nothing the report's JSON does not.
"""

from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence

from flywheel.contracts.agentqa import AgentFact, AgentReport, AgentReview
from flywheel.eval.agentqa.facts import DroppedCandidate

_PLACEHOLDER = re.compile(r"\{(F[0-9]+)\}")

_STYLE = """
body{font-family:sans-serif;max-width:1000px;margin:2em auto;color:#222}
h1{font-size:1.4em} .broken{background:#fde2e1;border:1px solid #d9534f;padding:.6em}
.dropped{background:#fff4d6;border:1px solid #e0a800;padding:.6em;margin:1em 0}
.finding{border:1px solid #ccc;border-radius:6px;padding:.8em;margin:1em 0}
.code{font-weight:bold;background:#eef;padding:0 .4em;border-radius:3px}
table{border-collapse:collapse;font-size:.9em} td,th{border:1px solid #ddd;padding:2px 6px}
.fact{border-bottom:1px dotted #555} .agree{color:#2e9e5b} .override{color:#d9534f}
"""


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _fmt(fact: AgentFact) -> str:
    value = fact.value
    text = f"{value:.4g}" if isinstance(value, float) else str(value)
    return f"{text} {fact.unit}".strip()


def render_text(text: str, facts: dict[str, AgentFact]) -> str:
    """Escape `text`, then put each cited fact's value in place of its `{F#}`."""
    out, last = [], 0
    for m in _PLACEHOLDER.finditer(text):
        out.append(_e(text[last : m.start()]))
        fact = facts.get(m.group(1))
        shown = _fmt(fact) if fact else m.group(0)
        title = f"{m.group(1)} · {fact.name}" if fact else m.group(1)
        out.append(f'<span class="fact" title="{_e(title)}">{_e(shown)}</span>')
        last = m.end()
    out.append(_e(text[last:]))
    return "".join(out)


def render_report(
    report: AgentReport,
    review: AgentReview | None = None,
    inline_svgs: Sequence[str] = (),
    dropped: Sequence[DroppedCandidate] = (),
) -> str:
    facts = {f.fact_id: f for f in report.facts}
    decisions = {d.finding_id: d for d in review.decisions} if review else {}
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>Agent QA/QC · {_e(report.subject_ref)}</title>",
        f"<style>{_STYLE}</style></head><body>",
        f"<h1>Agent QA/QC · {_e(report.stage)} · {_e(report.subject_ref)}</h1>",
        f"<p>Report <code>{_e(report.report_id)}</code>, {_e(report.created_at.isoformat())}; "
        f"model {_e(report.model.name)} {_e(report.model.revision)}, temperature "
        f"{report.model.temperature:g}, prompt <code>{_e(report.model.prompt_sha256[:12])}</code>."
        " Every number below was computed by code; the agent ranked and explained.</p>",
    ]
    if report.status == "broken":
        items = "".join(f"<li>{_e(p)}</li>" for p in report.problems)
        parts.append(f'<div class="broken"><b>Report broken</b><ul>{items}</ul></div>')
    if dropped:
        said = {"dropped_by_model": "dropped by the model", "refused_by_code": "refused by code"}
        rows = "".join(
            f"<tr><td>{_e(said[d.kind])}</td><td>{_e(d.cid)}</td><td>{_e(d.code)}</td>"
            f"<td>{_e(d.target)}</td><td>{_e(d.detail)}</td>"
            f"<td>{render_text(d.reason, facts)}</td></tr>"
            for d in dropped
        )
        parts.append(
            f'<div class="dropped"><b>{len(dropped)} item(s) did not become findings.</b> '
            "A detector raised these and the model dropped them, or the model added them on a "
            "code a detector had cleared. Check each before reading the findings below as the "
            "whole story.<table><tr><th>what</th><th>id</th><th>code</th><th>target</th>"
            f"<th>detector</th><th>model's text</th></tr>{rows}</table></div>"
        )
    if not report.findings:
        parts.append("<p>No findings.</p>")
    for finding in report.findings:
        decision = decisions.get(finding.finding_id)
        verdict = ""
        if decision:
            reason = f": {_e(decision.reason)}" if decision.reason else ""
            verdict = (
                f'<p class="{decision.decision}">Engineer: {decision.decision}{reason}</p>'
            )
        rows = "".join(
            f"<tr><td>{_e(f)}</td><td>{_e(facts[f].name)}</td><td>{_e(_fmt(facts[f]))}</td>"
            f"<td>{_e(facts[f].source_ref)}</td></tr>"
            for f in finding.evidence
            if f in facts
        )
        figures = "".join(
            f'<p><img src="{_e(path)}" alt="figure" style="max-width:100%"/></p>'
            for path in finding.figures
        )
        parts.append(
            f'<div class="finding"><h2>#{finding.rank} <span class="code">{_e(finding.code)}'
            f"</span> {_e(finding.target_ref)}</h2>"
            f"<p>{render_text(finding.insight, facts)}</p>"
            f"<p><b>Suggestion:</b> {render_text(finding.suggestion, facts)}</p>{verdict}"
            f"<table><tr><th>id</th><th>fact</th><th>value</th><th>source</th></tr>{rows}"
            f"</table>{figures}</div>"
        )
    if report.estimates:
        rows = "".join(
            f"<tr><td>{_e(e.estimate_id)}</td><td>{_e(e.quantity)}</td><td>{e.low:g}</td>"
            f"<td>{e.high:g}</td><td>{_e(e.unit)}</td><td>{_e(', '.join(e.basis))}</td></tr>"
            for e in report.estimates
        )
        parts.append(
            "<h2>Estimates (to compare with what is measured later)</h2><table><tr><th>id</th>"
            f"<th>quantity</th><th>low</th><th>high</th><th>unit</th><th>basis</th></tr>{rows}"
            "</table>"
        )
    parts += [f"<div>{svg}</div>" for svg in inline_svgs]
    rows = "".join(
        f"<tr><td>{_e(i.kind)}</td><td>{_e(i.ref)}</td><td><code>{_e(i.sha256[:12])}</code>"
        "</td></tr>"
        for i in report.inputs
    )
    parts.append(f"<h2>Inputs</h2><table><tr><th>kind</th><th>ref</th><th>sha256</th></tr>{rows}"
                 "</table></body></html>\n")
    return "".join(parts)


def render_index(
    reports: Sequence[tuple[str, AgentReport]], dropped: Mapping[str, int] | None = None
) -> str:
    """One line per report: its page, stage, status, findings, dropped code candidates."""
    rows = []
    for page, report in reports:
        top = report.findings[0] if report.findings else None
        n = (dropped or {}).get(report.report_id, 0)
        rows.append(
            f"<tr><td><a href=\"{_e(page)}\">{_e(report.subject_ref)}</a></td>"
            f"<td>{_e(report.stage)}</td><td>{_e(report.status)}</td>"
            f"<td>{len(report.findings)}</td><td>{n or ''}</td>"
            f"<td>{_e(top.code + ' ' + top.target_ref) if top else ''}</td></tr>"
        )
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>Agent QA/QC</title>"
        f"<style>{_STYLE}</style></head><body><h1>Agent QA/QC reports</h1><table>"
        "<tr><th>subject</th><th>stage</th><th>status</th><th>findings</th>"
        "<th>dropped by model</th><th>top</th></tr>"
        + "".join(rows)
        + "</table></body></html>\n"
    )

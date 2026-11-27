"""Step B7, render: `index.html` from `assembly.json`, `facts.jsonl` and `tables/`.

One self-contained file, standard library only, no script and no external resource.
Nothing is computed here beyond formatting: every number is a fact or a table cell.
A model sentence carries `{F#}` placeholders; each is replaced by that fact's value and
unit from `facts.jsonl`, and a placeholder no fact fills stops the page (`ValueError`).
Every string that comes from an artifact or a config is data and goes through
`html.escape` before it enters the page.

DA-52: facts are read from `facts.jsonl` and `investigation_facts.jsonl` (the facts the
investigate role's tool calls made). A hypothesis of the model shows its statement, the
data to collect and the first check each under a "Model's words" label; one kept without
comparison evidence is flagged "not enough evidence".
"""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

from flywheel.eval.agentqa.round.assemble import ASSEMBLY_FILE
from flywheel.eval.agentqa.round.measure import FACTS_FILE, TABLES_DIR
from flywheel.eval.agentqa.round.records import (
    Assembly,
    ClusterView,
    FactRecord,
    HypothesisView,
)
from flywheel.eval.agentqa.round.verify import INVESTIGATION_FACTS_FILE

INDEX_FILE = "index.html"
_PLACEHOLDER = re.compile(r"\{(F[0-9]+)\}")
MAX_ROWS = 200
STYLE = """
body{font:15px/1.45 system-ui,sans-serif;margin:0 auto;max-width:72rem;padding:1rem;
color:#1b1f24;background:#fff}
h1,h2,h3{line-height:1.2}h2{margin-top:2rem;border-bottom:1px solid #d0d7de}
table{border-collapse:collapse;margin:.5rem 0;font-size:13px}
th,td{border:1px solid #d0d7de;padding:.2rem .5rem;text-align:left;vertical-align:top}
th{background:#f6f8fa}caption{text-align:left;font-weight:600;padding:.3rem 0}
.badge{display:inline-block;padding:0 .4rem;border-radius:.6rem;font-size:12px;
background:#ddf4ff;border:1px solid #54aeff}
.badge.model{background:#fff8c5;border-color:#d4a72c}
.blocked{color:#9a3412;font-weight:600}.muted{color:#57606a}
.words{border-left:3px solid #d4a72c;padding-left:.6rem}.thin{color:#9a3412}
details.cluster{border:1px solid #d0d7de;border-radius:6px;margin:.5rem 0;padding:.4rem .8rem}
@media (prefers-color-scheme:dark){body{background:#0d1117;color:#e6edf3}
th{background:#161b22}th,td,details.cluster,h2{border-color:#30363d}
.badge{background:#0c2d6b}.badge.model{background:#4d3800}.muted{color:#9da7b3}}
"""


def _e(value: object) -> str:
    return escape(str(value))


def fill(text: str, facts: dict[str, FactRecord]) -> str:
    """`text` with every `{F#}` replaced by the fact's value and unit; escaped for HTML."""
    def one(match: re.Match[str]) -> str:
        fact = facts.get(match.group(1))
        if fact is None:
            raise ValueError(f"placeholder {match.group(0)} names no fact of facts.jsonl or "
                             f"{INVESTIGATION_FACTS_FILE}")
        return f"{fact.value} {fact.unit}".strip()

    return _e(_PLACEHOLDER.sub(one, text))


def _cell(value: object) -> str:
    if isinstance(value, list):
        return _e(", ".join(str(v) for v in value))
    return _e(value)


def _table(caption: str, columns: list[str], rows: list[list[object]]) -> str:
    head = "".join(f"<th>{_e(c)}</th>" for c in columns)
    body = "".join("<tr>" + "".join(f"<td>{_cell(v)}</td>" for v in row) + "</tr>"
                   for row in rows)
    return (f"<table><caption>{_e(caption)}</caption><thead><tr>{head}</tr></thead>"
            f"<tbody>{body}</tbody></table>")


def _header(a: Assembly) -> str:
    notes = "".join(f"<li>{_e(n)}</li>" for n in a.notes)
    return (
        f"<h1>Agent QA/QC round: {_e(a.task_id)}</h1><dl>"
        f"<dt>Task</dt><dd>{_e(a.task_id)}</dd><dt>Pack</dt><dd>{_e(a.pack_id)}</dd>"
        f"<dt>Run</dt><dd>{_e(a.run_id)}</dd><dt>Data class</dt><dd>{_e(a.data_class)}</dd>"
        f"<dt>Status</dt><dd>{_e(a.status)}</dd>"
        f"<dt>Agent</dt><dd>version {_e(a.agent_version)}, hash {_e(a.agent_hash[:12])}</dd>"
        f"</dl><ul>{notes}</ul>")


def _top(a: Assembly) -> str:
    head = a.headline
    if head is None:
        return "<h2>Top of the round</h2><p>No failure cluster to explain.</p>"
    first = head.hypotheses[0]
    where = f"{head.cluster.cluster_id}, size {head.cluster.size}"
    if head.verdict:
        where += f", ranked by {f'model {head.ranked_by}' if head.ranked_by else 'code'}"
    check = (f"{head.check.check_id} (cost {head.check.cost_key})" if head.check
             else "no check in the catalog")
    return (
        "<h2>Top of the round</h2><ol>"
        f"<li>Most likely cause: {_e(first.title)} ({_e(where)})</li>"
        f"<li>Cheapest check: {_e(check)}</li>"
        f"<li>Proposed intervention: {_e(head.intervention or 'none')} (not costed yet)</li>"
        "</ol>")


def _not_judged(a: Assembly) -> str:
    if not a.not_judged:
        return "<h2>Not judged</h2><p>Everything the plan asked for was judged.</p>"
    items = "".join(
        f"<li><strong>{_e(n.what)}</strong>: {_e(n.reason)}"
        f"{f' <span class=muted>({_e(n.fact_id)})</span>' if n.fact_id else ''}</li>"
        for n in a.not_judged)
    return f"<h2>Not judged</h2><ul>{items}</ul>"


def _fact_rows(h: HypothesisView, facts: dict[str, FactRecord],
               extra: tuple[tuple[str, list[str]], ...] = ()) -> str:
    rows: list[list[object]] = []
    for side, ids in (("support", h.support), ("contra", h.contra), *extra):
        for fid in ids:
            fact = facts.get(fid)
            rows.append([side, fid, *(
                [fact.name, fact.value, fact.unit, fact.source_ref] if fact
                else ["not in facts.jsonl", "", "", ""])])
    if not rows:
        return ""
    return _table("Facts", ["role", "fact id", "name", "value", "unit", "source"], rows)


def _model_hypothesis(h: HypothesisView, facts: dict[str, FactRecord]) -> str:
    """A hypothesis of the investigate role: every text is labelled as the model's words."""
    thin = h.evidence == "insufficient"
    flag = (" <span class=thin>not enough evidence: no comparison fact the code computed "
            "separates its cluster on a measure the scorer does not threshold; shown below "
            "the rules</span>" if thin else "")
    parts = [f"<h4>{_e(h.rank)}. {_e(h.title)} <span class='badge model'>model</span>{flag}"
             f"</h4><p>{_e(h.diagnosis)}, intervention {_e(h.intervention or 'none')}</p>"]
    for label, text in (("Model's words, hypothesis", h.explanation),
                        ("Model's words, data to collect", h.data_content),
                        ("Model's words, first check", h.first_check)):
        if text:
            parts.append(f"<p class=words><strong>{_e(label)}:</strong> "
                         f"{fill(text, facts)}</p>")
    cited = [f for f in h.cites if f not in (*h.support, *h.contra)]
    parts.append(_fact_rows(h, facts, (("cited", cited),)))
    return "".join(parts)


def _cluster(c: ClusterView, facts: dict[str, FactRecord]) -> str:
    parts = [f"<details class=cluster><summary>{_e(c.cluster.cluster_id)}, "
             f"size {_e(c.cluster.size)}"
             f"{' <span class=blocked>data spend blocked</span>' if c.blocked_data_spend else ''}"
             "</summary>"]
    if c.verdict:  # a model run: say who ranked this cluster
        who = f"model {c.ranked_by}" if c.ranked_by else "code"
        parts.append(f"<p>Ranked by: <span class='badge {'model' if c.ranked_by else 'code'}'>"
                     f"{_e(who)}</span> ({_e(c.verdict)})</p>")
    if c.floor_reason:
        parts.append(f"<p class=muted>{_e(c.floor_reason)}</p>")
    for h in c.hypotheses:
        if h.origin == "model":
            parts.append(_model_hypothesis(h, facts))
            continue
        parts.append(
            f"<h4>{_e(h.rank)}. {_e(h.title)} <span class='badge {_e(h.source)}'>"
            f"{_e(h.source)}</span></h4><p>{_e(h.diagnosis)}: {_e(h.note)}</p>")
        if h.refutes:
            parts.append(f"<p>Rules out: {_e(', '.join(h.refutes))} (by the support facts "
                         "below)</p>")
        if h.explanation:
            parts.append(f"<p>{fill(h.explanation, facts)}</p>")
        parts.append(_fact_rows(h, facts))
    top = c.hypotheses[0] if c.hypotheses else None
    if c.check is not None and top is not None:
        parts.append(f"<p>Check: {_e(c.check.check_id)} (cost {_e(c.check.cost_key)})</p>")
    if c.check_text:
        parts.append(f"<p>{fill(c.check_text, facts)}</p>")
    if c.intervention is not None:
        target = f" for {_e(c.intervention_for)}" if c.intervention_for else ""
        parts.append(f"<p>Intervention: {_e(c.intervention)}{target} "
                     f"<span class='badge {_e(c.intervention_source)}'>"
                     f"{_e(c.intervention_source)}</span></p>")
    if c.intervention_text:
        parts.append(f"<p>{fill(c.intervention_text, facts)}</p>")
    parts.append("</details>")
    return "".join(parts)


def _clusters(a: Assembly, facts: dict[str, FactRecord]) -> str:
    by_run: dict[str, list[ClusterView]] = {}
    for c in a.clusters:  # already largest first
        by_run.setdefault(c.cluster.run, []).append(c)
    runs = sorted(by_run, key=lambda r: (-sum(c.cluster.size for c in by_run[r]), r))
    out = ["<h2>Clusters</h2>"]
    if not runs:
        out.append("<p>No failure cluster.</p>")
    for run in runs:
        out.append(f"<h3>Run {_e(run)}</h3>")
        out += [_cluster(c, facts) for c in by_run[run]]
    return "".join(out)


def _tables(out: Path) -> str:
    parts = ["<h2>Tool tables</h2>"]
    for path in sorted((out / TABLES_DIR).glob("*.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not rows:
            parts.append(f"<p>{_e(path.name)}: no rows.</p>")
            continue
        columns = list(rows[0])
        shown = [[r.get(c, "") for c in columns] for r in rows[:MAX_ROWS]]
        parts.append(_table(path.name, columns, shown))
        if len(rows) > MAX_ROWS:
            parts.append(f"<p class=muted>{len(rows) - MAX_ROWS} more rows</p>")
    return "".join(parts)


def _facts(facts: dict[str, FactRecord]) -> str:
    rows: list[list[object]] = [[f.fact_id, f.name, f.value, f.unit, f.source_ref, f.provenance]
                                for f in facts.values()]
    return "<h2>Facts</h2>" + _table(FACTS_FILE, ["fact id", "name", "value", "unit",
                                                  "source", "provenance"], rows)


def render(out: Path) -> Path:
    """Write `out/index.html` and return its path."""
    assembly = Assembly.model_validate_json((out / ASSEMBLY_FILE).read_text(encoding="utf-8"))
    lines: list[str] = []
    for path in (out / FACTS_FILE, out / INVESTIGATION_FACTS_FILE):
        lines += path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    facts = {f.fact_id: f for f in map(FactRecord.model_validate_json, lines)}
    body = "".join([_header(assembly), _top(assembly), _not_judged(assembly),
                    _clusters(assembly, facts), _tables(out), _facts(facts)])
    page = (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>Agent QA/QC round {_e(assembly.pack_id)}</title><style>{STYLE}</style>"
            f"</head><body>{body}</body></html>\n")
    target = out / INDEX_FILE
    target.write_text(page, encoding="utf-8")
    return target

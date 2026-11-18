/* v5 OPS pages, part 1: shared kit + #/runs, #/eval, #/loop, #/qa.
   Part 2 (pages_ops.js) adds #/jobs. Single global: PAGES_OPS. Components come from UI (core.js). */
(function () {
"use strict";
const P = window.PAGES_OPS = window.PAGES_OPS || {};
const K = P.kit = {};
/* @budget-skip-start */
const GR = { w32: "minmax(0,3fr) minmax(0,2fr)", w21: "minmax(0,2fr) minmax(0,1fr)", groups: "repeat(auto-fill, minmax(110px,1fr))", runs: "minmax(430px,38%) minmax(0,1fr)", jobs: "minmax(380px,40%) minmax(0,1fr)", h: "calc(100vh - 110px)", hair: "1px solid " };
const CMD = {
  train: "finetune_simple_psi0_config", evalRun: "python -m flywheel_psi0.tray.eval_batch --level 1,2", evalRead: "python -m flywheel_psi0.tray.eval_results --json", gen: "generate.py --conditions",
  qaRun: "fw agentqa run --model nemotron --out D", qaReview: "fw agentqa review --reports D/reports.jsonl", qaBench: "python -m flywheel.eval.agentqa.bench"
};
const NUMCLS = "n ops-mono", AMACH = "colab A100", EV_SRC = "docs/he/tray.md";
K.GR = GR;
/* @budget-skip-end */

/* ------------------------------------------------------------ kit */
function h(tag, attrs, kids) {
  const e = document.createElement(tag);
  if (attrs) for (const k in attrs) {
    const v = attrs[k];
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") Object.assign(e.style, v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  (Array.isArray(kids) ? kids : kids == null ? [] : [kids]).flat(9).forEach(c => {
    if (c == null || c === false) return;
    e.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(c) : c);
  });
  return e;
}
async function api(path, body) {
  if (body !== undefined && !UI.canWrite(path.replace(/^\/api\//, "") + (body && body.kind ? " · " + body.kind : ""))) throw new Error("cancelled");
  const o = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, o);
  let d = null; try { d = await r.json(); } catch (e) { /* not json */ }
  if (!r.ok) throw new Error((d && d.error) || ("HTTP " + r.status));
  return d;
}
const tryApi = (path) => api(path).catch(() => null);
const startJob = (kind, params) => api("/api/jobs", { kind, params });
/* interval that stops itself once `owner` leaves the document */
function poll(fn, ms, owner) {
  const t = setInterval(() => { if (owner && !owner.isConnected) { clearInterval(t); return; } fn(); }, ms);
  return t;
}
let _story = null;
/* the same scoping as STORY (TASK.scopeStory): another task's keys and a round's withheld results are left out */
const story = () => (_story || (_story = fetch("data/story.json").then(r => r.json()))).then(s => TASK.scopeStory(s));
const cv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const col = {
  text: () => cv("--text"), t2: () => cv("--text-2"), t3: () => cv("--text-3"), line: () => cv("--line"),
  ok: () => cv("--ok"), warn: () => cv("--warn"), bad: () => cv("--bad"), run: () => cv("--run"),
  acc: () => cv("--accent"), llm: () => cv("--llm"), code: () => cv("--code")
};
/* series colour per run id, fixed order, shared by every page */
/* series colour i, read from the active theme at call time */
const ser = i => cv("--s" + (((i % 8) + 8) % 8 + 1));
/* fallback order when UI.color is missing: the round's runs (seed/tasks.yaml) */
const runOrder = () => (typeof TASK !== "undefined" ? TASK.runs() : []);
const runColor = id => { if (typeof UI !== "undefined" && UI.color) return UI.color(id); const o = runOrder(), i = o.indexOf(id); return ser(i < 0 ? o.length : i); };
const num = (v, f) => (typeof UI !== "undefined" && UI.fmt) ? UI.fmt(v, f) : (v == null ? "—" : String(v));
const dash = v => (v == null || v === "") ? "—" : v;
function secs(s) {
  if (s == null) return "—";
  if (typeof UI !== "undefined" && UI.fmt) return UI.fmt(s, "dur");
  if (s < 60) return num(s, "float1") + " s";
  const m = Math.floor(s / 60);
  return m >= 60 ? Math.floor(m / 60) + "h" + String(m % 60).padStart(2, "0") : m + "m" + String(Math.round(s % 60)).padStart(2, "0");
}
const jobSecs = j => j && j.started ? Math.max(0, ((j.ended ? new Date(j.ended) : new Date()) - new Date(j.started)) / 1000) : null;
const hhmm = iso => iso ? iso.slice(11, 16) : "—";
const dm = iso => iso ? iso.slice(8, 10) + "/" + iso.slice(5, 7) : "—";
const GLYPH = { ok: "✓", done: "✓", running: "▶", run: "▶", queued: "◷", wait: "◷", pending: "◷", failed: "✕", reject: "✕", flag: "!", partial: "!", cancelled: "·", cancel: "·", todo: "·", na: "·", agree: "✓", override: "✕" };
const GCOL = { ok: "ok", done: "ok", agree: "ok", running: "run", run: "run", queued: "warn", wait: "warn", pending: "warn", failed: "bad", reject: "bad", override: "bad", flag: "warn", partial: "warn", cancelled: "t3", cancel: "t3", todo: "t3", na: "t3" };
const STATE_MAP = { done: "ok", partial: "flag", todo: "idle", na: "idle", agree: "ok", override: "reject", cancel: "cancelled" };
function stateTag(s, label) {
  if (typeof UI !== "undefined" && UI.status) return UI.status(STATE_MAP[s] || s, label);
  return h("span", { class: "ops-tag", style: { color: col[GCOL[s] || "t2"]() } }, (GLYPH[s] || "·") + " " + (label || s));
}
function wilson(k, n, z = 1.96) {
  const p = k / n, d = 1 + z * z / n, c = p + z * z / (2 * n), m = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n));
  return [(c - m) / d, (c + m) / d];
}
function ctx(sel) { try { typeof CHAT !== "undefined" && CHAT.setContext && CHAT.setContext(sel); } catch (e) { /* chat optional */ } }
const setQs = p => { try { UI.setQs(p); } catch (e) { /* no router */ } };
function bindKeys(map, scope) { try { UI.keys.bind(map, scope); } catch (e) { /* keys optional */ } }
/* hash-link helper: route fragment without leading # */
const go = frag => { location.hash = "#/" + frag; };

let cssDone = false;
function css() {
  if (cssDone) return; cssDone = true;
  document.head.appendChild(h("style", { id: "ops-css" }, `
.ops-wrap{display:flex;flex-direction:column;gap:12px}
.ops-grid{display:grid;gap:12px}
.ops-panel{background:var(--surface);border:1px solid var(--line);border-radius:4px;padding:8px 12px;min-width:0;overflow-x:auto}
.ops-sec{font-size:11px;line-height:16px;text-transform:uppercase;letter-spacing:.06em;font-weight:600;color:var(--text-2);display:flex;gap:12px;align-items:center;margin:0 0 6px}
.ops-sec .sp{flex:1}
.ops-tag{font-family:var(--mono,"JetBrains Mono",ui-monospace,monospace);font-size:12px;white-space:nowrap}
.ops-mono{font-family:var(--mono,"JetBrains Mono",ui-monospace,monospace);font-variant-numeric:tabular-nums}
.ops-btn{height:26px;padding:0 8px;background:transparent;color:var(--text);border:1px solid var(--line-strong);border-radius:4px;font:inherit;font-size:12.5px;cursor:pointer}
.ops-btn:hover{background:var(--surface-2)}
.ops-btn.pri{background:var(--accent);border-color:var(--accent);color:#fff}
.ops-btn[disabled]{opacity:.4;cursor:default}
.ops-in{height:26px;padding:0 8px;background:var(--surface-2);color:var(--text);border:1px solid var(--line);border-radius:4px;font:inherit;font-size:12.5px}
.ops-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.ops-chart{width:100%}
.ops-dot{display:inline-block;width:8px;height:8px;border-radius:50%}
.ops-eye{cursor:pointer;background:none;border:0;color:var(--text-2);padding:0 2px;font-size:12px}
.ops-eye.off{opacity:.35}
.ops-strip{display:flex;flex-wrap:wrap;gap:0;align-items:stretch}
.ops-node{flex:1 1 0;min-width:84px;border:1px solid var(--line);margin-left:-1px;padding:4px 6px;cursor:pointer;background:var(--surface);display:flex;flex-direction:column;gap:2px;text-decoration:none;color:var(--text)}
.ops-node:first-child{margin-left:0;border-radius:4px 0 0 4px}
.ops-node:last-child{border-radius:0 4px 4px 0}
.ops-node.sel{outline:1px solid var(--accent);outline-offset:-1px;z-index:1}
.ops-node .v{font-size:15px;line-height:20px;font-weight:500}
.ops-node .l{font-size:11px;color:var(--text-2)}
.ops-node .m{font-size:11px;color:var(--text-2)}
.ops-drop{border:1px dashed var(--line-strong);border-radius:4px;padding:16px 12px;color:var(--text-2);cursor:pointer;font-size:12.5px}
.ops-drop.over{border-color:var(--accent);color:var(--text)}
.ops-bar{height:4px;background:var(--line);border-radius:2px}.ops-bar i{display:block;height:4px;background:var(--accent);border-radius:2px}
.ops-tbl{width:100%;border-collapse:collapse;font-size:12.5px}
.ops-tbl th{position:sticky;top:0;text-align:left;font-weight:600;color:var(--text-2);border-bottom:1px solid var(--line-strong);padding:4px 8px;font-size:11px;background:var(--surface)}
.ops-tbl td{padding:0 8px;height:28px;border-bottom:1px solid var(--line);white-space:nowrap}
.ops-tbl .n{text-align:right}
.ops-tbl tr.cur td{background:var(--surface-2)}
.ops-tbl tr.cur td:first-child{box-shadow:inset 2px 0 0 var(--accent)}
.ops-tbl tr.click{cursor:pointer}
.ops-sticky{position:sticky;bottom:0;z-index:3;background:var(--bg);padding-top:6px}
`));
}

/* tables: UI.Table with a safe fallback while core.js components land */
function table(spec) {
  const colLab = c => tt("ops.col." + (c.label || c.key).toLowerCase().replace(/[^a-z0-9]+/g, "_"), c.label || c.key);
  spec = Object.assign({}, spec, { columns: spec.columns.map(c => Object.assign({}, c, { label: colLab(c) })) });
  if (typeof UI !== "undefined" && UI.Table) return UI.Table(spec);
  const t = h("table", { class: "ops-tbl" }, [
    h("thead", null, h("tr", null, spec.columns.map(c => h("th", { text: c.label })))),
    h("tbody", null, spec.rows.map(r => h("tr", { class: spec.onRow ? "click" : "", onclick: spec.onRow ? () => spec.onRow(r) : null },
      spec.columns.map(c => { const v = c.fmt ? c.fmt(r[c.key], r) : r[c.key]; return h("td", { class: c.align === "right" ? NUMCLS : (c.mono ? "ops-mono" : "") }, v instanceof Node ? v : dash(v)); }))))]);
  return h("div", null, t);
}
/* panel titles and column headers read the dictionary (ops.<label>, ops.col.<key>); an unknown one stays as written */
const tt = (k, fb) => { const v = t(k); return v === k ? fb : v; };
const lab = x => typeof x === "string" ? tt("ops." + x.toLowerCase().replace(/[^a-z0-9]+/g, "_"), x) : x;
function sec(label, right) { return h("div", { class: "ops-sec" }, [lab(label), h("span", { class: "sp" }), right || null]); }
function panel(label, body, right, style) { return h("div", { class: "ops-panel", style }, [sec(label, right), body]); }
function pageHead(title, stat, actions) {
  const acts = actions == null ? [] : [].concat(actions), st = stat && stat.length ? stat.map(x => Object.assign({}, x, { label: lab(x.label) })) : null;
  /* on a process stage the stage header (PROC.head) names the page; elsewhere (Jobs) the page keeps its title */
  const stage = typeof EXPLAIN !== "undefined" && EXPLAIN.stationOf(location.hash.replace(/^#\/?/, "").split("?")[0], UI.qs()) != null;
  if (!stage && typeof UI !== "undefined" && UI.page) return UI.page({ title: lab(title), stat: st, actions: acts.length ? acts : null });
  return h("div", { class: "ops-row pr-statrow" }, [st ? statLine(st) : null, ...acts]);
}
function statLine(items) { return (typeof UI !== "undefined" && UI.StatLine) ? UI.StatLine(items) : h("div", { class: "ops-mono", text: items.map(i => i.label + " " + i.value).join(" · ") }); }
function logView(spec) { return (typeof UI !== "undefined" && UI.Log) ? UI.Log(spec) : h("pre", { class: "ops-mono", text: spec.text || "" }); }
function repro(spec) { return (typeof UI !== "undefined" && UI.Repro) ? UI.Repro(spec) : null; }
Object.assign(K, { h, api, tryApi, startJob, poll, story, col, runColor, num, dash, secs, jobSecs, hhmm, dm, stateTag, wilson, ctx, bindKeys, go, css, table, sec, panel, pageHead, statLine, logView, repro, GLYPH });

/* charts: one registry, disposed on the next page render */
let CH = [];
function chartsDispose() { CH.forEach(c => { try { c.dispose(); } catch (e) { /* gone */ } }); CH = []; }
function ec(box, opt, group) {
  const c = echarts.init(box, null, { renderer: "canvas" });
  c.setOption(Object.assign({ animation: false, backgroundColor: "transparent", textStyle: { color: col.t2(), fontSize: 11 } }, opt));
  if (group) c.group = group;
  CH.push(c);
  const ro = new ResizeObserver(() => { try { c.resize(); } catch (e) { /* disposed */ } });
  ro.observe(box);
  return c;
}
const axis = o => Object.assign({ axisLine: { lineStyle: { color: col.line() } }, axisTick: { show: false }, axisLabel: { color: col.t2(), fontSize: 11 },
  splitLine: { lineStyle: { color: col.line(), type: "dashed" } }, nameTextStyle: { color: col.t2(), fontSize: 11 } }, o);
function setPanel(o) { try { if (typeof UI !== "undefined" && UI.panel && UI.panel.set) UI.panel.set(o); } catch (e) { /* panel optional */ } }
const box = (hgt) => h("div", { class: "ops-chart", style: { height: hgt + "px" } });
Object.assign(K, { ec, axis, setPanel, box, ser });
const ema = (pts, a) => { let m = null; return pts.map(([x, y]) => { m = m == null ? y : a * m + (1 - a) * y; return [x, m]; }); };

/* ============================================================ RUNS */
/* abandoned attempts (branch "<run>.attempt1") were re-run in full; they are not runs of the experiment */
const notAttempt = r => !/\.attempt/.test(r.branch || "");
const IDENTITY_KEYS = new Set(["exp", "timestamp", "train.output_dir"]);
function flatConfig(r) {
  const c = r.config || {}, o = Object.assign({}, c, c.flags || {});
  delete o.flags;
  return o;
}
function storyConfig(r) {
  const flags = {};
  (r.argv || []).slice(1).forEach(a => { const m = /^--([^=]+)=(.*)$/.exec(a); if (m) flags[m[1]] = m[2]; });
  return { release_id: r.release, run_plan_id: r.run_plan_id, flags };
}
/* live runs: run_list + run_metrics tools; story.json as fallback */
async function loadLive(S) {
  const tool = (name, args) => UI.locked ? Promise.resolve(null) : tryApi("/api/tool?name=" + name + "&args=" + encodeURIComponent(JSON.stringify(args)));
  const rl = await tool("run_list", {});
  const runs = rl && rl.raw && rl.raw.runs;
  if (!runs || !runs.length) return S.runs.filter(notAttempt).map(r => ({ branch: r.branch, run: r.job, step: r.step, max_steps: r.max_steps, ema50: null, machine: AMACH, mtime: null, config: storyConfig(r),
    loss: r.loss, thr: r.thr.filter(p => p[1] != null), vram: r.vram, groups: r.groups_last, gser: {} }));
  return Promise.all(runs.filter(notAttempt).map(async r => {
    const m = await tool("run_metrics", { run_id: r.run, keys: "all", points: 2000 }), x = (m && m.raw) || {}, groups = {}, gser = {};
    Object.keys(x).forEach(k => { if (k.startsWith("loss_by_group.")) { const v = x[k]; gser[k.slice(14)] = v; groups[k.slice(14)] = v.length ? v[v.length - 1][1] : null; } });
    return Object.assign({}, r, { loss: x.loss || [], thr: x.throughput || [], vram: x.vram_gb || [], groups, gser });
  }));
}
const tail = v => { v = String(v); return v.length > 20 ? "…" + v.slice(-18) : v; };

async function runsPage(main, params, qs) {
  css(); chartsDispose(); main.replaceChildren();
  const S = await story();
  let live = await loadLive(S);
  const q = Object.assign({}, qs || (typeof UI !== "undefined" && UI.qs ? UI.qs() : {}));
  const state = {
    sel: new Set((q.sel ? q.sel.split(",") : live.map(r => r.branch)).filter(Boolean)),
    cmp: new Set((q.cmp ? q.cmp.split(",") : []).filter(Boolean)),
    smooth: q.smooth != null ? Math.min(.99, Math.max(0, +q.smooth)) : .9,
    logy: q.logy == null ? true : q.logy === "1" || q.logy === "true", raw: q.raw === "1",
    step: q.step != null ? +q.step : null,
    cur: null
  };
  const setQs = () => { try { UI.setQs({ sel: [...state.sel].join(","), cmp: [...state.cmp].join(",") || null, smooth: state.smooth, logy: state.logy ? 1 : 0, raw: state.raw ? 1 : null }); } catch (e) { /* no router */ } };
  const lastEma = r => { const e = ema(r.loss, state.smooth); return e.length ? e[e.length - 1][1] : null; };
  const rowsOf = () => live.map(r => ({ id: r.branch, step: r.step, max: r.max_steps, loss: r.ema50 != null ? r.ema50 : lastEma(r), machine: r.machine, cu: cuOf(r.branch), updated: r.mtime, live: true }));
  /* CU per model: story.demo.design.resource train_cu (index), never typed */
  const cuOf = id => { const x = ((((S.demo || {}).design || {}).resource) || []).find(y => y.id === "train_cu"); return x && x.per_model_cu && x.per_model_cu[id] != null ? x.per_model_cu[id] : null; };
  const liveBy = id => live.find(r => r.branch === id);

  /* header */
  const stat = [{ label: "runs", value: String(live.length) }, { label: "CU", value: num((S.colab_balance.at(-1) || [])[1], "float1") }];
  main.appendChild(pageHead("Runs", stat));

  /* left: table */
  const tbox = h("div", { style: { overflowX: "auto" } });
  let tbl = null;
  const curRow = () => tbl && tbl.table && tbl.table.cursor;
  function drawTable() {
    const rows = rowsOf();
    if (tbl && tbl.table) { tbl.table.setRows(rows); return; }
    tbl = table({
      columns: [
        { key: "id", label: "run", mono: true, fmt: (v, r) => h("span", { class: "ops-row", style: { gap: "6px", flexWrap: "nowrap" } }, [
          h("span", { class: "ops-dot", style: { background: runColor(v) } }),
          r.live ? h("button", { class: "ops-eye" + (state.sel.has(v) ? "" : " off"), title: "show", onclick: e => { e.stopPropagation(); state.sel.has(v) ? state.sel.delete(v) : state.sel.add(v); drawTable(); drawCharts(); setQs(); } }, "◉") : h("span", { class: "ops-eye off" }, "◉"),
          h("span", { class: "ops-mono", title: v, text: EXPLAIN.runName(v) }), state.cmp.has(v) ? h("span", { class: "ops-tag", style: { color: col.acc() } }, "x") : null]) },
        { key: "step", label: "step/" + (TASK.maxSteps() ? num(TASK.maxSteps() / 1000, "int") + "k" : "max"), align: "right", mono: true, fmt: (v, r) => v == null ? "—" : h("span", { class: "ops-row", style: { gap: "6px", flexWrap: "nowrap", justifyContent: "flex-end" } }, [h("span", { class: "ops-bar", style: { width: "44px" } }, h("i", { style: { width: Math.min(100, v / (r.max || TASK.maxSteps() || v || 1) * 100) + "%", background: runColor(r.id) } })), (v >= 1000 ? num(v / 1000, "float1") + "k" : String(v))]) },
        { key: "loss", align: "right", mono: true, fmt: v => v == null ? "—" : num(v, "float3") },
        { key: "machine", label: "host", fmt: v => v ? String(v).replace(/^colab /, "") : "—" },
        { key: "cu", label: "CU", align: "right", mono: true, fmt: v => v == null ? "—" : num(v, "float1") },
        { key: "updated", mono: true, fmt: v => v ? dm(v) : "—" }
      ],
      rows, qsKey: "run", onRow: r => { state.cur = r.id; pushCtx(); }
    });
    tbox.replaceChildren(tbl);
  }
  function toggleCmp(id) {
    if (!liveBy(id)) return;
    state.cmp.has(id) ? state.cmp.delete(id) : state.cmp.add(id);
    drawTable(); drawDiff(); setQs(); pushCtx();
  }
  function pushCtx() {
    ctx({ route: "runs", selection: { runs: [...state.sel], compare: [...state.cmp] } });
    const r = liveBy(state.cur) || live[0]; if (!r) return;
    const c = flatConfig(r);
    setPanel({ method: [{ step: "train", cmd: CMD.train + " " + Object.keys(c.flags || c).filter(k => /^(seed|data\.root_dir|model\.model_name_or_path)$/.test(k)).map(k => "--" + k + "=" + c[k]).join(" ") }, { step: "metrics", cfg: "fwdata/" + TASK.trainDir() + "/" + r.branch + "/" + r.run + "/metrics.jsonl" }],
      log: null, sources: [{ label: r.branch + " metrics", path: "fwdata/" + TASK.trainDir() + "/" + r.branch + "/" + r.run + "/metrics.jsonl" }, { label: "launch", path: "fwdata/" + TASK.trainDir() + "/" + r.branch + "/" + r.run + "/launch.json" }] });
  }

  /* right: charts */
  const lossBox = h("div", { class: "ops-chart", style: { height: "220px" } });
  const thrBox = h("div", { class: "ops-chart", style: { height: "140px" } });
  const vramBox = h("div", { style: { minHeight: "140px" } });
  const cuBox = h("div", { class: "ops-chart", style: { height: "140px" } });
  const groups = Object.keys((live[0] || {}).groups || {});
  const gBoxes = groups.map(g => h("div", null, [h("div", { class: "ops-mono", style: { fontSize: "11px", color: col.t2() }, text: g }), h("div", { class: "ops-chart", style: { height: "80px" } })]));
  const slider = h("input", { type: "range", min: 0, max: .99, step: .01, value: state.smooth, style: { width: "90px" }, oninput: e => { state.smooth = +e.target.value; smoothLab.textContent = state.smooth.toFixed(2); drawTable(); drawCharts(); }, onchange: setQs });
  const smoothLab = h("span", { class: "ops-mono", text: state.smooth.toFixed(2) });
  const rawChk = h("input", { type: "checkbox", checked: state.raw, onchange: e => { state.raw = e.target.checked; drawCharts(); setQs(); } });
  const logyChk = h("input", { type: "checkbox", checked: state.logy, onchange: e => { state.logy = e.target.checked; drawCharts(); setQs(); } });
  const lossRight = h("span", { class: "ops-row", style: { textTransform: "none", letterSpacing: 0 } }, [h("span", { text: "EMA" }), slider, smoothLab, h("label", { class: "ops-row", style: { gap: "4px" } }, [rawChk, "raw"]), h("label", { class: "ops-row", style: { gap: "4px" } }, [logyChk, "log-y"])]);
  const GROUP = "runs-x";
  let cLoss, cThr, cCu; const cG = [];
  const tipFmt = ps => { const L = (Array.isArray(ps) ? ps : [ps]).filter(p => !/raw$/.test(p.seriesName)).sort((a, b) => b.value[1] - a.value[1]);
    return (L.length ? "<span class=ops-mono>step " + L[0].value[0] + "</span><br>" : "") + L.map(p => "<span class=ops-mono style='display:flex;justify-content:space-between;gap:12px'><span>" + p.marker + p.seriesName + "</span><b>" + (+p.value[1]).toFixed(3) + "</b></span>").join(""); };
  const vis = () => live.filter(r => state.sel.has(r.branch));
  function drawCharts() {
    const rs = vis();
    const stepLine = state.step != null ? { silent: true, symbol: "none", lineStyle: { color: col.warn(), type: "dashed" }, label: { formatter: String(state.step), color: col.warn() }, data: [{ xAxis: state.step }] } : undefined;
    const xmax = Math.ceil(Math.max(1000, ...live.map(r => r.step || 0)) * 1.05);
    const target = { silent: true, symbol: "none", lineStyle: { color: col.t3(), type: "dashed" }, label: { formatter: "target", color: col.t3() }, data: TASK.maxSteps() ? [{ xAxis: TASK.maxSteps() }] : [] };
    const lossSeries = rs.flatMap((r, i) => {
      const c = runColor(r.branch);
      return (state.raw ? [{ name: r.branch + " raw", type: "line", showSymbol: false, data: r.loss, lineStyle: { width: 1, color: c, opacity: .15 }, silent: true, z: 1 }] : []).concat([
        { name: r.branch, type: "line", showSymbol: false, data: ema(r.loss, state.smooth), lineStyle: { width: 2, color: c }, itemStyle: { color: c }, z: 3, markLine: i === 0 ? Object.assign({}, target, stepLine ? { data: target.data.concat(stepLine.data) } : {}) : undefined }]);
    });
    const base = { grid: { left: 44, right: 10, top: 8, bottom: 22 }, tooltip: { trigger: "axis", confine: true, formatter: tipFmt, backgroundColor: cv("--surface-2"), borderColor: col.line(), textStyle: { color: col.text(), fontSize: 11 } },
      xAxis: axis({ type: "value", min: 0, max: xmax, axisLabel: { color: col.t2(), fontSize: 11, formatter: v => v / 1000 + "k" } }) };
    const set = (c, opt) => c.setOption(opt, true);
    if (!cLoss) { cLoss = ec(lossBox, {}, GROUP); cThr = ec(thrBox, {}, GROUP); cCu = ec(cuBox, {}); gBoxes.forEach(b => cG.push(ec(b.lastChild, {}, GROUP))); echarts.connect(GROUP); }
    set(cLoss, Object.assign({}, base, { yAxis: axis({ type: state.logy ? "log" : "value", min: state.logy ? undefined : 0 }), series: lossSeries }));
    set(cThr, Object.assign({}, base, { yAxis: axis({ type: "value", scale: true }), series: rs.map(r => ({ name: r.branch, type: "line", showSymbol: false, data: ema(r.thr.filter(p => p[1] != null), state.smooth), lineStyle: { width: 1.5, color: runColor(r.branch) }, itemStyle: { color: runColor(r.branch) } })) }));
    vramBox.replaceChildren(statLine(rs.map(r => ({ label: r.branch, value: r.vram.length ? num(r.vram[r.vram.length - 1][1], "float1") : "—", unit: "GB" }))));
    const bal = S.colab_balance; let jump = 0;
    for (let i = 1; i < bal.length; i++) if (Math.abs(bal[i][1] - bal[i - 1][1]) > 100) { jump = i; break; }
    set(cCu, { grid: { left: 44, right: 10, top: 8, bottom: 22 }, tooltip: { trigger: "axis", textStyle: { fontSize: 11 } }, xAxis: axis({ type: "time" }), yAxis: axis({ type: "value", scale: true }),
      series: [{ type: "line", step: "end", showSymbol: false, data: bal.slice(jump), lineStyle: { width: 1.5, color: col.t2() } }] });
    groups.forEach((g, i) => set(cG[i], { grid: { left: 30, right: 4, top: 4, bottom: 4 }, tooltip: base.tooltip,
      xAxis: axis({ type: "value", min: 0, max: xmax, axisLabel: { show: false } }), yAxis: axis({ type: "value", min: 0, splitNumber: 2, axisLabel: { color: col.t2(), fontSize: 10 } }),
      series: rs.map(r => ({ name: r.branch, type: "line", showSymbol: false, data: ema(r.gser[g] || [], state.smooth), lineStyle: { width: 1.5, color: runColor(r.branch) }, itemStyle: { color: runColor(r.branch) } })) }));
    pushCtx();
  }

  /* config diff */
  const diffBox = h("div", { style: { overflowX: "auto" } });
  function drawDiff() {
    const ids = state.cmp.size >= 2 ? [...state.cmp] : [];
    diffBox.replaceChildren();
    if (ids.length < 2) { diffBox.style.display = "none"; return; }
    diffBox.style.display = "";
    const cfgs = ids.map(id => flatConfig(liveBy(id)));
    const keys = [...new Set(cfgs.flatMap(c => Object.keys(c)))].filter(k => !IDENTITY_KEYS.has(k) && new Set(cfgs.map(c => c[k])).size > 1);
    diffBox.appendChild(panel("Diff", keys.length
      ? h("table", { class: "ops-tbl" }, [h("thead", null, h("tr", null, [h("th", { text: "key" })].concat(ids.map(id => h("th", { style: { color: runColor(id) }, text: id }))))),
        h("tbody", null, keys.map(k => h("tr", null, [h("td", { class: "ops-mono", text: k })].concat(cfgs.map(c => h("td", { class: "ops-mono", title: dash(c[k]), text: c[k] == null ? "—" : tail(c[k]) }))))))])
      : h("span", { class: "ops-mono", style: { color: col.t2() }, text: "none" }),
      h("button", { class: "ops-btn", text: lab("Clear"), onclick: () => { state.cmp.clear(); drawTable(); drawDiff(); setQs(); } })));
  }

  /* the training log lives in the stage's Log tab (PROC.log), not under the charts */
  /* layout */
  const right = h("div", { class: "ops-wrap", style: { minWidth: 0 } }, [
    panel("Loss", lossBox, lossRight),
    panel("Groups", h("div", { class: "ops-grid", style: { gridTemplateColumns: GR.groups } }, gBoxes)),
    h("div", { class: "ops-grid", style: { gridTemplateColumns: "repeat(3,minmax(0,1fr))" } }, [panel("Throughput", thrBox), panel("VRAM", vramBox), panel("CU burn", cuBox)])
  ]);
  const root = h("div", { class: "ops-wrap" }, [
    h("div", { class: "ops-grid", style: { gridTemplateColumns: GR.runs, alignItems: "start" } }, [h("div", { class: "ops-wrap", style: { minWidth: 0 } }, [panel("Runs", tbox, h("button", { class: "ops-btn", text: lab("Compare"), onclick: () => { if (state.cmp.size < 2) live.slice(0, 2).forEach(r => state.cmp.add(r.branch)); drawTable(); drawDiff(); setQs(); } })), diffBox]), right])
  ]);
  main.appendChild(root);
  drawTable(); drawCharts(); drawDiff();
  poll(async () => { live = await loadLive(S); drawTable(); drawCharts(); drawDiff(); }, 60 * 1000, root);
  bindKeys({
    x: () => { const r = curRow(); if (r) toggleCmp(r.id); },
    c: () => { if (state.cmp.size < 2) live.slice(0, 2).forEach(r => state.cmp.add(r.branch)); drawTable(); drawDiff(); setQs(); }
  }, root);
}

/* ============================================================ EVAL */
const pctS = v => (v * 100).toFixed(1) + "%";

/* bar per category with a Wilson whisker; ks successes of ns */
function succChart(el, cats, ks, ns) {
  ec(el, { grid: { left: 36, right: 10, top: 10, bottom: 22 }, tooltip: { trigger: "axis" }, xAxis: axis({ type: "category", data: cats, axisLabel: { color: col.t2(), fontSize: 11, interval: 0 } }), yAxis: axis({ type: "value", min: 0, axisLabel: { formatter: "{value}%", color: col.t2(), fontSize: 11 } }),
    series: [{ type: "bar", barMaxWidth: 28, data: ks.map((k, i) => +(k / ns[i] * 100).toFixed(1)), itemStyle: { color: col.acc(), borderRadius: 2 } },
      { type: "custom", z: 5, data: ks.map((k, i) => { const w = wilson(k, ns[i]); return [i, +(w[0] * 100).toFixed(1), +(w[1] * 100).toFixed(1)]; }), tooltip: { formatter: p => p.value[1] + "–" + p.value[2] + "%" },
        renderItem: (p, a) => { const lo = a.coord([a.value(0), a.value(1)]), hi = a.coord([a.value(0), a.value(2)]), st = { stroke: col.text(), lineWidth: 1.5 };
          return { type: "group", children: [{ type: "line", shape: { x1: lo[0], y1: lo[1], x2: hi[0], y2: hi[1] }, style: st }, { type: "line", shape: { x1: lo[0] - 5, y1: lo[1], x2: lo[0] + 5, y2: lo[1] }, style: st }, { type: "line", shape: { x1: hi[0] - 5, y1: hi[1], x2: hi[0] + 5, y2: hi[1] }, style: st }] }; } }] });
}
const L_CI = "CI 95%", L_D = "Δ", OUT_F = "F", PG_EVAL = "Eval";
const [P_SUCC, P_STACK, P_EVALS, P_FUN, P_CMP] = ["Success", "Failure stack", "Evals", "Step pass %", "Compare"];
/* "p" meant two things: the success rate in Evals and McNemar's p-value in Compare */
const [L_RATE, L_MCN] = ["rate", "p McNemar"];
/* the Failure → Data round run (role after_round) and its stage-1 outcome against every baseline */
function pairRound(PR) {
  const rr = (PR.runs || []).find(r => r.run === TASK.after()) || null;
  const cs = rr ? (PR.comparisons || []).filter(c => c.variant === rr.run) : [];
  const out = cs.length && cs.every(c => c.outcome === OUT_F) ? OUT_F : (cs[0] || {}).outcome;
  return { rr, cs, out };
}
function funnel(cats, series) {
  const fb = (typeof UI !== "undefined" && UI.Chart) ? UI.Chart({ type: "bar", categories: cats.map(x => TASK.stageName(x)), series }, { height: 200 }) : h("div", { class: "ops-mono", text: "—" });
  if (fb.instance) { let tries = 0; const fix = () => { const c = fb.instance(); if (c) c.setOption({ xAxis: { axisLabel: { interval: 0, fontSize: 10 } } }); else if (tries++ < 40) setTimeout(fix, 100); }; fix(); }
  return fb;
}

/* the round's runs read at stage 1 (story.pair) */
/* the scorer marks each step on its own, so the last step can disagree with the success count */
function stepGap(r, steps) {
  const last = (steps || []).at(-1), k = last == null ? null : Math.round((r.step_pass[last] || 0) * r.n);
  if (k == null || k === r.successes) return null;
  return h("span", { style: { color: col.warn() }, title: `${r.run}: ${r.successes} successes, ${last} passed ${k}` }, "⚠");
}
function evalPair(main, PR) {
  const R = PR.runs, best = R.find(r => r.run === PR.best) || R[0], { rr, cs, out } = pairRound(PR);
  const frac = r => r.successes + "/" + r.n, lvS = (r, lv) => (r.levels || {})[lv] ? r.levels[lv].successes + "/" + r.levels[lv].n : "—";
  const stat = [{ label: "runs", value: String(R.length) }, { label: "best", value: best.run + " " + frac(best) }];
  if (rr) stat.push({ label: "round", value: rr.run + " " + frac(rr) + " · " + dash(out) });
  main.appendChild(pageHead(PG_EVAL, stat));
  const top = f => Object.keys(f || {}).slice(0, 2).map(k => k.replace("L-", "") + " " + f[k]).join(" · ");
  const runTable = table({
    columns: [
      { key: "run", mono: true, fmt: (v, r) => h("span", { class: "ops-row", style: { gap: "6px" }, title: v }, [h("span", { class: "ops-dot", style: { background: runColor(v) } }), EXPLAIN.runName(v),
        v === best.run ? stateTag("ok", "best") : null, rr && v === rr.run ? stateTag("run", "round") : null]) },
      { key: "succ", align: "right", mono: true, fmt: (v, r) => frac(r) }, { key: "p", label: L_RATE, align: "right", mono: true, fmt: v => pctS(v) },
      { key: "wilson", label: L_CI, align: "right", mono: true, fmt: v => v ? (v[0] * 100).toFixed(1) + "–" + (v[1] * 100).toFixed(1) : "—" },
      { key: "l1", align: "right", mono: true, fmt: (v, r) => lvS(r, "1") }, { key: "l2", align: "right", mono: true, fmt: (v, r) => lvS(r, "2") },
      { key: "failures", mono: true, fmt: v => top(v) }
    ], rows: R.map(r => Object.assign({ id: r.run, succ: r.successes, l1: 0, l2: 0 }, r)), qsKey: "run", onRow: r => ctx({ route: "eval", selection: { run: r.run } })
  });
  const funBox = funnel(PR.steps || [], R.map(r => ({ name: r.run + " " + frac(r), values: (PR.steps || []).map(s => +((r.step_pass[s] || 0) * 100).toFixed(1)) })));
  const legend = h("div", { class: "ops-row ops-mono", style: { gap: "12px", fontSize: "11px" } }, R.map(r => h("span", { class: "ops-row", style: { gap: "4px" } }, [h("span", { class: "ops-dot", style: { background: (typeof UI !== "undefined" && UI.color) ? UI.color(r.run + " " + frac(r)) : col.acc() } }), r.run, stepGap(r, PR.steps)])));
  /* the round's comparisons first: they carry the stop decision */
  const crow = cs.concat((PR.comparisons || []).filter(c => cs.indexOf(c) < 0)).map(c => Object.assign({ id: c.variant + "·" + c.baseline, p: c.mcnemar_p }, c));
  const cmpTable = table({
    columns: [
      { key: "pair", mono: true, fmt: (v, r) => r.variant + " vs " + r.baseline }, { key: "succ", align: "right", mono: true, fmt: (v, r) => r.variant_succ + " vs " + r.baseline_succ },
      { key: "diff", label: L_D, align: "right", mono: true, fmt: v => v == null ? "—" : (v > 0 ? "+" : "") + (v * 100).toFixed(1) },
      { key: "ci", label: L_CI, align: "right", mono: true, fmt: v => v ? (v[0] * 100).toFixed(1) + "–" + (v[1] * 100).toFixed(1) : "—" },
      { key: "p", label: L_MCN, align: "right", mono: true, fmt: v => v == null ? "—" : String(v) },
      { key: "outcome", fmt: v => stateTag(v === OUT_F ? "failed" : "ok", dash(v)) }
    ], rows: crow, qsKey: "cmp"
  });
  const labels = []; R.forEach(r => Object.keys(r.failures || {}).forEach(k => { if (labels.indexOf(k) < 0) labels.push(k); }));
  const sBox = box(170), fBox = box(170), src = h("span", { class: "ops-mono", style: { textTransform: "none", letterSpacing: 0, color: col.t3() } }, PR.source || "");
  main.appendChild(h("div", { class: "ops-wrap" }, [
    h("div", { class: "ops-grid", style: { gridTemplateColumns: "repeat(2,minmax(0,1fr))" } }, [panel(P_SUCC, sBox, src), panel(P_STACK, fBox)]),
    panel(P_EVALS, runTable),
    h("div", { class: "ops-grid", style: { gridTemplateColumns: GR.w32 } }, [panel(P_FUN, h("div", null, [legend, funBox])), panel(P_CMP, cmpTable)])
  ]));
  succChart(sBox, R.map(r => r.run), R.map(r => r.successes), R.map(r => r.n));
  ec(fBox, { grid: { left: 36, right: 10, top: 10, bottom: 22 }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" } }, xAxis: axis({ type: "category", data: R.map(r => r.run), axisLabel: { color: col.t2(), fontSize: 11, interval: 0 } }), yAxis: axis({ type: "value" }),
    series: labels.map((k, i) => ({ name: k, type: "bar", stack: "f", barMaxWidth: 36, data: R.map(r => (r.failures || {})[k] || 0), itemStyle: { color: ser(i) } })) });
  setPanel({ method: [{ step: "run", cmd: CMD.evalRun }, { step: "read", cmd: CMD.evalRead }], log: null, sources: [{ label: (PR.source || "").split("/").pop(), path: PR.source }] });
  ctx({ route: "eval", selection: { run: best.run } });
}

async function evalPage(main, params, qs) {
  css(); chartsDispose(); main.replaceChildren();
  const S = await story();
  if (S.pair && (S.pair.runs || []).length) return evalPair(main, S.pair);
  main.appendChild(TASK.empty(4));
}

/* ============================================================ LOOP */
/* the C70_R1 round: cited chain (tray.md §20.11–20.16) plus its stage-1 read from fwdata; null when either is missing */
function roundLoop(S) {
  const RC = S.round || {}, c = RC.chain, { rr, cs, out } = pairRound(S.pair || {});
  if (!c || !rr) return null;
  const tr = (S.runs || []).find(r => r.branch === rr.run), stop = out === OUT_F;
  const vs = cs.map(x => x.variant_succ + " vs " + x.baseline_succ + " " + x.baseline).join(" · ");
  const chain = [
    [String(c.targets), "targets", "bad", "loop"], [String(c.generated), "generated", "ok", "data"], [String(c.recorded), "recorded", "ok", "data"],
    [String(c.qa_pass), "qa", "ok", "qa"], [String(c.quality), "quality", "ok", "data"], [String(c.selected), "selected", "ok", "data"],
    [tr ? Math.round(tr.step / 1000) + "k" : "—", rr.run, "ok", "runs"], [rr.successes + "/" + rr.n, "re-eval", "ok", "eval", vs], [stop ? "STOP" : dash(out), "stage1 " + dash(out), stop ? "bad" : "ok", "eval", vs]
  ];
  const rows = (RC.clusters || []).map(k => ({ id: k.id, stage: k.stage, n: k.n, diag: k.diagnosis, data: k.failures != null, interv: k.intervention + (k.failures != null ? "" : " · soạn sẵn, chưa mở"), eps: k.failures }));
  const flow = lk => {
    const [gen, rec, qa, q, sel] = [c.generated, c.recorded, c.qa_pass, c.quality, c.selected], R = rr.run;
    const nodes = ["generated", "failed", "recorded", "rejected", "passed", "filtered", "quality", "spare", "selected", R, "stop"].map(name => ({ name }));
    const links = [lk("generated", "recorded", rec), lk("generated", "failed", gen - rec), lk("recorded", "passed", qa), lk("recorded", "rejected", rec - qa), lk("passed", "quality", q), lk("passed", "filtered", qa - q),
      lk("quality", "selected", sel), lk("quality", "spare", q - sel), lk("selected", R, sel), lk(R, "stop", sel)];
    return { nodes, links, cols: { generated: 0, recorded: 1, passed: 2, quality: 3, selected: 4, [R]: 5, stop: 6 }, warn: "", bad: "stop" };
  };
  const src = h("span", { class: "ops-mono", style: { textTransform: "none", letterSpacing: 0, color: col.t3() }, title: RC.plan || "" }, RC.source || "");
  return { chain, rows, flow, src };
}

async function loopPage(main, params, qs, mode) {
  css(); chartsDispose(); main.replaceChildren();
  const S = await story();
  const cost = mode === "cost";
  if (cost) return costPage(main, S);
  const RD = roundLoop(S);
  if (!RD) { main.appendChild(TASK.empty(6)); return; }
  const strip = h("div", { class: "ops-strip" }, RD.chain.map(([v, l, st, link, m]) => h("a", { class: "ops-node", href: "#/" + link, title: m || "" }, [
    h("span", { class: "v ops-mono", style: { color: st === "bad" ? col.bad() : st === "pending" ? col.warn() : col.text() }, text: v }), h("span", { class: "l", text: lab(l) }), st === "pending" ? stateTag("pending", "wait") : null])));
  const clusters = table({
    columns: [{ key: "id", label: "cluster", mono: true }, { key: "stage", mono: true, fmt: v => TASK.stageName(v) }, { key: "n", label: "n", align: "right", mono: true },
      { key: "diag", label: "diagnosis", fmt: (v, r) => stateTag(r.data ? "run" : "todo", v) }, { key: "interv", label: "intervention" }, { key: "eps", label: "targets", mono: true }],
    rows: RD.rows, qsKey: "cluster", onRow: r => ctx({ route: "loop", selection: { cluster: r.id } })
  });
  const flowBox = box(360);
  main.appendChild(h("div", { class: "ops-wrap" }, [strip, panel("Flow", flowBox, RD.src), panel("Clusters", clusters)]));
  const lk = (source, target, value) => ({ source, target, value });
  const { nodes, links, cols, warn, bad } = RD.flow(lk);
  const CHAIN = { ...cols };
  ec(flowBox, { tooltip: { trigger: "item" }, series: [{ type: "sankey", left: 24, right: 60, top: 40, bottom: 40, nodeWidth: 10, nodeGap: 14, emphasis: { focus: "adjacency" },
    label: { color: col.text(), fontSize: 11, formatter: p => (p.value != null ? p.value + "\n" : "") + lab(p.name) }, lineStyle: { color: "gradient", opacity: .35 }, itemStyle: { borderWidth: 0 },
    /* main chain alternates label side by column so neighbours never share a row; sinks sit in the last column, labelled to the right */
    data: nodes.map((n, i) => Object.assign(n, { label: { position: n.name in CHAIN ? (CHAIN[n.name] % 2 ? "top" : "bottom") : "right" }, itemStyle: { color: n.name === warn ? col.warn() : n.name === bad ? col.bad() : ser(i) } })),
    links }] });
  setPanel({ method: [{ step: "eval", cmd: CMD.evalRun }, { step: "generate", cmd: CMD.gen }, { step: "train", cmd: CMD.train }], log: null, sources: [{ label: S.round.source, path: EV_SRC }] });
  ctx({ route: "loop" });
}

/* ============================================================ COST LEDGER (stage 0): estimates and measurements as separate rows */
async function costPage(main, S) {
  if (!S.ledger) { main.appendChild(TASK.empty(0)); return; }
  const live = await tryApi("/api/status");
  const bal = (live && live.machines && live.machines.colab && live.machines.colab.balance) || ((S.colab_balance || []).at(-1) || [])[1];
  const L = S.ledger.filter(r => r[1] || r[2]);
  const est = S.ledger.reduce((a, r) => a + r[1], 0), meas = S.ledger.reduce((a, r) => a + r[2], 0);
  main.appendChild(pageHead("Ledger", [{ label: "measured", value: num(meas, "float1"), unit: "$" }, { label: "estimated", value: num(est, "float1"), unit: "$" }, { label: "CU", value: num(bal, "float1") }]));
  const lrows = [];
  L.forEach(r => { if (r[1]) lrows.push({ id: r[0] + "·e", story: r[0], kind: "estimated", usd: r[1] }); if (r[2]) lrows.push({ id: r[0] + "·m", story: r[0], kind: "measured", usd: r[2] }); });
  const ledger = table({
    columns: [{ key: "story", mono: true }, { key: "kind", fmt: v => stateTag(v === "measured" ? "ok" : "todo", lab(v)) }, { key: "usd", label: "USD", align: "right", mono: true, fmt: v => num(v, "float1") }],
    rows: lrows, qsKey: "ledger"
  });
  const costBox = box(260);
  main.appendChild(h("div", { class: "ops-wrap" }, [panel("Cost", costBox), panel("Ledger", ledger)]));
  ec(costBox, { grid: { left: 54, right: 10, top: 24, bottom: 22, containLabel: true }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" } }, legend: { top: 0, right: 0, textStyle: { color: col.t2(), fontSize: 11 } },
    xAxis: axis({ type: "category", data: L.map(r => r[0]), axisLabel: { color: col.t2(), fontSize: 10, interval: 0, rotate: 30 } }), yAxis: axis({ type: "value", name: "USD" }),
    series: [{ name: lab("estimated"), type: "bar", barMaxWidth: 12, data: L.map(r => r[1]), itemStyle: { color: col.t3() } }, { name: lab("measured"), type: "bar", barMaxWidth: 12, data: L.map(r => r[2]), itemStyle: { color: col.ok() } }] });
  setPanel({ method: [], log: null, sources: [{ label: "ledger", path: "docs/g0/ledger" }] });
  ctx({ route: "cost" });
}

/* ============================================================ QA */
async function qaPage(main) {
  css(); chartsDispose(); main.replaceChildren();
  const S = await story();
  const [jobs, bench, traces] = await Promise.all([tryApi("/api/jobs?limit=200"), tryApi("/api/chat/bench"), UI.locked ? Promise.resolve(null) : tryApi("/api/chat/traces?limit=20")]);
  const runBy = job => S.runs.find(r => r.job === job);
  /* LLM findings: latest agentqa.run per subject */
  const aq = (jobs || []).filter(j => j.kind === "agentqa.run" && j.state === "ok" && j.outputs && j.outputs.out).sort((a, b) => (b.created > a.created ? 1 : -1));
  const results = (await Promise.all(aq.slice(0, 8).map(j => tryApi("/api/agent_result?out=" + encodeURIComponent(j.outputs.out)).then(r => r && { job: j, r })))).filter(Boolean);
  const seen = new Set(), reports = [], reviewed = {};
  results.forEach(({ r }) => (r.reviews || []).forEach(rv => { try { const d = JSON.parse(rv.text); (d.decisions || []).forEach(x => { reviewed[d.report_id + "/" + x.finding_id] = x; }); } catch (e) { /* truncated */ } }));
  results.forEach(({ job, r }) => r.reports.forEach(rep => { if (seen.has(rep.subject_ref)) return; seen.add(rep.subject_ref); reports.push({ job, rep, path: r.reports_path }); }));
  const rows = [], dec = {};
  reports.forEach(({ job, rep, path }) => {
    const facts = {}; (rep.facts || []).forEach(f => facts[f.fact_id] = f);
    const tgt = String(rep.subject_ref).match(/\/([^/]+)\/metrics\.jsonl$/); const run = tgt && runBy(tgt[1]);
    const lastStep = (rep.facts || []).find(f => f.name === "train_last_step");
    (rep.findings || []).forEach(f => {
      const key = rep.report_id + "/" + f.finding_id, prev = reviewed[key];
      rows.push({ id: key, source: "llm", code: f.code, rank: f.rank, subject: run ? run.branch : (f.target_ref || rep.stage), insight: f.insight, report: rep, report_path: path, fid: f.finding_id,
        link: run ? "runs?sel=" + run.branch + (lastStep ? "&step=" + lastStep.value : "") : "jobs?job=" + job.id, decided: prev ? (prev.decision === "agree" ? "agree" : "override") : null, reason: prev && prev.reason });
      if (prev) dec[key] = { finding_id: f.finding_id, decide: prev.decision, reason: prev.reason || null, locked: true };
    });
  });
  /* rule layer: QA reasons from the egocentric pipeline */
  (S.reasons || []).forEach(([code, n]) => rows.push({ id: "rule/" + code, source: "rule", code: code.replace(/ \(.*\)$/, ""), rank: null, subject: n + " ep", n, insight: "", link: "data?qa=flag&reason=" + encodeURIComponent(code.replace(/ \(.*\)$/, "")), decided: null, rule: true }));
  const nLlm = rows.filter(r => r.source === "llm").length;
  const B = bench && bench.n != null ? bench : null, pc = v => v == null ? "—" : (v * 100).toFixed(1) + "%";
  main.appendChild(pageHead("QA", [{ label: "findings", value: String(rows.length) }, { label: "llm", value: String(nLlm) }, { label: "rule", value: String(rows.length - nLlm) }]));

  /* inbox */
  const codeBox = box(150), decBox = box(150), benchBox = box(150); let cCode, cDec, cBench;
  const state = { cur: null };
  const reasonIn = h("input", { class: "ops-in", placeholder: "reason", style: { width: "200px" } });
  const msg = h("span", { class: "ops-mono", style: { color: col.t2() } });
  const tbox = h("div"), nlab = h("div", { class: "ops-mono", style: { fontSize: "11px", color: col.t2(), padding: "4px 0" } });
  let tbl = null;
  function drawInbox() {
    const dn = rows.filter(r => r.source === "llm" && dec[r.id]).length;
    if (tbl && tbl.table) { tbl.table.setRows(rows); nlab.textContent = dn + " of " + nLlm + " decided"; drawCharts(); return; }
    tbl = table({
      columns: [
        { key: "source", fmt: v => h("span", { class: "ops-tag", style: { color: v === "llm" ? col.llm() : col.code() } }, v === "llm" ? "LLM" : "CODE") },
        { key: "code", mono: true }, { key: "rank", align: "right", mono: true, fmt: v => v == null ? "—" : String(v) },
        { key: "subject", mono: true },
        { key: "insight", label: "finding", fmt: v => v ? v.slice(0, 80) + (v.length > 80 ? "…" : "") : "—" },
        { key: "decided", label: "decision", fmt: (v, r) => r.rule ? "—" : (dec[r.id] ? stateTag(dec[r.id].decide, dec[r.id].decide === "agree" ? "accept" : "reject") : stateTag("todo", "open")) },
        { key: "link", label: "evidence", fmt: v => h("a", { href: "#/" + v, class: "ops-mono", style: { color: col.acc() }, onclick: e => e.stopPropagation() }, "open") }
      ], rows, qsKey: "finding", onRow: r => { state.cur = r; ctx({ route: "qa", selection: { finding: r.fid || r.code, source: r.source } }); }
    });
    tbox.replaceChildren(tbl, nlab); nlab.textContent = dn + " of " + nLlm + " decided"; drawCharts();
  }
  function decide(kind) {
    const cr = tbl && tbl.table && tbl.table.cursor, r = cr || state.cur; if (!r || r.rule) return;
    if (dec[r.id] && dec[r.id].locked) { msg.textContent = "locked"; return; }
    if (kind === "override") { const why = reasonIn.value.trim(); if (!why) { reasonIn.focus(); msg.textContent = "reason?"; return; } dec[r.id] = { finding_id: r.fid, decide: "override", reason: why }; reasonIn.value = ""; }
    else dec[r.id] = { finding_id: r.fid, decide: "agree", reason: null };
    msg.textContent = ""; drawInbox();
  }
  const submit = h("button", { class: "ops-btn pri wbtn", text: lab("Submit"), onclick: async () => {
    const byRep = {};
    rows.filter(r => r.source === "llm").forEach(r => { (byRep[r.report.report_id] = byRep[r.report.report_id] || { r, ds: [], total: 0 }).total++; if (dec[r.id] && !dec[r.id].locked) byRep[r.report.report_id].ds.push(dec[r.id]); });
    const todo = Object.values(byRep).filter(b => b.ds.length);
    if (!todo.length) { msg.textContent = "none"; return; }
    const out = [];
    for (const b of todo) {
      const all = rows.filter(r => r.report && r.report.report_id === b.r.report.report_id);
      if (all.some(r => !dec[r.id])) { msg.textContent = "open"; return; }
      try { const j = await startJob("agentqa.review", { reports: b.r.report_path, report_id: b.r.report.report_id, decisions: all.map(r => ({ finding_id: r.fid, decide: dec[r.id].decide, reason: dec[r.id].reason })) }); out.push(j.id); all.forEach(r => { dec[r.id].locked = true; }); }
      catch (e) { msg.textContent = e.message; return; }
    }
    msg.textContent = "job " + out.join(","); drawInbox();
  } });
  const bar = h("div", { class: "ops-row" }, [h("button", { class: "ops-btn", text: lab("Accept"), onclick: () => decide("agree") }), h("button", { class: "ops-btn", text: lab("Reject"), onclick: () => decide("override") }), reasonIn, submit, msg]);

  /* bench + traces */
  const traceBox = h("div"), treeBox = h("div");
  function drawTraces() {
    const list = Array.isArray(traces) ? traces : (traces && traces.traces) || [];
    if (UI.locked) { traceBox.replaceChildren(h("span", { class: "dim", text: t("lock.off") })); return; }
    if (!list.length) { traceBox.replaceChildren(h("span", { class: "ops-mono", style: { color: col.t2() }, text: "—" })); return; }
    traceBox.replaceChildren(table({
      columns: [{ key: "ts", label: "time", mono: true, fmt: v => v ? hhmm(String(v)) : "—" }, { key: "question", fmt: v => v ? String(v).slice(0, 48) : "—" },
        { key: "tools", align: "right", mono: true, fmt: v => Array.isArray(v) ? (v.join(",") || "—") : dash(v) },
        { key: "ms_total", label: "ms", align: "right", mono: true, fmt: v => v == null ? "—" : num(v, "int") }, { key: "tokens_out", label: "tok out", align: "right", mono: true, fmt: v => v == null ? "—" : num(v, "int") },
        { key: "error", label: "err", mono: true, fmt: v => v ? stateTag("fail", String(v).slice(0, 20)) : "—" }],
      rows: list.map(t => Object.assign({ id: t.turn_id }, t)), qsKey: "trace", onRow: r => { showTrace(r.turn_id); setQs({ trace: r.turn_id }); }
    }));
  }
  async function showTrace(id) {
    const t = await tryApi("/api/chat/traces/" + encodeURIComponent(id)); treeBox.replaceChildren();
    if (!t) { treeBox.appendChild(h("span", { class: "ops-mono", text: "—" })); return; }
    const nodes = t.nodes || [];
    treeBox.appendChild(panel("Trace " + String(id).slice(-8), h("table", { class: "ops-tbl" }, [h("thead", null, h("tr", null, ["node", "name", "ms", "tok in", "tok out"].map(x => h("th", { text: x })))),
      h("tbody", null, nodes.map(n => h("tr", null, [h("td", { class: "ops-mono", style: { paddingLeft: (8 + (n.type === "tool" ? 16 : 0)) + "px", color: n.type === "tool" ? col.code() : col.llm() }, text: n.type === "tool" ? "tool" : "gen"  }),
        h("td", { class: "ops-mono", text: n.type === "tool" ? n.name + (n.ok === false ? " ✕" : "") : "round " + dash(n.round) }),
        h("td", { class: NUMCLS, text: n.ms == null ? "—" : num(n.ms, "int") }), h("td", { class: NUMCLS, text: n.tokens_in == null ? "—" : num(n.tokens_in, "int") }), h("td", { class: NUMCLS, text: n.tokens_out == null ? "—" : num(n.tokens_out, "int") })])))])));
  }
  drawInbox(); drawTraces();
  function drawCharts() {
    const codes = [...new Set(rows.map(r => r.code))], cnt = src => codes.map(c => rows.filter(r => r.code === c && r.source === src).reduce((a, r) => a + (r.n || 1), 0));
    if (!cCode) { cCode = ec(codeBox, {}); cDec = ec(decBox, {}); cBench = ec(benchBox, {}); }
    cCode.setOption({ grid: { left: 110, right: 10, top: 4, bottom: 18 }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" } }, xAxis: axis({ type: "log", min: .5 }), yAxis: axis({ type: "category", data: codes, inverse: true, splitLine: { show: false } }),
      series: [{ name: "CODE", type: "bar", stack: "s", barMaxWidth: 12, data: cnt("rule"), itemStyle: { color: col.code() } }, { name: "LLM", type: "bar", stack: "s", barMaxWidth: 12, data: cnt("llm"), itemStyle: { color: col.llm() } }] }, true);
    const d = Object.values(dec), acc = d.filter(x => x.decide === "agree").length, rej = d.filter(x => x.decide === "override").length;
    cDec.setOption({ tooltip: {}, series: [{ type: "pie", radius: ["55%", "78%"], label: { color: col.text(), fontSize: 11, formatter: "{b} {c}" }, data: [{ name: "accept", value: acc, itemStyle: { color: col.ok() } }, { name: "reject", value: rej, itemStyle: { color: col.bad() } }, { name: "open", value: Math.max(0, nLlm - acc - rej), itemStyle: { color: col.t3() } }].filter(x => x.value) }] }, true);
    const QB = EXPLAIN.read.bench(), bars = [QB ? ["defects", QB.caught / QB.planted * 100, QB.caught + "/" + QB.planted] : null, QB && QB.clean != null ? ["false pos", QB.clean ? 100 - QB.false_alarms / QB.clean * 100 : 0, QB.false_alarms + "/" + QB.clean] : null, ["tool acc", B ? B.tool_acc * 100 : 0, B ? pc(B.tool_acc) : "—"], ["guardrail", B && B.guardrail ? B.guardrail.pass / B.guardrail.n * 100 : 0, B && B.guardrail ? B.guardrail.pass + "/" + B.guardrail.n : "—"], ["grounded", B ? B.grounded_rate * 100 : 0, B ? pc(B.grounded_rate) : "—"]].filter(Boolean);
    cBench.setOption({ grid: { left: 70, right: 56, top: 4, bottom: 4 }, xAxis: { type: "value", min: 0, max: 100, show: false }, yAxis: axis({ type: "category", data: bars.map(b => b[0]), inverse: true, splitLine: { show: false } }),
      series: [{ type: "bar", barMaxWidth: 10, showBackground: true, backgroundStyle: { color: col.line() }, data: bars.map(b => ({ value: b[1], itemStyle: { color: col.ok(), borderRadius: 2 } })), label: { show: true, position: "right", color: col.text(), fontSize: 11, formatter: p => bars[p.dataIndex][2] } }] }, true);
  }
  const root = h("div", { class: "ops-wrap" }, [
    h("div", { class: "ops-grid", style: { gridTemplateColumns: "repeat(3,minmax(0,1fr))" } }, [panel("By code", codeBox), panel("Decisions", decBox), panel("Bench", benchBox)]),
    panel("Inbox", h("div", { class: "ops-wrap", style: { gap: "6px" } }, [bar, tbox])),
    panel("Traces", h("div", { class: "ops-wrap", style: { gap: "6px" } }, [traceBox, treeBox]))
  ]);
  main.appendChild(root);
  setPanel({ method: [{ step: "run", cmd: CMD.qaRun }, { step: "review", cmd: CMD.qaReview }, { step: "bench", cmd: CMD.qaBench }], log: aq[0] ? { jobId: aq[0].id } : null,
    sources: [{ label: "agent.yaml", path: "configs/eval/agentqa/agent.yaml" }, { label: "reports", path: aq[0] ? aq[0].outputs.out + "/reports.jsonl" : "fwdata/console/agentqa" }] });
  bindKeys({ a: () => decide("agree"), r: () => decide("override") }, root);
}

/* ------------------------------------------------------------ routes */
if (typeof UI !== "undefined" && UI.route) {
  UI.route("runs", runsPage);
  UI.route("eval", evalPage);
  UI.route("loop", loopPage);
  UI.route("cost", (main, params, qs) => loopPage(main, params, qs, "cost"));
  UI.route("qa", qaPage);
}
Object.assign(P, { runsPage, evalPage, loopPage, costPage, qaPage, chartsDispose });
})();

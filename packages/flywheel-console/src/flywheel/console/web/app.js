/* shell: sidebar, top bar, right panel, router, command palette, shortcut sheet, Home page.
   Pages register with UI.route(pattern, fn). Unregistered routes fall back to the v4 page functions (LEGACY block at the bottom). */
"use strict";
const SIDE = [
  { g: null, items: [{ id: "home", t: "Tổng quan", ic: "▣", href: "#/home" }] },
  { g: "DỮ LIỆU", items: [{ id: "data", t: "Datasets", ic: "▤", href: "#/data", ct: () => ({ n: CAT ? CAT.rows.filter(r => r.status === "current").length : null }) },
    { id: "pipeline", t: "Pipeline", ic: "▷", href: "#/jobs?view=pipeline", ct: () => ({ n: ST.jobs.filter(j => j.state === "running" && /^ego\./.test(j.kind)).length, run: 1 }) }] },
  { g: "AGENT", items: [{ id: "qa", t: "QA/QC", ic: "✓", href: "#/qa", ct: () => ({ n: ST.agent ? ST.agent.findings : null, warn: 1 }) }] },
  { g: "MODEL", items: [{ id: "runs", t: "Training", ic: "↗", href: "#/runs", ct: () => ({ n: trainRuns().filter(r => r.running).length, run: 1 }) },
    { id: "eval", t: "Eval", ic: "◎", href: "#/eval", ct: () => { const e = evalSucc(); return { s: e == null ? null : UI.fmt(e, "pct") }; } }] },
  { g: "VÒNG LẶP", items: [{ id: "loop", t: "Failure→Data", ic: "↺", href: "#/loop" }, { id: "cost", t: "Chi phí", ic: "$", href: "#/loop?tab=cost", ct: () => ({ s: ST.machines && ST.machines.colab && ST.machines.colab.balance != null ? UI.fmt(ST.machines.colab.balance, "int") : null }) }] },
  { g: "HẠ TẦNG", items: [{ id: "jobs", t: "Jobs", ic: "☰", href: "#/jobs", ct: () => ({ n: ST.jobs.filter(j => j.state === "running" || j.state === "queued").length, run: 1 }) }, { id: "machines", t: "Máy", ic: "▦", href: "#/jobs?view=machines" }] },
];
const STRIP = [["collect", "col", "#/data"], ["process", "proc", "#/jobs"], ["release", "rel", "#/jobs?panel=export"], ["train", "train", "#/runs"], ["eval", "eval", "#/eval"], ["loop", "loop", "#/loop"]];
const REDIRECT = { overview: "home", process: "jobs", training: "runs", agent: "qa", "data/nhap": "jobs?panel=import", "data/xuat": "jobs?panel=export" };
let CAT = null, STORY = null;
const CATP = () => CAT ? Promise.resolve(CAT) : J("data/catalog.json").then(c => (CAT = c));
const STORYP = () => STORY ? Promise.resolve(STORY) : J("data/story.json").then(s => (STORY = s));
const rowById = id => CAT.rows.find(r => r.id === id);
const nodeById = id => rowById(id) || (CAT.runs || []).find(r => r.id === id);
const jget = (u) => fetch(u).then(r => { if (!r.ok) throw new Error(u + " " + r.status); return r.json(); });

/* ---------------- router ---------------- */
function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "") || "home";
  const [p, q] = raw.split("?");
  const qs = {}; (q || "").split("&").filter(Boolean).forEach(kv => { const [k, v] = kv.split("="); qs[decodeURIComponent(k)] = decodeURIComponent(v || ""); });
  return { parts: p.split("/").filter(Boolean).map(decodeURIComponent), qs };
}
function go(path) { location.hash = "#/" + path; }
let RT = 0;
function sideActive() {
  const { parts, qs } = parseHash(), p = parts[0] || "home";
  if (p === "jobs") return qs.view === "pipeline" ? "pipeline" : qs.view === "machines" ? "machines" : "jobs";
  if (p === "loop") return qs.tab === "cost" ? "cost" : "loop";
  return p;
}
function drawSide() {
  const el = $("#side"); el.innerHTML = ""; const act = sideActive();
  SIDE.forEach(g => {
    if (g.g) el.appendChild(h("div", { class: "gh", text: g.g }));
    g.items.forEach(it => { const c = it.ct ? it.ct() : {}, txt = c.n != null ? String(c.n) : c.s != null ? c.s : "";
      el.appendChild(h("a", { href: it.href, class: it.id === act ? "on" : "", title: it.t }, [h("span", { class: "ic", text: it.ic }), h("span", { class: "nm", text: it.t }), txt ? h("span", { class: "ct" + (c.run && c.n ? " run" : c.warn && c.n ? " warn" : ""), text: txt }) : null])); });
  });
}
function chatRoute() { const { parts } = parseHash(); return parts.join("/") || "home"; }
async function route() {
  const tok = ++RT;
  UI.keys.clear("page"); disposeCharts(); if (window.opsStop) opsStop(); if (window.__raf) cancelAnimationFrame(window.__raf);
  UI.panel.reset();
  let raw = location.hash.replace(/^#\/?/, "") || "home";
  const qi = raw.indexOf("?"), path = qi < 0 ? raw : raw.slice(0, qi), q = qi < 0 ? "" : raw.slice(qi);
  const tgt = REDIRECT[path];
  if (tgt) { const [tp, tq] = tgt.split("?"), mq = [tq, q.slice(1)].filter(Boolean).join("&"); history.replaceState(null, "", "#/" + tp + (mq ? "?" + mq : "")); return route(); }
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  const main = $("#main"); main.innerHTML = "";
  drawSide();
  const view = h("div", { class: "view" }, [h("div", { class: "skel" }), h("div", { class: "skel" }), h("div", { class: "skel" })]);
  main.appendChild(view); main.scrollTop = 0;
  if (window.CHAT) CHAT.touchContext();
  try {
    await Promise.all([CATP(), STORYP()]);
    if (tok !== RT) return;
    const body = h("div"); const m = UI.matchRoute(path || "home"); const qs = UI.qs();
    if (m) await m.fn(body, m.params, qs); else await legacyRoute(body, parts, qs);
    if (tok !== RT) return;
    view.innerHTML = ""; view.appendChild(body);
  } catch (e) {
    console.error(e); if (tok !== RT) return; view.innerHTML = "";
    view.appendChild(h("div", { class: "errline" }, ["✕ " + String(e.message || e) + " ", h("a", { href: "#/home", text: "[home]" })]));
  }
  if (window.CHAT) CHAT.touchContext();
}
window.addEventListener("hashchange", () => { route(); });

/* ---------------- header + live state ---------------- */
const ST = { stages: null, jobs: [], models: null, machines: null, agent: null };
const trainRuns = () => { const t = (ST.stages || []).find(s => s.id === "train"); return t && t.runs ? t.runs : []; };
const evalSucc = () => { const e = ((ST.stages || []).find(s => s.id === "eval") || {}).now, m = /(\d+)\/(\d+)/.exec(e || ""); return m ? +m[1] / +m[2] : null; };
const waitingN = () => (ST.stages || []).filter(s => s.state === "waiting").length + (ST.agent ? ST.agent.findings || 0 : 0);
function drawMeta() {
  const el = $("#meta"); el.innerHTML = "";
  const run = ST.jobs.filter(j => j.state === "running" || j.state === "queued").length;
  const m = ST.machines || {}, rtx = m.rtx3060, nm = ST.models ? ST.models.nemotron || (ST.models.agent_ready ? "warm" : "down") : "down";
  const dot = (s) => h("span", { class: "c-" + UI.stateClass(s), text: s === "down" ? "✕" : s === "cold" ? "○" : "●" });
  const pill = (kids, fn, title) => h(fn ? "button" : "span", { class: "pill", title, onclick: fn }, kids);
  [pill(["jobs ", h("span", { class: run ? "c-run" : "", text: String(run) })], () => go("jobs"), "running + queued"), pill(["3060 ", dot(rtx && rtx.tunnel === "up" ? "up" : "down")], null, "rtx3060 tunnel"),
    pill(["nemotron ", dot(nm)], () => { if (window.CHAT) { CHAT.open(); CHAT.prewarm(); } }, nm), pill(["chờ duyệt ", h("span", { class: waitingN() ? "c-warn" : "", text: String(waitingN()) })], () => go("qa")),
    h("button", { title: "demo", onclick: () => toggleDemo(), text: "demo" }), h("button", { title: "theme", onclick: () => { setTheme(curTheme() === "dark" ? "light" : "dark"); route(); }, text: "◐" }),
    h("button", { title: "shortcuts", onclick: () => openKeys(), text: "?" })].forEach(x => el.appendChild(x));
}
async function poll() {
  try {
    const [st, jb, md, ag] = await Promise.all([jget("/api/status"), jget("/api/jobs?limit=100").catch(() => []), jget("/api/models").catch(() => null), jget("/api/agent_stats").catch(() => null)]);
    ST.stages = st.stages; ST.machines = st.machines; ST.jobs = jb; ST.models = md; ST.agent = ag; ST.status = st; ST.at = Date.now();
    if (window.CHAT) CHAT.setModelState(md);
  } catch (e) { ST.stages = ST.stages || null; }
  drawSide(); drawMeta();
}

/* ---------------- shortcut sheet and palette ---------------- */
const KEYS = [["g h/d/j/r/e/l/q", "go to page"], ["j / k", "row down / up"], ["Enter", "open row"], ["x", "select row"], ["c", "compare"], ["a", "ask chat about row"], ["[ ]", "prev / next"],
  ["⌘K", "palette"], ["/", "focus chat"], ["⌘.", "toggle panel"], ["Esc", "back out"], ["?", "this sheet"]];
function openKeys() { const b = $("#keys-box"); b.innerHTML = ""; b.appendChild(h("div", { class: "gr" }, KEYS.map(([k, d]) => h("div", { class: "kr" }, [h("span", { text: d }), h("kbd", { text: k })])))); $("#keys").classList.add("open"); }
function closeKeys() { $("#keys").classList.remove("open"); }
const PAL = { items: [], sel: 0, built: false };
async function buildPalette() {
  const it = []; const add = (k, t, d, fn) => it.push({ k, t, d, fn });
  SIDE.forEach(g => g.items.forEach(x => add("go", x.t, x.href, () => { location.hash = x.href; })));
  await CATP().catch(() => {}); await STORYP().catch(() => {});
  if (CAT) CAT.rows.filter(r => !UI.demo || r.data_class === "public").forEach(r => add("data", r.id, r.title || r.name, () => go("data/" + r.id)));
  const runs = new Set(); (STORY ? STORY.runs : []).forEach(r => runs.add(r.branch)); runs.forEach(b => add("run", b, "#/runs?sel=" + b, () => go("runs?sel=" + b)));
  try { (await jget("/api/jobs?limit=20")).forEach(j => add("job", j.id, j.kind + " " + j.state, () => go("jobs?job=" + j.id))); } catch (e) {}
  try { (await jget("/api/tools?route=" + encodeURIComponent(chatRoute()))).forEach(t => add("tool", "/" + String(t.slash || t.name).replace(/^\//, ""), t.description ? t.description.slice(0, 60) : "", () => { if (window.CHAT) CHAT.open("/" + String(t.slash || t.name).replace(/^\//, "") + " "); })); } catch (e) {}
  PAL.items = it;
}
function palRender() {
  const q = $("#pal-in").value.trim().toLowerCase(), res = $("#pal-res"); res.innerHTML = "";
  const hit = PAL.items.filter(x => !q || (x.t + " " + x.d).toLowerCase().includes(q)).slice(0, 40); PAL.view = hit; PAL.sel = Math.min(PAL.sel, Math.max(0, hit.length - 1));
  hit.forEach((x, i) => res.appendChild(h("div", { class: "it" + (i === PAL.sel ? " on" : ""), onclick: () => palRun(i) }, [h("span", { class: "k", text: x.k }), h("span", { class: "t mono", text: x.t }), h("span", { class: "d", text: x.d || "" })])));
  const on = $(".it.on", res); if (on) on.scrollIntoView({ block: "nearest" });
}
function palRun(i) { const x = PAL.view[i]; if (!x) return; closePal(); x.fn(); }
async function openPal() { $("#pal").classList.add("open"); const i = $("#pal-in"); i.value = ""; i.focus(); PAL.sel = 0; palRender(); await buildPalette(); palRender(); }
function closePal() { $("#pal").classList.remove("open"); }
function initPal() {
  const i = $("#pal-in");
  i.addEventListener("input", () => { PAL.sel = 0; palRender(); });
  i.addEventListener("keydown", e => { if (e.key === "ArrowDown") { PAL.sel = Math.min(PAL.sel + 1, PAL.view.length - 1); palRender(); e.preventDefault(); } else if (e.key === "ArrowUp") { PAL.sel = Math.max(0, PAL.sel - 1); palRender(); e.preventDefault(); } else if (e.key === "Enter") { palRun(PAL.sel); } });
  $("#pal").addEventListener("mousedown", e => { if (e.target.id === "pal") closePal(); });
  $("#keys").addEventListener("mousedown", e => { if (e.target.id === "keys") closeKeys(); });
  $("#srch").addEventListener("click", openPal);
}

/* ---------------- demo ---------------- */
function toggleDemo() { try { sessionStorage.setItem("v5demo", UI.demo ? "" : "1"); } catch (e) {} const u = new URL(location.href); u.searchParams.delete("demo"); if (!UI.demo) u.searchParams.set("demo", "1"); location.href = u.toString(); }

/* ---------------- Home ---------------- */
const dsec = (t, n, right) => h("div", { class: "u-sec", style: { justifyContent: "space-between" } }, [h("span", null, [t, n != null ? h("span", { class: "n", text: " " + n }) : null]), right || null]);
const grow = (g, name, tx, act) => h("div", { class: "row" }, [g, h("span", { class: "nm", text: name }), h("span", { class: "tx", text: tx || "" }), act || null]);
const jdur = j => j.started ? Math.max(0, ((j.ended ? new Date(j.ended) : new Date()) - new Date(j.started)) / 1000) : null;
const k0 = n => n == null ? "—" : n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n);
const down = (a, n) => { if (a.length <= n) return a; const o = []; for (let i = 0; i < n; i++) o.push(a[Math.floor(i * (a.length - 1) / (n - 1))]); return o; };
function timelineStrip(jobs) {
  const now = Date.now(), T0 = now - 24 * 3600e3, W = 900, L = 96, rh = 13;
  const ok = jobs.filter(j => j.created && (j.ended ? new Date(j.ended) : now) >= T0);
  const kinds = {}; ok.forEach(j => kinds[j.kind] = (kinds[j.kind] || 0) + 1);
  const ks = Object.keys(kinds).sort((a, b) => kinds[b] - kinds[a]).slice(0, 8), ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg"); svg.setAttribute("viewBox", `0 0 ${W} ${Math.max(1, ks.length) * rh + 16}`); svg.setAttribute("class", "u-tl");
  const e = (t, a, txt) => { const x = document.createElementNS(ns, t); for (const k in a) x.setAttribute(k, a[k]); if (txt != null) x.textContent = txt; svg.appendChild(x); return x; };
  const X = t => L + (Math.max(T0, t) - T0) / (now - T0) * (W - L - 4);
  for (let hh = 0; hh <= 24; hh += 6) { const x = L + hh / 24 * (W - L - 4); e("line", { x1: x, x2: x, y1: 0, y2: ks.length * rh, class: "gl" }); e("text", { x: x, y: ks.length * rh + 11, "text-anchor": hh === 0 ? "start" : hh === 24 ? "end" : "middle" }, hh === 24 ? "now" : "-" + (24 - hh) + "h"); }
  ks.forEach((k, i) => { e("text", { x: 0, y: i * rh + 10 }, k);
    ok.filter(j => j.kind === k).forEach(j => { const a = new Date(j.started || j.created).getTime(), b = j.ended ? new Date(j.ended).getTime() : now; const x0 = X(a), w = Math.max(2, X(b) - x0); const r = e("rect", { x: x0, y: i * rh + 2, width: w, height: rh - 4, rx: 1, class: "bk " + j.state }); const t = document.createElementNS(ns, "title"); t.textContent = j.id + " " + j.state; r.appendChild(t); r.style.cursor = "pointer"; r.addEventListener("click", () => go("jobs?job=" + j.id)); }); });
  return svg;
}
async function pageHome(main) {
  const [st, jobs, works, ag] = await Promise.all([jget("/api/status").catch(() => null), jget("/api/jobs?limit=100").catch(() => []), jget("/api/works").catch(() => []), jget("/api/agent_stats").catch(() => null)]);
  if (st) { ST.stages = st.stages; ST.machines = st.machines; } ST.agent = ag || ST.agent;
  const stages = st ? st.stages : [], stage = id => stages.find(s => s.id === id) || {}, sv = id => stage(id).state || "idle";
  const S = STORY, h1 = S.h1m || {}, cur = CAT.rows.filter(r => r.status === "current"), byG = g => cur.filter(r => r.group === g);
  main.appendChild(UI.page({ title: "Tổng quan", stat: [{ label: "jobs running", value: jobs.filter(j => j.state === "running").length, unit: "run" }, { label: "datasets", value: CAT.rows.length, unit: "sets" }] }));
  UI.panel.set({ method: [{ step: "Status", cmd: "curl -s 127.0.0.1:4178/api/status" }, { step: "Jobs", cmd: "curl -s 127.0.0.1:4178/api/jobs?limit=100" }], sources: [{ label: "status", path: "/api/status" }, { label: "story", path: "v5/data/story.json" }, { label: "catalog", path: "v5/data/catalog.json" }] });

  /* tiles */
  const live = trainRuns(), sr = S.runs || [], es = evalSucc();
  const L = S.ledger || [], est = L.reduce((a, r) => a + (r[1] || 0), 0), meas = L.reduce((a, r) => a + (r[2] || 0), 0), cu = (ST.machines || {}).colab, bal = S.colab_balance || [];
  let cum = 0; const cumS = L.filter(r => r[2]).map(r => (cum += r[2]));
  const avgStep = live.length ? live.reduce((a, r) => a + r.step, 0) / live.length : (sr.length ? sr.reduce((a, r) => a + r.step, 0) / sr.length : null);
  main.appendChild(UI.Tiles([
    { label: "Ego clips QA'd", value: h1.clips, state: (h1.qa && h1.qa.flag) ? "warn" : "ok", spark: (S.sources || []).map(x => x.episodes), href: "#/qa" },
    { label: "Synthetic S1", value: byG("s1").reduce((a, r) => a + (r.episodes || 0), 0), unit: "ep", state: "ok", href: "#/data" },
    { label: "Eval succ", value: es == null ? null : UI.fmt(es, "pct"), state: "warn", href: "#/eval" },
    { label: "Training", value: avgStep == null ? null : k0(Math.round(avgStep)), unit: "/60k", state: live.some(r => r.running) ? "run" : "idle", spark: sr[0] && sr[0].loss ? down(sr[0].loss.map(p => p[1]), 40) : null, href: "#/runs" },
    { label: "CU left", value: cu && cu.balance != null ? Math.round(cu.balance) : null, state: "ok", spark: down(bal.map(p => p[1]), 40), href: "#/loop?tab=cost" },
    { label: "Measured cost", value: "$" + UI.fmt(meas, "float1"), state: "idle", spark: cumS, unit: "est $" + UI.fmt(est, "int"), href: "#/loop?tab=cost" }]));

  /* flywheel + attention */
  const agDone = jobs.some(j => /^agentqa/.test(j.kind) && j.state === "ok"), fnd = ag ? ag.findings || 0 : 0, lp = /(L-[A-Z-]+)\s+(\d+)\/(\d+)/.exec(stage("loop").now || "");
  const fw = UI.Flywheel([
    { id: "src", label: "Nguồn", state: sv("collect"), metric: cur.length + " sets", href: "#/data" },
    { id: "pipe", label: "Pipeline", state: sv("process"), metric: (h1.clips || "—") + " clips", href: "#/jobs?view=pipeline" },
    { id: "qa", label: "Agent QA/QC", state: fnd ? "waiting" : agDone ? "done" : "idle", metric: fnd + " findings", href: "#/qa" },
    { id: "rel", label: "Release", state: sv("release"), metric: (h1.exported || "—") + " exported", href: "#/data" },
    { id: "train", label: "Training", state: sv("train"), metric: avgStep == null ? "—" : Math.round(avgStep / 600) + "%", href: "#/runs" },
    { id: "probe", label: "Probe", state: "idle", metric: "—", href: "#/eval" },
    { id: "eval", label: "Eval", state: sv("eval"), metric: es == null ? "—" : UI.fmt(es, "pct"), href: "#/eval" },
    { id: "loop", label: "Failure→Data", state: sv("loop"), metric: lp ? lp[1] + " " + lp[2] : "—", href: "#/loop" },
    { id: "cost", label: "Chi phí", state: "done", metric: cu && cu.balance != null ? "CU " + Math.round(cu.balance) : "—", href: "#/loop?tab=cost" }], { height: 320 });

  const att = [], pend = [];
  let ack = []; try { ack = JSON.parse(localStorage.getItem("v5ack") || "[]"); } catch (e) {}
  const tgt = j => { const p = j.params || {}; return j.kind + "|" + (p.work || p.input || p.name || JSON.stringify(p)); };
  const hushed = j => ack.includes(j.id) || jobs.some(o => o.state === "ok" && tgt(o) === tgt(j) && o.created > j.created);
  let hov = null;
  const doAck = (id, row) => { ack.push(id); try { localStorage.setItem("v5ack", JSON.stringify(ack)); } catch (e) {} row.remove(); };
  jobs.filter(j => (j.state === "failed" || j.state === "cancelled") && !hushed(j)).slice(0, 4).forEach(j => {
    const row = grow(h("span", { class: "c-bad", text: "✕" }), j.kind, "rc " + j.rc + " · " + j.id, h("span", null, [h("a", { class: "go", href: "#/jobs?job=" + j.id, text: "[log]" }), h("button", { class: "u-btn sm", title: "ack (e)", text: "×", onclick: () => doAck(j.id, row) })]));
    row.addEventListener("mouseenter", () => hov = { id: j.id, row }); row.addEventListener("mouseleave", () => hov = null); att.push(row);
  });
  UI.keys.bind({ e: () => { if (!hov) return false; doAck(hov.id, hov.row); hov = null; } }, "page");
  stages.filter(s => s.state === "blocked").forEach(s => att.push(grow(h("span", { class: "c-bad", text: "✕" }), s.id, "blocked")));
  works.filter(w => w.summary && w.summary.qa && w.summary.qa.flag > 0).slice(0, 3).forEach(w => att.push(grow(h("span", { class: "c-warn", text: "!" }), "QA " + w.summary.qa.flag + " flag", w.name, h("a", { class: "go", href: "#/jobs?work=" + encodeURIComponent(w.name), text: "[open]" }))));
  if (fnd) pend.push(grow(h("span", { class: "c-warn", text: "◷" }), "agentqa", fnd + " findings", h("a", { class: "go", href: "#/qa", text: "[review]" })));
  stages.filter(s => s.state === "waiting").forEach(s => pend.push(grow(h("span", { class: "c-warn", text: "◷" }), s.id, "waiting", h("a", { class: "go", href: (STRIP.find(x => x[0] === s.id) || [0, 0, "#/home"])[2], text: "[open]" }))));
  const side = h("div", { class: "blk" }, [dsec("Chờ duyệt", pend.length), pend.length ? h("div", null, pend) : grow(h("span", { class: "c-ok", text: "✓" }), "none", ""), h("div", { style: { height: "12px" } }), dsec("Attention", att.length), att.length ? h("div", null, att) : grow(h("span", { class: "c-ok", text: "✓" }), "none", "")]);
  main.appendChild(h("div", { class: "hm2" }, [h("div", { class: "blk" }, [dsec("Flywheel"), fw]), side]));

  /* 3 mini charts */
  const C = UI.colors(), groups = ["egocentric", "teleop", "s1", "s2", "eval"], statuses = [...new Set(CAT.rows.map(r => r.status))];
  const sCol = { current: C.ok, superseded: C.text2, upstream: C.run, test: C.warn, duplicate: C.series[3], missing: C.bad, archived: C.line2 };
  const epOpt = { grid: { left: 8, right: 8, top: 40, bottom: 4, containLabel: true }, legend: { top: 0, itemGap: 6, textStyle: { color: C.text2, fontSize: 10 }, itemWidth: 8, itemHeight: 8 }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, confine: true, backgroundColor: C.surface, borderColor: C.line2, textStyle: { color: C.text, fontSize: 11 } },
    xAxis: { type: "category", data: groups, axisLabel: { color: C.text2, fontSize: 10 }, axisLine: { lineStyle: { color: C.line2 } } }, yAxis: { type: "value", axisLabel: { color: C.text2, fontSize: 10 }, splitLine: { lineStyle: { color: C.line, type: "dashed" } } },
    series: statuses.map(s => ({ name: s, type: "bar", stack: "e", barMaxWidth: 28, itemStyle: { color: sCol[s] || C.text3 }, data: groups.map(g => CAT.rows.filter(r => r.group === g && r.status === s).reduce((a, r) => a + (r.episodes || 0), 0)) })) };
  const srcs = (S.sources || []).slice(0, 12), qaOpt = { grid: { left: 8, right: 8, top: 40, bottom: 4, containLabel: true }, legend: { top: 0, itemGap: 6, textStyle: { color: C.text2, fontSize: 10 }, itemWidth: 8, itemHeight: 8 }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, confine: true, backgroundColor: C.surface, borderColor: C.line2, textStyle: { color: C.text, fontSize: 11 } },
    yAxis: { type: "category", inverse: true, data: srcs.map(x => String(x.id).slice(0, 8)), axisLabel: { color: C.text2, fontSize: 10 }, axisLine: { lineStyle: { color: C.line2 } } }, xAxis: { type: "value", axisLabel: { color: C.text2, fontSize: 10 }, splitLine: { lineStyle: { color: C.line, type: "dashed" } } },
    series: [["pass", C.ok], ["flag", C.warn], ["reject", C.bad]].map(([k, c]) => ({ name: k, type: "bar", stack: "q", barMaxWidth: 14, itemStyle: { color: c }, data: srcs.map(x => x[k] || 0) })) };
  main.appendChild(h("div", { class: "hm3" }, [
    h("div", { class: "blk" }, [dsec("Loss"), UI.Chart({ type: "line", x_label: "step", series: sr.map(r => ({ name: r.branch, points: down(r.loss || [], 120) })), log_y: true, smooth: 0.6 }, { height: 170 })]),
    h("div", { class: "blk" }, [dsec("Episodes"), UI.Chart({ type: "echarts", option: epOpt }, { height: 170 })]),
    h("div", { class: "blk" }, [dsec("QA by source"), UI.Chart({ type: "echarts", option: qaOpt }, { height: 170 })])]));

  /* jobs timeline */
  main.appendChild(h("div", { class: "blk" }, [dsec("Jobs 24h", jobs.length, h("a", { href: "#/jobs", text: "all →" })), timelineStrip(jobs)]));
  if (window.CHAT) CHAT.setContext({ route: "home" });
}
UI.route("home", pageHome);

/* @budget-skip-start legacy */
/* ---------------- legacy v4 dispatch (delete when DATA/OPS pages register UI.route) ---------------- */
async function legacyRoute(main, parts, qs) {
  const p = parts[0], F = n => typeof window[n] === "function" ? window[n] : null;
  const pf = (n, ...a) => { const f = F(n); if (!f) throw new Error("page missing: " + parts.join("/")); return f(main, ...a); };
  if (p === "data" && parts.length === 1) return pf("pageHub", qs);
  if (p === "data" && parts.length === 2) return pf("pageDataset", parts[1], qs);
  if (p === "data" && parts[2] === "ep") return pf("pageEpisode", parts[1], parts[3], qs);
  if (p === "jobs") return qs.panel === "import" ? pf("pageImport") : qs.panel === "export" ? pf("pageExport") : pf("pageProcess", qs);
  if (p === "runs") return pf("pageTraining");
  if (p === "qa") return pf("pageAgent");
  if (p === "eval") return pf("pageEval");
  if (p === "loop") return pf("pageLoop", qs);
  main.appendChild(h("div", { class: "errline", text: "✕ no route: " + parts.join("/") }));
}

/* ---------------- boot ---------------- */
function initKeys() {
  const nav = { h: "home", d: "data", j: "jobs", r: "runs", e: "eval", l: "loop", q: "qa" }, m = {};
  Object.keys(nav).forEach(k => m["g " + k] = () => go(nav[k]));
  m["mod+k"] = () => ($("#pal").classList.contains("open") ? closePal() : openPal()); m["?"] = () => openKeys();
  m["/"] = () => { if (window.CHAT) { CHAT.open(); CHAT.focus(); } };
  m["mod+."] = () => UI.panel.toggle();
  m["["] = () => { document.body.classList.toggle("side-min"); try { localStorage.setItem("v5side", document.body.classList.contains("side-min") ? "1" : ""); } catch (e) {} };
  m.Escape = () => { if ($("#pal").classList.contains("open")) return closePal(); if ($("#keys").classList.contains("open")) return closeKeys(); if (window.CHAT && CHAT.esc()) return; if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur(); else return false; };
  UI.keys.bind(m);
}
document.addEventListener("DOMContentLoaded", () => {
  UI.demo = document.documentElement.classList.contains("demo");
  $("#dclose").onclick = closeDrawer; $("#drawer-bg").onclick = closeDrawer;
  try { if (localStorage.getItem("v5side")) document.body.classList.add("side-min"); if (localStorage.getItem("v5dock") === "off") document.body.classList.add("dock-off"); UI.task = localStorage.getItem("v5task") || "tray"; $("#task").value = UI.task; } catch (e) { UI.task = "tray"; }
  $("#task").onchange = e => { UI.task = e.target.value; try { localStorage.setItem("v5task", UI.task); } catch (x) {} route(); };
  initKeys(); initPal(); drawSide(); drawMeta();
  if (window.CHAT) CHAT.mount($("#chat"));
  UI.panel.init();
  if (window.DEMO) DEMO.init();
  route(); poll(); setInterval(poll, 5000);
});

/* ---------------- LEGACY v4 helpers (lineage widget, hub, spark) ---------------- */
/* ---------------- sparkline svgs ---------------- */
function spark(pts, color, logy) {
  const xs = pts.map(p => p[0]), ys = pts.map(p => logy ? Math.log(Math.max(p[1], 1e-3)) : p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const d = pts.map((p, i) => (i ? "L" : "M") + (6 + (xs[i] - x0) / (x1 - x0 || 1) * 188).toFixed(1) + " " + (8 + (1 - (ys[i] - y0) / (y1 - y0 || 1)) * 76).toFixed(1)).join("");
  return `<svg viewBox="0 0 200 92" preserveAspectRatio="none"><path d="${d}" fill="none" stroke="${color}" stroke-width="2.2"/></svg>`;
}
function emaArr(p, a = 0.9) { let m = null; return p.map(([x, y]) => { m = m == null ? y : a * m + (1 - a) * y; return [x, m]; }); }

/* ---------------- LINEAGE WIDGET ---------------- */
function layerOf(n) {
  if (n.ext) return 3;
  if (n.branch !== undefined || (n.id || "").startsWith("run-")) return 4;
  return { "raw source": 0, "pipeline source": 1, export: 2, release: 2, "subset-cut": 3, "eval conditions": 4, "bench copy": 4 }[n.kind] ?? 0;
}
const LAYERS = ["Raw", "Pipeline", "Release · Export", "Cut", "Run · Eval"];
function svgEl(tag, attrs, kids) { const e = document.createElementNS("http://www.w3.org/2000/svg", tag); for (const k in attrs || {}) e.setAttribute(k, attrs[k]); (kids || []).forEach(k => e.appendChild(k)); return e; }
function lineageView(nodes, edges, opt) {
  opt = opt || {};
  const W = 196, H = 40, GX = 52, GY = 10, TOP = 26;
  const ids = new Set(nodes.map(n => n.id));
  edges = edges.filter(([a, b]) => ids.has(a) && ids.has(b) && a !== b);
  if (!opt.keepIsolated) { const con = new Set(edges.flat()); nodes = nodes.filter(n => con.has(n.id) || n.id === opt.focus); }
  const cols = [[], [], [], [], []];
  const go_ = { egocentric: 0, teleop: 1, s1: 2, s2: 3, eval: 4 };
  nodes.forEach(n => cols[layerOf(n)].push(n));
  cols.forEach(c => c.sort((a, b) => ((go_[a.group] ?? 5) - (go_[b.group] ?? 5)) || a.title.localeCompare(b.title)));
  const pos = {}; let maxH = 0;
  cols.forEach((c, ci) => c.forEach((n, i) => { pos[n.id] = { x: 8 + ci * (W + GX), y: TOP + i * (H + GY) }; maxH = Math.max(maxH, TOP + (i + 1) * (H + GY)); }));
  const Wt = 16 + 5 * W + 4 * GX;
  const svg = svgEl("svg", { viewBox: `0 0 ${Wt} ${maxH + 6}` });
  LAYERS.forEach((l, i) => { const t = svgEl("text", { x: 8 + i * (W + GX), y: 14, class: "colh" }); t.textContent = l; svg.appendChild(t); });
  const adjO = {}, adjI = {};
  edges.forEach(([a, b]) => { (adjO[a] = adjO[a] || []).push(b); (adjI[b] = adjI[b] || []).push(a); });
  const eEls = edges.map(([a, b]) => {
    const p = pos[a], q = pos[b], x1 = p.x + W, y1 = p.y + H / 2, x2 = q.x, y2 = q.y + H / 2, dx = Math.max(30, (x2 - x1) / 2);
    const e = svgEl("path", { class: "edge", d: `M${x1} ${y1} C${x1 + dx} ${y1} ${x2 - dx} ${y2} ${x2} ${y2}` }); svg.appendChild(e); return [a, b, e];
  });
  const nEls = {};
  nodes.forEach(n => {
    const p = pos[n.id]; const col = gcol(n.group || (n.ext ? "s1" : "eval"));
    const t = n.title.length > 28 ? n.title.slice(0, 27) + "…" : n.title;
    const sub = n.episodes != null ? `${fmt(n.episodes)} ep · ${({ current: "hiện hành", superseded: "đã thay", test: "thử", duplicate: "trùng", missing: "thiếu", upstream: "ngoài", archived: "lưu trữ" })[n.status] || n.status}` : (n.ext ? "xuất bản" : "run");
    const g = svgEl("g", { class: "node" + (n.id === opt.focus ? " focus" : ""), transform: `translate(${p.x},${p.y})` }, [
      svgEl("title", {}, []), svgEl("rect", { class: "bg", width: W, height: H, rx: 7 }), svgEl("rect", { width: 5, height: H, rx: 2, fill: col }),
    ]);
    g.firstChild.textContent = n.title + (n.name && n.name !== n.title ? "\n" + n.name : "") + "\n" + n.id;
    const t1 = svgEl("text", { x: 13, y: 17 }); t1.textContent = t; const t2 = svgEl("text", { x: 13, y: 31, class: "sub" }); t2.textContent = sub; g.appendChild(t1); g.appendChild(t2);
    g.addEventListener("click", () => { if (rowById(n.id)) go("data/" + n.id); });
    g.addEventListener("mouseenter", () => hl(n.id)); g.addEventListener("mouseleave", () => hl(null));
    svg.appendChild(g); nEls[n.id] = g;
  });
  function walk(start, adj) { const s = new Set(); const st = [start]; while (st.length) { const x = st.pop(); (adj[x] || []).forEach(y => { if (!s.has(y)) { s.add(y); st.push(y); } }); } return s; }
  function hl(id) {
    if (!id) { Object.values(nEls).forEach(e => e.classList.remove("dim")); eEls.forEach(([a, b, e]) => e.setAttribute("class", "edge")); return; }
    const keep = new Set([id, ...walk(id, adjO), ...walk(id, adjI)]);
    Object.entries(nEls).forEach(([k, e]) => e.classList.toggle("dim", !keep.has(k)));
    eEls.forEach(([a, b, e]) => e.setAttribute("class", "edge " + (keep.has(a) && keep.has(b) && (walk(id, adjO).has(b) || b === id || walk(id, adjI).has(a) || a === id) ? "hl" : "dim")));
  }
  return h("div", { class: "lin-wrap" }, [svg, h("div", { class: "count", style: { padding: "6px 4px 2px" }, text: `${nodes.length} nút · ${edges.length} cạnh · rê chuột để sáng tổ tiên và hậu duệ, bấm để mở tập` })]);
}

/* ---------------- DATA HUB ---------------- */
const HUB = { sub: "cards", status: "current", type: "", task: "", loc: "", q: "" };
async function pageHub(main, qs) {
  if (qs.type) HUB.type = qs.type;
  const R = CAT.rows;
  const body = h("div"), controls = h("div");
  const filt = (ignoreType) => R.filter(r => (HUB.status === "all" || r.status === HUB.status) && (ignoreType || !HUB.type || r.group === HUB.type) && (!HUB.task || r.task === HUB.task) &&
    (!HUB.loc || r.locations.some(l => l.where === HUB.loc)) && (!HUB.q || (r.title + " " + r.name + " " + r.id).toLowerCase().includes(HUB.q.toLowerCase())));
  function draw() {
    controls.innerHTML = "";
    const fl = filt(true);
    const sel = (k, opts) => h("select", { onchange: e => { HUB[k] = e.target.value; draw(); } }, opts.map(([v, l]) => h("option", { value: v, selected: HUB[k] === v, text: l })));
    controls.appendChild(h("div", { class: "controls" }, [h("input", { type: "search", placeholder: "Tìm theo tên hoặc id…", value: HUB.q, oninput: e => { HUB.q = e.target.value; clearTimeout(window.__qt); window.__qt = setTimeout(() => { drawBody(); }, 150); } }),
      sel("status", [["current", "Trạng thái: hiện hành"], ["all", "Mọi trạng thái"], ["superseded", "đã thay"], ["test", "thử"], ["duplicate", "trùng"], ["missing", "thiếu"], ["upstream", "ngoài"], ["archived", "lưu trữ"]]),
      sel("task", [["", "Task: tất cả"], ["tray", "tray"], ["two_table", "two_table"], ["hug", "hug"], ["other", "other"]]),
      sel("loc", [["", "Nơi lưu: tất cả"], ["laptop", "laptop"], ["rtx3060", "rtx3060"], ["hf", "HF"], ["colab", "Colab"], ["remote", "từ xa"]])]));
    const chips = h("div", { class: "controls" }, [h("button", { class: "chip" + (!HUB.type ? " on" : ""), text: `Tất cả ${fl.length}`, onclick: () => { HUB.type = ""; draw(); } })]
      .concat(Object.keys(GNAME).map(g => h("button", { class: "chip" + (HUB.type === g ? " on" : ""), text: `${GNAME[g]} ${fl.filter(r => r.group === g).length}`, onclick: () => { HUB.type = g; draw(); } }))));
    controls.appendChild(chips);
    drawBody();
  }
  function card(r) {
    const stripe = gcol(r.group);
    const hasThumbs = r.thumbs && r.thumbs.length;
    let mos;
    if (hasThumbs) mos = h("div", { class: "mosaic" + (r.thumbs.length < 4 ? " one" : "") }, (r.thumbs.length < 4 ? r.thumbs.slice(0, 1) : r.thumbs.slice(0, 4)).map(u => h("img", { src: u, loading: "lazy", alt: "" })));
    else {
      const msg = r.view === "missing" ? "không có trên đĩa" : r.view === "remote" ? (r.locations.some(l => l.where === "rtx3060") ? "chỉ có trên rtx3060" : "chỉ từ xa") : r.view === "psi" ? "bảng · video chưa giải nén" : r.view === "cond" ? "bộ điều kiện (bảng)" : "chỉ metadata";
      mos = h("div", { class: "mosaic one", style: { "--stripe": r.view === "missing" ? "var(--bad)" : stripe } }, h("div", { class: "ph", text: msg }));
    }
    const eps = r.episodes != null ? fmt(r.episodes) + " ep" : "? ep";
    return h("a", { class: "dcard" + (r.status !== "current" ? " dim" : ""), href: "#/data/" + r.id, style: { "--stripe": stripe } }, [mos, h("div", { class: "corner" }, r.status !== "current" ? statusTag(r.status) : null),
      h("div", { class: "body" }, [h("div", { class: "t", text: r.title }), h("div", { class: "m", text: [eps, r.hours != null ? fmt(r.hours, 2) + " h" : null, r.fps ? r.fps + " fps" : null, r.task !== "other" ? r.task : null].filter(Boolean).join(" · ") }), qabar(r.qa_counts), locChips(r.locations)])]);
  }
  function drawBody() {
    body.innerHTML = "";
    const rs = filt(false);
    if (HUB.sub === "cards") {
      Object.keys(GNAME).forEach(g => {
        const gr = rs.filter(r => r.group === g); if (!gr.length) return;
        body.appendChild(h("div", { class: "sec" }, [h("i", { style: { background: gcol(g) } }), h("h2", { text: GNAME[g] }), h("span", { class: "count", text: gr.length + " tập" })]));
        body.appendChild(h("div", { class: "grid" }, gr.map(card)));
      });
      if (!rs.length) body.appendChild(h("div", { class: "empty", text: "Không có tập nào khớp bộ lọc." }));
      body.appendChild(src("catalog.json ← datasets.json (kiểm kê 11/11) + fwdata/ (poster cv2, meta LeRobot). Poster chỉ có khi tập có trên laptop."));
    } else if (HUB.sub === "table") {
      body.appendChild(dataTable([
        { k: "title", label: "Tập dữ liệu", render: r => h("a", { href: "#/data/" + r.id, text: r.title }) },
        { k: "group", label: "Loại", render: r => h("span", null, [h("span", { class: "legend-dot", style: { background: gcol(r.group) } }), GNAME[r.group]]) },
        { k: "kind", label: "Dạng" }, { k: "task", label: "Task" }, { k: "episodes", label: "Episode", num: true }, { k: "frames", label: "Khung", num: true }, { k: "fps", label: "fps", num: true },
        { k: "licence", label: "Licence" }, { k: "data_class", label: "Lớp" }, { k: "loc", label: "Nơi lưu", get: r => r.locations.map(l => l.where).filter((v, i, a) => a.indexOf(v) === i).join(", ") },
        { k: "qa", label: "QA", render: r => r.qa_counts ? Object.entries(r.qa_counts).map(([k, v]) => v + " " + k).join(" / ") : (r.qa || "–").slice(0, 40) },
        { k: "status", label: "Trạng thái", render: r => statusTag(r.status) }], rs, { onrow: r => go("data/" + r.id), free: true, limit: 100 }));
      body.appendChild(src("catalog.json · 60 dòng. Bấm tiêu đề cột để sắp xếp."));
    } else {
      const nodes = R.map(r => r).concat(CAT.runs).filter(n => n.ext || n.branch !== undefined || n.id.startsWith("run-") || rs.includes(n));
      const keep = new Set(nodes.map(n => n.id));
      // keep run nodes only when their parent is visible
      const vis = nodes.filter(n => rowById(n.id) || CAT.edges.some(([a, b]) => b === n.id && keep.has(a) && (rowById(a) ? rs.includes(rowById(a)) : true)));
      body.appendChild(lineageView(vis, CAT.edges));
      body.appendChild(src("datasets.json · mục lineage (50 cạnh: manifest parent, cut id, data.root_dir trong launch.json). Cùng bộ lọc với tab Thẻ."));
    }
  }
  main.appendChild(dataSubtabs(""));
  main.appendChild(h("div", { class: "page-h" }, [h("div", null, [h("h1", { text: "Dữ liệu · mọi tập trên mọi máy" }), h("p", { class: "lede", text: "Có dữ liệu gì, nằm ở đâu, tập nào đang dùng? Bấm một thẻ để xuống từng episode." })]),
    howBtn({ title: "Dữ liệu", tabs: { method: "<p>Kiểm kê quét laptop <code>fwdata/</code>, rtx3060 (chỉ đọc), HF và Drive, rồi đọc metadata có sẵn: <code>meta/info.json</code> (LeRobot), <code>source.json</code>, <code>batch_summary.json</code>. Poster là khung giữa của video, dựng bằng cv2 (320 px, JPEG q70).</p><h4>Trạng thái</h4><p><b>hiện hành</b> đang dùng · <b>đã thay</b> bị thay · <b>trùng</b> bản trùng · <b>thử</b> bản thử · <b>thiếu</b> có trong tài liệu nhưng không có trên đĩa.</p>", log: pre("python mock_v4/build.py\nrobot posters: S70 425 + ALL 181 mới (425 dùng chung)\ncatalog rows 60 edges 50"), src: pre("datasets.json (kiểm kê 11/11)\nfwdata/da34-dryrun/cut-all-zone1/{S70,ALL}\nfwdata/human1m/ego-h1m-20261111\nfwdata/pipeline/src_*") } })]));
  main.appendChild(subtabs([["cards", "Thẻ"], ["table", "Bảng"], ["lineage", "Lineage"]], HUB.sub, id => { HUB.sub = id; main.innerHTML = ""; pageHub(main, {}); }));
  main.appendChild(controls); main.appendChild(body); draw();
}


/* @budget-skip-end */

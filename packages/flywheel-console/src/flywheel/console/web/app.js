/* shell: sidebar, top bar (task and round selectors), right panel, router, command palette, shortcut sheet.
   Pages register with UI.route(pattern, fn). Unregistered routes fall back to the v4 page functions (LEGACY block at the bottom).
   Information architecture (brief 2 · T2): Tổng quan (#/home) · Quy trình (six stages and the cost ledger, one page template
   with tabs, PROC in pages_proc.js) · Báo cáo vòng (#/report, #/follow, #/base, #/design) · Vận hành (jobs, machines, import).
   Lock mode is read-only, not another site: every entry stays, write controls are switched off with a padlock and a tooltip. */
"use strict";
/* sidebar; a function so labels follow the language and the task (counts come from the index or /api/status, never typed) */
const SIDE = () => [
  { g: null, items: [{ id: "tasks", t: t("nav.tasks"), ic: "▦", href: "#/tasks" }] },
  { g: TASK.name() || null, items: [{ id: "home", t: t("nav.overview"), ic: "◎", href: "#/home" }] },
  { g: t("nav.process"), items: [
    ...EXPLAIN.STEPS.map(n => ({ id: "s" + n, t: PROC.name(n), ic: String(n), step: n, href: EXPLAIN.href(n),
      ct: n === 1 ? () => ({ n: EXPLAIN.read.tot("all") != null ? UI.fmt(EXPLAIN.read.tot("all"), "int") : null, tip: t("side.episodes") })
        : n === 3 ? () => ({ n: trainRuns().filter(r => r.running).length || null, run: 1, tip: t("pr.s.run") }) : null })),
    { id: "cost", t: PROC.name(0), ic: "$", step: 0, href: EXPLAIN.href(0) },
    { id: "egoflow", t: t("nav.egoflow"), ic: "✋", href: "#/egoflow" }] },
  { g: null, items: [{ id: "report", t: t("nav.report"), ic: "◷", href: "#/report" }] },
  { g: t("nav.ops"), ops: 1, items: [
    { id: "jobs", t: t("nav.jobs"), ic: "☰", href: "#/jobs", ct: () => ({ n: ST.jobs.filter(j => j.state === "running" || j.state === "queued").length || null, run: 1 }) },
    { id: "machines", t: t("nav.machines"), ic: "▦", href: "#/jobs?view=machines", ct: () => ({ s: ST.machines && ST.machines.colab && ST.machines.colab.balance != null ? UI.fmt(ST.machines.colab.balance, "int") : null, tip: "Colab CU" }) },
    { id: "import", t: t("nav.import"), ic: "⇣", href: "#/jobs?panel=import" }] },
];
const REDIRECT = { overview: "home", process: "jobs?view=pipeline", training: "runs", agent: "qa", "data/nhap": "jobs?panel=import", "data/xuat": "jobs?panel=export" };
/* STORY is story.json as the current task sees it (TASK.scopeStory): another task's or round's numbers are left out */
let CAT = null, STORY = null, STORY_RAW = null;
const CATP = () => CAT ? Promise.resolve(CAT) : J("data/catalog.json").then(c => (CAT = c));
const STORYP = () => (STORY_RAW ? Promise.resolve(STORY_RAW) : J("data/story.json").then(s => (STORY_RAW = s))).then(s => (STORY = TASK.scopeStory(s)));
/* pages of the round report (sub-navigation in PROC.reportHead); a task without a round gets an empty state there */
const REPORT = /^(report|follow|base|design)$/;
const rowById = id => CAT.rows.find(r => r.id === id);
const nodeById = id => rowById(id) || (CAT.runs || []).find(r => r.id === id);
const jget = (u) => fetch(u).then(r => { if (!r.ok) throw new Error(u + " " + r.status); return r.json(); });

/* ---------------- router ---------------- */
function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "") || "tasks";
  const [p, q] = raw.split("?");
  const qs = {}; (q || "").split("&").filter(Boolean).forEach(kv => { const [k, v] = kv.split("="); qs[decodeURIComponent(k)] = decodeURIComponent(v || ""); });
  return { parts: p.split("/").filter(Boolean).map(decodeURIComponent), qs };
}
function go(path) { location.hash = "#/" + path; }
let RT = 0;
function sideActive() {
  const { parts, qs } = parseHash(), p = parts[0] || "tasks";
  if (p === "jobs") return qs.view === "machines" ? "machines" : qs.panel === "import" ? "import" : "jobs";
  if (REPORT.test(p)) return "report";
  const n = EXPLAIN.stationOf(parts.join("/"), qs);
  if (n === 0) return "cost";
  if (n != null) return "s" + n;
  return p;
}
function drawSide() {
  const el = $("#side"); el.innerHTML = ""; const act = sideActive();
  SIDE().forEach(g => {
    const box = h("div", { class: "sg" + (g.ops ? " ops" : "") }); el.appendChild(box);
    if (g.g) box.appendChild(h("div", { class: "gh", text: g.g }));
    g.items.forEach(it => { const c = it.ct ? it.ct() : {}, txt = c.n != null ? String(c.n) : c.s != null ? c.s : "";
      const ic = it.step != null ? "ic sn" + (it.step === 0 ? " cost" : "") : "ic";
      box.appendChild(h("a", { href: it.href, class: it.id === act ? "on" : "", title: it.t }, [h("span", { class: ic, text: it.ic }), h("span", { class: "nm", text: it.t }), txt ? h("span", { class: "ct" + (c.run && c.n ? " run" : c.warn && c.n ? " warn" : ""), title: c.tip || null, text: txt }) : null])); });
  });
}
function chatRoute() { const { parts } = parseHash(); return parts.join("/") || "home"; }
const qsOf = q => { const o = {}; q.replace(/^\?/, "").split("&").filter(Boolean).forEach(kv => { const [k, v] = kv.split("="); o[decodeURIComponent(k)] = decodeURIComponent(v || ""); }); return o; };
async function route() {
  const tok = ++RT;
  UI.keys.clear("page"); disposeCharts(); if (window.opsStop) opsStop(); if (window.__raf) cancelAnimationFrame(window.__raf);
  UI.panel.reset();
  let raw = location.hash.replace(/^#\/?/, "") || "tasks";
  const qi = raw.indexOf("?"), path = qi < 0 ? raw : raw.slice(0, qi), q = qi < 0 ? "" : raw.slice(qi), q0 = qsOf(q);
  /* the wheel moved from #/home to the round report; the ledger left the loop page */
  const moved = path === "home" && (q0.s != null || q0.tour != null) ? "report" : path === "loop" && q0.tab === "cost" ? "cost" : null;
  if (moved) { history.replaceState(null, "", "#/" + moved + (moved === "cost" ? "" : q)); return route(); }
  const tgt = REDIRECT[path];
  if (tgt) { const [tp, tq] = tgt.split("?"), mq = [tq, q.slice(1)].filter(Boolean).join("&"); history.replaceState(null, "", "#/" + tp + (mq ? "?" + mq : "")); return route(); }
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent), p0 = parts[0] || "home";
  const main = $("#main"); main.innerHTML = "";
  drawSide();
  const view = h("div", { class: "view" }, [h("div", { class: "skel" }), h("div", { class: "skel" }), h("div", { class: "skel" })]);
  main.appendChild(view); main.scrollTop = 0;
  if (window.CHAT) CHAT.touchContext();
  try {
    if (!TASK.loaded) { await TASK.load(); taskSelect(); drawSide(); }   /* the side labels carry task placeholders */
    await Promise.all([CATP(), STORYP(), typeof SIMP === "function" ? SIMP() : null, typeof EGOP === "function" && /^(data|sim)/.test(path) ? EGOP() : null]);
    if (tok !== RT) return;
    const m = UI.matchRoute(path || "home"), qs = UI.qs(), stn = EXPLAIN.stationOf(path, qs), out = [];
    const page = async () => { const body = h("div"); if (m) await m.fn(body, m.params, qs); else await legacyRoute(body, parts, qs); return body; };
    let cls = "proc";
    if (p0 === "home") { const body = h("div"); await PROC.home(body); out.push(body); }
    else if (REPORT.test(p0)) {
      cls = "story"; out.push(PROC.reportHead(p0, qs));
      if (!TASK.round()) out.push(PROC.noRound());
      else { const strip = resultStrip(); if (strip) out.push(strip); out.push(await page()); }
    } else if (stn != null && parts.length < 2 && p0 !== "sim") {
      /* a process stage: head, tabs (?tab=), then the tab */
      const tab = PROC.tabOf(qs);
      out.push(PROC.head(stn), PROC.tabs(stn, tab));
      if (tab === "result") out.push(...PROC.result(stn, TASK.hasData(stn) ? await page() : TASK.empty(stn)));
      else out.push(...await PROC.tab(stn, tab, qs));
    } else if (stn != null) { out.push(PROC.crumb(stn), await page()); }   /* one dataset, one episode, the sim library */
    else out.push(await page());
    if (tok !== RT) return;
    view.innerHTML = ""; view.classList.add(cls);
    out.filter(Boolean).forEach(x => view.appendChild(x));
  } catch (e) {
    console.error(e); if (tok !== RT) return; view.innerHTML = "";
    view.appendChild(h("div", { class: "errline" }, ["✕ " + String(e.message || e) + " ", h("a", { href: "#/home", text: "[home]" })]));
  }
  if (window.CHAT) CHAT.touchContext();
}
window.addEventListener("hashchange", () => { route(); });

/* ---------------- task and round selectors: kept as a stored preference and ?task= / ?round= ---------------- */
const LBL = o => o == null ? "" : typeof o === "string" ? o : (o[UI.lang] || o.vi || "");
function taskSelect() {
  const sel = $("#task"); if (!sel) return;
  sel.replaceChildren(...TASK.list().map(x => h("option", { value: x.id, selected: x.id === TASK.id, text: LBL(x.name) || x.id })));
  sel.title = t("task.sel");
  const rs = $("#round"), ids = (TASK.cur() || {}).rounds || []; if (!rs) return;
  rs.hidden = !ids.length; rs.title = t("task.round");
  rs.replaceChildren(...ids.map(id => { const r = (TASK.doc.rounds || []).find(x => x.id === id) || { id }; return h("option", { value: id, selected: id === TASK.roundId, text: LBL(r.title) || id }); }));
}
function retask() { taskSelect(); PAL.built = false; drawSide(); drawMeta(); route(); }

/* ---------------- header + live state ---------------- */
const ST = { stages: null, jobs: [], models: null, machines: null, agent: null };
const trainRuns = () => { const s = (ST.stages || []).find(x => x.id === "train" && (!x.task || x.task === TASK.id)); return s && s.runs ? s.runs : []; };
function drawMeta() {
  const el = $("#meta"); el.innerHTML = "";
  const run = ST.jobs.filter(j => j.state === "running" || j.state === "queued").length;
  const m = ST.machines || {}, rtx = m.rtx3060, nm = ST.models ? ST.models.nemotron || (ST.models.agent_ready ? "warm" : "down") : "down";
  /* lock mode: the server does not connect out, so a link it never tried is neutral, not a red cross */
  const dot = (s, live) => UI.locked && !live ? h("span", { class: "dim", text: "–" }) : h("span", { class: "c-" + UI.stateClass(s), text: s === "down" ? "✕" : s === "cold" ? "○" : "●" });
  const pill = (kids, fn, title) => h(fn ? "button" : "span", { class: "pill", title: UI.locked && !fn ? t("lock.off") : title, onclick: fn }, kids);
  [pill([t("nav.jobs") + " ", h("span", { class: run ? "c-run" : "", text: String(run) })], () => go("jobs"), t("pr.home.running")),
    pill(["3060 ", dot(rtx && rtx.tunnel === "up" ? "up" : "down")], null, "rtx3060 tunnel"),
    pill([t("hdr.chat") + " ", dot(nm, !UI.chatOff)], () => { if (window.CHAT) CHAT.toggle(); }, UI.chatOff ? t("chat.locked") : nm),
    UI.locked ? h("span", { class: "lockpill", title: t("lock.refused"), text: t("lock.badge") }) : null,
    h("button", { class: "langbtn", title: "VI / EN", onclick: () => { UI.setLang(UI.lang === "vi" ? "en" : "vi"); retask(); if (window.CHAT) CHAT.locked(UI.chatOff); } }, [h("span", { class: UI.lang === "vi" ? "on" : "", text: "VI" }), " | ", h("span", { class: UI.lang === "en" ? "on" : "", text: "EN" })]),
    h("button", { class: "themebtn", title: "theme", onclick: () => { setTheme(curTheme() === "dark" ? "light" : "dark"); route(); }, text: "◐" }),
    h("button", { class: "keysbtn", title: "shortcuts", onclick: () => openKeys(), text: "?" })].forEach(x => x && el.appendChild(x));
}
async function poll() {
  try {
    const [st, jb, md, ag] = await Promise.all([jget("/api/status"), jget("/api/jobs?limit=100").catch(() => []), jget("/api/models").catch(() => null), jget("/api/agent_stats").catch(() => null)]);
    ST.stages = st.stages; ST.machines = st.machines; ST.jobs = jb; ST.models = md; ST.agent = ag; ST.status = st; ST.at = Date.now();
    UI.locked = !!st.locked; document.documentElement.classList.toggle("locked", UI.locked);
    UI.chatOff = UI.locked && !st.chat_on;   /* a locked server started with --chat keeps the chat */
    if (window.CHAT) { CHAT.setModelState(md); CHAT.locked(UI.chatOff); }
  } catch (e) { ST.stages = ST.stages || null; }
  drawSide(); drawMeta();
}
/* lock mode: a write control stays in view, switched off, with a padlock (CSS) and a tooltip saying why */
document.addEventListener("click", e => { const b = UI.locked && e.target.closest && e.target.closest(".wbtn"); if (b) { e.preventDefault(); e.stopPropagation(); } }, true);
document.addEventListener("mouseover", e => { const b = UI.locked && e.target.closest && e.target.closest(".wbtn"); if (b && b.title !== t("lock.tip")) { b.title = t("lock.tip"); b.setAttribute("aria-disabled", "true"); } }, true);

/* ---------------- shortcut sheet and palette ---------------- */
const KEYS = [["g h/d/j/r/e/l/q", "go to page"], ["j / k", "row down / up"], ["Enter", "open row"], ["x", "select row"], ["c", "compare"], ["a", "ask chat about row"], ["[ ]", "prev / next"],
  ["⌘K", "palette"], ["/", "focus chat"], ["⌘.", "toggle panel"], ["Esc", "back out"], ["?", "this sheet"]];
function openKeys() { const b = $("#keys-box"); b.innerHTML = ""; b.appendChild(h("div", { class: "gr" }, KEYS.map(([k, d]) => h("div", { class: "kr" }, [h("span", { text: d }), h("kbd", { text: k })])))); $("#keys").classList.add("open"); }
function closeKeys() { $("#keys").classList.remove("open"); }
const PAL = { items: [], sel: 0, built: false };
async function buildPalette() {
  const it = []; const add = (k, t, d, fn) => it.push({ k, t, d, fn });
  SIDE().forEach(g => g.items.forEach(x => add("go", x.t, x.href, () => { location.hash = x.href; })));
  await CATP().catch(() => {}); await STORYP().catch(() => {});
  if (CAT) CAT.rows.filter(r => !UI.demo || r.data_class === "public").forEach(r => add("data", r.id, r.title || r.name, () => go("data/" + r.id)));
  const runs = new Set(); ((STORY && STORY.runs) || []).forEach(r => runs.add(r.branch)); runs.forEach(b => add("run", b, "#/runs?sel=" + b, () => go("runs?sel=" + b)));
  try { (await jget("/api/jobs?limit=20")).forEach(j => add("job", j.id, j.kind + " " + j.state, () => go("jobs?job=" + j.id))); } catch (e) {}
  if (!UI.locked) try { (await jget("/api/tools?route=" + encodeURIComponent(chatRoute()))).forEach(t => add("tool", "/" + String(t.slash || t.name).replace(/^\//, ""), t.description ? t.description.slice(0, 60) : "", () => { if (window.CHAT) CHAT.open("/" + String(t.slash || t.name).replace(/^\//, "") + " "); })); } catch (e) {}
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
  document.documentElement.lang = UI.lang;
  if (!EXPLAIN.on()) document.body.classList.add("explain-off");
  $("#dclose").onclick = closeDrawer; $("#drawer-bg").onclick = closeDrawer;
  try { if (localStorage.getItem("v5side")) document.body.classList.add("side-min"); if (localStorage.getItem("v5dock") !== "on") document.body.classList.add("dock-off"); } catch (e) { /* storage blocked */ }
  /* ?task= beats the stored choice; UI.task / UI.round read TASK (core.js) */
  const tq = /[?&#]task=([\w-]+)/.exec(location.search + location.hash), rq = /[?&#]round=([\w-]+)/.exec(location.search + location.hash);
  const tp = tq ? tq[1] : (() => { try { return localStorage.getItem("v5task"); } catch (e) { return null; } })();
  if (tp) TASK.set(tp, rq ? rq[1] : null);
  $("#task").onchange = e => { TASK.set(e.target.value); UI.pref("v5task", TASK.id); retask(); };
  $("#round").onchange = e => { TASK.set(TASK.id, e.target.value); retask(); };
  initKeys(); initPal(); drawSide(); drawMeta();
  if (window.CHAT) CHAT.mount($("#chat"));
  UI.panel.init();
  poll().then(() => {
    /* locked demo laptop: ignore what an earlier visitor chose; only ?lang= counts (design 14.2) */
    if (UI.locked) { const m = /[?&#]lang=(vi|en)\b/.exec(location.search + location.hash); UI.lang = m ? m[1] : "vi"; document.documentElement.lang = UI.lang; document.body.classList.remove("explain-off");
      if (!tq) TASK.set(TASK.loaded && TASK.list().length ? TASK.list()[0].id : null, rq ? rq[1] : null);   /* the first task of the manifest, whatever an earlier visitor chose */
      /* the demo opens in the deck's light look whatever an earlier visitor chose; ◐ still works for this visit */
      if (!/[?&#]theme=dark\b/.test(location.search + location.hash)) document.documentElement.setAttribute("data-theme", "light");
      if (window.CHAT) { CHAT.close(true); CHAT.locked(UI.chatOff); } taskSelect(); drawSide(); drawMeta(); }   /* chat closed by default, can be opened */
    route();
  }); setInterval(poll, 5000);  /* first status first: a locked server must not see /api/tool calls */
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
    const sub = n.episodes != null ? `${fmt(n.episodes)} ep · ${({ current: "hiện hành", superseded: "đã thay", test: "thử", duplicate: "trùng", missing: "thiếu", upstream: "ngoài", archived: "lưu trữ", reference: "tham chiếu", benchmark: "chuẩn đo" })[n.status] || n.status}` : (n.ext ? "xuất bản" : "run");
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
  /* a task that counts only its own rows (inventory "task") opens the store filtered to them */
  const tk = TASK.cur(); if (!HUB.userTask) HUB.task = tk && tk.inventory === "task" ? tk.catalog_task : "";
  const R = CAT.rows;
  const body = h("div"), controls = h("div");
  const filt = (ignoreType) => R.filter(r => (HUB.status === "all" || r.status === HUB.status || (HUB.status === "current" && r.status === "reference")) && (ignoreType || !HUB.type || r.group === HUB.type) && (!HUB.task || r.task === HUB.task) &&
    (!HUB.loc || r.locations.some(l => l.where === HUB.loc)) && (!HUB.q || (r.title + " " + r.name + " " + r.id).toLowerCase().includes(HUB.q.toLowerCase())));
  function draw() {
    controls.innerHTML = "";
    const fl = filt(true);
    const sel = (k, opts) => h("select", { onchange: e => { HUB[k] = e.target.value; if (k === "task") HUB.userTask = 1; draw(); } }, opts.map(([v, l]) => h("option", { value: v, selected: HUB[k] === v, text: l })));
    controls.appendChild(h("div", { class: "controls" }, [h("input", { type: "search", placeholder: "Tìm theo tên hoặc id…", value: HUB.q, oninput: e => { HUB.q = e.target.value; clearTimeout(window.__qt); window.__qt = setTimeout(() => { drawBody(); }, 150); } }),
      sel("status", [["current", "Trạng thái: hiện hành"], ["all", "Mọi trạng thái"], ["superseded", "đã thay"], ["test", "thử"], ["duplicate", "trùng"], ["missing", "thiếu"], ["upstream", "ngoài"], ["archived", "lưu trữ"], ["reference", "tham chiếu"], ["benchmark", "chuẩn đo"]]),
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
    return h("a", { class: "dcard" + (r.status !== "current" && r.status !== "reference" ? " dim" : ""), href: "#/data/" + r.id, style: { "--stripe": stripe } }, [mos, h("div", { class: "corner" }, r.status !== "current" ? statusTag(r.status) : null),
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

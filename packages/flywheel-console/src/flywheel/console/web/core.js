/* core: legacy v4 helpers (kept until DATA/OPS pages convert) + namespace UI (v5 components). */
"use strict";
/* @budget-skip-start legacy v4 helpers */
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
function h(tag, attrs, kids) {
  const e = document.createElement(tag);
  if (attrs) for (const k in attrs) {
    const v = attrs[k];
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "html") e.innerHTML = v;
    else if (k === "text") e.textContent = v;
    else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") Object.assign(e.style, v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  (Array.isArray(kids) ? kids : kids == null ? [] : [kids]).flat(9).forEach(c => { if (c == null || c === false) return; e.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(c) : c); });
  return e;
}
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
const nf = new Intl.NumberFormat("vi-VN");
const fmt = (x, d) => x == null || x === "" || Number.isNaN(x) ? "–" : (typeof x === "number" ? (d != null ? x.toLocaleString("vi-VN", { minimumFractionDigits: d, maximumFractionDigits: d }) : nf.format(x)) : x);
const pct = (x, d = 1) => x == null ? "–" : (x * 100).toLocaleString("vi-VN", { maximumFractionDigits: d, minimumFractionDigits: d }) + " %";
const wilson = (k, n, z = 1.96) => { const p = k / n, d = 1 + z * z / n, c = p + z * z / (2 * n), m = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return [(c - m) / d, (c + m) / d]; };

const _cache = {};
function J(url) { return _cache[url] || (_cache[url] = fetch(url).then(r => { if (!r.ok) throw new Error(url + " " + r.status); return r.json(); })); }

/* ---- theme + colors ---- */
function cv(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function palette() { return { ink: cv("--ink"), mute: cv("--muted"), line: cv("--line"), panel: cv("--panel"), bg: cv("--bg"), acc: cv("--accent"), warn: cv("--warn"), bad: cv("--bad"), run: cv("--run"), idle: cv("--idle"), ego: cv("--t-ego"), tele: cv("--t-tele"), s1: cv("--t-s1"), s2: cv("--t-s2"), eval: cv("--t-eval"), head: cv("--head") }; }
const SER = () => { const c = palette(); return [c.tele, c.ego, c.s1, c.s2, c.warn, c.bad, c.idle]; };
const GCOL = { egocentric: "--t-ego", teleop: "--t-tele", s1: "--t-s1", s2: "--t-s2", eval: "--t-eval" };
const GNAME = { egocentric: "Egocentric", teleop: "Teleop", s1: "Synthetic S1", s2: "Synthetic S2", eval: "Eval & bench" };
const gcol = g => cv(GCOL[g] || "--idle");
function setTheme(t) {
  if (t) document.documentElement.setAttribute("data-theme", t); else document.documentElement.removeAttribute("data-theme");
  try { localStorage.setItem("v5theme", t || ""); } catch (e) {}
}
function curTheme() { return document.documentElement.getAttribute("data-theme") || "dark"; }

/* ---- charts ---- */
let CHARTS = [];
function disposeCharts() { CHARTS.forEach(c => { try { c.dispose(); } catch (e) {} }); CHARTS = []; }
function chart(el, opt, extra) {
  const c = echarts.init(el, null, { renderer: "canvas" });
  const p = palette();
  opt = Object.assign({ textStyle: { color: p.mute, fontFamily: "system-ui, sans-serif" }, animation: false, backgroundColor: "transparent" }, opt);
  c.setOption(opt);
  CHARTS.push(c);
  return c;
}
function ax(o) {
  const p = palette();
  return Object.assign({ axisLine: { lineStyle: { color: p.line } }, axisTick: { show: false }, axisLabel: { color: p.mute, fontSize: 11 }, splitLine: { lineStyle: { color: p.line, opacity: .7 } }, nameTextStyle: { color: p.mute, fontSize: 11 } }, o);
}
window.addEventListener("resize", () => CHARTS.forEach(c => c.resize()));

/* ---- ui atoms ---- */
function tag(text, cls) { return h("span", { class: "tag " + (cls || ""), text }); }
function qaTag(q) { return tag(q, q === "pass" ? "" : q === "flag" ? "flag" : q === "reject" ? "reject" : "idle"); }
function statusTag(s) { const m = { current: ["hiện hành", ""], superseded: ["đã thay", "idle"], test: ["thử", "idle"], duplicate: ["trùng", "flag"], missing: ["thiếu", "reject"], upstream: ["nguồn ngoài", "run"], archived: ["lưu trữ", "idle"] }; const x = m[s] || [s, "idle"]; return tag(x[0], x[1]); }
const illus = () => tag("minh hoạ", "ill");
function src(text, extra) { return h("div", { class: "src" }, ["nguồn: " + text, extra || null]); }
function panel(title, cap, body, source, cls) {
  return h("div", { class: "panel " + (cls || "") }, [title ? h("h3", { text: title }) : null, cap ? h("div", { class: "cap", text: cap }) : null, body, source ? src(source) : null]);
}
function stat(v, k, s, color) { return h("div", { class: "stat" }, [h("div", { class: "v", style: color ? { color } : null }, v), h("div", { class: "k", text: k }), s ? h("div", { class: "s", html: s }) : null]); }
function qabar(c) {
  if (!c) return null;
  const t = (c.pass || 0) + (c.flag || 0) + (c.reject || 0); if (!t) return null;
  return h("div", { title: `pass ${c.pass || 0} · flag ${c.flag || 0} · reject ${c.reject || 0}` }, [h("div", { class: "qabar" }, [["p", "pass"], ["f", "flag"], ["r", "reject"]].map(([k, n]) => h("i", { class: k, style: { width: (c[n] || 0) / t * 100 + "%" } }))),
    h("div", { class: "m", style: { fontSize: "12px", marginTop: "3px" }, text: [c.pass ? c.pass + " pass" : "", c.flag ? c.flag + " flag" : "", c.reject ? c.reject + " reject" : ""].filter(Boolean).join(" · ") })]);
}
function locChips(locs) {
  const m = { laptop: ["laptop", "lap"], rtx3060: ["rtx3060", "rtx"], hf: ["HF", ""], colab: ["Colab", ""], remote: ["từ xa", ""] };
  const seen = new Set();
  return h("div", { class: "chips" }, locs.filter(l => { if (seen.has(l.where)) return false; seen.add(l.where); return true; }).map(l => h("span", { class: "loc " + (m[l.where] ? m[l.where][1] : ""), text: m[l.where] ? m[l.where][0] : "?" })));
}
function copyBtn(text, label) {
  return h("button", { class: "btn copy", text: label || "Chép", onclick: e => { navigator.clipboard && navigator.clipboard.writeText(text).catch(() => {}); e.target.textContent = "Đã chép"; setTimeout(() => e.target.textContent = label || "Chép", 1200); } });
}
function cmdBox(cmd) { return h("div", { style: { display: "flex", gap: "8px", alignItems: "flex-start" } }, [h("pre", { style: { flex: 1, margin: 0 }, text: cmd }), copyBtn(cmd)]); }
function subtabs(items, cur, onpick) {
  return h("div", { class: "subtabs" }, items.map(([id, label]) => h("a", { class: id === cur ? "on" : "", href: "javascript:void 0", onclick: () => onpick(id), text: label })));
}

/* ---- sortable table ---- */
function dataTable(cols, rows, opt) {
  opt = opt || {};
  let sk = opt.sort || null, sd = opt.dir || 1, lim = opt.limit || 120;
  const wrap = h("div");
  function draw() {
    let rs = rows.slice();
    if (sk) { const c = cols.find(c => c.k === sk); const g = c.sort || c.get || (r => r[sk]); rs.sort((a, b) => { const x = g(a), y = g(b); if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * sd; }); }
    const shown = rs.slice(0, lim);
    wrap.innerHTML = "";
    const tb = h("tbody", null, shown.map(r => {
      const tr = h("tr", { class: opt.onrow ? "click" : "", onclick: opt.onrow ? () => opt.onrow(r) : null }, cols.map(c => { const v = c.render ? c.render(r) : (c.get ? c.get(r) : r[c.k]); const td = h("td", { class: c.num ? "n" : "" }); if (v instanceof Node) td.appendChild(v); else td.textContent = v == null ? "–" : (typeof v === "number" ? fmt(v, c.d) : v); return td; }));
      return tr;
    }));
    const th = h("thead", null, h("tr", null, cols.map(c => h("th", { class: (c.num ? "n " : "") + (c.nosort ? "nosort" : ""), onclick: c.nosort ? null : () => { if (sk === c.k) sd = -sd; else { sk = c.k; sd = c.num ? -1 : 1; } draw(); } }, [c.label, sk === c.k ? h("span", { class: "arr", text: sd > 0 ? " ▲" : " ▼" }) : null]))));
    wrap.appendChild(h("div", { class: "tscroll" + (opt.free ? " free" : "") }, h("table", { class: "t" }, [th, tb])));
    wrap.appendChild(h("div", { class: "count", style: { margin: "8px 2px" } }, [`${fmt(shown.length)} / ${fmt(rs.length)} dòng`, rs.length > lim ? h("button", { class: "btn", style: { marginLeft: "10px" }, text: "Hiện thêm 200", onclick: () => { lim += 200; draw(); } }) : null]));
  }
  draw();
  return wrap;
}

/* ---- drawer ---- */
const DRAWER = {};
function openDrawer(spec) {
  // spec: {title, tabs: {method: node|string, log:..., src:...}}
  const d = $("#drawer"), bg = $("#drawer-bg");
  let cur = "method";
  const body = $("#dbody"); $("#dtitle").textContent = spec.title || "Cách làm";
  function draw() {
    $$("#dtabs a").forEach(a => a.classList.toggle("on", a.dataset.t === cur));
    body.innerHTML = ""; const v = spec.tabs[cur]; if (v == null) body.appendChild(h("p", { class: "muted", text: "Chưa có." })); else if (typeof v === "string") body.innerHTML = v; else body.appendChild(v);
  }
  $("#dtabs").onclick = e => { const t = e.target.dataset.t; if (t) { cur = t; draw(); } };
  if (spec.start) cur = spec.start;
  draw(); d.classList.add("open"); bg.classList.add("open");
}
function closeDrawer() { $("#drawer").classList.remove("open"); $("#drawer-bg").classList.remove("open"); }
document.addEventListener("keydown", e => { if (e.key === "Escape") closeDrawer(); });
function howBtn(spec) { return h("button", { class: "btn", text: "Cách làm", onclick: () => openDrawer(spec) }); }
const pre = t => h("pre", { text: t });
const J2 = o => JSON.stringify(o, null, 2);

/* @budget-skip-end */
/* =====================================================================
   UI namespace (v5). Contract: CONTRACTS.md section 2.
   Extras beyond the contract: UI.status, UI.tag, UI.color, UI.copy, UI.sec, UI.demo,
   UI.Table options select/onSelect/total/title/search, UI.fmt names "status|id|spark" for table cells.
   ===================================================================== */
const UI = (() => {
  const U = { demo: false };
  const text = (s) => document.createTextNode(s);
  const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const MONO = '"JetBrains Mono","Geist Mono",ui-monospace,"SF Mono",Menlo,monospace';

  /* ---------- fmt ---------- */
  const DASH = "—";
  const grp = (n, d) => n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  U.fmt = function (v, f) {
    if (v == null || v === "" || (typeof v === "number" && !isFinite(v))) return DASH;
    if (f === "date" || f === "time") {
      const d = v instanceof Date ? v : new Date(v); if (isNaN(d)) return String(v);
      const p = n => String(n).padStart(2, "0");
      return f === "date" ? p(d.getDate()) + "/" + p(d.getMonth() + 1) : p(d.getHours()) + ":" + p(d.getMinutes());
    }
    const n = typeof v === "number" ? v : parseFloat(v);
    if (isNaN(n)) return String(v);
    switch (f) {
      case "int": return grp(Math.round(n), 0);
      case "float1": return grp(n, 1);
      case "float3": return grp(n, 3);
      case "pct": return grp(n * 100, 1) + "%";          // input is a ratio 0..1
      case "dur": {                                       // input is seconds
        if (n < 60) return grp(n, 1) + " s";
        if (n < 3600) { const m = Math.floor(n / 60); return m + "m" + String(Math.round(n - m * 60)).padStart(2, "0"); }
        const hh = Math.floor(n / 3600); return hh + "h" + String(Math.floor((n - hh * 3600) / 60)).padStart(2, "0");
      }
      case "bytes": {
        const u = ["B", "K", "M", "G", "T"]; let i = 0, x = n; while (Math.abs(x) >= 1024 && i < 4) { x /= 1024; i++; }
        return (i ? grp(x, x < 10 ? 1 : x < 100 ? 1 : 0) : String(Math.round(x))) + " " + u[i];
      }
      default: return Number.isInteger(n) ? grp(n, 0) : grp(n, 3);
    }
  };
  const NUMFMT = new Set(["int", "float1", "float3", "pct", "dur", "bytes"]);

  /* ---------- url state ---------- */
  function hashSplit() { const raw = location.hash.replace(/^#\/?/, ""); const i = raw.indexOf("?"); return i < 0 ? [raw, ""] : [raw.slice(0, i), raw.slice(i + 1)]; }
  U.qs = function () {
    const o = {}; hashSplit()[1].split("&").filter(Boolean).forEach(kv => {
      const j = kv.indexOf("="); const k = decodeURIComponent(j < 0 ? kv : kv.slice(0, j));
      try { o[k] = j < 0 ? "" : decodeURIComponent(kv.slice(j + 1)); } catch (e) { o[k] = kv.slice(j + 1); }
    }); return o;
  };
  U.setQs = function (patch) {
    const cur = U.qs(); for (const k in patch) { const v = patch[k]; if (v == null || v === "" || v === false) delete cur[k]; else cur[k] = Array.isArray(v) ? v.join(",") : String(v); }
    const q = Object.keys(cur).map(k => encodeURIComponent(k) + "=" + encodeURIComponent(cur[k]).replace(/%2C/g, ",").replace(/%3A/g, ":")).join("&");
    const path = hashSplit()[0] || "home";
    history.replaceState(null, "", location.pathname + location.search + "#/" + path + (q ? "?" + q : ""));
    if (window.CHAT && CHAT.touchContext) CHAT.touchContext();
  };

  /* ---------- small atoms ---------- */
  const STATE = {
    ok: ["✓", "ok"], done: ["✓", "ok"], pass: ["✓", "ok"], current: ["✓", "ok"], warm: ["●", "ok"], up: ["●", "ok"],
    running: ["▶", "run"], run: ["▶", "run"], busy: ["▶", "run"],
    waiting: ["◷", "warn"], wait: ["◷", "warn"], queued: ["◷", "warn"], cold: ["○", "warn"], pending: ["◷", "warn"],
    flag: ["!", "warn"], warn: ["!", "warn"], blocked: ["✕", "bad"],
    failed: ["✕", "bad"], fail: ["✕", "bad"], reject: ["✕", "bad"], bad: ["✕", "bad"], down: ["✕", "bad"], error: ["✕", "bad"],
    cancelled: ["·", "idle"], idle: ["·", "idle"], superseded: ["·", "idle"], test: ["·", "idle"],
  };
  const SHORT = { running: "run", waiting: "wait", queued: "wait", failed: "fail", cancelled: "cancel", superseded: "old", pending: "wait", blocked: "block" };
  U.glyph = s => (STATE[s] || ["·", "idle"])[0];
  U.stateClass = s => (STATE[s] || ["", "idle"])[1];
  U.tag = (t, cls) => h("span", { class: "u-tag " + (cls || ""), text: t });
  U.status = (s, label) => { const m = STATE[s]; return h("span", { class: "u-tag " + (m ? m[1] : "idle") }, (m ? m[0] : "·") + " " + (label != null ? label : SHORT[s] || String(s == null ? DASH : s))); };
  U.sec = (title, n) => h("div", { class: "u-sec" }, [title, n != null ? h("span", { class: "n", text: String(n) }) : null]);
  U.copy = (t) => { try { return navigator.clipboard.writeText(t); } catch (e) { return Promise.resolve(); } };
  const SERIES = () => ["--s1", "--s2", "--s3", "--s4", "--s5", "--s6", "--s7", "--s8"].map(cssv);
  const _col = (() => { try { return JSON.parse(localStorage.getItem("v5colors") || "{}"); } catch (e) { return {}; } })();
  U.color = function (id) {   // one colour per run/category id, assigned once, same on every page
    id = String(id); if (!(id in _col)) { _col[id] = Object.keys(_col).length % 8; try { localStorage.setItem("v5colors", JSON.stringify(_col)); } catch (e) {} }
    return SERIES()[_col[id]];
  };

  /* ---------- Spark ---------- */
  U.Spark = function (values, o) {
    o = o || {}; const w = o.w || 64, hh = o.h || 16, ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg"); svg.setAttribute("width", w); svg.setAttribute("height", hh); svg.setAttribute("viewBox", `0 0 ${w} ${hh}`); svg.setAttribute("class", "u-spark");
    const vs = (values || []).map(v => Array.isArray(v) ? v[1] : v).filter(v => v != null && isFinite(v));
    if (vs.length < 2) return svg;
    const lo = Math.min(...vs), hi = Math.max(...vs), pad = 2, col = o.color || cssv("--accent");
    const pts = vs.map((v, i) => [pad + i / (vs.length - 1) * (w - 2 * pad), pad + (1 - (v - lo) / (hi - lo || 1)) * (hh - 2 * pad)]);
    const p = document.createElementNS(ns, "polyline"); p.setAttribute("points", pts.map(q => q[0].toFixed(1) + "," + q[1].toFixed(1)).join(" ")); p.setAttribute("fill", "none"); p.setAttribute("stroke", col); p.setAttribute("stroke-width", "1");
    const c = document.createElementNS(ns, "circle"); const l = pts[pts.length - 1]; c.setAttribute("cx", l[0]); c.setAttribute("cy", l[1]); c.setAttribute("r", "1.8"); c.setAttribute("fill", col);
    svg.appendChild(p); svg.appendChild(c); return svg;
  };

  /* ---------- StatLine ---------- */
  U.StatLine = function (items) {
    return h("div", { class: "u-stat" }, (items || []).filter(Boolean).map(it => {
      const val = h("span", { class: "v", text: typeof it.value === "number" ? U.fmt(it.value, Number.isInteger(it.value) ? "int" : "float3") : (it.value == null ? DASH : String(it.value)) });
      const kids = it.unit ? [val, h("span", { class: "lb", text: it.unit })] : [h("span", { class: "lb", text: it.label || "" }), val];
      if (it.delta != null) kids.push(h("span", { class: "dl", text: String(it.delta) }));
      if (it.spark) kids.push(U.Spark(it.spark, { w: 48, h: 12 }));
      return h("span", { class: "it", title: it.label || null }, kids);
    }));
  };

  /* ---------- page header ---------- */
  U.page = function (o) {
    o = o || {}; document.title = "FW · " + (o.title || "");
    const st = o.stat ? (Array.isArray(o.stat) ? U.StatLine(o.stat) : o.stat) : null;
    return h("div", { class: "u-page" }, [h("h1", { text: o.title || "" }), st, o.actions ? h("div", { class: "u-actions" }, o.actions) : null]);
  };

  /* ---------- router registry ---------- */
  const ROUTES = [];
  U.route = function (pattern, fn) { ROUTES.push({ segs: pattern.split("/").filter(Boolean), fn }); };
  U.matchRoute = function (path) {
    const parts = path.split("/").filter(Boolean).map(decodeURIComponent); let best = null;
    ROUTES.forEach(r => {
      if (r.segs.length !== parts.length) return;
      const params = {}; let score = 0;
      for (let i = 0; i < parts.length; i++) {
        if (r.segs[i][0] === ":") params[r.segs[i].slice(1)] = parts[i]; else if (r.segs[i] === parts[i]) score++; else return;
      }
      if (!best || score > best.score) best = { fn: r.fn, params, score };
    });
    return best;
  };
  U.routes = () => ROUTES.map(r => r.segs.join("/"));

  /* ---------- keys ---------- */
  const BINDS = []; let pend = null, pendT = 0;
  const editable = t => t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
  function keyName(e) { const k = e.key; return (e.metaKey || e.ctrlKey) ? "mod+" + k.toLowerCase() : k; }
  U.keys = {
    bind(map, scope) { const b = { map, scope: scope || null }; BINDS.push(b); return () => { const i = BINDS.indexOf(b); if (i >= 0) BINDS.splice(i, 1); }; },
    clear(scope) { for (let i = BINDS.length - 1; i >= 0; i--) if (BINDS[i].scope === scope) BINDS.splice(i, 1); },
  };
  function runKey(name) {
    for (let i = BINDS.length - 1; i >= 0; i--) {
      const b = BINDS[i]; if (b.scope instanceof Element && !b.scope.isConnected) continue;
      const fn = b.map[name]; if (fn) { if (fn(name) !== false) return true; }
    } return false;
  }
  const hasSeq = k => BINDS.some(b => Object.keys(b.map).some(n => n.indexOf(k + " ") === 0));
  document.addEventListener("keydown", e => {
    if (e.isComposing || e.altKey && !e.ctrlKey && !e.metaKey) return;
    const t = e.target, name = keyName(e), ed = editable(t);
    if (ed && !(name.indexOf("mod+") === 0 || name === "Escape")) return;
    if (["Shift", "Control", "Meta", "Alt"].includes(e.key)) return;
    if (pend) { const seq = pend + " " + name; clearTimeout(pendT); pend = null; if (runKey(seq)) e.preventDefault(); return; }
    if (!e.ctrlKey && !e.metaKey && hasSeq(name)) { pend = name; pendT = setTimeout(() => pend = null, 900); e.preventDefault(); return; }
    if (runKey(name)) e.preventDefault();
  });

  /* ---------- Table ---------- */
  let ACTIVE = null;
  U.Table = function (o) {
    const cols = o.columns || [], P = o.qsKey ? o.qsKey + "_" : "", LIM0 = o.limit || 500;
    let rows = (o.rows || []).slice(), lim = LIM0, cur = -1, view = [];
    const S = { sort: o.sortKey || null, f: {}, q: "" };
    const picked = new Set();
    if (o.qsKey) { const q = U.qs(); if (q[P + "sort"]) S.sort = q[P + "sort"]; if (q[P + "q"]) S.q = q[P + "q"]; cols.forEach(c => { if (q[P + "f." + c.key]) S.f[c.key] = parseF(q[P + "f." + c.key]); }); }
    function parseF(s) { const m = /^(-?[\d.eE+]+)\.\.(-?[\d.eE+]+)$/.exec(s); return m ? { lo: +m[1], hi: +m[2] } : { eq: s }; }
    function encF(f) { return f.eq != null ? String(f.eq) : (+f.lo.toPrecision(6)) + ".." + (+f.hi.toPrecision(6)); }
    function save() { if (!o.qsKey) return; const patch = { [P + "sort"]: S.sort, [P + "q"]: S.q }; cols.forEach(c => patch[P + "f." + c.key] = S.f[c.key] ? encF(S.f[c.key]) : null); U.setQs(patch); }
    const isNum = c => c.numeric != null ? c.numeric : NUMFMT.has(c.fmt) || (!c.fmt && rows.some(r => r[c.key] != null) && rows.every(r => r[c.key] == null || typeof r[c.key] === "number"));
    const val = (r, c) => r[c.key];
    const passes = (r, skip) => {
      for (const c of cols) { if (c.key === skip) continue; const f = S.f[c.key]; if (!f) continue; const v = val(r, c);
        if (f.eq != null) { if (String(v) !== f.eq) return false; } else if (v == null || v < f.lo || v > f.hi) return false; }
      if (S.q) { const q = S.q.toLowerCase(); if (!cols.some(c => { const v = val(r, c); return v != null && String(v).toLowerCase().includes(q); })) return false; }
      return true;
    };
    const linkOf = r => typeof o.rowLink === "function" ? o.rowLink(r) : typeof o.rowLink === "string" ? o.rowLink.replace(/\{(\w+)\}/g, (_, k) => encodeURIComponent(r[k] == null ? "" : r[k])) : null;
    const root = h("div", { class: "u-tbl", tabindex: -1 });
    const bar = h("div", { class: "tbar" }), tbl = h("table", { class: "u" }), thead = h("thead"), tbody = h("tbody"), more = h("div", { class: "u-more" });
    tbl.appendChild(thead); tbl.appendChild(tbody); root.appendChild(bar); root.appendChild(tbl); root.appendChild(more);
    const mk = (c) => ({ right: c.align ? c.align === "right" : isNum(c), mono: c.mono != null ? c.mono : (isNum(c) || ["id", "spark"].includes(c.fmt)) });

    function cell(c, r) {
      const v = val(r, c); let out;
      if (typeof c.fmt === "function") out = c.fmt(v, r);
      else if (c.fmt === "status") out = v == null ? null : U.status(v);
      else if (c.fmt === "spark") out = Array.isArray(v) && v.length ? U.Spark(v) : null;
      else if (c.fmt === "id") out = v == null ? null : (() => { const s = String(v); const t = s.length > 16 ? s.slice(0, 9) + "…" + s.slice(-5) : s; return h("span", { title: s, onclick: e => { e.stopPropagation(); U.copy(s); }, style: { cursor: "copy" }, text: t }); })();
      else if (c.fmt) out = U.fmt(v, c.fmt);
      else out = v == null || v === "" ? null : typeof v === "number" ? U.fmt(v) : String(v);
      if (out == null || out === "") return h("span", { class: "emp", text: DASH });
      return out;
    }
    function histOf(c) {
      const sub = rows.filter(r => passes(r, c.key)); const f = S.f[c.key];
      if (isNum(c)) {
        const vs = sub.map(r => val(r, c)).filter(v => typeof v === "number" && isFinite(v)); if (vs.length < 2) return null;
        const lo = Math.min(...vs), hi = Math.max(...vs); if (lo === hi) return null;
        const N = 20, bins = new Array(N).fill(0), step = (hi - lo) / N; vs.forEach(v => bins[Math.min(N - 1, Math.floor((v - lo) / step))]++);
        const mx = Math.max(...bins);
        return h("div", { class: "u-hist" }, bins.map((n, i) => {
          const a = lo + i * step, b = a + step, on = f && f.lo != null && a >= f.lo - 1e-9 && b <= f.hi + 1e-9;
          return h("i", { class: on ? "on" : "", style: { height: Math.max(1, n / mx * 18) + "px" }, title: `${U.fmt(a, c.fmt)} – ${U.fmt(b, c.fmt)} · ${n}`,
            onclick: e => { e.stopPropagation(); if (on) delete S.f[c.key]; else if (e.shiftKey && f && f.lo != null) S.f[c.key] = { lo: Math.min(f.lo, a), hi: Math.max(f.hi, b) }; else S.f[c.key] = { lo: a, hi: i === N - 1 ? hi : b }; save(); draw(); } });
        }));
      }
      const cnt = {}; sub.forEach(r => { const v = val(r, c); if (v != null && v !== "") cnt[v] = (cnt[v] || 0) + 1; });
      const ks = Object.keys(cnt).sort(); if (ks.length < 2 || ks.length > 12) return null; const mx = Math.max(...ks.map(k => cnt[k]));
      return h("div", { class: "u-hist cat" }, ks.map(k => h("i", { class: f && f.eq === k ? "on" : "", style: { height: Math.max(1, cnt[k] / mx * 18) + "px" }, title: `${k} · ${cnt[k]}`,
        onclick: e => { e.stopPropagation(); if (f && f.eq === k) delete S.f[c.key]; else S.f[c.key] = { eq: k }; save(); draw(); } })));
    }
    function head() {
      thead.innerHTML = "";
      const tr = h("tr"); if (o.select) tr.appendChild(h("th", { class: "ck" }));
      cols.forEach(c => {
        const m = mk(c), sk = S.sort && S.sort.replace(/^-/, "") === c.key, desc = sk && S.sort[0] === "-";
        const hist = c.hist ? histOf(c) : null;
        tr.appendChild(h("th", { class: m.right ? "r" : "", style: c.width ? { width: typeof c.width === "number" ? c.width + "px" : c.width } : null,
          onclick: () => { const f1 = (m.right ? "-" : "") + c.key, f2 = (m.right ? "" : "-") + c.key; S.sort = !sk ? f1 : S.sort === f1 ? f2 : null; save(); draw(); } },
          [hist, h("span", { text: c.label == null ? c.key : c.label }), sk ? h("span", { class: "ar", text: desc ? "▼" : "▲" }) : null]));
      });
      thead.appendChild(tr);
    }
    function sorted(list) {
      if (!S.sort) return list; const k = S.sort.replace(/^-/, ""), d = S.sort[0] === "-" ? -1 : 1, c = cols.find(x => x.key === k) || { key: k };
      return list.slice().sort((a, b) => { const x = val(a, c), y = val(b, c); if (x == null) return y == null ? 0 : 1; if (y == null) return -1; return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true })) * d; });
    }
    function body() {
      tbody.innerHTML = ""; view = sorted(rows.filter(r => passes(r)));
      view.slice(0, lim).forEach((r, i) => {
        const href = linkOf(r), tr = h("tr", { class: (href || o.onRow ? "lnk " : "") + (picked.has(r) ? "sel" : ""), onclick: e => { if (e.target.closest("a,button,input")) return; setCur(i, false); activate(i); } });
        if (o.select) tr.appendChild(h("td", { class: "ck" }, h("input", { type: "checkbox", checked: picked.has(r), onclick: e => { e.stopPropagation(); toggle(r); } })));
        cols.forEach(c => { const m = mk(c); const v = cell(c, r); tr.appendChild(h("td", { class: (m.right ? "r " : "") + (m.mono ? "mono" : ""), title: typeof v === "string" ? v : null }, v)); });
        tbody.appendChild(tr);
      });
      more.innerHTML = "";
      if (view.length > lim) more.appendChild(h("button", { class: "u-btn sm", text: `+${Math.min(view.length - lim, LIM0)} more`, onclick: () => { lim += LIM0; body(); } }));
      if (cur >= view.length) cur = view.length - 1; paintCur();
    }
    function barDraw() {
      bar.innerHTML = "";
      if (o.title) bar.appendChild(U.sec(o.title));
      const act = cols.filter(c => S.f[c.key]);
      act.forEach(c => { const f = S.f[c.key]; bar.appendChild(h("span", { class: "u-chip", title: "clear", onclick: () => { delete S.f[c.key]; save(); draw(); } }, [`${c.label || c.key} ${f.eq != null ? "=" : "∈"} ${f.eq != null ? f.eq : U.fmt(f.lo, c.fmt) + ".." + U.fmt(f.hi, c.fmt)}`, h("span", { class: "x", text: "×" })])); });
      if (o.search !== false && (rows.length > 12 || S.q)) bar.appendChild(h("input", { class: "u-in", placeholder: "filter", value: S.q, oninput: e => { S.q = e.target.value; save(); clearTimeout(root._t); root._t = setTimeout(() => { head(); body(); barCount(); }, 120); } }));
      bar.appendChild(h("span", { class: "cnt" }));
      barCount();
    }
    function barCount() { const c = $(".cnt", bar); if (c) c.textContent = `${U.fmt(view.length, "int")} of ${U.fmt(o.total != null ? o.total : rows.length, "int")}`; }
    function draw() { head(); body(); barDraw(); }
    function paintCur() { Array.from(tbody.children).forEach((tr, i) => tr.classList.toggle("cur", i === cur)); }
    function setCur(i, scroll) { cur = Math.max(-1, Math.min(i, Math.min(view.length, lim) - 1)); paintCur(); if (scroll !== false && cur >= 0) { const tr = tbody.children[cur]; if (tr) tr.scrollIntoView({ block: "nearest" }); } if (window.CHAT && CHAT.touchContext) CHAT.touchContext(); }
    function activate(i) { const r = view[i]; if (!r) return; if (o.onRow) return o.onRow(r); const href = linkOf(r); if (href) location.hash = href.replace(/^#?\/?/, "#/"); }
    function toggle(r) { picked.has(r) ? picked.delete(r) : picked.add(r); body(); if (o.onSelect) o.onSelect(Array.from(picked)); }
    const api = {
      el: root, get rows() { return rows; }, get view() { return view; }, get cursor() { return view[cur] || null; }, selected: () => Array.from(picked),
      setRows(rs) { rows = (rs || []).slice(); picked.clear(); lim = LIM0; draw(); },
      move(d) { setCur(cur < 0 ? (d > 0 ? 0 : view.length - 1) : cur + d); }, open() { if (cur >= 0) activate(cur); }, toggle() { if (o.select && view[cur]) toggle(view[cur]); },
    };
    root.table = api; root.addEventListener("mouseenter", () => ACTIVE = api); root.addEventListener("focusin", () => ACTIVE = api);
    if (o.keyboard !== false) ACTIVE = api;
    draw();
    return root;
  };
  U.activeTable = () => (ACTIVE && ACTIVE.el.isConnected ? ACTIVE : null);
  const tblKey = fn => () => { if (!ACTIVE || !ACTIVE.el.isConnected) return false; fn(ACTIVE); };
  U.keys.bind({
    j: tblKey(t => t.move(1)), k: tblKey(t => t.move(-1)), ArrowDown: tblKey(t => t.move(1)), ArrowUp: tblKey(t => t.move(-1)),
    Enter: tblKey(t => t.open()), x: tblKey(t => t.toggle()),
    a: tblKey(t => { const r = t.cursor; if (r && window.CHAT && CHAT.ref) { const k = Object.keys(r)[0]; CHAT.ref({ label: String(r[k]), row: r }); } }),
  });

  /* ---------- Chart ---------- */
  const fmtTick = v => { const a = Math.abs(v); return a >= 1e6 ? +(v / 1e6).toFixed(1) + "M" : a >= 1000 ? +(v / 1000).toFixed(1) + "k" : +v.toFixed(3) + ""; };
  function ema(pts, a) { let m = null; return pts.map(([x, y]) => { m = m == null ? y : a * m + (1 - a) * y; return [x, m]; }); }
  function chartOption(spec, o) {
    if (spec.type === "echarts") return Object.assign({ animation: false, backgroundColor: "transparent", textStyle: { fontFamily: MONO, color: cssv("--text-2") } }, spec.option || {});
    const text2 = cssv("--text-2"), line = cssv("--line"), surf = cssv("--surface"), ls = cssv("--line-strong"), tx = cssv("--text");
    const axis = (extra) => Object.assign({ axisLine: { lineStyle: { color: ls } }, axisTick: { show: false }, axisLabel: { color: text2, fontSize: 11, fontFamily: MONO, formatter: fmtTick },
      splitLine: { lineStyle: { color: line, type: "dashed" } }, nameTextStyle: { color: text2, fontSize: 11, fontFamily: MONO } }, extra);
    const base = { animation: false, backgroundColor: "transparent", textStyle: { fontFamily: MONO, color: text2 },
      grid: { left: 8, right: 12, top: 16, bottom: 4, containLabel: true },
      tooltip: { trigger: "axis", confine: true, backgroundColor: surf, borderColor: ls, borderWidth: 1, padding: [4, 8], textStyle: { color: tx, fontFamily: MONO, fontSize: 11 },
        axisPointer: { type: "line", lineStyle: { color: ls, type: "solid" } },
        formatter: ps => { ps = (Array.isArray(ps) ? ps : [ps]).filter(p => !p.seriesName.startsWith("​")).sort((a, b) => (b.value[1] != null ? b.value[1] : b.value) - (a.value[1] != null ? a.value[1] : a.value));
          const x = ps[0] && (Array.isArray(ps[0].value) ? ps[0].value[0] : ps[0].axisValueLabel); return `<div style="text-align:right;color:${text2}">${esc(String(x))}</div>` + ps.map(p => `<div style="display:flex;gap:12px;justify-content:space-between"><span style="color:${p.color}">${esc(p.seriesName)}</span><span>${(Array.isArray(p.value) ? p.value[1] : p.value) == null ? DASH : fmtTick(Array.isArray(p.value) ? p.value[1] : p.value)}</span></div>`).join(""); } } };
    if (spec.type === "bar") {
      const hz = !!spec.horizontal, cat = axis({ type: "category", data: spec.categories || [], splitLine: { show: false }, axisLabel: { color: text2, fontSize: 11, fontFamily: MONO, hideOverlap: false, width: 120, overflow: "truncate" } });
      const valx = axis({ type: "value" }); const one = (spec.series || []).length === 1;
      return Object.assign(base, { xAxis: hz ? valx : cat, yAxis: hz ? Object.assign(cat, { inverse: true }) : valx, tooltip: Object.assign(base.tooltip, { trigger: "axis", axisPointer: { type: "shadow" } }),
        series: (spec.series || []).map((s, i) => ({ name: s.name, type: "bar", data: s.values, barMaxWidth: 14, itemStyle: { color: one ? SERIES()[0] : U.color(s.name), borderRadius: 2 } })) });
    }
    const sm = spec.smooth != null && spec.smooth > 0 ? 1 - spec.smooth * 0.5 : null; // alpha for EMA
    const series = [];
    (spec.series || []).forEach(s => {
      const c = U.color(s.name), pts = s.points || [];
      if (sm != null) { series.push({ name: "​" + s.name, type: "line", data: pts, showSymbol: false, silent: true, lineStyle: { width: 1, color: c, opacity: .25 }, z: 1 }); series.push({ name: s.name, type: "line", data: ema(pts, spec.smooth), showSymbol: false, lineStyle: { width: 1.5, color: c }, itemStyle: { color: c }, z: 2 }); }
      else series.push({ name: s.name, type: "line", data: pts, showSymbol: false, lineStyle: { width: 1.5, color: c }, itemStyle: { color: c } });
    });
    return Object.assign(base, { xAxis: axis({ type: "value", scale: true, name: spec.x_label || "", nameLocation: "end", nameGap: 4 }), yAxis: axis({ type: spec.log_y ? "log" : "value", scale: true, name: spec.y_label || "", nameLocation: "end" }), series });
  }
  U.Chart = function (spec, o) {
    o = o || {}; const el = h("div", { class: "u-chart", style: { height: (o.height || 220) + "px" } }); let ch = null, cur = spec;
    const build = () => { if (ch || !el.clientWidth) return; ch = echarts.init(el, null, { renderer: "canvas" }); ch.setOption(chartOption(cur, o), true); if (o.group !== null) { ch.group = o.group || "fw"; echarts.connect(ch.group); } };
    const ro = new ResizeObserver(() => { if (!el.isConnected) { ro.disconnect(); if (ch) { try { ch.dispose(); } catch (e) {} ch = null; } return; } if (!ch) build(); else ch.resize(); });
    ro.observe(el);
    el.update = s => { cur = s; if (ch) ch.setOption(chartOption(cur, o), true); };
    el.instance = () => ch; return el;
  };

  /* ---------- Log ---------- */
  U.Log = function (o) {
    o = o || {}; let jid = o.jobId || null, off = 0, lines = [""], timer = null, state = null, follow = o.follow !== false, wrap = false, g = "";
    const gin = h("input", { class: "u-in", placeholder: "grep", oninput: e => { g = e.target.value.toLowerCase(); paint(); } });
    const fol = h("input", { type: "checkbox", checked: follow, onchange: e => { follow = e.target.checked; if (follow) pin(); } });
    const wr = h("input", { type: "checkbox", onchange: e => { wrap = e.target.checked; root.classList.toggle("wrap", wrap); } });
    const st = h("span", { class: "st" }), ls = h("div", { class: "ls" });
    const root = h("div", { class: "u-log" }, [h("div", { class: "tb" }, [gin, h("label", null, [fol, "follow"]), h("label", null, [wr, "wrap"]), h("span", { class: "sp" }), st,
      h("button", { class: "u-btn sm", text: "copy", onclick: () => U.copy(lines.join("\n")) })]), ls]);
    function feed(t) { let c = lines.pop(); for (const ch of t) { if (ch === "\n") { lines.push(c); c = ""; } else if (ch === "\r") c = ""; else c += ch; } lines.push(c); if (lines.length > 4000) lines = lines.slice(-3000); }
    function pin() { ls.scrollTop = ls.scrollHeight; }
    function paint() {
      const n0 = lines.length, frag = document.createDocumentFragment(); let shown = 0;
      for (let i = Math.max(0, n0 - 1200); i < n0; i++) { const L = lines[i]; if (g && !L.toLowerCase().includes(g)) continue; shown++;
        frag.appendChild(h("div", { class: "ln" + (/ERROR|Traceback|Exception/.test(L) ? " err" : /WARN/.test(L) ? " wrn" : "") }, [h("span", { class: "no", text: String(i + 1) }), h("span", { text: L })])); }
      ls.innerHTML = ""; ls.appendChild(frag); st.textContent = jid ? (state || "") : ""; if (follow) pin();
    }
    async function tick() {
      if (!jid) return; if (!root.isConnected && timer) { clearInterval(timer); timer = null; return; }
      try { const r = await fetch(`/api/jobs/${jid}/log?offset=${off}`); const d = await r.json(); if (d.text) { feed(d.text); off = d.offset; } state = d.state; paint();
        if (d.state !== "running" && d.state !== "queued") { clearInterval(timer); timer = null; } } catch (e) { st.textContent = "log error"; }
    }
    root.setJob = id => { jid = id; off = 0; lines = [""]; state = null; clearInterval(timer); timer = null; paint(); if (id) { tick(); timer = setInterval(tick, 1000); } };
    root.setText = t => { lines = [""]; feed(t || ""); paint(); };
    if (o.text != null) root.setText(o.text); else paint();
    if (jid) { tick(); timer = setInterval(tick, 1000); }
    return root;
  };

  /* ---------- Repro ---------- */
  U.Repro = function (o) {
    o = o || {}; let pop = null;
    const wrap = h("span", { class: "u-repro" });
    const close = () => { if (pop) { pop.remove(); pop = null; document.removeEventListener("mousedown", away, true); } };
    const away = e => { if (pop && !wrap.contains(e.target)) close(); };
    const argv = Array.isArray(o.argv) ? o.argv.join(" ") : (o.argv || "");
    const row = (k, v, cp) => v == null || v === "" ? null : h("div", null, [h("span", { class: "k", text: k }), h("div", { class: "row" }, [h("span", { text: String(v) }), cp ? h("button", { class: "u-btn sm", text: "copy", onclick: () => U.copy(String(v)) }) : null])]);
    wrap.appendChild(h("button", { class: "u-btn sm", text: "repro ⧉", onclick: () => { if (pop) return close(); pop = h("div", { class: "u-pop", style: { top: "26px", left: 0 } }, [row("argv", argv, true), row("config", o.config, true), row("sha", o.sha), row("host", o.host), row("dur", o.dur)]); wrap.appendChild(pop); document.addEventListener("mousedown", away, true); } }));
    return wrap;
  };

  /* ---------- render(spec) ---------- */
  const tmpl = (t, r) => t.replace(/\{(\w+)\}/g, (_, k) => encodeURIComponent(r[k] == null ? "" : r[k]));
  U.render = function (s, ro) {
    ro = ro || {}; if (!s) return h("div");
    switch (s.type) {
      case "table": {
        const wrap = h("div", null, [s.title || s.link ? h("div", { class: "u-sec" }, [s.title || "", s.link ? h("a", { href: s.link, text: "open →" }) : null]) : null]);
        wrap.appendChild(U.Table({ columns: (s.columns || []).map(c => ({ key: c.key, label: c.label, fmt: c.fmt, align: c.align, hist: c.hist })), rows: s.rows || [], total: s.total, rowLink: s.row_link ? (r => tmpl(s.row_link, r)) : null, search: false, keyboard: ro.keyboard, limit: ro.limit || 200 }));
        return wrap;
      }
      case "stat": return U.StatLine(s.items);
      case "line": case "bar": return h("div", null, [s.title ? U.sec(s.title) : null, U.Chart(s, { height: ro.height || 180, group: ro.group === undefined ? null : ro.group })]);
      case "log": return h("div", null, [s.job_id ? h("div", { class: "u-sec" }, [h("a", { href: "#/jobs?job=" + s.job_id, text: s.job_id })]) : null, U.Log({ text: s.text, jobId: null, follow: false }), s.truncated ? h("div", { class: "u-more", text: "truncated" }) : null]);
      case "thumbs": return h("div", { class: "u-thumbs" }, (s.items || []).map(it => h("a", { href: it.link || "#" }, [h("img", { src: it.src, loading: "lazy", alt: "" }), h("div", { text: it.label || "" })])));
      case "text": return h("div", { class: "u-text", text: s.text || "" });
      case "group": return h("div", { style: { display: "flex", flexDirection: "column", gap: "8px" } }, (s.items || []).map(x => U.render(x, ro)));
      case "confirm": return confirmCard(s);
      default: return h("div", { class: "errline", text: "unknown ui type: " + s.type });
    }
  };
  function confirmCard(s) {
    const out = h("span", { class: "dim" }), run = h("button", { class: "u-btn pri", text: "Run" }), card = h("div", { class: "u-confirm" });
    const argv = Array.isArray(s.argv_preview) ? s.argv_preview.join(" ") : (s.argv_preview || "");
    run.onclick = async () => {
      run.disabled = true; out.textContent = "";
      try { const r = await fetch("/api/jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: s.kind, params: s.params || {} }) }); const d = await r.json();
        if (!r.ok) throw new Error(d.error || ("HTTP " + r.status)); out.className = "c-ok"; out.innerHTML = ""; out.appendChild(h("span", { text: "✓ " })); out.appendChild(h("a", { href: "#/jobs?job=" + d.id, text: d.id }));
      } catch (e) { run.disabled = false; out.className = "c-bad"; out.textContent = "✕ " + e.message; }
    };
    [h("div", { class: "kind", text: s.kind }), argv ? h("div", { class: "argv", text: argv }) : null,
      h("div", { class: "kv" }, [h("span", { text: "host " + (s.host || DASH) }), s.est_seconds != null ? h("span", { text: "est " + U.fmt(s.est_seconds, "dur") }) : null, ...(s.inputs || []).slice(0, 3).map(i => h("span", { text: String(i) }))]),
      h("div", { class: "acts" }, [run, h("button", { class: "u-btn", text: "Dismiss", onclick: () => card.remove() }), out])].forEach(x => x && card.appendChild(x));
    return card;
  }

  /* ---------- v3 merge: Tile, Tiles, Thumbs, Flywheel, panel ---------- */
  const EDGE = { ok: "ok", done: "ok", pass: "ok", running: "run", run: "run", waiting: "warn", warn: "warn", flag: "warn", partial: "warn", blocked: "bad", bad: "bad", failed: "bad", reject: "bad", idle: "idle" };
  U.Tile = function (o) {
    o = o || {}; const v = typeof o.value === "number" ? U.fmt(o.value, Number.isInteger(o.value) ? "int" : "float3") : (o.value == null ? DASH : String(o.value));
    const kids = [h("div", { class: "lb", text: o.label || "" }), h("div", { class: "vl" }, [h("span", { class: "v", text: v }), o.unit ? h("span", { class: "un", text: o.unit }) : null, o.delta != null ? h("span", { class: "dl", text: String(o.delta) }) : null]),
      o.spark && o.spark.length > 1 ? U.Spark(o.spark, { w: 96, h: 22, color: o.color }) : h("div", { style: { height: "22px" } })];
    return h(o.href ? "a" : "div", { class: "u-tile e-" + (EDGE[o.state] || "idle"), href: o.href || null }, kids);
  };
  U.Tiles = items => h("div", { class: "u-tiles" }, (items || []).map(U.Tile));
  U.colors = () => ({ text: cssv("--text"), text2: cssv("--text-2"), line: cssv("--line"), line2: cssv("--line-strong"), surface: cssv("--surface"), ok: cssv("--ok"), warn: cssv("--warn"), bad: cssv("--bad"), run: cssv("--run"), accent: cssv("--accent"), series: SERIES() });
  U.Thumbs = function (o) {
    return h("div", { class: "u-thumbs2" }, ((o && o.items) || []).map(it => {
      const img = h("img", { src: it.src, loading: "lazy", alt: "" }), box = h("div", { class: "im" }, img);
      let st = null, dead = false;
      if (it.strip) { box.addEventListener("mouseenter", () => { if (dead) return; if (!st) { st = h("img", { class: "st", src: it.strip, alt: "" }); st.addEventListener("error", () => { dead = true; st.remove(); }); box.appendChild(st); } st.style.display = "block"; }); box.addEventListener("mouseleave", () => { if (st) st.style.display = "none"; }); }
      return h(it.href ? "a" : "div", { class: "th e-" + (EDGE[it.state] || "idle"), href: it.href || null }, [box, h("div", { class: "lb", text: it.label || "" })]);
    }));
  };
  U.Flywheel = function (stages, o) {
    o = o || {}; stages = stages || []; const W = 760, H = o.height || 330, cx = W / 2, cy = H / 2, rx = 296, ry = H / 2 - 38, n = stages.length || 1, nw = 136, nh = 48, ns = "http://www.w3.org/2000/svg";
    const el = (t, a, k) => { const e = document.createElementNS(ns, t); for (const x in a || {}) e.setAttribute(x, a[x]); (k || []).forEach(c => e.appendChild(c)); return e; };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "u-fw-svg" }), ang = i => -90 + i * 360 / n, P = d => { const a = d * Math.PI / 180; return [cx + rx * Math.cos(a), cy + ry * Math.sin(a)]; };
    svg.appendChild(el("defs", {}, [el("marker", { id: "fwa", viewBox: "0 0 10 10", refX: 8, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto" }, [el("path", { d: "M0 0L10 5L0 10z", class: "fwm" })])]));
    stages.forEach((s, i) => { const gap = 360 / n, d0 = ang(i) + 17, d1 = ang(i) + gap - 17, [x0, y0] = P(d0), [x1, y1] = P(d1); svg.appendChild(el("path", { class: "fwarc e-" + (EDGE[s.state] || "idle"), d: `M${x0.toFixed(1)} ${y0.toFixed(1)} A${rx} ${ry} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`, "marker-end": "url(#fwa)" })); });
    stages.forEach((s, i) => {
      const [x, y] = P(ang(i)), t1 = el("text", { x: 10, y: 19, class: "fl" }), t2 = el("text", { x: 10, y: 38, class: "fm" }), dot = el("circle", { cx: nw - 10, cy: 10, r: 3.5, class: "fd" });
      t1.textContent = s.label || s.id; t2.textContent = s.metric == null ? "" : String(s.metric);
      const g = el("g", { class: "fn e-" + (EDGE[s.state] || "idle"), transform: `translate(${(x - nw / 2).toFixed(1)},${(y - nh / 2).toFixed(1)})`, tabindex: 0 }, [el("rect", { width: nw, height: nh, rx: 4 }), t1, t2, dot]);
      const t = el("title", {}); t.textContent = (s.label || s.id) + (s.state ? " · " + s.state : ""); g.appendChild(t);
      const go = () => { if (o.onClick) o.onClick(s); else if (s.href) location.hash = s.href.replace(/^#?\/?/, "#/"); };
      g.addEventListener("click", go); g.addEventListener("keydown", e => { if (e.key === "Enter") go(); }); svg.appendChild(g);
    });
    return h("div", { class: "u-fw" }, svg);
  };

  /* right panel: tabs Chat / Cách làm / Log / Nguồn. Pages call UI.panel.set({method, log, sources}); the router resets it per route. */
  const PN = { method: null, log: null, sources: null, tab: "chat", inited: false }, TABS = [["chat", "Chat"], ["method", "Cách làm"], ["log", "Log"], ["src", "Nguồn"]];
  let logEl = null, logTimer = 0;
  const pane = n => document.getElementById(n === "chat" ? "chat" : "rp-" + n);
  U.panel = {
    init() {
      const rp = document.getElementById("rp"); if (!rp || PN.inited) return; PN.inited = true;
      const bar = h("div", { class: "rp-tabs" }, TABS.map(([k, l]) => h("a", { "data-k": k, text: l, onclick: () => U.panel.tab(k) })));
      rp.insertBefore(bar, rp.firstChild); ["method", "log", "src"].forEach(k => rp.appendChild(h("div", { id: "rp-" + k, class: "rp-pane hide" })));
      const q = U.qs().rp; U.panel.tab(["chat", "method", "log", "src"].includes(q) ? q : "chat", true);
    },
    tab(k, silent) {
      PN.tab = k; document.querySelectorAll("#rp .rp-tabs a").forEach(a => a.classList.toggle("on", a.dataset.k === k));
      TABS.forEach(([n]) => { const p = pane(n); if (p) p.classList.toggle("hide", n !== k); });
      if (!silent) U.setQs({ rp: k === "chat" ? null : k }); U.panel.render();
    },
    toggle() { document.body.classList.toggle("dock-off"); try { localStorage.setItem("v5dock", document.body.classList.contains("dock-off") ? "off" : "on"); } catch (e) {} },
    open(k) { document.body.classList.remove("dock-off"); if (k) U.panel.tab(k); },
    reset() { PN.method = PN.log = PN.sources = null; clearInterval(logTimer); logEl = null; U.panel.render(); },
    set(o) { Object.keys(o || {}).forEach(k => { if (k in PN && k !== "tab") PN[k] = o[k]; }); if (o && o.sources !== undefined) PN.sources = o.sources; U.panel.render(); },
    render() {
      if (!PN.inited) return;
      const cnt = { method: (PN.method || []).length, src: (PN.sources || []).length }; document.querySelectorAll("#rp .rp-tabs a").forEach(a => { const c = cnt[a.dataset.k]; const base = TABS.find(t => t[0] === a.dataset.k)[1]; a.textContent = c ? base + " " + c : base; });
      const m = pane("method"), s = pane("src"), l = pane("log");
      m.innerHTML = ""; (PN.method || []).forEach((st, i) => m.appendChild(h("div", { class: "rp-step" }, [h("span", { class: "no", text: String(i + 1) }), h("div", { class: "bd" }, [h("div", { text: st.step || "" }),
        st.cmd ? h("div", { class: "cmd" }, [h("code", { text: st.cmd }), h("button", { class: "u-btn sm", text: "copy", onclick: () => U.copy(st.cmd) })]) : null, st.cfg ? h("div", { class: "cfg", text: st.cfg }) : null, st.note ? h("div", { class: "nt", text: st.note }) : null])])));
      if (!(PN.method || []).length) m.appendChild(h("div", { class: "rp-empty", text: DASH }));
      s.innerHTML = ""; (PN.sources || []).forEach(x => s.appendChild(h("div", { class: "rp-src", title: x.path, onclick: () => U.copy(x.path) }, [h("span", { text: x.label || "" }), h("code", { text: x.path })])));
      if (!(PN.sources || []).length) s.appendChild(h("div", { class: "rp-empty", text: DASH }));
      clearInterval(logTimer); l.innerHTML = "";
      if (PN.log && PN.log.jobId) { logEl = U.Log({ jobId: PN.log.jobId }); l.appendChild(logEl); }
      else if (PN.log && PN.log.url) { logEl = U.Log({ text: "" }); l.appendChild(logEl); const pull = () => fetch(PN.log.url).then(r => r.text()).then(t => { if (logEl && logEl.isConnected) logEl.setText(t.slice(-60000)); }).catch(() => {}); pull(); logTimer = setInterval(pull, 3000); }
      else l.appendChild(h("div", { class: "rp-empty", text: DASH }));
    },
  };

  return U;
})();
window.UI = UI;

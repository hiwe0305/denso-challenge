/* v5 data pages: #/data (catalog), #/data/:id (dataset), #/data/:id/ep/:n (episode). Owner: DATA agent. */
/* @budget-skip-start */ "use strict"; /* @budget-skip-end */
const PAGES_DATA = (() => {
  /* ---------- small local helpers (no UI component copies) ---------- */
  const E = (tag, attrs, kids) => {
    const e = document.createElement(tag);
    for (const k in attrs || {}) {
      const v = attrs[k];
      if (v == null || v === false) continue;
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k === "style" && typeof v === "object") Object.assign(e.style, v);
      else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    (Array.isArray(kids) ? kids : kids == null ? [] : [kids]).flat(9).forEach(c => {
      if (c == null || c === false) return;
      e.appendChild(typeof c === "object" ? c : document.createTextNode(String(c)));
    });
    return e;
  };
  const SVGNS = "http://www.w3.org/2000/svg";
  const S = (tag, attrs, kids) => {
    const e = document.createElementNS(SVGNS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    (kids || []).forEach(c => e.appendChild(c));
    return e;
  };
  const cache = {};
  const jget = url => cache[url] || (cache[url] = fetch(url).then(r => { if (!r.ok) throw new Error(url + " " + r.status); return r.json(); }));
  const dsf = (id, f) => "data/ds/" + id + "/" + f;
  const epPath = (d, n) => "data/" + d + "/ep/" + n;
  const jtry = url => jget(url).catch(() => null);
  const fmtN = (v, f) => (typeof UI !== "undefined" && UI.fmt) ? UI.fmt(v, f) : (v == null ? "—" : String(v));
  const int = v => v == null ? "—" : fmtN(v, "int");
  const dec = (v, d) => v == null || Number.isNaN(v) ? "—" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  const sig3 = v => v == null ? "—" : (Math.abs(v) >= 100 ? Math.round(v).toString() : Number(v.toPrecision(3)).toString());
  const mid = (s, n) => s && s.length > n ? s.slice(0, Math.ceil((n - 1) / 2)) + "…" + s.slice(-Math.floor((n - 1) / 2)) : s;
  const demoOn = () => !!(typeof UI !== "undefined" && (typeof UI.demo === "function" ? UI.demo() : UI.demo));
  const ctx = (route, selection, filters) => { try { typeof CHAT !== "undefined" && CHAT.setContext && CHAT.setContext({ route, selection, filters: filters || {} }); } catch (e) {} };
  const q = () => (typeof UI !== "undefined" && UI.qs ? UI.qs() : {});
  const setQs = p => UI.setQs(p);
  const goto = path => { location.hash = "#/" + path; };
  /* @budget-skip-start */
  const TR = { "dài": "long", "Lần chạy": "attempts", "Thành công": "success", "Đã ghi": "recorded", "QA pass": "qa pass", "Giữ trong cut": "kept" };
  const tr = x => TR[x] || x;
  /* @budget-skip-end */
  const line = (text, cls) => E("div", { class: "pd-line " + (cls || ""), text });

  const css = `
.pd-line{font:12.5px/16px var(--mono,ui-monospace,monospace);color:var(--text-2);padding:8px 12px}
.pd-line.bad{color:var(--bad)}
.pd-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:6px 12px}
.pd-bar .cnt{margin-left:auto;font:12px var(--mono,monospace);color:var(--text-2)}
.pd-chip,.pd-seg a,.pd-tabs a{font:12px/16px var(--mono,ui-monospace,monospace);border:1px solid var(--line);border-radius:4px;padding:3px 8px;color:var(--text-2);background:transparent;cursor:pointer;text-decoration:none}
.pd-chip.on{color:var(--text);border-color:var(--line-strong)}
.pd-seg{display:inline-flex}.pd-seg a{border-radius:0;margin-left:-1px}.pd-seg a:first-child{border-radius:4px 0 0 4px;margin-left:0}.pd-seg a:last-child{border-radius:0 4px 4px 0}
.pd-seg a.on,.pd-tabs a.on{color:var(--text);border-color:var(--accent)}
.pd-tabs{display:flex;gap:4px;padding:6px 12px;border-bottom:1px solid var(--line)}
.pd-sel{height:26px;font:12px var(--mono,monospace);background:var(--surface-2);color:var(--text);border:1px solid var(--line);border-radius:4px;padding:0 4px}
.pd-sum{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:4px 12px}
.pd-card .qb{display:flex;height:3px}.pd-card .qb i{display:block;height:3px}
.pd-card .hc{display:flex;gap:4px;flex-wrap:wrap}.pd-card .hc span{font:10px var(--mono,monospace);color:var(--text-3);border:1px solid var(--line);border-radius:2px;padding:0 3px}
.pd-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:8px;padding:8px 12px}
.pd-card{display:block;border:1px solid var(--line);border-left:2px solid var(--stripe);border-radius:4px;background:var(--surface);color:var(--text);text-decoration:none;overflow:hidden}
.pd-card:hover,.pd-card:focus{background:var(--surface-2);outline:none}
.pd-card .im{height:72px;background:var(--surface-2);display:grid;grid-template-columns:repeat(2,1fr);overflow:hidden}
.pd-card .im.one{grid-template-columns:1fr}.pd-card .im img{width:100%;height:72px;object-fit:cover}
.pd-card .im span{grid-column:1/-1;align-self:center;padding:0 8px;font:11px var(--mono,monospace);color:var(--text-3)}
.pd-card .b{padding:4px 8px;font:12px/16px var(--mono,monospace)}
.pd-card .b i{font-style:normal;color:var(--text-2)}
.pd-lin{overflow:auto;padding:8px 12px}
.pd-lin text{font:11px var(--mono,monospace);fill:var(--text)}
.pd-lin text.s{fill:var(--text-2)}.pd-lin text.h{fill:var(--text-3);text-transform:uppercase;font-size:10px}
.pd-lin .nd rect.bg{fill:var(--surface);stroke:var(--line)}
.pd-lin .nd{cursor:pointer}.pd-lin .nd.focus rect.bg{stroke:var(--accent)}
.pd-lin .nd.dim{opacity:.25}
.pd-lin path.e{fill:none;stroke:var(--line-strong);stroke-width:1}
.pd-lin path.e.hl{stroke:var(--accent)}.pd-lin path.e.dim{opacity:.2}
.pd-copy{display:flex;gap:8px;align-items:flex-start;margin:4px 12px}
.pd-copy pre{flex:1;margin:0;padding:6px 8px;font:12px/16px var(--mono,monospace);background:var(--surface-2);border:1px solid var(--line);border-radius:4px;white-space:pre-wrap;word-break:break-all}
.pd-copy button,.pd-btn{height:26px;font:12px var(--mono,monospace);background:transparent;color:var(--text);border:1px solid var(--line);border-radius:4px;padding:0 8px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center}
.pd-charts{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:8px;padding:8px 12px}
.pd-charts>div{border:1px solid var(--line);border-radius:4px;background:var(--surface);padding:4px 8px}
.pd-ep{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:12px;padding:8px 12px;align-items:start}
.pd-ep video{width:100%;max-height:320px;background:#000;display:block;border-radius:4px}
.pd-ep iframe{width:100%;height:calc(100vh - 130px);min-height:480px;border:1px solid var(--line);border-radius:4px;background:#000}
.pd-links{display:flex;gap:4px;flex-wrap:wrap;padding:4px 0}
.pd-tl{padding:0 12px 24px}
.pd-row{position:relative;display:flex;align-items:center;min-height:20px}
.pd-row>.lb{position:absolute;left:2px;top:0;font:10px/14px var(--mono,monospace);color:var(--text-3);z-index:2}
.pd-row .seg{position:absolute;top:4px;height:12px;border-radius:2px;background:var(--code);opacity:.7}
.pd-row .seg.ok{background:var(--ok)}.pd-row .seg.warn{background:var(--warn)}.pd-row .seg.bad{background:var(--bad)}
.pd-ph{position:absolute;top:0;bottom:0;width:1px;background:var(--accent);pointer-events:none;z-index:3}
.pd-lane{position:relative;margin:2px 0;border-bottom:1px solid var(--line)}
.pd-lane .lb{position:absolute;left:4px;top:2px;font:10px/14px var(--mono,monospace);color:var(--text-3);z-index:2;pointer-events:none}
.pd-lane .lb.p{left:52px}
.pd-strip{position:relative;height:56px;cursor:pointer}
.pd-strip img{display:block;height:56px;position:absolute;top:0}
.qa-ok{color:var(--ok)}.qa-bad{color:var(--bad)}.qa-warn{color:var(--warn)}
`;
  const ensureCss = () => { if (!document.getElementById("pd-css")) { const s = document.createElement("style"); s.id = "pd-css"; s.textContent = css; document.head.appendChild(s); } };

  /* ---------- catalog ---------- */
  const GROUP = { egocentric: ["ego", "--t-ego"], teleop: ["tele", "--t-tele"], s1: ["synS1", "--t-s1"], s2: ["synS2", "--t-s2"], eval: ["eval", "--run"] };
  const GORDER = ["egocentric", "teleop", "s1", "s2", "eval"];
  const gcolor = g => cv((GROUP[g] || ["", "--text-2"])[1]);
  const sizeBytes = s => {
    const m = /(\d[\d.]*)\s*(B|KB|MB|GB|TB)\b/.exec(String(s || "").replace(/,(?=\d{3})/g, ""));
    if (!m) return null;
    return parseFloat(m[1]) * ({ B: 1, KB: 1024, MB: 1048576, GB: 1073741824, TB: 1099511627776 })[m[2]];
  };
  const sizeShort = s => { const m = /~?\d[\d.,]*\s*(?:KB|MB|GB|TB|B)\b/.exec(s || ""); return m ? m[0] : null; };
  const qaStr = c => c ? `${c.pass || 0}/${c.flag || 0}/${c.reject || 0}` : null;
  let CAT = null;
  async function loadCat() {
    if (CAT) return CAT;
    const c = await jget("data/catalog.json");
    const runs = {}; (c.runs || []).forEach(r => { runs[r.id] = r; });
    const byId = {}; c.rows.forEach(r => { byId[r.id] = r; });
    c.rows.forEach(r => {
      r._host = [...new Set(r.locations.map(l => l.where).filter(w => w && w !== "?"))];
      r._type = (GROUP[r.group] || [r.group])[0];
      r._qa = qaStr(r.qa_counts);
      r._bytes = sizeBytes(r.size);
      r._used = (r.children || []).filter(x => runs[x]).map(x => runs[x].name.replace(/^RUN\s+/i, ""));
    });
    CAT = { rows: c.rows, edges: c.edges, runs, byId };
    return CAT;
  }

  /* ---------- lineage SVG (layered, restyled) ---------- */
  const LAYERS = ["raw", "pipeline", "release", "cut", "run"];
  /* @budget-skip-start */
  const KIND_LAYER = { "raw source": 0, "pipeline source": 1, export: 2, release: 2, "subset-cut": 3, "eval conditions": 4, "bench copy": 4 };
  /* @budget-skip-end */
  const layerOf = n => {
    if (n.ext) return 3;
    if (n.branch !== undefined || (n.id || "").startsWith("run-")) return 4;
    return KIND_LAYER[n.kind] ?? 0;
  };
  function lineageSvg(nodes, edges, focus) {
    const W = 168, H = 32, GX = 40, GY = 8, TOP = 20;
    const ids = new Set(nodes.map(n => n.id));
    edges = edges.filter(([a, b]) => ids.has(a) && ids.has(b) && a !== b);
    if (!focus) { const con = new Set(edges.flat()); nodes = nodes.filter(n => con.has(n.id)); }
    if (!nodes.length) return line("—");
    const cols = LAYERS.map(() => []);
    nodes.forEach(n => cols[layerOf(n)].push(n));
    cols.forEach(c => c.sort((a, b) => (GORDER.indexOf(a.group) - GORDER.indexOf(b.group)) || a.id.localeCompare(b.id)));
    const pos = {}; let maxH = 0;
    cols.forEach((c, ci) => c.forEach((n, i) => { pos[n.id] = { x: 6 + ci * (W + GX), y: TOP + i * (H + GY) }; maxH = Math.max(maxH, TOP + (i + 1) * (H + GY)); }));
    const Wt = 12 + LAYERS.length * W + (LAYERS.length - 1) * GX;
    const svg = S("svg", { viewBox: `0 0 ${Wt} ${maxH + 4}`, width: Wt, height: maxH + 4 });
    LAYERS.forEach((l, i) => { if (cols[i].length) { const t = S("text", { x: 6 + i * (W + GX), y: 12, class: "h" }); t.textContent = l; svg.appendChild(t); } });
    const adjO = {}, adjI = {};
    edges.forEach(([a, b]) => { (adjO[a] = adjO[a] || []).push(b); (adjI[b] = adjI[b] || []).push(a); });
    const eEls = edges.map(([a, b]) => {
      const p = pos[a], r = pos[b], x1 = p.x + W, y1 = p.y + H / 2, x2 = r.x, y2 = r.y + H / 2, dx = Math.max(24, (x2 - x1) / 2);
      const e = S("path", { class: "e", d: ["M", x1, y1, "C", x1 + dx, y1, x2 - dx, y2, x2, y2].join(" ") }); svg.appendChild(e); return [a, b, e];
    });
    const walk = (s, adj) => { const o = new Set(), st = [s]; while (st.length) { const x = st.pop(); (adj[x] || []).forEach(y => { if (!o.has(y)) { o.add(y); st.push(y); } }); } return o; };
    const nEls = {};
    nodes.forEach(n => {
      const p = pos[n.id], row = CAT.byId[n.id];
      const g = S("g", { class: "nd" + (n.id === focus ? " focus" : ""), transform: `translate(${p.x},${p.y})` }, [S("title", {}, []), S("rect", { class: "bg", width: W, height: H, rx: 4 }), S("rect", { width: 3, height: H, fill: gcolor(n.group || "eval") })]);
      g.firstChild.textContent = n.id + (n.name && n.name !== n.id ? "\n" + n.name : "");
      const t1 = S("text", { x: 10, y: 13 }); t1.textContent = mid(row ? n.id : n.name.replace(/^RUN\s+/i, ""), 24);
      const t2 = S("text", { x: 10, y: 26, class: "s" }); t2.textContent = row ? [n.episodes != null ? int(n.episodes) + " ep" : null, n.status].filter(Boolean).join(" · ") : "run";
      g.appendChild(t1); g.appendChild(t2);
      if (row) g.addEventListener("click", () => goto("data/" + n.id));
      g.addEventListener("mouseenter", () => hl(n.id)); g.addEventListener("mouseleave", () => hl(null));
      svg.appendChild(g); nEls[n.id] = g;
    });
    function hl(id) {
      if (!id) { Object.values(nEls).forEach(e => e.classList.remove("dim")); eEls.forEach(([, , e]) => e.setAttribute("class", "e")); return; }
      const anc = walk(id, adjI), dsc = walk(id, adjO), keep = new Set([id, ...anc, ...dsc]);
      Object.entries(nEls).forEach(([k, e]) => e.classList.toggle("dim", !keep.has(k)));
      eEls.forEach(([a, b, e]) => e.setAttribute("class", "e " + ((keep.has(a) && keep.has(b) && (dsc.has(b) || b === id || anc.has(a) || a === id)) ? "hl" : "dim")));
    }
    return E("div", { class: "pd-lin" }, svg);
  }
  function neighbourhood(id) {
    const adjO = {}, adjI = {}; CAT.edges.forEach(([a, b]) => { (adjO[a] = adjO[a] || []).push(b); (adjI[b] = adjI[b] || []).push(a); });
    const walk = (s, adj) => { const o = new Set(), st = [s]; while (st.length) { const x = st.pop(); (adj[x] || []).forEach(y => { if (!o.has(y)) { o.add(y); st.push(y); } }); } return o; };
    const keep = new Set([id, ...walk(id, adjO), ...walk(id, adjI)]);
    return CAT.rows.concat(Object.values(CAT.runs)).filter(n => keep.has(n.id));
  }

  /* ---------- shared bits ---------- */
  let teardownFns = [];
  const teardown = () => { teardownFns.forEach(f => { try { f(); } catch (e) {} }); teardownFns = []; };
  const copyBox = cmd => E("div", { class: "pd-copy" }, [E("pre", { text: cmd }), E("button", { text: "copy", onclick: ev => { UI.copy(cmd); ev.target.textContent = "✓"; setTimeout(() => ev.target.textContent = "copy", 1000); } })]);
  const tabBar = (items, cur, hrefFor) => E("div", { class: "pd-tabs" }, items.map(t => E("a", { class: t === cur ? "on" : "", href: hrefFor(t), text: t })));
  const qaGlyph = v => v === "pass" ? "✓ pass" : v === "flag" ? "! flag" : v === "reject" ? "✕ reject" : v || "—";
  const stateGlyph = s => ({ ok: "✓ ok", done: "✓ done", failed: "✕ failed", error: "✕ error", running: "▶ run", queued: "◷ wait", cancelled: "✕ stop", stopped: "✕ stop" })[s] || s;
  const pageHead = o => UI.page(o);
  const hrefHash = (path, patch) => { const p = Object.assign({}, q(), patch); const s = Object.keys(p).filter(k => p[k] != null && p[k] !== "").map(k => k + "=" + encodeURIComponent(p[k])).join("&"); return "#/" + path + (s ? "?" + s : ""); };
  const statItems = list => list.filter(x => x && x.value != null && x.value !== "—");


  /* ---------- visual helpers ---------- */
  const cv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const SC = () => ({ current: cv("--ok"), superseded: cv("--text-3"), test: cv("--line-strong"), duplicate: cv("--warn"), missing: cv("--bad"), upstream: cv("--run"), archived: cv("--line-strong") });
  const QC = () => ({ pass: cv("--ok"), flag: cv("--warn"), reject: cv("--bad") });
  const eopt = (extra, horizontal) => {
    const t2 = cv("--text-2"), ln = cv("--line"), tx = cv("--text");
    const ax = o => Object.assign({ axisLine: { lineStyle: { color: ln } }, axisTick: { show: false }, axisLabel: { color: t2, fontSize: 11 }, splitLine: { lineStyle: { color: ln, type: "dashed" } } }, o);
    return Object.assign({ animation: false, backgroundColor: "transparent", textStyle: { color: t2 }, grid: { left: 8, right: 16, top: 8, bottom: 4, containLabel: true },
      tooltip: { trigger: "item", confine: true, backgroundColor: cv("--surface"), borderColor: cv("--line-strong"), textStyle: { color: tx, fontSize: 11 } }, _ax: ax }, extra);
  };
  const echart = (option, height) => UI.Chart({ type: "echarts", option }, { height: height || 160, group: null });
  const whenInst = (el, fn, n) => { const i = el.instance && el.instance(); if (i) fn(i); else if ((n || 0) < 40) setTimeout(() => whenInst(el, fn, (n || 0) + 1), 100); };
  const panelSet = o => { try { typeof UI !== "undefined" && UI.panel && UI.panel.set && UI.panel.set(o); } catch (e) {} };
  const tileRow = items => (typeof UI !== "undefined" && UI.Tiles) ? UI.Tiles(items) : null;

  function summaryRow(rows) {
    const wrap = E("div", { class: "pd-sum" });
    const types = GORDER.map(g => GROUP[g][0]).filter(t => rows.some(r => r._type === t));
    const stat = ["current", "superseded", "test", "duplicate", "missing", "upstream", "archived"].filter(x => rows.some(r => r.status === x));
    const sc = SC(), qc = QC();
    // episodes by type x status
    const o1 = eopt({ legend: { show: false }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" } } });
    const A = o1._ax; delete o1._ax;
    o1.xAxis = A({ type: "value" }); o1.yAxis = A({ type: "category", data: types, inverse: true });
    o1.series = stat.map(st => ({ name: st, type: "bar", stack: "a", barMaxWidth: 16, itemStyle: { color: sc[st] }, data: types.map(t => rows.filter(r => r._type === t && r.status === st).reduce((a, r) => a + (r.episodes || 0), 0) || null) }));
    // hours by type
    const o2 = eopt({}); const A2 = o2._ax; delete o2._ax;
    o2.xAxis = A2({ type: "value" }); o2.yAxis = A2({ type: "category", data: types, inverse: true });
    o2.series = [{ type: "bar", barMaxWidth: 16, data: types.map(t => ({ value: R2(rows.filter(r => r._type === t).reduce((a, r) => a + (r.hours || 0), 0)), itemStyle: { color: gcolor(GORDER.find(g => GROUP[g][0] === t)) } })) }];
    // qa per source
    const qr = rows.filter(r => r.qa_counts).sort((a, b) => (b.episodes || 0) - (a.episodes || 0)).slice(0, 8);
    const o3 = eopt({ tooltip: { trigger: "axis", axisPointer: { type: "shadow" } } }); const A3 = o3._ax; delete o3._ax;
    o3.xAxis = A3({ type: "value" }); o3.yAxis = A3({ type: "category", data: qr.map(r => mid(r.id, 16)), inverse: true });
    o3.series = ["pass", "flag", "reject"].map(k => ({ name: k, type: "bar", stack: "a", barMaxWidth: 14, itemStyle: { color: qc[k] }, data: qr.map(r => r.qa_counts[k] || null) }));
    [["episodes", o1], ["hours", o2], ["qa", o3]].forEach(([t, o]) => wrap.appendChild(E("div", null, [UI.sec(t), echart(o, 150)])));
    return wrap;
  }
  function catalogFlow(rows) {
    const set = new Set(rows.map(r => r.id)), byId = CAT.byId;
    const runs = Object.values(CAT.runs).filter(n => CAT.edges.some(([a, b]) => b === n.id && set.has(a)));
    const ids = new Set([...set, ...runs.map(n => n.id)]);
    const links = CAT.edges.filter(([a, b]) => ids.has(a) && ids.has(b) && a !== b).map(([a, b]) => ({ source: a, target: b, value: Math.max(1, (byId[b] && byId[b].episodes) || 1) }));
    if (!links.length) return line("—");
    const nodes = [...new Set(links.flatMap(l => [l.source, l.target]))];
    const sc = SC(), tx = cv("--text");
    const o = eopt({ tooltip: { trigger: "item" } }); delete o._ax;
    o.series = [{ type: "sankey", left: 8, right: 150, top: 8, bottom: 8, nodeGap: 12, nodeWidth: 10, layoutIterations: 64, emphasis: { focus: "adjacency" }, lineStyle: { color: "source", opacity: .3 },
      label: { color: tx, fontSize: 10, formatter: p => (p.value != null ? p.value + " " : "") + mid(p.name.replace(/^run-/, ""), 28) },
      data: nodes.map(n => ({ name: n, itemStyle: { color: byId[n] ? (byId[n].status === "superseded" ? sc.superseded : gcolor(byId[n].group)) : cv("--run") } })), links }];
    const el = echart(o, Math.max(320, nodes.length * 18));
    whenInst(el, i => i.on("click", p => { if (p.dataType === "node" && byId[p.name]) goto("data/" + p.name); }));
    return E("div", { class: "pd-lin" }, el);
  }

  /* ================= #/data : catalog ================= */
  async function pageCatalog(main) {
    teardown(); ensureCss();
    main.innerHTML = "";
    let cat;
    try { cat = await loadCat(); } catch (e) { main.appendChild(line(e.message, "bad")); return; }
    ctx("data", {}, q());
    const pool = demoOn() ? cat.rows.filter(r => r.data_class === "public") : cat.rows;
    const view = () => ["table", "grid", "lineage", "flow"].includes(q().view) ? q().view : "grid";
    const F = () => { const s = q(); return { type: s.type || "", status: s.status || "current", task: s.task || "", host: s.host || "", q: s.q || "" }; };
    const match = (r, f) => (!f.type || r._type === f.type) && (f.status === "all" || r.status === f.status) && (!f.task || r.task === f.task) && (!f.host || r._host.includes(f.host)) && (!f.q || (r.id + " " + r.name).toLowerCase().includes(f.q.toLowerCase()));
    const uniq = k => [...new Set(pool.map(r => k === "host" ? r._host : r[k === "type" ? "_type" : k]).flat())].filter(Boolean).sort();
    const statN = () => pool.length;
    main.appendChild(pageHead({ title: "data", stat: UI.StatLine(statItems([{ unit: "sets", value: int(statN()) }, { unit: "eps", value: int(pool.reduce((a, r) => a + (r.episodes || 0), 0)) }, { unit: "hours", value: dec(pool.reduce((a, r) => a + (r.hours || 0), 0), 1) }])) }));
    const bar = E("div", { class: "pd-bar" }), body = E("div");
    const sumBox = E("div");
    main.appendChild(sumBox); main.appendChild(bar); main.appendChild(body);
    const patch = p => { setQs(p); draw(); };
    function draw() {
      const f = F(), rows = pool.filter(r => match(r, f));
      bar.innerHTML = "";
      const sel = (k, opts) => E("select", { class: "pd-sel", "aria-label": k, onchange: ev => { if (ev.target.value) patch({ [k]: ev.target.value }); } }, [E("option", { value: "", text: k + " ▾" })].concat(opts.map(o => E("option", { value: o, text: o }))));
      bar.appendChild(sel("type", uniq("type"))); bar.appendChild(sel("status", ["all", ...uniq("status")])); bar.appendChild(sel("task", uniq("task"))); bar.appendChild(sel("host", uniq("host")));
      bar.appendChild(E("input", { class: "pd-sel", type: "search", placeholder: "id…", value: f.q, style: { width: "120px" }, oninput: ev => { clearTimeout(draw._t); draw._t = setTimeout(() => patch({ q: ev.target.value || null }), 200); } }));
      ["type", "status", "task", "host"].forEach(k => { if (f[k] && !(k === "status" && f[k] === "all")) bar.appendChild(E("a", { class: "pd-chip on", href: "javascript:void 0", text: `${k}=${f[k]} ✕`, onclick: () => patch({ [k]: k === "status" ? "all" : null }) })); });
      bar.appendChild(E("span", { class: "pd-seg" }, ["grid", "table", "lineage", "flow"].map(v => E("a", { class: v === view() ? "on" : "", href: "javascript:void 0", text: v, onclick: () => patch({ view: v === "grid" ? null : v }) }))));
      if (view() !== "table") bar.appendChild(E("span", { class: "cnt", text: `${rows.length} of ${pool.length}` }));
      const sf = Object.assign({}, f, { type: "" });
      const srows = pool.filter(r => match(r, sf));
      sumBox.innerHTML = "";
      const tiles = tileRow([{ label: "sets", value: srows.length }, { label: "eps", value: srows.reduce((a, r) => a + (r.episodes || 0), 0) }, { label: "hours", value: dec(srows.reduce((a, r) => a + (r.hours || 0), 0), 1) },
        { label: "missing", value: pool.filter(r => r.status === "missing").length, state: "bad" }]);
      if (tiles) sumBox.appendChild(tiles);
      sumBox.appendChild(summaryRow(srows));
      body.innerHTML = "";
      if (view() === "table") body.appendChild(catalogTable(rows, pool.length));
      else if (view() === "grid") body.appendChild(catalogGrid(rows));
      else if (view() === "flow") body.appendChild(catalogFlow(rows));
      else body.appendChild(catalogLineage(rows));
      panelSet({ sources: [{ label: "catalog", path: "data/catalog.json" }] });
      ctx("data", {}, f);
    }
    draw();
  }
  /* spec: [name, getter, opts]; the name is the column header and the row key */
  const tbl = (spec, items, o) => UI.Table(Object.assign({
    columns: spec.map(([k, , c]) => Object.assign({ key: k }, c || {})),
    rows: items.map(e => { const r = { _e: e }; spec.forEach(([k, g]) => { r[k] = g(e); }); return r; }),
  }, o));
  const R1 = v => v == null ? null : Math.round(v * 10) / 10, R2 = v => v == null ? null : Math.round(v * 100) / 100;
  function catalogTable(rows, total) {
    return tbl([["id", r => r.id, { mono: true, width: 190 }], ["type", r => r._type], ["task", r => r.task], ["status", r => r.status], ["eps", r => r.episodes, { fmt: "int", hist: true }],
      ["hours", r => R2(r.hours), { hist: true, numeric: true, fmt: v => v == null ? "—" : dec(v, 2) }], ["qa", r => r._qa, { mono: true, align: "right" }], ["size", r => r._bytes, { fmt: "bytes", hist: true }],
      ["host", r => r._host.join(",") || null], ["used", r => r._used.join(", ") || null, { width: 150 }]], rows, { total, onRow: r => goto("data/" + r.id), qsKey: "h", keyboard: true, search: false });
  }
  function catalogGrid(rows) {
    return E("div", { class: "pd-grid" }, rows.map(r => {
      const th = (r.thumbs || []).slice(0, r.thumbs && r.thumbs.length >= 4 ? 4 : 1);
      const im = th.length ? E("div", { class: "im" + (th.length < 4 ? " one" : "") }, th.map(u => E("img", { src: u.replace(/^\//, ""), loading: "lazy", alt: "" }))) : E("div", { class: "im one" }, E("span", { text: r.view === "missing" ? "missing" : r._host.join(",") || "—" }));
      const c = r.qa_counts, tot = c ? (c.pass || 0) + (c.flag || 0) + (c.reject || 0) : 0, qc = QC();
      const qb = tot ? E("div", { class: "qb" }, ["pass", "flag", "reject"].map(k => E("i", { style: { width: (c[k] || 0) / tot * 100 + "%", background: qc[k] } }))) : null;
      return E("a", { class: "pd-card", href: "#/data/" + r.id, style: { "--stripe": gcolor(r.group) } }, [im, qb, E("div", { class: "b" }, [E("div", { text: mid(r.id, 24) }), E("i", { text: [r.episodes != null ? int(r.episodes) + " ep" : null, r.hours != null ? dec(r.hours, 2) + " h" : null].filter(Boolean).join(" · ") || r.status }), E("div", { class: "hc" }, r._host.map(h => E("span", { text: h })))])]);
    }));
  }
  function catalogLineage(rows) {
    const set = new Set(rows.map(r => r.id));
    const nodes = rows.concat(Object.values(CAT.runs).filter(n => CAT.edges.some(([a, b]) => b === n.id && set.has(a))));
    return lineageSvg(nodes, CAT.edges, null);
  }

  /* ================= #/data/:id : dataset ================= */
  async function pageDataset(main, params, qs) {
    teardown(); ensureCss();
    main.innerHTML = "";
    const id = decodeURIComponent(params.id);
    let cat;
    try { cat = await loadCat(); } catch (e) { main.appendChild(line(e.message, "bad")); return; }
    const r = cat.byId[id];
    if (!r) { main.appendChild(pageHead({ title: id })); main.appendChild(line("unknown", "bad")); return; }
    const [eps, qual, meth, jobs] = await Promise.all([jtry(dsf(id, "episodes.json")), jtry(dsf(id, "quality.json")), jtry(dsf(id, "method.json")), jtry("/api/jobs")]);
    const job = findJobs(r, jobs)[0];
    const gal = galleryItems(r, eps);
    const tabs = ["gallery", "quality", "episodes", "lineage", "jobs"].filter(t => t === "gallery" ? gal.length > 0 : t === "episodes" ? !!eps : t === "quality" ? !!(qual && (qual.hists.length || qual.qa || qual.funnel || qual.levels)) : true);
    const tab = tabs.includes(qs.tab) ? qs.tab : tabs[0];
    const frames = meth && meth.info ? meth.info.total_frames : r.frames;
    const fps = meth && meth.info && meth.info.fps || r.fps;
    const hours = frames && fps ? frames / fps / 3600 : r.hours;
    const nEp = eps ? eps.length : r.episodes;
    const stat = UI.StatLine(statItems([
      { value: nEp == null ? null : int(nEp), unit: "ep" }, { value: frames == null ? null : int(frames), unit: "fr" }, { value: hours == null ? null : dec(hours, hours < 0.1 ? 3 : 2), unit: "h" }, { value: fps, unit: "fps" },
      { value: sizeShort(r.size), unit: "" }, r._qa ? { label: "qa", value: r._qa } : null,
    ]));
    const actions = [];
    const argv = job ? job.argv : (r.laptop_dir ? ["ls", "-l", r.laptop_dir] : null);
    if (argv) actions.push(UI.Repro({ argv, config: r.name, sha: undefined }));
    main.appendChild(pageHead({ title: id, stat, actions }));
    ctx("data/" + id, { dataset: id }, { tab });
    panelSet(datasetPanel(r, meth, job));
    if (!r.laptop_dir) main.appendChild(remoteBlock(r));
    main.appendChild(tabBar(tabs, tab, t => hrefHash("data/" + id, { tab: t })));
    const holder = E("div"); main.appendChild(holder);
    if (tab === "gallery") holder.appendChild(galleryView(id, gal, qs));
    else if (tab === "episodes") holder.appendChild(episodesTable(r, eps));
    else if (tab === "quality") holder.appendChild(qualityCharts(r, qual, eps));
    else if (tab === "lineage") holder.appendChild(lineageSvg(neighbourhood(id), CAT.edges, id));
    else holder.appendChild(jobsTable(r, jobs));
  }
  function remoteBlock(r) {
    const host = r._host.join(",");
    const d = E("div");
    if (r.view === "missing") {
      d.appendChild(line("missing", "bad"));
      r.locations.forEach(l => d.appendChild(line(l.raw)));
      return d;
    }
    d.appendChild(line((r._host.includes("rtx3060") ? "remote" : "absent") + " · " + (host || "?") + (r.size ? " · " + sizeShort(r.size) : "")));
    if (r.rsync) { d.appendChild(copyBox(r.rsync)); d.appendChild(copyBox(r.rsync_full.replace(/\s+#.*$/, ""))); }
    else r.locations.forEach(l => d.appendChild(line(l.raw)));
    return d;
  }
  function findJobs(r, jobs) {
    if (!Array.isArray(jobs)) return [];
    const keys = [r.id, r.laptop_dir].filter(Boolean);
    return jobs.filter(j => { const s = JSON.stringify([j.params, j.outputs, j.argv]); return keys.some(k => s.includes(k)); }).sort((a, b) => (b.created || "").localeCompare(a.created || ""));
  }
  function dur(j) { if (!j.started) return null; const e = j.ended ? Date.parse(j.ended) : Date.now(); return Math.max(0, (e - Date.parse(j.started)) / 1000); }
  function jobsTable(r, jobs) {
    if (!Array.isArray(jobs)) return line("offline", "bad");
    const js = findJobs(r, jobs);
    if (!js.length) return line("none");
    return tbl([["id", j => j.id, { mono: true }], ["kind", j => j.kind], ["state", j => stateGlyph(j.state)], ["host", j => j.host], ["dur", dur, { fmt: "dur" }], ["created", j => (j.created || "").replace("T", " ").slice(5, 16), { mono: true }]],
      js, { onRow: x => goto("jobs?job=" + x.id), qsKey: "j" });
  }


  /* ---- gallery (UI.Thumbs) ---- */
  const egoStrip = (work, ep) => "/api/ego_strip?work=" + encodeURIComponent(work) + "&ep=" + encodeURIComponent(ep);
  function galleryItems(r, eps) {
    if (!eps) return [];
    if (r.view === "robot") return eps.map(e => ({ key: e.i, src: dsf(r.id, "posters/" + e.i + ".jpg"), label: String(e.i), state: e.out ? "flag" : "pass", href: "#/" + epPath(r.id, e.i), strip: "/api/strip?ds=" + r.id + "&ep=" + e.i }));
    if (r.view === "ego" || r.view === "src") return eps.filter(e => e.poster).map(e => ({ key: e.id, src: e.poster, label: e.title || mid(e.id, 14), state: e.qa, href: "#/" + epPath(r.id, encodeURIComponent(e.id)), strip: egoStrip(r.work || r.id, e.id) }));
    return [];
  }
  function galleryView(id, items, qs) {
    const d = E("div"), bar = E("div", { class: "pd-bar" }), host = E("div");
    const states = ["pass", "flag", "reject"].filter(k => items.some(i => i.state === k));
    let cur = qs.g || "", lim = 120;
    const draw = () => {
      bar.innerHTML = ""; host.innerHTML = "";
      const rs = items.filter(i => !cur || i.state === cur);
      if (states.length > 1) states.forEach(k => bar.appendChild(E("a", { class: "pd-chip" + (cur === k ? " on" : ""), href: "javascript:void 0", text: k, onclick: () => { cur = cur === k ? "" : k; lim = 120; setQs({ g: cur || null }); draw(); } })));
      bar.appendChild(E("span", { class: "cnt", text: Math.min(lim, rs.length) + " of " + rs.length }));
      host.appendChild(UI.Thumbs ? UI.Thumbs({ items: rs.slice(0, lim) }) : line("—"));
      if (rs.length > lim) host.appendChild(E("div", { class: "pd-bar" }, E("a", { class: "pd-chip", href: "javascript:void 0", text: "+120", onclick: () => { lim += 120; draw(); } })));
    };
    draw(); d.appendChild(bar); d.appendChild(host); return d;
  }
  function datasetPanel(r, meth, job) {
    const m = [], root = (meth && meth.root) || r.laptop_dir;
    if (meth && meth.subset) {
      const sb = meth.subset;
      m.push({ step: "cut", cfg: sb.demo_set + " " + sb.n + " " + sb.order + (sb.fraction ? " " + sb.fraction * 100 + "%" : "") });
      sb.parts.forEach(p => m.push({ step: "part", cmd: p.release_id, note: p.n + " from " + p.first_episode_index }));
      if (meth.batch_summary) m.push({ step: "batch", note: meth.batch_summary.attempts + " → " + meth.batch_summary.successes + " ok" });
    } else if ((r.view === "src" || r.view === "ego") && root) {
      ["ingest", "deid", "pose", "annotate", "qa", "report"].forEach(st => m.push({ step: st, cmd: "fw egocentric " + st + " " + root }));
    } else if (r.notes) m.push({ step: "notes", note: r.notes });
    if (job) m.push({ step: job.kind, cmd: job.argv.join(" ") });
    const sources = [];
    if (root) sources.push({ label: "dir", path: root });
    r.locations.forEach(l => sources.push({ label: l.where, path: l.path || l.raw }));
    ["episodes", "quality", "method"].forEach(f => sources.push({ label: f, path: dsf(r.id, f + ".json") }));
    return { method: m, log: job ? { jobId: job.id } : null, sources };
  }

  /* ---- episodes table ---- */
  const AMP = ["lhand", "rhand", "larm", "rarm", "walk", "waist", "height"];
  function episodesTable(r, eps) {
    const view = r.view, pass = r.qa_counts && r.qa_counts.pass === eps.length;
    const H = { hist: true }, I = { fmt: "int", hist: true }, F1 = { fmt: "float1", hist: true }, F3 = { fmt: "float3", hist: true }, NI = { fmt: "int" };
    let spec, key = null;
    if (view === "robot") {
      key = e => e.i;
      spec = [["ep", e => e.i, { fmt: "int", mono: true }], ["secs", e => R1(e.s), F1], ["fr", e => e.n, I], ["dr", e => e.lv, I], ["seed", e => e.seed, NI], ["part", e => e.part], ["dist", e => R2(e.dist), F3], ["qa", e => pass ? "✓ pass" : null], ["flag", e => tr(e.out) || null]]
        .concat(AMP.map((l, i) => [l, e => R2(e.r[i]), F3]));
    } else if (view === "ego") {
      key = e => e.id;
      spec = [["clip", e => e.title, { width: 240 }], ["secs", e => R1(e.s), F1], ["qa", e => qaGlyph(e.qa)], ["hands", e => e.hands, F3], ["pose", e => e.pose], ["sub", e => e.nsub, I], ["reason", e => (e.reasons || []).join(", ") || null]];
    } else if (view === "src") {
      key = e => e.id;
      spec = [["clip", e => e.id, { mono: true, width: 190 }], ["qa", e => qaGlyph(e.qa)], ["reason", e => (e.detail && e.detail[0]) || null, { width: 200 }], ["fr", e => e.n, I], ["secs", e => R1(e.s), F1], ["out", e => e.out, F3], ["jitter", e => e.jit, F1], ["conf", e => e.lowc, F3], ["viewer", e => e.ego ? "✓" : null]];
    } else if (view === "psi") {
      spec = [["ep", e => e.i, NI], ["fr", e => e.n, I], ["secs", e => R1(e.s), F1], ["dr", e => e.lv, I], ["video", e => e.vid ? "✓" : null]];
    } else spec = [["ep", e => e.i, NI], ["dr", e => e.lv, I], ["seed", e => e.seed, NI]];
    return tbl(spec, eps, { qsKey: "e", keyboard: true, onRow: key ? x => goto(epPath(r.id, encodeURIComponent(key(x._e)))) : null });
  }

  /* ---- quality charts ---- */
  const HTITLE = { n: "length", s: "seconds", dist: "distance", hands: "hands", out: "outside", jit: "jitter", lowc: "conf", r0: "lhand", r1: "rhand", r2: "larm", r3: "rarm", r4: "walk", r5: "waist", r6: "height" };
  function qualityCharts(r, qual, eps) {
    const wrap = E("div", { class: "pd-charts" });
    const add = spec => wrap.appendChild(E("div", null, [UI.sec(spec.title), UI.Chart(spec, { height: spec.horizontal ? Math.max(120, spec.categories.length * 22 + 30) : 160 })]));
    const bars = (title, items, horizontal) => add({ type: "bar", title, horizontal, categories: items.map(i => tr(String(i[0]))), series: [{ name: title, values: items.map(i => i[1]) }] });
    if (qual.funnel) bars("funnel", qual.funnel, true);
    if (qual.failures) bars("failures", qual.failures, true);
    if (qual.levels) bars("coverage", qual.levels.map(([l, n]) => ["dr " + l, n]).concat((qual.parts || []).filter(p => p[0] !== "?").map(([k, n]) => [k, n])), true);
    if (qual.qa) bars("qa", Object.entries(qual.qa), false);
    if (qual.reasons && qual.reasons.length) bars("reasons", qual.reasons, true);
    if (qual.checks_fail && qual.checks_fail.length) bars("fails", qual.checks_fail, true);
    (qual.hists || []).forEach(hs => add({ type: "bar", title: HTITLE[hs.field] || hs.field, categories: hs.bins.map(b => sig3(b.lo)), series: [{ name: HTITLE[hs.field] || hs.field, values: hs.bins.map(b => b.c) }] }));
    if (!wrap.children.length) return line("none");
    return wrap;
  }

  /* ================= #/data/:id/ep/:n : episode ================= */
  async function pageEpisode(main, params, qs) {
    teardown(); ensureCss();
    main.innerHTML = "";
    const id = decodeURIComponent(params.id), ep = decodeURIComponent(params.n);
    let cat;
    try { cat = await loadCat(); } catch (e) { main.appendChild(line(e.message, "bad")); return; }
    const r = cat.byId[id];
    if (!r) { main.appendChild(pageHead({ title: id })); main.appendChild(line("unknown", "bad")); return; }
    try {
      if (r.view === "robot") await robotEpisode(main, r, +ep, qs);
      else if (r.view === "ego" || r.view === "src") await egoEpisode(main, r, ep);
      else main.appendChild(line("none"));
    } catch (e) { main.appendChild(line(e.message, "bad")); }
  }
  const navKeys = (prevHref, nextHref) => {
    const h0 = location.hash.split("?")[0];
    const fn = ev => {
      if (location.hash.split("?")[0] !== h0 || /^(INPUT|SELECT|TEXTAREA)$/.test((ev.target || {}).tagName || "")) return;
      if (ev.key === "[" && prevHref) location.hash = prevHref; else if (ev.key === "]" && nextHref) location.hash = nextHref;
    };
    document.addEventListener("keydown", fn);
    teardownFns.push(() => document.removeEventListener("keydown", fn));
  };
  const navBtns = (prev, next) => [prev ? E("a", { class: "pd-btn", href: prev.href, text: "◀ " + prev.label }) : null, next ? E("a", { class: "pd-btn", href: next.href, text: next.label + " ▶" }) : null].filter(Boolean);

  const CHK = ["check", "value", "thr", "ok"].map(key => ({ key, mono: key === "value" || key === "thr", align: key === "ok" ? "right" : undefined }));
  const PART_REL = { pool: "tray_s1_41899efb4b27", tgt: "tray_s1_4a8f4a8c6a8d" };
  const GROUPS7 = ["left_hand", "right_hand", "left_arm", "right_arm", "navigate", "waist", "base_height"];
  const GSHORT = { left_hand: "lhand", right_hand: "rhand", left_arm: "larm", right_arm: "rarm", navigate: "walk", waist: "waist", base_height: "height", hand: "hand", arm: "arm", leg: "leg", torso_rpy: "torso" };

  async function robotEpisode(main, r, ep, qs) {
    const ds = r.id, pad = String(ep).padStart(6, "0");
    const [eps, env] = await Promise.all([jget(dsf(ds, "episodes.json")), jget(dsf(ds, "env.json"))]);
    const idx = eps.findIndex(e => e.i === ep);
    if (idx < 0) { main.appendChild(line("unknown " + ep, "bad")); return; }
    const row = eps[idx], Ev = env[ep], prev = eps[idx - 1], next = eps[idx + 1];
    const T = row.n / 50, sm = Ev.sample, fl = Ev.flywheel;
    const pHref = prev && "#/" + epPath(ds, prev.i), nHref = next && "#/" + epPath(ds, next.i);
    navKeys(pHref, nHref);
    ctx(epPath(ds, ep), { dataset: ds, episode: ep }, {});
    { const base = r.laptop_dir || ""; panelSet({ method: [{ step: "parquet", cmd: base + "/data/chunk-000/episode_" + pad + ".parquet" }, { step: "video", cmd: base + "/videos/chunk-000/egocentric/episode_" + pad + ".mp4" }, { step: "signals", cmd: "/api/episode?ds=" + ds + "&ep=" + ep }],
      log: null, sources: [{ label: "parquet", path: base + "/data/chunk-000/episode_" + pad + ".parquet" }, { label: "mp4", path: base + "/videos/chunk-000/egocentric/episode_" + pad + ".mp4" }, { label: "meta", path: base + "/meta/episodes.jsonl" }] }); }
    main.appendChild(pageHead({
      title: `${ds} / ${ep}`,
      stat: UI.StatLine(statItems([{ value: dec(T, 1), unit: "s" }, { value: int(row.n), unit: "fr" }, { unit: "dr", value: String(sm.level) }, { unit: "seed", value: String(sm.seed) }, { value: row.part === "?" ? null : row.part }])),
      actions: navBtns(prev && { href: pHref, label: prev.i }, next && { href: nHref, label: next.i }),
    }));
    /* video + checks */
    const v = E("video", { src: `/media/${ds}/episode_${pad}.mp4`, preload: "auto", controls: true, muted: true, playsinline: true, poster: dsf(ds, "posters/" + ep + ".jpg") });
    v.muted = true;
    const stepsOk = (Ev.report.steps || []).filter(Boolean).length, stepsN = (Ev.report.steps || []).length;
    const okg = b => b ? "✓" : "✕";
    const xy = p => `${dec(p.x, 2)}, ${dec(p.y, 2)}, ${dec(p.yaw, 2)}`;
    const checks = [
      { check: "steps", value: `${stepsOk}/${stepsN}`, thr: String(stepsN), ok: okg(stepsOk === stepsN) },
      { check: "success", value: Ev.report.success ? "true" : String(Ev.report.failure), thr: "true", ok: okg(Ev.report.success) },
      { check: "qa", value: row.out ? "len " + tr(row.out) : "pass", thr: "—", ok: row.out ? "!" : "✓" },
      { check: "dist", value: dec(row.dist, 2), thr: "—", ok: "—" },
      { check: "tray", value: xy(sm.tray_pose), thr: "—", ok: "—" },
      { check: "target", value: xy(sm.target_pose), thr: "—", ok: "—" },
      { check: "gap", value: String(sm.table_gap), thr: "—", ok: "—" },
      { check: "mass", value: String(sm.part_mass), thr: "—", ok: "—" },
      { check: "light", value: String(sm.light_scale), thr: "—", ok: "—" },
      { check: "planner", value: fl.planner_version, thr: "—", ok: "—" },
      { check: "source", value: `${fl.source_kind} ${fl.synthetic_tier} ${fl.action_quality}`, thr: "—", ok: "—" },
    ];
    const links = E("div", { class: "pd-links" });
    const chip = (href, text) => links.appendChild(E("a", { class: "pd-chip", href, text }));
    if (ds === "S70" && row.cut != null) chip("#/" + epPath("ALL", row.cut), "ALL / " + row.cut);
    if (ds === "ALL") jtry(dsf("S70", "episodes.json")).then(s => { const m = s && s.find(e => e.cut === ep); if (m) chip("#/" + epPath("S70", m.i), "S70 / " + m.i); });
    if (PART_REL[row.part]) chip("#/data/" + PART_REL[row.part], mid(PART_REL[row.part], 20));
    const right = E("div", null, [UI.Table({ columns: CHK, rows: checks, keyboard: false }), links]);
    main.appendChild(E("div", { class: "pd-ep" }, [E("div", null, v), right]));

    /* timeline: strip + marker rows + plots, one playhead */
    const tl = E("div", { class: "pd-tl" });
    main.appendChild(tl);
    const lanes = [];                       // {host, ph}
    const addPh = host => { const ph = E("div", { class: "pd-ph" }); host.appendChild(ph); return ph; };
    const stripLane = E("div", { class: "pd-lane pd-strip" });
    const stripImg = E("img", { alt: "", src: `/api/strip?ds=${ds}&ep=${ep}` });
    stripLane.appendChild(stripImg);
    const markWalk = E("div", { class: "pd-lane pd-row" }, E("span", { class: "lb", text: "walk" }));
    const markQa = E("div", { class: "pd-lane pd-row" }, E("span", { class: "lb", text: "qa" }));
    tl.appendChild(stripLane); tl.appendChild(markWalk); tl.appendChild(markQa);
    [stripLane, markWalk, markQa].forEach(l => lanes.push({ host: l, ph: addPh(l), sync: true }));
    const insts = [];                       // echarts instances
    const secLabel = t => tl.appendChild(E("div", { class: "pd-line", text: t, style: { padding: "4px 0 0" } }));
    let A;
    try { A = await jget(`/api/episode?ds=${ds}&ep=${ep}`); if (A.error) throw new Error(A.error); } catch (e) { tl.appendChild(line(e.message, "bad")); }
    const plotHosts = [];
    if (A) {
      const mk = (title, g) => {
        const spec = { type: "line", title, x_label: "s", y_label: "", series: g.v.map((vals, i) => ({ name: g.names[i], points: A.t.map((t, k) => [t, Math.round(vals[k] * 1000) / 1000]) })) };
        const host = E("div", { class: "pd-lane", style: { height: "104px" } }, [E("span", { class: "lb p", text: title }), UI.Chart(spec, { height: 104 })]);
        tl.appendChild(host); plotHosts.push(host);
      };
      secLabel("action");
      GROUPS7.filter(g => A.action[g]).forEach(g => mk(GSHORT[g], A.action[g]));
      secLabel("state");
      Object.keys(A.state).forEach(g => mk(GSHORT[g] || g, A.state[g]));
      // walk segments from the navigate command, qa as one episode-level span
      const nav = A.action.navigate;
      if (nav) {
        const act = A.t.map((_, k) => nav.v.slice(0, 3).some(s => Math.abs(s[k]) > 0.05));
        const segs = []; let st = null;
        act.forEach((a, k) => { if (a && st == null) st = k; if ((!a || k === act.length - 1) && st != null) { segs.push([A.t[st], A.t[a ? k : k - 1] + 0.1]); st = null; } });
        markWalk._segs = segs;
      }
      markQa._segs = [[0, T, row.out ? "warn" : "ok"]];
    }
    /* sync engine */
    const findInst = host => { const c = host.querySelector(".u-chart"); const i = c && c.instance && c.instance(); if (i && !i._pdFit) { i._pdFit = 1; i.setOption({ grid: { left: 48, right: 12, top: 14, bottom: 18, containLabel: false }, xAxis: { min: 0, max: T, scale: false, name: "" } }); } return i; };
    const X = (inst, t) => inst.convertToPixel({ xAxisIndex: 0 }, t);
    let ref = null, lastW = -1, lastT = -1, raf = 0, alive = true;
    const plotLanes = () => plotHosts.map(h => ({ host: h, inst: findInst(h) })).filter(p => p.inst);
    const seek = t => { t = Math.max(0, Math.min(T, t)); v.currentTime = t; lastT = -1; };
    plotHosts.forEach(h => h.addEventListener("click", ev => { const p = plotLanes().find(x => x.host === h); if (!p) return; const dom = p.inst.getDom().getBoundingClientRect(); const t = p.inst.convertFromPixel({ xAxisIndex: 0 }, ev.clientX - dom.left); if (isFinite(t)) seek(t); }));
    const laneSeek = host => host.addEventListener("click", ev => { if (!ref) return; const b = host.getBoundingClientRect(), x0 = X(ref, 0), x1 = X(ref, T); seek((ev.clientX - b.left - x0) / (x1 - x0) * T); });
    [stripLane, markWalk, markQa].forEach(laneSeek);
    const layout = () => {
      const pl = plotLanes(); if (!pl.length) return;
      ref = pl[0].inst;
      const x0 = X(ref, 0), x1 = X(ref, T), w = x1 - x0;
      stripImg.style.left = x0 + "px"; stripImg.style.width = w + "px";
      [[markWalk, markWalk._segs], [markQa, markQa._segs]].forEach(([host, segs]) => {
        host.querySelectorAll(".seg").forEach(s => s.remove());
        (segs || []).forEach(([a, b, c]) => host.appendChild(E("div", { class: "seg " + (c || ""), style: { left: x0 + a / T * w + "px", width: Math.max(2, (b - a) / T * w) + "px" } })));
      });
    };
    const frame = () => {
      if (!alive || !document.body.contains(v)) return;
      raf = requestAnimationFrame(frame);
      const pl = plotLanes();
      if (!pl.length) return;
      const w = pl[0].host.clientWidth;
      if (!ref || w !== lastW) { lastW = w; layout(); lastT = -1; }
      const t = v.currentTime; if (t === lastT) return; lastT = t;
      pl.forEach(p => { let ph = p.host._ph; if (!ph) { ph = p.host._ph = E("div", { class: "pd-ph" }); p.inst.getDom().appendChild(ph); } ph.style.left = X(p.inst, t) + "px"; });
      if (ref) { const x = X(ref, t); lanes.forEach(l => { l.ph.style.left = x + "px"; }); }
    };
    raf = requestAnimationFrame(frame);
    teardownFns.push(() => { alive = false; cancelAnimationFrame(raf); });
    const writeT = () => setQs({ t: dec(v.currentTime, 1).replace(",", "") });
    v.addEventListener("pause", writeT); v.addEventListener("seeked", writeT);
    if (qs.t) { const t0 = parseFloat(qs.t); const go = () => { if (isFinite(t0)) v.currentTime = Math.min(t0, T); }; v.readyState ? go() : v.addEventListener("loadedmetadata", go, { once: true }); }
  }

  /* ---- egocentric episode ---- */
  async function egoEpisode(main, r, epId) {
    const id = r.id;
    const eps = await jget(dsf(id, "episodes.json"));
    const idx = eps.findIndex(e => e.id === epId);
    if (idx < 0) { main.appendChild(line("unknown " + epId, "bad")); return; }
    const row = eps[idx], prev = eps[idx - 1], next = eps[idx + 1];
    const qaDs = r.view === "src" ? id : (id === "h1m-team" ? "src_805804635f9af7f7" : "src_158ec3c813ffe9a6");
    const checksAll = await jtry(dsf(qaDs, "qa.json"));
    const checks = checksAll && checksAll[epId];
    const viewer = r.view === "ego" || row.ego;
    const pHref = prev && "#/" + epPath(id, prev.id), nHref = next && "#/" + epPath(id, next.id);
    navKeys(pHref, nHref);
    ctx(epPath(id, epId), { dataset: id, episode: epId }, {});
    panelSet({ method: [{ step: "viewer", cmd: "/ego/index.html#/ep/" + epId }], log: null, sources: [{ label: "qa", path: dsf(qaDs, "qa.json") }, { label: "dir", path: r.laptop_dir || "" }] });
    const actions = navBtns(prev && { href: pHref, label: "" }, next && { href: nHref, label: "" });
    if (viewer) actions.push(E("a", { class: "pd-btn", href: `/ego/index.html#/ep/${epId}`, target: "_blank", text: "viewer ↗" }));
    main.appendChild(pageHead({
      title: `${id} / ${mid(epId, 18)}`,
      stat: UI.StatLine(statItems([{ value: dec(row.s, 1), unit: "s" }, { label: "qa", value: row.qa }, row.hands != null ? { unit: "hands", value: dec(row.hands, 2) } : null, row.pose ? { unit: "pose", value: row.pose } : null, row.n ? { value: int(row.n), unit: "fr" } : null, (row.reasons || []).length ? { value: row.reasons.join(", ") } : null])),
      actions,
    }));
    const left = viewer ? E("iframe", { src: `/ego/index.html#/ep/${epId}`, title: "explorer" }) : line("none");
    const ctab = checks ? UI.Table({ columns: CHK, rows: checks.map(c => ({ check: c[0], value: sig3(c[1]), thr: sig3(c[2]), ok: c[3] ? "✓" : "✕" })), keyboard: false }) : line("none");
    main.appendChild(E("div", { class: "pd-ep" }, [left, ctab]));
  }

  /* ---------- register ---------- */
  const register = () => {
    UI.route("data", (m, p, qs) => pageCatalog(m, qs));
    UI.route("data/:id", (m, p, qs) => pageDataset(m, p, qs || q()));
    UI.route("data/:id/ep/:n", (m, p, qs) => pageEpisode(m, p, qs || q()));
  };
  register();
  return { loadCat };
})();

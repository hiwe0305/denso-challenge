/* v5 OPS pages, part 2: #/jobs (job table, pipeline strip, log) with ?panel=import|export.
   Talks to serve.py /api/* (runner.py). Shares the PAGES_OPS.kit helpers from pages_story.js. */
(function () {
"use strict";
const P = window.PAGES_OPS = window.PAGES_OPS || {};
const FWDIR = "/home/hiwe/project/denso-challenge/fwdata";
const NODES = ["ingest", "deid", "ea", "pose", "annotate", "qa", "report"];
const GATED = ["ea", "pose", "annotate", "qa", "report"];
const VIDEO_RE = /\.(mp4|mov|mkv|avi|webm)$/i;
const mb = n => n == null ? "—" : (typeof UI !== "undefined" && UI.fmt ? UI.fmt(n, "bytes") : (n / 1e6).toFixed(1) + " M");

const jobWork = j => (j.params && j.params.work) || (j.outputs && j.outputs.work) || null;
const isActive = j => j.state === "running" || j.state === "queued";
const setQs = patch => { try { UI.setQs(patch); } catch (e) { /* no router */ } };

async function jobsPage(main, params, qs0) {
  const K = P.kit, { h, api, tryApi, startJob, poll, col, num, dash, secs, jobSecs, dm, hhmm, stateTag, ctx, bindKeys, table, sec, panel, pageHead } = K;
  K.css(); P.chartsDispose && P.chartsDispose(); main.replaceChildren();
  const { setPanel, ec, axis, box } = K;
  const q = Object.assign({}, qs0 || (typeof UI !== "undefined" && UI.qs ? UI.qs() : {}));
  const S = { jobs: [], works: [], job: q.job || null, work: q.work || null, kind: "", state: "", text: "", ann: true, sig: "", wsig: "", follow: null };

  /* ---------------- data ---------------- */
  const jobBy = id => S.jobs.find(j => j.id === id);
  const curWork = () => S.works.find(w => w.name === S.work) || S.works[0] || null;
  const jobsOf = w => w ? S.jobs.filter(j => jobWork(j) === w.path) : [];
  const nodeJob = (w, id) => jobsOf(w).filter(j => j.kind === "ego." + id).sort((a, b) => (b.created > a.created ? 1 : -1))[0] || null;
  async function refresh(first) {
    const [jobs, works] = await Promise.all([api("/api/jobs?limit=200").catch(() => S.jobs), (first || S.jobs.some(isActive) || Date.now() - (S.wt || 0) > 6000) ? api("/api/works").catch(() => S.works) : Promise.resolve(S.works)]);
    if (works !== S.works) S.wt = Date.now();
    S.jobs = jobs; S.works = works;
    if (!S.work || !S.works.some(w => w.name === S.work)) {
      const j = S.job && jobBy(S.job), w = j && S.works.find(x => x.path === jobWork(j));
      S.work = (w || S.works[0] || {}).name || null;
    }
    if (!S.job) { const w = curWork(); const a = jobsOf(w).find(isActive) || jobsOf(w)[0] || S.jobs[0]; if (a) S.job = a.id; }
    const sig = S.jobs.map(j => j.id + j.state + (j.ended || "")).join("|"), wsig = JSON.stringify(S.works.map(w => w.tiers.map(t => t.state + t.n)));
    const changed = sig !== S.sig, wchanged = wsig !== S.wsig || changed;
    S.sig = sig; S.wsig = wsig;
    if (first) return;
    if (changed) drawTable();
    if (wchanged) drawStrip();
    drawHead(); drawLog();
  }

  /* ---------------- left: job timeline ---------------- */
  const gBox = box(110); let gCh = null;
  function drawGantt() {
    const js = S.jobs.filter(j => j.started), kinds = [...new Set(js.map(j => j.kind))].sort(), now = Date.now();
    if (!gCh) { gCh = ec(gBox, {}); gCh.on("click", p => p.value && selectJob(p.value[4])); }
    const c = { ok: col.ok(), running: col.run(), failed: col.bad(), cancelled: col.t3(), queued: col.warn() };
    gCh.setOption({ grid: { left: 84, right: 8, top: 4, bottom: 18 }, tooltip: { formatter: p => p.value[4] + " " + p.value[3] }, xAxis: axis({ type: "time" }), yAxis: axis({ type: "category", data: kinds, inverse: true, axisLabel: { color: col.t2(), fontSize: 10 }, splitLine: { show: false } }),
      series: [{ type: "custom", encode: { x: [1, 2], y: 0 }, data: js.map(j => [kinds.indexOf(j.kind), +new Date(j.started), j.ended ? +new Date(j.ended) : now, j.state, j.id]),
        renderItem: (p, a) => { const y = a.coord([0, a.value(0)])[1], x1 = a.coord([a.value(1), 0])[0], x2 = a.coord([a.value(2), 0])[0];
          return { type: "rect", shape: { x: x1, y: y - 5, width: Math.max(2, x2 - x1), height: 10 }, style: { fill: c[a.value(3)] || col.t3() } }; } }] }, true);
  }

  /* ---------------- left: job table ---------------- */
  let jtbl = null;
  const tbox = h("div", { style: { overflowX: "auto" } });
  const stSel = h("select", { class: "ops-in", onchange: e => { S.state = e.target.value; drawTable(); } }, ["", "running", "queued", "ok", "failed", "cancelled"].map(s => h("option", { value: s, text: s || "state" })));
  const kindSel = h("select", { class: "ops-in", onchange: e => { S.kind = e.target.value; drawTable(); } });
  function drawTable() {
    const kinds = [...new Set(S.jobs.map(j => j.kind))].sort();
    kindSel.replaceChildren(...[""].concat(kinds).map(k => h("option", { value: k, text: k || "kind", selected: k === S.kind })));
    const rows = S.jobs.filter(j => (!S.state || j.state === S.state) && (!S.kind || j.kind === S.kind) && true)
      .map(j => ({ id: j.id, kind: j.kind, state: j.state, host: j.host, dur: jobSecs(j), created: j.created, chain: j.chain_id }));
    drawGantt();
    if (jtbl && jtbl.table) { jtbl.table.setRows(rows); return; }
    jtbl = table({
      columns: [
        { key: "id", label: "id", mono: true, fmt: (v, r) => h("span", { class: "ops-mono", title: v, style: r.id === S.job ? { color: col.acc() } : null }, (r.chain ? "↳ " : "") + v.replace(/^j-\d{8}-/, "")) },
        { key: "kind", label: "kind", mono: true },
        { key: "state", label: "state", fmt: v => stateTag(v) },
        { key: "host", label: "host", mono: true },
        { key: "dur", label: "dur", align: "right", mono: true, fmt: v => secs(v) },
        { key: "created", label: "created", mono: true, fmt: v => v ? hhmm(v) + " " + dm(v) : "—" }
      ], rows, qsKey: "jobs", onRow: r => selectJob(r.id)
    });
    tbox.replaceChildren(jtbl);
  }

  /* ---------------- right top: pipeline strip ---------------- */
  const sbox = h("div"), wsel = h("select", { class: "ops-in", onchange: e => { S.work = e.target.value; S.job = null; setQs({ work: S.work, job: null }); refresh(); } });
  const annChk = h("input", { type: "checkbox", checked: true, onchange: e => { S.ann = e.target.checked; } });
  async function runKind(kind, extra) {
    const w = curWork(); if (!w) return;
    try { const j = await startJob(kind, Object.assign({ work: w.path }, extra || {})); S.job = j.id; setQs({ job: j.id, work: w.name }); await refresh(); drawTable(); drawStrip(); drawLog(true); }
    catch (e) { msg.textContent = e.message; }
  }
  function drawStrip() {
    const w = curWork();
    wsel.replaceChildren(...S.works.map(x => h("option", { value: x.name, selected: x.name === (w && w.name), text: x.name.replace(/^src_/, "").slice(0, 10) + " · " + x.episodes + " ep" })));
    sbox.replaceChildren();
    if (!w) { sbox.appendChild(h("span", { class: "ops-mono", style: { color: col.t2() }, text: "—" })); return; }
    const busy = jobsOf(w).some(isActive), deid = (w.tiers.find(t => t.id === "deid") || {}).state === "done";
    sbox.appendChild(h("div", { class: "ops-strip" }, NODES.map(id => {
      const t = w.tiers.find(x => x.id === id) || { state: "todo" }, nj = nodeJob(w, id), na = t.state === "na", gated = GATED.includes(id) && !deid;
      const st = t.state === "done" ? "done" : t.state === "partial" ? "partial" : na ? "na" : "todo";
      const selNode = nj && nj.id === S.job;
      return h("div", { class: "ops-node" + (selNode ? " sel" : ""), title: dash(t.note), onclick: () => nj && selectJob(nj.id) }, [
        h("span", { class: "ops-tag", style: { color: nj && isActive(nj) ? col.run() : col[{ done: "ok", partial: "warn" }[st] || "t3"]() } }, (nj && isActive(nj) ? "▶ " : (K.GLYPH[st] + " ")) + id),
        h("span", { class: "v ops-mono", text: na ? "—" : (t.n != null && t.total != null ? t.n + "/" + t.total : "—") }),
        na ? null : h("span", { class: "ops-bar", style: { margin: "2px 0" } }, h("i", { style: { width: (t.total ? Math.min(100, t.n / t.total * 100) : 0) + "%", background: st === "done" ? col.ok() : col.warn() } })),
        h("span", { class: "m ops-mono", text: t.took != null ? secs(t.took) : "—" }),
        na ? null : h("button", { class: "ops-btn" + (st !== "done" ? " pri" : ""), disabled: busy || gated, title: gated ? "deid first" : null, style: { marginTop: "4px" }, text: st === "done" ? "Re-run" : "Run", onclick: e => { e.stopPropagation(); runKind("ego." + id); } })]);
    })));
    if (deid) {
      const tbox = h("div", { style: { marginTop: "6px" } });
      sbox.appendChild(tbox);
      fetch("/api/work_episodes?work=" + encodeURIComponent(w.name)).then(r => r.ok ? r.json() : []).then(eps => {
        const QS = { pass: "ok", flag: "warn", reject: "bad" };
        const items = (eps || []).filter(e => e.deid).slice(0, 8).map(e => ({ src: "/api/poster?w=240&work=" + encodeURIComponent(w.name) + "&ep=" + encodeURIComponent(e.episode_id), label: e.episode_id.slice(3, 9) + " · " + (e.qa || "—"), state: QS[e.qa], strip: "/api/ego_strip?work=" + encodeURIComponent(w.name) + "&ep=" + encodeURIComponent(e.episode_id) }));
        if (items.length) tbox.appendChild(UI.Thumbs({ items }));
      }).catch(() => {});
    }
    setPanel({ method: NODES.map(id => { const nj = nodeJob(w, id); return { step: id, cmd: nj && nj.argv ? nj.argv.slice(-3).join(" ") : undefined }; }), log: S.job ? { jobId: S.job } : null, sources: [{ label: "work", path: w.path }, { label: "source", path: w.path + "/source.json" }] });
  }
  const runAll = () => runKind("ego.pipeline", { annotate: S.ann });

  /* ---------------- right bottom: header + log ---------------- */
  const msg = h("span", { class: "ops-mono", style: { color: col.bad() } });
  const headBox = h("div", { class: "ops-row", style: { minHeight: "26px" } }), outBox = h("span"), logBox = h("div", { style: { flex: 1, minHeight: "260px", display: "flex", flexDirection: "column" } });
  let logFor = null, logEl = null;
  function selectJob(id) { S.job = id; setQs({ job: id }); drawTable(); drawStrip(); drawHead(); drawLog(); const j = jobBy(id); ctx({ route: "jobs", selection: { job: id, kind: j && j.kind, state: j && j.state } }); }
  function effective() {
    const j = S.job && jobBy(S.job);
    if (j && j.kind === "ego.pipeline" && isActive(j) && j.outputs && j.outputs.current && jobBy(j.outputs.current)) return jobBy(j.outputs.current);
    return j;
  }
  function drawHead() {
    const j = effective();
    headBox.replaceChildren();
    if (!j) { headBox.appendChild(h("span", { class: "ops-mono", style: { color: col.t2() }, text: "—" })); return; }
    headBox.appendChild(h("b", { class: "ops-mono", text: j.kind })); headBox.appendChild(stateTag(j.state));
    headBox.appendChild(h("span", { class: "ops-mono", style: { color: col.t2() }, text: secs(jobSecs(j)) + " · " + j.host }));
    headBox.appendChild(h("span", { class: "ops-mono", style: { color: col.t2() }, text: j.id }));
    const rp = K.repro({ argv: j.argv || [], config: j.params ? JSON.stringify(j.params) : undefined }); if (rp) headBox.appendChild(rp);
    if (!rp) headBox.appendChild(h("button", { class: "ops-btn", text: "argv ⧉", onclick: () => navigator.clipboard && navigator.clipboard.writeText((j.argv || []).join(" ")) }));
    if (isActive(j)) headBox.appendChild(h("button", { class: "ops-btn", text: "Cancel", onclick: () => api("/api/jobs/" + j.id + "/cancel", {}).then(() => refresh()) }));
    const o = j.outputs || {};
    if (o.zip && o.name) headBox.appendChild(h("a", { class: "ops-btn", style: { textDecoration: "none", display: "inline-flex", alignItems: "center" }, href: "/api/exports/" + o.name, text: "Download " + mb(o.bytes) }));
    headBox.appendChild(msg);
  }
  function drawLog(force) {
    const j = effective(); const id = j ? j.id : null;
    if (id === logFor && !force) return;
    logFor = id;
    if (!logEl) { logEl = K.logView({ follow: true }); logEl.style.flex = "1"; logBox.replaceChildren(logEl); }
    if (logEl.setJob) logEl.setJob(id); else if (logEl.setText) logEl.setText("");
  }

  /* ---------------- panels ---------------- */
  const panelId = q.panel;
  const left = panel("Jobs", h("div", { class: "ops-wrap", style: { gap: "6px" } }, [gBox, h("div", { class: "ops-row" }, [stSel, kindSel]), tbox]));
  let right;
  if (panelId === "import") right = await importPanel(K);
  else if (panelId === "export") right = await exportPanel(K);
  else right = h("div", { class: "ops-wrap", style: { minWidth: 0 } }, [
    q.view === "jobs" ? null : panel("Pipeline", sbox, h("span", { class: "ops-row", style: { textTransform: "none", letterSpacing: 0 } }, [wsel, h("label", { class: "ops-row", style: { gap: "4px" } }, [annChk, "annotate"]), h("button", { class: "ops-btn pri", text: "Run pipeline", onclick: runAll })])),
    panel("Log", h("div", { class: "ops-wrap", style: { gap: "6px", flex: 1 } }, [headBox, logBox]), null, { flex: 1, display: "flex", flexDirection: "column" })
  ]);
  const acts = h("span", { class: "ops-row" }, [h("a", { class: "ops-btn", style: { textDecoration: "none", display: "inline-flex", alignItems: "center" }, href: "#/jobs?panel=import", text: "Import" }),
    h("a", { class: "ops-btn", style: { textDecoration: "none", display: "inline-flex", alignItems: "center" }, href: "#/jobs?panel=export", text: "Export" })]);
  main.appendChild(pageHead("Jobs", null, acts));
  const root = h("div", { class: "ops-grid", style: { gridTemplateColumns: K.GR.jobs, alignItems: "stretch", minHeight: K.GR.h } }, [left, right]);
  main.appendChild(root);

  await refresh(true);
  drawTable(); drawStrip(); drawHead(); drawLog();
  if (S.job) { const j = jobBy(S.job); ctx({ route: "jobs", selection: { job: S.job, kind: j && j.kind } }); }
  poll(() => refresh(), 1500, root);
  bindKeys({ Escape: () => { if (!panelId) return false; location.hash = "#/jobs"; } }, root);
}

/* ============================================================ import panel */
async function importPanel(K) {
  const { h, api, startJob, col, panel, tryApi } = K;
  const S = { root: "", source: "video", split: "train", ann: false };
  const models = await tryApi("/api/models");
  S.ann = !!(models && models.tunnel === "up");
  const files = h("div"), taskIn = h("input", { class: "ops-in", value: "two_table", style: { width: "110px" }, title: "task" });
  const zone = h("div", { class: "ops-drop", text: "Drop videos" });
  const picker = h("input", { type: "file", multiple: true, accept: ".mp4,.mov,.mkv,.avi,.webm,video/*", style: { display: "none" } });
  const rootBox = h("div", { class: "ops-mono", style: { fontSize: "12px", color: col.t2(), wordBreak: "break-all" } });
  const out = h("div", { class: "ops-mono", style: { color: col.bad() } });
  let batch = null;
  const stamp = () => { const d = new Date(), p = n => String(n).padStart(2, "0"); return "upload-" + d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + "-" + p(d.getHours()) + p(d.getMinutes()); };
  zone.onclick = () => picker.click();
  zone.ondragover = e => { e.preventDefault(); zone.classList.add("over"); };
  zone.ondragleave = () => zone.classList.remove("over");
  zone.ondrop = e => { e.preventDefault(); zone.classList.remove("over"); upload(Array.from(e.dataTransfer.files)); };
  picker.onchange = () => { upload(Array.from(picker.files)); picker.value = ""; };
  async function upload(fl) {
    fl = fl.filter(f => VIDEO_RE.test(f.name));
    if (!fl.length) { out.textContent = "no video"; return; }
    batch = batch || stamp();
    for (const f of fl) {
      const bar = h("i", { style: { width: "0%" } }), lab = h("span", { class: "ops-mono", text: "0%" });
      files.appendChild(h("div", { style: { margin: "4px 0" } }, [h("div", { class: "ops-row", style: { justifyContent: "space-between" } }, [h("span", { class: "ops-mono", text: f.name + " · " + mb(f.size) }), lab]), h("div", { class: "ops-bar" }, bar)]));
      try {
        const d = await new Promise((res, rej) => {
          const x = new XMLHttpRequest();
          x.open("POST", "/api/upload?dir=" + batch + "&task=" + encodeURIComponent(taskIn.value || "two_table"));
          x.setRequestHeader("X-Filename", encodeURIComponent(f.name));
          x.upload.onprogress = e => { if (e.lengthComputable) { const p = Math.round(e.loaded / e.total * 100); bar.style.width = p + "%"; lab.textContent = p + "%"; } };
          x.onload = () => { let j = {}; try { j = JSON.parse(x.responseText); } catch (e) { /* ignore */ } x.status < 300 ? res(j) : rej(new Error(j.error || "HTTP " + x.status)); };
          x.onerror = () => rej(new Error("connection lost")); x.send(f);
        });
        lab.textContent = "✓"; S.root = d.dir; showRoot();
      } catch (e) { lab.textContent = "✕ " + e.message; lab.style.color = col.bad(); }
    }
  }
  function showRoot() {
    rootBox.replaceChildren(S.root ? "root " + S.root : "root —");
    if (S.root) api("/api/dir_check?path=" + encodeURIComponent(S.root)).then(d => { if (!d.has_device) rootBox.appendChild(h("span", { style: { color: col.warn() } }, "  ! no device.json")); }).catch(() => {});
  }
  /* folder picker */
  const pickHold = h("div");
  function folderPicker() {
    const list = h("div", { style: { maxHeight: "220px", overflow: "auto" } }), pathIn = h("input", { class: "ops-in", style: { flex: 1, minWidth: "200px" }, placeholder: "path" });
    async function open(p) {
      list.replaceChildren();
      try {
        const d = await api("/api/fs?path=" + encodeURIComponent(p)); pathIn.value = d.path;
        list.appendChild(h("div", { class: "ops-row", style: { margin: "4px 0" } }, [h("button", { class: "ops-btn pri", text: "Use", onclick: () => { S.root = d.path; showRoot(); pickHold.replaceChildren(); } }),
          h("span", { class: "ops-mono", style: { color: d.has_device ? col.ok() : col.warn() }, text: d.has_device ? "✓ device.json" : "! device.json" }), h("span", { class: "ops-mono", style: { color: col.t2() }, text: d.videos.length + " video" })]));
        if (d.parent) list.appendChild(h("div", null, h("a", { href: "javascript:void 0", class: "ops-mono", onclick: () => open(d.parent), text: "↑ .." })));
        d.dirs.forEach(x => list.appendChild(h("div", null, h("a", { href: "javascript:void 0", class: "ops-mono", onclick: () => open(x.path), text: x.name + "/" }))));
        d.videos.slice(0, 30).forEach(v => list.appendChild(h("div", { class: "ops-mono", style: { color: col.t2() }, text: v.name + " · " + mb(v.size) })));
      } catch (e) { list.appendChild(h("div", { class: "ops-mono", style: { color: col.bad() }, text: e.message })); }
    }
    pickHold.replaceChildren(h("div", { class: "ops-wrap", style: { gap: "6px" } }, [h("div", { class: "ops-row" }, [pathIn, h("button", { class: "ops-btn", text: "Open", onclick: () => open(pathIn.value.trim()) })]), list]));
    open(FWDIR + "/egocentric-raw");
  }
  const srcSel = h("select", { class: "ops-in", onchange: e => { S.source = e.target.value; } }, [h("option", { value: "video", text: "video" }), h("option", { value: "egodex", text: "egodex" })]);
  const splitSel = h("select", { class: "ops-in", onchange: e => { S.split = e.target.value; } }, [h("option", { value: "train", text: "train" }), h("option", { value: "dev", text: "dev" })]);
  const annChk = h("input", { type: "checkbox", checked: S.ann, onchange: e => { S.ann = e.target.checked; } });
  const ingP = () => ({ source: S.source, root: S.source === "video" ? S.root : undefined, split: S.split });
  async function go(kind, params) {
    out.textContent = "";
    try { const j = await startJob(kind, params); location.hash = "#/jobs?job=" + j.id; } catch (e) { out.textContent = e.message; }
  }
  showRoot();
  return h("div", { class: "ops-wrap", style: { minWidth: 0 } }, [
    panel("Import", h("div", { class: "ops-wrap", style: { gap: "8px" } }, [
      h("div", { class: "ops-row" }, [h("span", { text: "task" }), taskIn]), zone, picker, files,
      h("div", { class: "ops-row" }, [h("button", { class: "ops-btn", text: "Folder…", onclick: folderPicker }), rootBox]), pickHold,
      h("div", { class: "ops-row" }, [srcSel, splitSel, h("label", { class: "ops-row", style: { gap: "4px" } }, [annChk, "annotate"]),
        h("button", { class: "ops-btn", text: "Ingest", onclick: () => go("ego.ingest", ingP()) }), h("button", { class: "ops-btn pri", text: "Run pipeline", onclick: () => go("ego.pipeline", Object.assign(ingP(), { annotate: S.ann })) })]), out]),
      h("a", { class: "ops-btn", style: { textDecoration: "none" }, href: "#/jobs", text: "×" }))
  ]);
}

/* ============================================================ export panel */
async function exportPanel(K) {
  const { h, api, startJob, col, panel, table, tryApi, hhmm, dm } = K;
  const [works, ests, cat] = await Promise.all([api("/api/works").catch(() => []), tryApi("/api/estimates"), fetch("data/catalog.json").then(r => r.json()).catch(() => null)]);
  const picked = new Set(), p2 = n => String(n).padStart(2, "0"), d = new Date();
  const nameIn = h("input", { class: "ops-in", value: "ego-h1m-" + d.getFullYear() + p2(d.getMonth() + 1) + p2(d.getDate()) + "-" + p2(d.getHours()) + p2(d.getMinutes()), style: { width: "220px" } });
  const sampleIn = h("input", { class: "ops-in", type: "number", value: 2, min: 0, max: 200, style: { width: "60px" }, title: "sample" });
  const estSel = h("select", { class: "ops-in", style: { maxWidth: "260px" } }, [h("option", { value: "", text: "estimates: auto" })].concat((ests || []).map(e => h("option", { value: e.path, text: e.label }))));
  const out1 = h("div", { class: "ops-mono", style: { color: col.bad() } }), out2 = h("div", { class: "ops-mono", style: { color: col.bad() } }), hist = h("div", { style: { overflowX: "auto" } });
  const wrows = works.map(w => h("label", { class: "ops-row", style: { padding: "2px 0", cursor: "pointer" } }, [
    h("input", { type: "checkbox", onchange: e => { e.target.checked ? picked.add(w.path) : picked.delete(w.path); } }), h("span", { class: "ops-mono", text: w.name }),
    h("span", { class: "ops-mono", style: { color: col.t2() }, text: w.source_detail + " · " + w.episodes + " ep" }), K.stateTag(w.summary && w.summary.has_report ? "done" : "todo", w.summary && w.summary.has_report ? "report" : "no report")]));
  const rows = cat && cat.rows ? cat.rows.filter(r => r.laptop_dir) : [];
  const dsSel = h("select", { class: "ops-in", style: { maxWidth: "280px" } }, rows.map(r => h("option", { value: FWDIR + "/" + r.laptop_dir.replace(/^fwdata\//, ""), text: r.id })));
  async function go(kind, params, box) {
    box.textContent = "";
    try { const j = await startJob(kind, params); location.hash = "#/jobs?job=" + j.id; } catch (e) { box.textContent = e.message; }
  }
  async function loadHist() {
    const l = await api("/api/exports").catch(() => []);
    hist.replaceChildren(table({
      columns: [{ key: "kind", label: "kind", mono: true, fmt: v => v === "zip" ? "zip" : "h1m" }, { key: "name", label: "name", mono: true }, { key: "size", label: "size", align: "right", mono: true, fmt: v => mb(v) },
        { key: "time", label: "time", mono: true, fmt: v => v ? hhmm(v) + " " + dm(v) : "—" },
        { key: "url", label: "get", fmt: (v, r) => r.kind === "zip" ? h("a", { href: v, class: "ops-mono", style: { color: col.acc() }, onclick: e => e.stopPropagation() }, "download") : (r.viewer ? h("a", { href: r.viewer + "index.html", target: "_blank", class: "ops-mono", style: { color: col.acc() }, onclick: e => e.stopPropagation() }, "viewer") : "—") }],
      rows: l.map(x => Object.assign({ id: x.name }, x)), qsKey: "exp"
    }));
  }
  loadHist();
  return h("div", { class: "ops-wrap", style: { minWidth: 0 } }, [
    panel("Export h1m", h("div", { class: "ops-wrap", style: { gap: "6px" } }, [h("div", null, wrows), h("div", { class: "ops-row" }, [nameIn, sampleIn, estSel,
      h("button", { class: "ops-btn pri", text: "Export", onclick: () => go("ego.human1m", { name: nameIn.value.trim(), works: [...picked], sample: +sampleIn.value || 0, estimates: estSel.value ? [estSel.value] : undefined }, out1) })]), out1]),
      h("a", { class: "ops-btn", style: { textDecoration: "none" }, href: "#/jobs", text: "×" })),
    panel("Metadata zip", h("div", { class: "ops-row" }, [dsSel, h("button", { class: "ops-btn", text: "Zip", onclick: () => go("export.zip", { path: dsSel.value }, out2) }), out2])),
    panel("Past exports", hist)
  ]);
}

if (typeof UI !== "undefined" && UI.route) UI.route("jobs", jobsPage);
P.jobsPage = jobsPage;
})();

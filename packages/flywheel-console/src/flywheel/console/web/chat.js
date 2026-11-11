/* Chat dock (namespace CHAT). Contract: CONTRACTS.md sections 3 and 4.
   Public API: mount(el) open(prefill?) close() toggle() focus() esc() prewarm() setModelState(models) setContext(obj) touchContext() ref({label,row}) */
"use strict";
const CHAT = (() => {
  const C = {};
  const LS = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) {} return null; };
  const S = { conv: null, history: [], busy: false, abort: null, model: null, ctx: {}, off: new Set(), refs: [], tools: null, warmed: false, sug: [], sugI: 0, toolsRoute: null };
  let root, list, input, ctxRow, pill, sug, sendBtn, traces;

  /* ---------- helpers ---------- */
  const ts = () => { const d = new Date(); return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0"); };
  const scrollEnd = () => { list.scrollTop = list.scrollHeight; };
  const route = () => (typeof chatRoute === "function" ? chatRoute() : "home");
  const scalar = row => { const o = {}; Object.keys(row || {}).slice(0, 10).forEach(k => { const v = row[k]; if (v == null || typeof v === "object") return; o[k] = typeof v === "string" && v.length > 80 ? v.slice(0, 80) : v; }); return o; };
  const jsn = (o, n) => { let t; try { t = JSON.stringify(o, null, 1); } catch (e) { t = String(o); } return t && t.length > (n || 4000) ? t.slice(0, n || 4000) + "…" : t; };

  /* ---------- context chips ---------- */
  function context() {
    live(); const c = { route: route() }, auto = C.auto();
    if (!S.off.has("sel")) { const sel = S.refs.length ? S.refs.map(r => r.row || r.label) : auto.sel ? [auto.sel] : []; if (sel.length) c.selection = sel.length === 1 ? sel[0] : sel; }
    const f = Object.assign({}, auto.filters, S.ctx.filters || {}); if (!S.off.has("filter") && Object.keys(f).length) c.filters = f;
    if (S.ctx.selection && !c.selection && !S.off.has("sel")) c.selection = S.ctx.selection;
    return c;
  }
  C.auto = function () {
    const qs = UI.qs(), filters = {}; Object.keys(qs).forEach(k => { if (k === "demo" || k === "tab" || k === "t") return; if (/^(sel|cmp|smooth|logy|work|job|panel)$/.test(k) || /_f\./.test(k) || k === "qa" || k === "status") filters[k.replace(/^[a-z]+_f\./, "")] = qs[k]; });
    const t = UI.activeTable && UI.activeTable(), row = t && t.cursor;
    return { filters, sel: row ? scalar(row) : null };
  };
  const hpath = () => (location.hash || "").split("?")[0];
  const live = () => { if (S.ctx && S.ctx._at && S.ctx._at !== hpath()) S.ctx = {}; return S.ctx; };
  C.setContext = function (o) { S.ctx = Object.assign({}, live(), o || {}, { _at: hpath() }); C.touchContext(); };
  C.touchContext = function () {
    if (!ctxRow) return; live(); ctxRow.innerHTML = "";
    const c = context(), chip = (key, text, cls) => ctxRow.appendChild(h("span", { class: "u-chip " + (cls || "") + (S.off.has(key) ? " off" : ""), title: "toggle", onclick: () => { S.off.has(key) ? S.off.delete(key) : S.off.add(key); C.touchContext(); } }, [text]));
    ctxRow.appendChild(h("span", { class: "u-chip", style: { cursor: "default" } }, "page: " + c.route));
    const auto = C.auto();
    if (S.refs.length) S.refs.forEach((r, i) => ctxRow.appendChild(h("span", { class: "u-chip ref", title: "remove", onclick: () => { S.refs.splice(i, 1); C.touchContext(); } }, ["ref: " + r.label, h("span", { class: "x", text: "×" })])));
    else if (auto.sel || S.ctx.selection) { const v = auto.sel ? String(auto.sel[Object.keys(auto.sel)[0]]) : (typeof S.ctx.selection === "string" ? S.ctx.selection : "row"); chip("sel", "sel: " + (v.length > 18 ? v.slice(0, 17) + "…" : v)); }
    const f = Object.assign({}, auto.filters, S.ctx.filters || {}), fk = Object.keys(f);
    if (fk.length) chip("filter", "filter: " + fk.slice(0, 3).map(k => k + "=" + String(f[k]).slice(0, 14)).join(" "));
  };
  C.ref = function (r) { if (!r) return; S.refs = S.refs.filter(x => x.label !== r.label).concat([r]).slice(-4); C.open(); C.touchContext(); input.focus(); };

  /* ---------- dock chrome ---------- */
  C.mount = function (el) {
    root = el; el.innerHTML = "";
    const w = parseInt(LS("v5dockw"), 10); if (w >= 320 && w <= 640) document.documentElement.style.setProperty("--dock", w + "px");
    if (LS("v5dock") === "off") document.body.classList.add("dock-off");
    const grip = h("div", { class: "grip" });
    grip.addEventListener("mousedown", e => { e.preventDefault(); const mv = ev => { const nw = Math.max(320, Math.min(640, window.innerWidth - ev.clientX)); document.documentElement.style.setProperty("--dock", nw + "px"); LS("v5dockw", String(Math.round(nw))); }; const up = () => { document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up); }; document.addEventListener("mousemove", mv); document.addEventListener("mouseup", up); });
    pill = h("span", { class: "ch-pill", title: "model", onclick: () => C.prewarm(true) });
    const head = h("div", { class: "ch-head" }, [pill, h("span", { class: "sp" }), h("button", { class: "ch-ib", title: "traces", text: "traces", onclick: showTraces }), h("button", { class: "ch-ib", title: "new", text: "new", onclick: reset }), h("button", { class: "ch-ib", title: "close ⌘.", text: "×", onclick: C.close })]);
    list = h("div", { class: "ch-list" }); ctxRow = h("div", { class: "ch-ctx" }); sug = h("div", { class: "ch-sug hide" });
    input = h("textarea", { rows: 1, placeholder: "ask or /command", "aria-label": "chat input" });
    sendBtn = h("button", { class: "u-btn pri", text: "Send", onclick: () => send() });
    input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(120, input.scrollHeight) + "px"; suggest(); });
    input.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { if (!sug.classList.contains("hide") && S.sug.length && input.value.indexOf(" ") < 0) { pickSug(S.sugI); e.preventDefault(); return; } e.preventDefault(); send(); }
      else if (e.key === "Tab" && S.sug.length && !sug.classList.contains("hide")) { e.preventDefault(); pickSug(S.sugI); }
      else if (e.key === "ArrowDown" && !sug.classList.contains("hide")) { e.preventDefault(); S.sugI = (S.sugI + 1) % S.sug.length; paintSug(); }
      else if (e.key === "ArrowUp") { if (!sug.classList.contains("hide")) { e.preventDefault(); S.sugI = (S.sugI + S.sug.length - 1) % S.sug.length; paintSug(); } else if (!input.value && S.last) { input.value = S.last; e.preventDefault(); } }
    });
    (root.parentNode || root).appendChild(grip); root.appendChild(head); root.appendChild(list);
    root.appendChild(h("div", { class: "ch-foot" }, [sug, ctxRow, h("div", { class: "ch-row" }, [input, sendBtn])]));
    emptyState(); C.touchContext(); C.setModelState(S.model); loadTools();
  };
  C.open = function (prefill) { document.body.classList.remove("dock-off"); if (UI.panel) UI.panel.tab("chat"); if (!UI.demo) LS("v5dock", "on"); if (prefill != null) { input.value = prefill; input.focus(); suggest(); } C.prewarm(); };
  C.close = function (temp) { document.body.classList.add("dock-off"); if (temp !== true) LS("v5dock", "off"); };
  C.toggle = function () { document.body.classList.contains("dock-off") ? C.open() : C.close(); if (!document.body.classList.contains("dock-off")) input.focus(); };
  C.focus = function () { if (document.body.classList.contains("dock-off")) C.open(); input.focus(); };
  C.esc = function () {
    if (S.busy && S.abort) { S.abort.abort(); return true; }
    if (!sug.classList.contains("hide")) { sug.classList.add("hide"); return true; }
    if (document.activeElement === input) { input.blur(); return true; } return false;
  };

  /* ---------- model status ---------- */
  C.setModelState = function (md) {
    S.model = md || S.model; if (!pill) return;
    const m = S.model, st = m ? (m.nemotron || (m.agent_ready ? "warm" : "down")) : "down"; S.state = st;
    pill.innerHTML = ""; pill.appendChild(h("span", { class: "c-" + UI.stateClass(st === "down" ? "down" : st === "cold" ? "cold" : st === "busy" ? "run" : "ok"), text: st === "down" ? "✕" : st === "cold" ? "○" : st === "busy" ? "▶" : "●" })); pill.appendChild(document.createTextNode(" nemotron " + st));
  };
  C.prewarm = function (force) {
    if ((S.warmed && !force) || S.state === "down" || S.state === "warm" && !force) return; S.warmed = true;
    fetch("/api/models/prewarm", { method: "POST" }).then(r => r.json()).then(() => fetch("/api/models").then(r => r.json()).then(C.setModelState)).catch(() => {});
  };

  /* ---------- tools + slash ---------- */
  async function loadTools() {
    if (S.tools) return S.tools; const all = {};
    await Promise.all(["home", "data", "runs", "eval", "jobs", "qa", "loop"].map(r => fetch("/api/tools?route=" + r).then(x => x.json()).then(a => (a || []).forEach(t => all[t.name] = t)).catch(() => {})));
    S.tools = Object.keys(all).map(k => all[k]); return S.tools;
  }
  const slashOf = t => (t.slash || "/" + t.name).replace(/^\/?/, "/");
  function suggest() {
    const v = input.value; if (v[0] !== "/" || v.indexOf(" ") >= 0 || !S.tools) { sug.classList.add("hide"); return; }
    S.sug = S.tools.filter(t => slashOf(t).startsWith(v.toLowerCase())).slice(0, 6); S.sugI = 0; paintSug();
  }
  function paintSug() { sug.innerHTML = ""; if (!S.sug.length) { sug.classList.add("hide"); return; } sug.classList.remove("hide"); S.sug.forEach((t, i) => sug.appendChild(h("div", { class: i === S.sugI ? "on" : "", onmousedown: e => { e.preventDefault(); pickSug(i); } }, [h("span", { text: slashOf(t) }), h("span", { class: "d", text: (t.description || "").slice(0, 48) })]))); }
  function pickSug(i) { const t = S.sug[i]; if (!t) return; input.value = slashOf(t) + " "; sug.classList.add("hide"); input.focus(); }
  function parseSlash(v) {
    const m = /^\/(\S+)\s*(.*)$/.exec(v.trim()); if (!m) return null; const key = "/" + m[1].toLowerCase();
    const t = (S.tools || []).find(x => slashOf(x) === key) || (S.tools || []).find(x => x.name === m[1]); if (!t) return { error: "unknown " + key };
    const props = (t.parameters && t.parameters.properties) || {}, req = (t.parameters && t.parameters.required) || [], order = req.concat(Object.keys(props).filter(k => req.indexOf(k) < 0)), args = {}; let pi = 0;
    (m[2].match(/(?:[^\s"]+|"[^"]*")+/g) || []).forEach(tok => { const kv = /^(\w+)=(.*)$/.exec(tok); let k, val; if (kv && props[kv[1]]) { k = kv[1]; val = kv[2]; } else { k = order[pi++]; val = tok; } if (!k) return; val = val.replace(/^"|"$/g, ""); const ty = props[k] && props[k].type; args[k] = ty === "integer" || ty === "number" ? Number(val) : ty === "boolean" ? val === "true" : val; });
    return { name: t.name, args };
  }

  /* ---------- message blocks ---------- */
  function emptyState() {
    list.innerHTML = ""; const ex = h("div", { class: "ch-empty" }); S.empty = ex; list.appendChild(ex);
    (S.tools ? S.tools.slice(0, 5) : []).forEach(t => ex.appendChild(h("a", { text: slashOf(t), title: t.description || "", onclick: () => { input.value = slashOf(t) + " "; input.focus(); } })));
    if (!S.tools) loadTools().then(() => { if (S.empty && S.empty.isConnected && !S.empty.children.length) emptyState(); });
  }
  function reset() { if (S.abort) S.abort.abort(); S.conv = null; S.history = []; S.busy = false; S.refs = []; emptyState(); C.touchContext(); }
  function userMsg(t) { if (S.empty) { S.empty.remove(); S.empty = null; } const m = h("div", { class: "ch-me" }, [h("span", { class: "who", text: "you" }), h("span", { class: "tx", text: t }), h("span", { class: "ts", text: ts() })]); list.appendChild(m); scrollEnd(); }
  function toolBlock(name, args, res, ms) {
    const cap = h("div", { class: "ch-cap" }, [UI.tag("CODE", "code"), h("span", { text: name + "(" + Object.keys(args || {}).map(k => k + "=" + String(args[k]).slice(0, 24)).join(", ") + ")" }), ms != null ? h("span", { class: "ms", text: UI.fmt(ms / 1000, "float1") + " s" }) : null]);
    const body = res && res.ui ? UI.render(res.ui, { keyboard: false, group: null }) : h("div", { class: "u-text", text: (res && res.model) || "" });
    return h("div", { class: "ch-code" }, [cap, body]);
  }
  function errBlock(msg, fallback) {
    const e = h("div", { class: "ch-err" }, ["✕ " + msg]);
    if (fallback === "slash" || /offline|fetch|HTTP/.test(msg)) { const hint = h("span", { class: "hint" }, "slash only: "); (S.tools || []).slice(0, 4).forEach(t => hint.appendChild(h("a", { text: slashOf(t) + " ", onclick: () => { input.value = slashOf(t) + " "; input.focus(); } }))); e.appendChild(hint); }
    return e;
  }
  function prose(text, nums) {
    const el = h("div", { class: "ch-llm" }); const bad = (nums || []).filter(n => n && n.grounded === false && n.text).map(n => String(n.text)).filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => b.length - a.length);
    const esc2 = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (!bad.length) { el.textContent = text; return el; }
    const re = new RegExp("(?<![\\d.,])(" + bad.map(esc2).join("|") + ")(?![\\d])", "g"); let last = 0, m;
    while ((m = re.exec(text))) { if (m.index > last) el.appendChild(document.createTextNode(text.slice(last, m.index))); el.appendChild(h("span", { class: "ungr", title: "not in tool output", text: m[0] })); last = m.index + m[0].length; }
    el.appendChild(document.createTextNode(text.slice(last))); return el;
  }
  function llmWrap(inner) { return h("div", { class: "ch-llm-wrap" }, [h("div", { class: "ch-cap", style: { marginLeft: "10px" } }, [UI.tag("LLM", "llm")]), inner]); }

  /* ---------- trace tree ---------- */
  async function openTrace(turn, holder) {
    if (holder.firstChild && !holder._err) { holder.innerHTML = ""; return; }
    holder._err = false; holder.innerHTML = "";
    holder.appendChild(h("div", { class: "ch-wait", text: "loading" }));
    try {
      const t = await (await fetch("/api/chat/traces/" + encodeURIComponent(turn))).json(); holder.innerHTML = "";
      if (t && t.error && !t.nodes) { holder._err = true; holder.appendChild(errBlock("trace: " + t.error)); return; }
      const nodes = Array.isArray(t) ? t : t.nodes || t.tree || t.events || null, tree = h("div", { class: "ch-tree" });
      if (!nodes) { tree.appendChild(h("pre", { text: jsn(t, 6000) })); }
      else walk(nodes, tree, 0);
      holder.appendChild(tree);
    } catch (e) { holder.innerHTML = ""; holder.appendChild(errBlock("trace: " + e.message)); }
  }
  function walk(nodes, into, d) {
    nodes.forEach(n => {
      const kind = n.type || n.kind || n.node || "node", name = n.name || n.tool || n.model || (n.tool_calls && n.tool_calls.length ? n.tool_calls.map(c => c.name).join(",") : String(n.content || "").slice(0, 36)), ms = n.ms != null ? n.ms : n.latency_ms;
      const tok = n.tokens_in != null || n.tokens_out != null ? (n.tokens_in || 0) + "→" + (n.tokens_out || 0) + " tok" : "";
      const det = h("pre", { class: "hide", text: jsn(Object.assign({}, n, { children: undefined, nodes: undefined })) });
      into.appendChild(h("div", { class: "ch-node" + (d ? " l1" : "") }, [h("div", { class: "hd", onclick: () => det.classList.toggle("hide") }, [h("span", { class: kind === "tool" ? "c-code" : "c-llm", text: kind === "tool" ? "▸ tool" : kind === "generation" ? "▸ gen" : "▸ " + kind }), h("span", { text: String(name).slice(0, 40) }), h("span", { class: "dim3", text: tok }), h("span", { class: "ms", text: ms != null ? UI.fmt(ms / 1000, "float1") + " s" : "" })]), det]));
      const kids = n.children || n.nodes; if (Array.isArray(kids)) walk(kids, into, d + 1);
    });
  }
  async function showTraces() {
    if (traces && traces.isConnected) { traces.remove(); return; }
    traces = h("div", { class: "ch-traces" }, [UI.sec("Traces")]); root.appendChild(traces);
    try {
      const l = await (await fetch("/api/chat/traces?limit=20")).json(); const rows = (Array.isArray(l) ? l : l.traces || []).map(t => ({ id: t.turn_id || t.id, time: t.time || t.ts || t.started, q: t.question || t.user || t.input || "", ms: t.ms_total != null ? t.ms_total / 1000 : null, tools: t.tools != null ? (Array.isArray(t.tools) ? t.tools.length : t.tools) : t.n_tools }));
      const holder = h("div");
      traces.appendChild(UI.Table({ columns: [{ key: "time", label: "time", fmt: (v) => v ? UI.fmt(v, "time") : null }, { key: "q", label: "q", mono: false }, { key: "tools", label: "tools", fmt: "int" }, { key: "ms", label: "dur", fmt: "dur" }], rows, search: false, keyboard: false, onRow: r => { holder.innerHTML = ""; openTrace(r.id, holder); } }));
      traces.appendChild(holder);
    } catch (e) { traces.appendChild(errBlock("traces: " + e.message)); }
  }

  /* ---------- send ---------- */
  async function send(text) {
    const v = (text != null ? text : input.value).trim(); if (!v || S.busy) return;
    input.value = ""; input.style.height = "auto"; sug.classList.add("hide"); S.last = v; userMsg(v);
    if (v[0] === "/") return slash(v);
    return ask(v);
  }
  C.send = send;
  async function slash(v) {
    await loadTools(); const p = parseSlash(v), turn = h("div", { class: "ch-turn" }); list.appendChild(turn);
    if (!p || p.error) { turn.appendChild(errBlock(p ? p.error : "bad command")); return scrollEnd(); }
    const wait = h("div", { class: "ch-wait", text: p.name }); turn.appendChild(wait); scrollEnd(); const t0 = performance.now();
    try {
      const r = await fetch("/api/tool?name=" + encodeURIComponent(p.name) + "&args=" + encodeURIComponent(JSON.stringify(p.args))); const d = await r.json(); wait.remove();
      if (!r.ok || d.ok === false) turn.appendChild(errBlock((d && (d.error || d.message)) || "HTTP " + r.status)); else turn.appendChild(toolBlock(p.name, p.args, d, performance.now() - t0));
    } catch (e) { wait.remove(); turn.appendChild(errBlock(e.message)); }
    scrollEnd();
  }
  async function ask(v) {
    S.busy = true; sendBtn.disabled = true; S.history.push({ role: "user", content: v });
    const turn = h("div", { class: "ch-turn" }), traceRow = h("div", { class: "ch-trace" }), tree = h("div"), calls = {}; let proseEl = null, text = "", t0 = performance.now(), turnId = null, nTools = 0, bodyWrap = null;
    traceRow.appendChild(h("span", { text: "▸ trace …" })); turn.appendChild(traceRow); turn.appendChild(tree);
    const wait = h("div", { class: "ch-wait", text: "thinking" }); turn.appendChild(wait); list.appendChild(turn); scrollEnd();
    S.abort = new AbortController();
    const body = { conversation_id: S.conv || undefined, messages: S.history.slice(-8), context: context() };
    const handle = (ev, d) => {
      if (ev === "trace_start") { S.conv = d.conversation_id || S.conv; turnId = d.turn_id; traceRow.innerHTML = ""; traceRow.appendChild(h("span", { text: "▸ trace " })); traceRow.appendChild(h("span", { class: "dim3", text: (d.tools_offered || []).length + " tools offered" })); traceRow.appendChild(h("span", { class: "open", text: "open", onclick: () => turnId && openTrace(turnId, tree) })); }
      else if (ev === "tool_start") { nTools++; wait.remove(); const sk = h("div", { class: "ch-code" }, [h("div", { class: "ch-cap" }, [UI.tag("CODE", "code"), h("span", { text: d.name + "(" + Object.keys(d.args || {}).map(k => k + "=" + String(d.args[k]).slice(0, 24)).join(", ") + ")" })]), h("div", { class: "skel", style: { height: "20px" } })]); sk._args = d.args; calls[d.call_id] = sk; turn.insertBefore(sk, bodyWrap); scrollEnd(); }
      else if (ev === "tool_result") { const old = calls[d.call_id]; const blk = d.ok === false ? h("div", { class: "ch-code" }, [errBlock(d.name + " failed")]) : toolBlock(d.name, (old && old._args) || {}, d, d.ms); if (old && old.parentNode) old.replaceWith(blk); else turn.insertBefore(blk, bodyWrap); scrollEnd(); }
      else if (ev === "token") { wait.remove(); if (!proseEl) { proseEl = h("div", { class: "ch-llm" }); bodyWrap = llmWrap(proseEl); turn.appendChild(bodyWrap); } text += d.text || ""; proseEl.textContent = text; scrollEnd(); }
      else if (ev === "done") {
        wait.remove(); const ms = d.ms_total != null ? d.ms_total : performance.now() - t0, tok = (d.tokens_in || 0) + (d.tokens_out || 0); turnId = d.turn_id || turnId;
        traceRow.innerHTML = ""; traceRow.appendChild(h("span", { text: "▸ trace  " + nTools + " tool" + (nTools === 1 ? "" : "s") + " · " + UI.fmt(ms / 1000, "float1") + " s · " + UI.fmt(tok, "int") + " tok" })); traceRow.appendChild(h("span", { class: "open", text: "open", onclick: () => openTrace(turnId, tree) }));
        if (text) { const pe = prose(text, d.numbers); if (bodyWrap) bodyWrap.replaceWith(llmWrap(pe)), bodyWrap = null; if (d.unverified && d.unverified.length) pe.parentNode && pe.parentNode.appendChild(h("div", { class: "ch-unv", text: "unverified: " + d.unverified.map(x => '"' + x + '"').join(", ") })); }
        S.history.push({ role: "assistant", content: text });
      }
      else if (ev === "error") { wait.remove(); turn.appendChild(errBlock(d.message || "error", d.fallback)); if (S.state !== "warm") fetch("/api/models").then(r => r.json()).then(C.setModelState).catch(() => {}); }
    };
    try {
      const r = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: S.abort.signal });
      if (!r.ok || !r.body) { let m = "HTTP " + r.status; try { const j = await r.json(); m = j.error || j.message || m; } catch (e) {} throw new Error(m); }
      const rd = r.body.getReader(), dec = new TextDecoder(); let buf = "";
      for (;;) {
        const { value, done } = await rd.read(); if (done) break; buf += dec.decode(value, { stream: true });
        let i; while ((i = buf.indexOf("\n\n")) >= 0) { const chunk = buf.slice(0, i); buf = buf.slice(i + 2); let ev = null, data = ""; chunk.split("\n").forEach(l => { if (l.startsWith("event:")) ev = l.slice(6).trim(); else if (l.startsWith("data:")) data += l.slice(5).trim(); });
          if (!data) continue; let d; try { d = JSON.parse(data); } catch (e) { continue; } handle(ev || d.type, d); }
      }
    } catch (e) { wait.remove(); if (e.name === "AbortError") { turn.appendChild(h("div", { class: "ch-wait", text: "cancelled" }).cloneNode(false)); turn.lastChild.textContent = "cancelled"; turn.lastChild.className = "ch-unv"; if (text) S.history.push({ role: "assistant", content: text }); else S.history.pop(); } else { turn.appendChild(errBlock(e.message === "Failed to fetch" ? "chat offline" : e.message, "slash")); S.history.pop(); } }
    S.busy = false; S.abort = null; sendBtn.disabled = false; scrollEnd();
  }
  return C;
})();
window.CHAT = CHAT;

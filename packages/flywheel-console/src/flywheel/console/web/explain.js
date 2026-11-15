/* Step template (flywheel v0.3 design 5.2) and the six steps of the data wheel (deck slide 8-9).
   route() in app.js calls EXPLAIN.page(n, body) and puts the result in place of the page body:
   step bar · BƯỚC n / 6 · question · answer · Input → Does → Output · up to 3 numbers · figure ·
   "where this can go wrong" · technical page folded in "Chi tiết kỹ thuật" · prev / next buttons.
   The home wheel (pages_wheel.js) reads the same registry, so one spec feeds both surfaces.
   Every number comes from CAT (catalog.json), STORY (story.json) or SIMD (sim.json); text from t().

   Extension API: EXPLAIN.register(n, spec), n = 1..6 for the steps, 0 for the cost ledger (centre).
   Specs merge, so a later file can add or replace single fields. Text is not in the spec: it lives in
   the dictionaries as st.<n>.name, .q (question), .a (one-sentence answer, may use {vars}),
   .in, .do, .out (the three boxes), .risk, and labels st.<n>.k1..k3 (all st.<n>.* ≤ 90 words).
   Spec fields (all functions, called at render time, errors are caught and logged):
     vars()  -> {name: value}   placeholders for st.<n>.a
     stats() -> [{v, k, src, tone}]   up to 3 proof numbers; v = shown value (string), k = label,
                                      src = source for the tooltip, tone = "good" | "bad" | undefined (neutral)
     node()  -> {v, src}        the ONE number on the wheel node (default: stats()[0])
     fig()   -> Element | null  the step's figure
     note()  -> string          one extra line under the numbers
     links() -> [[i18nKey, href], ...]
   Shared readers: EXPLAIN.read.{pair, run, best, round, follow, row, tot, frac, bench, placeShare, decision},
   EXPLAIN.runName(id) (plain model name for story pages), EXPLAIN.chain(title, steps). */
"use strict";
const EXPLAIN = (() => {
  const E = {}, REG = {};
  const HREF = { 0: "#/loop?tab=cost", 1: "#/data", 2: "#/jobs?view=pipeline", 3: "#/runs", 4: "#/eval", 5: "#/diagnose", 6: "#/loop" };
  E.STEPS = [1, 2, 3, 4, 5, 6];
  E.KEEP = 3;   /* the one step the team kept as-is (deck slide 8 draws it grey) */
  E.href = n => HREF[n];
  E.name = n => t("st." + n + ".name");
  /* route -> step 1..6, 0 for the cost ledger, null for pages outside the wheel (home, follow, jobs, machines, import) */
  E.stationOf = function (path, qs) {
    const p = String(path || "").split("/")[0];
    if (p === "data" && !/^data\/(nhap|xuat)$/.test(path)) return 1;
    if (p === "sim") return 1;
    if (p === "jobs" && qs.panel === "export") return 1;
    if (p === "qa" || p === "agent" || p === "process" || (p === "jobs" && qs.view === "pipeline")) return 2;
    if (p === "runs" || p === "training") return 3;
    if (p === "eval") return 4;
    if (p === "diagnose") return 5;
    if (p === "loop") return qs.tab === "cost" ? 0 : 6;
    return null;
  };
  E.register = (n, spec) => { REG[n] = Object.assign(REG[n] || {}, spec); };
  E.spec = n => REG[n] || {};
  E.on = () => UI.pref("v5explain") !== "off";
  E.toggle = function () {
    const off = document.body.classList.toggle("explain-off");
    UI.pref("v5explain", off ? "off" : "on");
    if (typeof drawMeta === "function") drawMeta();   /* keep the top-bar button in step with × */
  };
  const safe = (fn, d) => { try { return fn ? fn() : d; } catch (e) { console.warn("explain", e); return d; } };
  E.safe = safe;
  E.stats = n => safe(E.spec(n).stats, []).filter(s => s && s.v != null).slice(0, 3);
  E.node = n => { const s = E.spec(n); return s.node ? safe(s.node, null) : (E.stats(n)[0] || null); };
  /* one proof number tile: class xb-stat (+ good | bad) */
  E.stat = s => h("div", { class: "xb-stat" + (s.tone ? " " + s.tone : ""), title: s.src ? t("xb.src") + ": " + s.src : null }, [h("b", { text: s.v }), h("span", { text: s.k })]);
  /* Input → What the system does → Output */
  E.io = n => h("div", { class: "xb-io" }, [
    h("div", null, [h("b", { text: t("xb.in") }), t("st." + n + ".in")]), h("i", { text: "→" }),
    h("div", { class: "mid" }, [h("b", { text: t("xb.do") }), t("st." + n + ".do")]), h("i", { text: "→" }),
    h("div", null, [h("b", { text: t("xb.out") }), t("st." + n + ".out")])]);
  E.kicker = n => n ? t("xb.station", { n }) : t("xb.centre");
  /* six step chips and a separate cost chip; the current one is navy, earlier ones pale green */
  E.bar = function (n) {
    const chip = i => h("a", { class: "xb-chip" + (i === n ? " on" : n && i < n ? " done" : "") + (i === E.KEEP ? " keep" : ""), href: HREF[i] }, [h("span", { class: "sn", text: String(i) }), h("span", { text: E.name(i) })]);
    return h("nav", { class: "xb-stepbar" }, [...E.STEPS.map(chip), h("a", { class: "xb-chip cost" + (n === 0 ? " on" : ""), href: HREF[0] }, [h("span", { class: "sn", text: "$" }), h("span", { text: E.name(0) })])]);
  };
  const prevOf = n => n === 0 ? 6 : n - 1, nextOf = n => n === 0 ? null : n + 1;
  E.nav = function (n) {
    const p = prevOf(n), x = nextOf(n);
    const prev = p >= 1 ? h("a", { class: "xb-go prev", href: HREF[p] }, [h("small", { text: t("xb.prev") }), h("span", { text: "← " + p + " · " + E.name(p) })]) : h("a", { class: "xb-go prev", href: "#/home" }, [h("small", { text: t("xb.prev") }), h("span", { text: "← " + t("nav.start") })]);
    const next = x && x <= 6 ? h("a", { class: "xb-go next", href: HREF[x] }, [h("small", { text: t("xb.next") }), h("span", { text: x + " · " + E.name(x) + " →" })])
      : n === 6 ? h("a", { class: "xb-go next", href: HREF[0] }, [h("small", { text: t("xb.centre") }), h("span", { text: "$ " + E.name(0) + " →" })])
        : h("a", { class: "xb-go next", href: "#/home" }, [h("small", { text: t("xb.next") }), h("span", { text: t("nav.start") + " →" })]);
    return h("div", { class: "xb-nav" }, [prev, next]);
  };
  /* the band: everything above the technical page; short = sub-pages (one dataset, one sim episode) */
  E.band = function (n, short) {
    const R = E.spec(n);
    const head = h("div", { class: "xb-head" }, [h("span", { class: "xb-st", text: E.kicker(n) + " · " + E.name(n) }),
      h("h2", { text: t("st." + n + ".q") }), short ? null : h("button", { class: "xb-x", title: t("xb.hide"), text: "×", onclick: E.toggle })]);
    if (short) return h("section", { class: "xb short" }, [E.bar(n), head]);
    const stats = E.stats(n), fig = safe(R.fig, null), links = safe(R.links, null), note = safe(R.note, null);
    return h("section", { class: "xb" }, [E.bar(n), head,
      h("p", { class: "xb-a", text: t("st." + n + ".a", safe(R.vars, null)) }),
      E.io(n),
      stats.length ? h("div", { class: "xb-stats" }, stats.map(E.stat)) : null,
      note ? h("p", { class: "xb-note", text: note }) : null,
      fig ? h("div", { class: "xb-fig" }, fig) : null,
      h("p", { class: "xb-risk" }, [h("b", { text: t("xb.risk") + ": " }), t("st." + n + ".risk")]),
      links ? h("div", { class: "xb-links" }, links.map(([k, href]) => h("a", { href, text: t(k) }))) : null]);
  };
  /* the whole step page: band, technical page folded (closed in lock mode, open otherwise), prev / next */
  E.page = function (n, body, short) {
    if (short) return [E.band(n, true), body];
    const det = h("details", { class: "xb-tech" }, [h("summary", { text: t("xb.tech") }), body]);
    det.open = !UI.locked;
    det.addEventListener("toggle", () => { if (det.open) window.dispatchEvent(new Event("resize")); });
    return [E.band(n, false), det, E.nav(n)];
  };

  /* ---------- shared readers ---------- */
  const N = v => v == null ? null : UI.fmt(v, "int");
  const pair = () => (STORY && STORY.pair) || {};
  const run = id => (pair().runs || []).find(r => r.run === id);
  const best = () => run(pair().best) || null;
  const round = () => (STORY && STORY.round && STORY.round.chain) || {};
  const follow = () => (STORY && STORY.follow) || {};
  const row = id => CAT && CAT.rows.find(r => r.id === id);
  const tot = g => CAT && CAT.totals && CAT.totals[g] ? CAT.totals[g].episodes : null;
  const frac = r => r ? r.successes + "/" + r.n : null;
  /* QA bench (planted defects), when the index carries it: {caught, planted, false_alarms, clean, source} */
  const bench = () => { const b = STORY && (STORY.qa_bench || STORY.bench); return b && b.planted ? b : null; };
  /* share of failed runs labelled "placed off target" or "tray tilted", over the four base models */
  const BASE = ["C_ALL", "C_70", "B_ALL", "B_70"];
  const placeShare = () => {
    const xs = BASE.map(run).filter(r => r && r.failures && r.n > r.successes).map(r => ((r.failures["L-PLACE-POSE"] || 0) + (r.failures["L-TRAY-TILT"] || 0)) / (r.n - r.successes));
    return xs.length ? { lo: Math.min(...xs), hi: Math.max(...xs), n: xs.length } : null;
  };
  /* the pre-written rule's verdict on round 1 (pair.comparisons, tag r, against the round's base) */
  const decision = () => { const c = (pair().comparisons || []).find(x => x.tag === "r" && x.baseline === "C_70"); return c ? c.outcome : null; };
  E.read = { pair, run, best, round, follow, row, tot, frac, bench, placeShare, decision };
  /* plain model name for story pages (brief 5); the id goes in the tooltip */
  const CUT = { C_ALL: "ALL", B_ALL: "ALL", C_70: "S70", B_70: "S70", C70_R1: "S70" };
  E.runName = id => { const r = row(CUT[id]); return t("run." + id, { n: r ? r.episodes : null, k: round().selected }); };
  E.runLabel = id => h("span", { title: id, text: E.runName(id) });

  /* chain of counts drawn as shrinking bars: [[labelKey, value], ...] */
  E.chain = function (title, steps) {
    const mx = Math.max(...steps.map(s => s[1] || 0), 1);
    return h("div", { class: "xb-chain" }, [h("div", { class: "xb-cap", text: title }), ...steps.filter(s => s[1] != null).map(([k, v, cls]) =>
      h("div", { class: "xb-bar " + (cls || "") }, [h("i", { style: { width: Math.max(2, v / mx * 100) + "%" } }), h("b", { text: N(v) }), h("span", { text: t(k) })]))]);
  };

  /* ---------- step 1 · ingest & standardise (figure registered by pages_sim.js) ---------- */
  E.register(1, {
    stats: () => [{ v: N(tot("all")), k: t("st.1.k1"), src: "catalog.json · totals.all" },
      { v: N(tot("egocentric")), k: t("st.1.k2"), src: "catalog.json · totals.egocentric" },
      { v: N((tot("s1") || 0) + (tot("s2") || 0) || null), k: t("st.1.k3"), src: "catalog.json · totals.s1 + totals.s2" }],
  });

  /* ---------- step 2 · Agent QA/QC ---------- */
  E.register(2, {
    stats: () => { const m = (STORY && STORY.h1m) || {}, d = m.decisions || {}, b = bench();
      const clips = { v: d.exported != null ? N(d.exported) + "/" + N(m.clips) : null, k: t("st.2.k1"), src: "story.json · h1m.decisions" };
      return b ? [{ v: N(b.caught) + "/" + N(b.planted), k: t("st.2.k2"), src: b.source || "story.json · qa_bench", tone: "good" },
        b.clean != null ? { v: N(b.false_alarms) + "/" + N(b.clean), k: t("st.2.k3"), src: b.source || "story.json · qa_bench" } : null, clips]
        : [clips, { v: N(d.rejected_qa), k: t("st.2.k3"), src: "story.json · h1m.decisions" }]; },
    fig: () => { const m = (STORY && STORY.h1m) || {}, d = m.decisions || {}, c = round();
      return h("div", { class: "xb-two" }, [
        E.chain(t("fig.chain.ego"), [["fig.c.clips", m.clips], ["fig.c.exported", d.exported, "ok"], ["fig.c.rejected", d.rejected_qa, "bad"], ["fig.c.excluded", d.excluded, "bad"]]),
        E.chain(t("fig.chain.sim"), [["fig.c.generated", c.generated], ["fig.c.recorded", c.recorded], ["fig.c.qa", c.qa_pass], ["fig.c.quality", c.quality], ["fig.c.selected", c.selected, "ok"]])]); },
    links: () => [["fig.link.pipe", "#/jobs?view=pipeline"], ["fig.link.qa", "#/qa"]],
  });

  /* ---------- step 3 · train Ψ₀ (kept as-is) ---------- */
  const steps60 = () => { const r = ((STORY && STORY.runs) || []).find(x => x.branch === pair().best); return r ? r.max_steps : null; };
  E.register(3, {
    stats: () => { const c = row("C70_R1");
      return [{ v: N((pair().runs || []).length || null), k: t("st.3.k1"), src: "story.json · pair.runs" },
        { v: N(steps60()), k: t("st.3.k2"), src: "story.json · runs.max_steps" },
        { v: N(c && c.episodes), k: t("st.3.k3"), src: "catalog.json · C70_R1" }]; },
    fig: () => {
      const cell = id => { const r = run(id); return h("div", { class: "xb-cell", title: id }, [h("b", { text: E.runName(id) }), h("span", { text: r ? r.successes + "/" + r.n : "–" })]); };
      return h("div", { class: "xb-grid4" }, [
        h("span"), h("span", { class: "xb-gh", text: t("fig.grid.all") }), h("span", { class: "xb-gh", text: t("fig.grid.s70") }),
        h("span", { class: "xb-gh l", text: t("fig.grid.c") }), cell("C_ALL"), cell("C_70"),
        h("span", { class: "xb-gh l", text: t("fig.grid.b") }), cell("B_ALL"), cell("B_70"),
        h("span", { class: "xb-gh l", text: t("fig.grid.r1") }), h("span"), cell("C70_R1"),
        h("div", { class: "xb-qs" }, [h("span", { text: "? " + t("fig.q1") }), h("span", { text: "? " + t("fig.q2") }), h("span", { class: "dim", text: t("fig.ans") })])]);
    },
  });

  /* ---------- step 4 · test, score 7 steps ---------- */
  E.register(4, {
    note: () => t("st.4.note"),
    vars: () => { const b = best() || {}, tol = follow().tol || {};
      return { n: b.n, d: tol.distance_m != null ? Math.round(tol.distance_m * 100) : null, y: tol.yaw_error_deg }; },
    node: () => { const b = best(); return b ? { v: frac(b), src: pair().source || "story.json · pair" } : null; },
    stats: () => { const b = best(); if (!b) return [];
      const w = b.wilson || [], ps = placeShare();
      return [{ v: frac(b), k: t("st.4.k1", { run: E.runName(b.run) }), src: (pair().source || "story.json · pair") + " · " + b.run },
        { v: ps ? UI.fmt(ps.lo * 100, "int") + "–" + UI.fmt(ps.hi * 100, "int") + " %" : null, k: t("st.4.k2"), src: "story.json · pair.runs[].failures (L-PLACE-POSE + L-TRAY-TILT) / failed runs" },
        { v: w.length ? UI.fmt(w[0], "pct") + " – " + UI.fmt(w[1], "pct") : null, k: t("st.4.k3"), src: "story.json · pair.runs.wilson" }]; },
    fig: () => { const b = best(); if (!b) return null; const steps = pair().steps || [];
      return h("div", { class: "xb-chain" }, [h("div", { class: "xb-cap", text: t("fig.steps", { run: E.runName(b.run) }) }), ...steps.map((s, i) => { const v = (b.step_pass || {})[s];
        return h("div", { class: "xb-bar" + (i === steps.length - 1 ? " ok" : "") }, [h("i", { style: { width: Math.max(2, (v || 0) * 100) + "%" } }), h("b", { text: UI.fmt(v, "pct") }), h("span", { text: (i + 1) + " · " + t("fig.step." + s) })]); })]); },
  });

  /* ---------- step 5 · system check & diagnosis (page #/diagnose; full figure by its own workstream) ---------- */
  const clusters = () => (STORY && STORY.round && STORY.round.clusters) || [];
  const toData = c => !/^phiếu|ticket/i.test(String(c.intervention || ""));
  E.register(5, {
    node: () => { const c = clusters(); return c.length ? { v: c.filter(toData).length + "/" + c.length, src: "story.json · round.clusters" } : null; },
    stats: () => { const c = clusters(); if (!c.length) return [];
      const d = c.filter(toData).length;
      return [{ v: d + "/" + c.length, k: t("st.5.k1"), src: "story.json · round.clusters" }, { v: (c.length - d) + "/" + c.length, k: t("st.5.k2"), src: "story.json · round.clusters" }]; },
    fig: () => E.clusterCards(),
  });
  /* the eight clusters in two groups: to data / system ticket (classes .wh-cls, .wh-cl.data|.sys, .wh-clc) */
  E.clusterCards = function () {
    const C = clusters(); if (!C.length) return null;
    const grp = (k, xs, cls) => h("div", { class: "wh-cl " + cls }, [h("div", { class: "xb-cap", text: t(k, { n: xs.length, m: C.length }) }),
      ...xs.map(c => h("div", { class: "wh-clc" }, [h("b", { text: c.id }), h("span", { text: String(c.diagnosis || "") }), h("span", { class: "dim", text: String(c.intervention || "") })]))]);
    return h("div", { class: "wh-cls", title: t("xb.src") + ": story.json · round.clusters" }, [grp("dg.data", C.filter(toData), "data"), grp("dg.sys", C.filter(c => !toData(c)), "sys")]);
  };

  /* ---------- step 6 · failure → data ---------- */
  const r3 = () => follow().r3 || {};
  E.r3Table = function () {
    const R = r3(), order = [["C_70", "fig.r3.before"], ["C70_R1", "fig.r3.after"], ["C_ALL", "fig.r3.control"], ["B_70", "fig.r3.control"], ["B_ALL", "fig.r3.control"]].filter(([id]) => R[id]);
    if (!order.length) return null;
    const a = R[order[0][0]], cell = p => p ? p[0] + "/" + p[1] : "–";
    return h("table", { class: "xb-tbl" }, [h("thead", null, h("tr", null, [h("th", { text: "" }), h("th", { text: t("fig.r3.got", { n: a.got[1] }) }), h("th", { text: t("fig.r3.rest", { n: a.rest[1] }) }), h("th", { text: t("fig.r3.total") })])),
      h("tbody", null, order.map(([id, k]) => { const x = R[id]; return h("tr", { class: id === "C70_R1" ? "hot" : "" }, [h("td", { title: id }, [h("b", { text: E.runName(id) }), " ", h("span", { class: "dim", text: t(k) })]), h("td", { text: cell(x.got) }), h("td", { text: cell(x.rest) }), h("td", { text: (x.got[0] + x.rest[0]) + "/" + x.n })]); }))]);
  };
  E.verdict = function () {
    const a = run("C_70"), b = run("C70_R1"), R = r3(), ctl = ["C_ALL", "B_70", "B_ALL"].filter(id => R[id]).map(id => R[id].got[0]);
    if (!a || !b || !R.C70_R1 || !ctl.length) return null;
    return h("p", { class: "xb-verdict", text: t("fig.verdict", { a: a.successes, b: b.successes, n: a.n, m: R.C70_R1.got[1], g: R.C70_R1.got[0], lo: Math.min(...ctl), hi: Math.max(...ctl) }) });
  };
  /* "10/60 → 4/60 · dừng": before, after, and the rule's verdict, all from the index */
  E.roundLine = function () {
    const a = run("C_70"), b = run("C70_R1"), d = decision();
    if (!a || !b) return null;
    return frac(a) + " → " + frac(b) + (d ? " · " + (d === "F" ? t("wh.stop") : t("wh.go")) : "");
  };
  E.register(6, {
    node: () => { const v = E.roundLine(); return v ? { v, src: (pair().source || "story.json · pair") + " · comparisons (r)" } : null; },
    stats: () => { const c = round(), b = run("C70_R1"), a = run("C_70"), d = decision();
      return [{ v: frac(b), k: t("st.6.k1", { b: frac(a) }), src: (pair().source || "story.json · pair") + " · C70_R1, C_70" },
        { v: d ? (d === "F" ? t("wh.stop") : t("wh.go")) : null, k: t("st.6.k2"), src: "story.json · pair.comparisons (tag r)" },
        { v: c.targets != null ? N(c.targets) + " → " + N(c.selected) : null, k: t("st.6.k3"), src: "story.json · round.chain (tray.md 20.13–20.16)" }]; },
    fig: () => h("div", null, [h("div", { class: "xb-loop" }, [1, 2, 3, 4, 5, 6].map(i => h("span", { class: i === 6 ? "stop" : "", text: t("fig.loop." + i) }))), E.r3Table(), E.verdict()]),
  });

  /* ---------- centre · cost ledger ---------- */
  const ledger = () => (STORY && STORY.ledger) || [];
  E.register(0, {
    node: () => ({ v: t("wh.ledger", { n: ledger().length }), src: "story.json · ledger" }),
    stats: () => { const L = ledger(); if (!L.length) return [];
      return [{ v: N(L.length), k: t("st.0.k1"), src: "story.json · ledger" },
        { v: N(L.filter(r => r[1] && r[2]).length), k: t("st.0.k2"), src: "story.json · ledger (estimated and measured both > 0)" }]; },
  });
  return E;
})();
